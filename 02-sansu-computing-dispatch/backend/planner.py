"""24-hour receding-horizon batch transport after local interactive reservations."""
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import csr_matrix

from .world import BASE_PUE, BW, CAP, DOM, EF, GB_PER_EF, GRID, weather

H, N, REGIONS = 24, 16, 4
REGION = np.r_[np.zeros(13, dtype=int), 1, 2, 3]
DEFAULT = dict(cost=.32, carbon=.38, network=.12, utilization=.18, sla=.7)
DOM_FLOOR = .30


@dataclass
class Plan:
    quota: np.ndarray       # allocated flexible effective EF-hours, by execution hour/node
    reserve: np.ndarray     # local physical headroom for inference
    renewable: np.ndarray   # forecast available green power / node peak IT power
    tariff: np.ndarray
    timing: np.ndarray      # first cohort, mass by deadline class and delay
    resource: np.ndarray
    carbon: np.ndarray
    elapsed: float
    unserved: float
    domestic_share: float
    max_cross_flow: float
    status: str


def solve(prediction,hour,scenario,health,pue_extra,weights=None,committed=None):
    """Allocate weekly-workload forecast cohorts over legal near-term service hours.

    Columns are spatial routes with start offsets 0..6h. One integer leases WAN
    circuits. Destination weights are computed before each solve from its forecast.
    """
    start = perf_counter()
    w = DEFAULT | (weights or {})
    hours = np.arange(hour,hour+H)
    day = ((hours%24>=8)&(hours%24<21))[:,None]
    arrivals = prediction[:,:,0].clip(0)
    ren = prediction[:,:,1].clip(0,1)
    tariff,_,temp = weather(hours,scenario)
    pue = BASE_PUE+pue_extra+.003*(temp-24)
    # Forecast local inference headroom as mean simultaneous work with a burst margin.
    inference = arrivals*np.where(day,.52,.15)*.43
    reserve = np.minimum(.65*EF*health,1.25*inference)
    fixed = np.minimum(.85*EF*health,reserve+arrivals*.15)
    if committed is not None:
        fixed = np.maximum(fixed,committed)
    capacity = np.maximum(0,.93*(EF*health-fixed))
    flex = arrivals*np.where(day,.08*2.3+.15*1.2,.33*2.3+.28*1.2)*.90
    green = np.maximum(0,ren*EF/pue-fixed)
    intensity = GRID*pue*(1-np.clip(green/(1e-6+capacity),0,1))
    unit = w["cost"]*tariff*pue+w["carbon"]*intensity
    modes = 8  # local now, distributed now, distributed with 1..6h shift
    cols = H*modes+1
    flows = np.zeros((H,N,cols))
    domestic = np.zeros_like(flows)
    wan = np.zeros((H,cols))
    fraction = np.zeros((H,cols))
    timing = np.zeros((5,7,cols))
    t = np.arange(H)
    c = np.zeros(cols)
    cross = REGION[:,None]!=REGION
    net_cost = w["network"]*.35*cross
    # A coastal site with available generation can absorb daytime work until
    # its predicted local demand and green supply are exhausted.
    clean_capacity = .20*capacity+np.minimum(green,capacity)
    shares = np.exp(-7*(unit[:,None,:]+net_cost))*clean_capacity[:,None,:]
    shares /= np.maximum(shares.sum(axis=2,keepdims=True),1e-8)
    for m in range(modes):
        col = t*modes+m
        fraction[t,col] = 1
        domestic_fraction = (.45,.54,.62,.48,.58,.38,.64,.48)[m]
        for tier in range(5):
            delay = min(max(0,m-1),2+tier)
            dest_t = np.minimum(t+delay,H-1)
            offered = flex/5
            if m==0:
                dest = offered*health
                transfer = np.zeros(H)
            else:
                transport = offered[:,:,None]*shares[dest_t]
                dest = transport.sum(axis=1)
                transfer = (transport*cross).sum(axis=(1,2))
            flows[dest_t,:,col] += dest
            domestic[dest_t,:,col] += domestic_fraction*dest
            wan[dest_t,col] += transfer
            c[col] += ((unit[dest_t]*dest).sum(axis=1)+w["network"]*.35*transfer+
                       w["sla"]*.009*(dest_t-t)*dest.sum(1))
            timing[tier,delay,col[0]] = dest[0].sum()
    c[:-1] -= 80*flows[:,:,:-1].sum(axis=(0,1))
    c[:-1] -= w["utilization"]*.12*np.minimum(flows[:,:,:-1],capacity[:,:,None]*.65).sum(axis=(0,1))
    c[-1] = .05
    wan[:,-1] = -BW/GB_PER_EF/4
    per_node = H*N
    ub = csr_matrix(np.vstack((fraction,domestic.reshape(per_node,cols),
                               (flows-domestic).reshape(per_node,cols),
                               (intensity[:,:,None]*flows).reshape(per_node,cols),
                               wan,(DOM_FLOOR*flows-domestic).sum(axis=1))))
    cap_dom = capacity*CAP[:,DOM].sum(1)/EF
    rhs = np.r_[np.ones(H),cap_dom.ravel(),(capacity-cap_dom).ravel(),
                np.tile(.48*EF*health,H),np.zeros(2*H)]
    lower = np.zeros(cols)
    upper = np.r_[np.ones(cols-1),4.]
    lp = linprog(c,A_ub=ub,b_ub=rhs,bounds=np.column_stack((lower,upper)),method="highs")
    if not lp.success:
        raise RuntimeError(lp.message)
    lower[-1],upper[-1] = np.floor(lp.x[-1]),np.ceil(lp.x[-1])
    integers = np.zeros(cols,dtype=int)
    integers[-1] = 1
    res = milp(c,integrality=integers,bounds=Bounds(lower,upper),
               constraints=LinearConstraint(ub,-np.inf,rhs),
               options={"time_limit":.35,"mip_rel_gap":.0001})
    if res.x is None:
        x = lp.x.copy()
        x[-1] = upper[-1]
        status = "feasible-rounded"
    else:
        x,status = res.x,"optimal" if res.success else "feasible-incumbent"
    quota = flows@x
    dual = -lp.ineqlin.marginals[H:H+3*per_node].reshape(3,H,N)
    return Plan(quota,reserve,ren,tariff,timing@x,dual[:2,0].max(0),dual[2,0],
                perf_counter()-start,float(max(0,flex.sum()-quota.sum())),
                float((domestic@x).sum()/max(1e-8,quota.sum())),
                float((wan[:,:-1]@x[:-1]).max()),status)
