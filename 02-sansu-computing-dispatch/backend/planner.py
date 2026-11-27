"""Restricted-route rolling MILP, effective EF-hours. LP relaxation duals for audit."""
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp, linprog
from scipy.sparse import csr_matrix

from .world import BASE_PUE, BW, CAP, CROSS, DOM, EF, GB_PER_EF, GRID, LAT, weather

H = 24
N = 16
DEFAULT = dict(cost=.32, carbon=.38, network=.12, utilization=.18, sla=.7)
DOM_FLOOR = .30


@dataclass
class Plan:
    quota: np.ndarray       # [execution hour,node] effective EF-hour
    delay: np.ndarray       # [origin] preferred batch deferral for first cohort
    resource: np.ndarray    # first-hour LP marginals (objective/EF-hour)
    carbon: np.ndarray      # carbon budget LP marginals (objective/kg in scaled model)
    elapsed: float
    unserved: float
    domestic_share: float
    max_cross_flow: float
    status: str


def solve(prediction, hour, scenario, health, pue_extra, weights=None):
    """Optimize hourly mix of feasible route templates and integer WAN circuits.

    A column is a complete routing pattern for one release cohort. Inference
    stays within its own ring. A batch can shift one hour inside its time window.
    """
    start = perf_counter()
    w = DEFAULT | (weights or {})
    price, _, _ = weather(np.arange(hour,hour+H), scenario)
    pue = BASE_PUE+pue_extra
    carbon = GRID*(1-np.clip(prediction[:,:,1],0,1))*pue
    unit = w['cost']*price*pue + w['carbon']*carbon
    count = prediction[:,:,0]
    # Hourly shares, continuously mixed by MILP; the final variable leases
    # an integer number of 1/4-link circuits for the entire forecast horizon.
    modes = 5
    columns = H*modes+1
    flow = np.zeros((H,N,columns))
    dom_flow = np.zeros_like(flow)
    wan = np.zeros((H,columns))
    balanced = np.zeros((H,columns))
    delayed = np.zeros((N,columns))
    c = np.zeros(columns)
    src = np.arange(N)
    times = np.arange(H)
    src_grid = np.broadcast_to(src,(H,N))
    for m in range(modes):
        col = times*modes+m
        balanced[times,col] = 1
        domestic = [.45,.24,.69,.52,.78][m]
        for ratio, ring, batch in [(.09,1,False),(.27,5,False),(.14,10,False),(.50,10,True)]:
            t = np.minimum(H-1,times+int(batch and m>=3))
            legal = (LAT<=ring) & (health[None,:]>0)
            if m==0:
                dst = src_grid
            else:
                rank = (unit[t,None,:] + w['network']*.35*CROSS +
                        (.18 if m in (2,4) else .04)*(LAT-1)/9 -
                        w['utilization']*.25*EF/EF.max())
                # Rotate the second-choice route for load diversity.
                rank = np.where(legal,rank,np.inf)
                dst = rank.argmin(axis=2)
                if m in (2,4):
                    rank[np.arange(H)[:,None],src_grid,dst] = np.inf
                    alt = rank.argmin(axis=2)
                    dst = np.where(legal.sum(1)>1,alt,dst)
                dst = np.where(legal.any(1),dst,src_grid)
            work = ratio*count*(health[dst]>0)
            indices = (t[:,None],dst,col[:,None])
            np.add.at(flow,indices,work)
            np.add.at(dom_flow,indices,domestic*work)
            np.add.at(wan,(t,col),(work*CROSS[src_grid,dst]).sum(1))
            c[col] += (work*(unit[t[:,None],dst]+w['network']*.35*CROSS[src_grid,dst]
                             +w['sla']*.08*(t-times)[:,None])).sum(1)
            if batch and t[0]>0:
                delayed[:,col[0]] = work[0]
    # Admission is optional, with a strictly dominant missed-demand penalty.
    c[:-1] -= 80*flow[:,:,:-1].sum(axis=(0,1))
    c[-1] = .05
    c[:-1] -= w['utilization']*np.sum(np.minimum(flow[:,:,:-1],EF[None,:,None]*.6),axis=(0,1))
    cap_d = CAP[:,DOM].sum(1)*health
    cap_o = CAP[:,~DOM].sum(1)*health
    wan[:,-1] = -BW/GB_PER_EF/4
    u = np.vstack((balanced,dom_flow.reshape(-1,columns),(flow-dom_flow).reshape(-1,columns),
                   (carbon[:,:,None]*flow).reshape(-1,columns),wan,
                   (DOM_FLOOR*flow-dom_flow).sum(axis=1)))
    rhs = np.r_[np.ones(H),np.tile(cap_d,H),np.tile(cap_o,H),np.tile(.48*EF*health,H),
                np.zeros(2*H)]
    u = csr_matrix(u)
    upper = np.r_[np.ones(columns-1),4.]
    lower = np.zeros(columns)
    lp = linprog(c,A_ub=u,b_ub=rhs,bounds=list(zip(lower,upper)),method="highs")
    if not lp.success:
        raise RuntimeError(lp.message)
    # With one integer, convexity bounds the optimum between adjacent integers.
    lower[-1],upper[-1] = np.floor(lp.x[-1]),np.ceil(lp.x[-1])
    integer = np.zeros(columns,dtype=int)
    integer[-1] = 1
    res = milp(c,integrality=integer,bounds=Bounds(lower,upper),
               constraints=LinearConstraint(u,-np.inf,rhs),
               options={"time_limit":.40,"mip_rel_gap":0.0001})
    if res.x is None:
        x = lp.x.copy()
        x[-1] = upper[-1]
        status = "feasible-rounded"
    else:
        x,status = res.x,"optimal" if res.success else "feasible-incumbent"
    quota = flow@x
    dual = -lp.ineqlin.marginals[H:H+3*H*N].reshape(3,H,N)
    return Plan(quota,(delayed@x)/np.maximum(.5*count[0],1e-8),
                dual[:2,0].max(axis=0),dual[2,0],perf_counter()-start,
                float(np.maximum(0,count.sum()-quota.sum())),
                float((dom_flow@x).sum()/max(1e-8,quota.sum())),
                float((wan[:,:-1]@x[:-1]).max()),status)
