"""Five-minute reservation calendar shared by every baseline, training and inference."""
from dataclasses import dataclass, replace
from time import perf_counter

import gymnasium as gym
import numpy as np
import torch
from gymnasium import spaces

from .models import FEATURES, forecast, load_model
from .planner import DEFAULT, DOM_FLOOR, solve
from .world import (BASE_PUE, BW, CAP, CITIES, CROSS, DOM, EF, ETA, GB_PER_EF,
                    GRID, KINDS, KW_PER_EF, LAT, SLOTS, STRATEGIES, Trace)

N, M = CAP.shape
A = N*M


@dataclass
class Segment:
    task: int
    node: int
    pool: int
    begin: int
    end: int
    rate: float
    physical: float
    cross_gb: float
    latency: int
    resource_dual: float
    carbon_dual: float
    probability: float | None


class Calendar:
    def __init__(self, trace, strategy, weights=None):
        if strategy not in STRATEGIES:
            raise ValueError("unknown strategy")
        self.trace, self.strategy = trace, strategy
        self.weights = DEFAULT | (weights or {})
        self.slots = trace.hours*SLOTS
        self.used = np.zeros((self.slots,N,M))
        self.effective = np.zeros((self.slots,N))
        self.link = np.zeros(self.slots)
        self.health = np.ones((self.slots,N))
        self.pue_extra = np.zeros_like(self.health)
        self.segments = []
        self.costs = {}
        self.decisions = {}
        self.book = {}
        self.plan = None
        self.hour = -1
        self.solves = []
        self.committed_efslots = 0.
        self.domestic_efslots = 0.
        self.faults = []
        self.rr = 0
        self.actor = load_model("policy") if strategy in ("SuCompute","Safe-RL-only") else None

    def advance(self, slot, force=False):
        h = slot//SLOTS
        if self.strategy in ("SuCompute","MILP-only") and (force or h != self.hour):
            pred = forecast(load_model("forecast"),self.trace.history_at(h))
            self.plan = solve(pred,h,self.trace.scenario,self.health[slot],self.pue_extra[slot],self.weights)
            self.solves.append(self.plan.elapsed)
        self.hour = h

    def candidates(self, j):
        h = j.slot//SLOTS
        start = j.slot
        if self.plan and j.kind < 2 and self.plan.delay[j.src] > .5:
            start = min(j.deadline-j.duration, (h+1)*SLOTS)
        end = start+j.duration
        free = (self.health[start:end,:,None]*CAP-self.used[start:end]).min(axis=0)
        raw = j.rate/ETA[j.kind]
        valid = (free+1e-9 >= raw) & (ETA[j.kind] >= .30)
        cross = CROSS[j.src]
        valid &= (~cross | (self.link[start:end].max()+j.rate*GB_PER_EF <= BW+1e-8))[:,None]
        if self.plan and self.domestic_efslots < DOM_FLOOR*(self.committed_efslots+j.rate*j.duration):
            valid &= DOM
        util = self.used[start]/CAP
        city_fill = self.used[start].sum(axis=1)/EF
        green = self.trace.series[48+h,:,1]
        price = self.trace.tariffs[0][h]
        base = BASE_PUE+self.pue_extra[start]
        latency = LAT[j.src]/j.latency
        q = self.plan.quota[min(23,start//SLOTS-h)] if self.plan else np.zeros(N)
        q = np.clip((q-self.effective[start])/EF,-1,1) if self.plan else q
        # Estimate the marginal facility energy, including discrete bank wake-ups.
        # The final meter integrates every slot and concurrent reservation.
        bank = np.maximum(self.health[start,:,None]*CAP/8,1e-8)
        occupied = self.used[start].clip(0)
        before = np.ceil(np.round(occupied/bank,9))*bank
        after = np.ceil(np.round((occupied+raw)/bank,9))*bank
        def bank_power(load, online):
            return .32*online+.68*load*(load/np.maximum(online,1e-8))**.55
        energy = base[:,None]*(bank_power(occupied+raw,after)-bank_power(occupied,before))/j.rate
        headroom = green[:,None]*EF[:,None] - city_fill[:,None]*EF[:,None]*base[:,None]
        renewable = np.clip(headroom/np.maximum(energy*j.rate,.01),0,1)
        arr = np.empty((N,M,len(FEATURES)),np.float32)
        for i, v in enumerate((ETA[j.kind],price[:,None],renewable,(base-1)[:,None],
                               util,city_fill[:,None],latency[:,None],cross[:,None],DOM,
                               q[:,None],(latency>1)[:,None],(start-j.slot)/SLOTS,
                               energy,valid,j.priority)):
            arr[:,:,i] = v
        return arr.reshape(A,-1), valid.ravel(), start

    def select(self, j, features, valid):
        mask = valid.copy()
        if self.strategy in ("SuCompute","MILP-only","Safe-RL-only"):
            mask &= features[:,10] == 0
        if not mask.any():
            return -1,None
        if self.strategy == "RR-Local":
            ids = np.flatnonzero(mask)
            nearby = ids[LAT[j.src,ids//M] == LAT[j.src,ids//M].min()]
            action = nearby[self.rr%len(nearby)]
            self.rr += 1
            return int(action),None
        if self.strategy == "Least-Loaded":
            scores = -features[:,4]
        elif self.strategy == "Cost-First":
            scores = -features[:,1]
        elif self.strategy == "MILP-only":
            scores = 2*features[:,9]+features[:,0]-.2*features[:,4]
        else:
            with torch.inference_mode():
                scores = self.actor(torch.from_numpy(features)).numpy()
            w = self.weights
            scores = (scores + 3*w["utilization"]*features[:,9] -
                      4*(w["cost"]-DEFAULT["cost"])*features[:,1] -
                      4*(w["carbon"]-DEFAULT["carbon"])*(1-features[:,2])*features[:,12] -
                      (w["network"]-DEFAULT["network"])*features[:,7])
        action = int(np.argmax(np.where(mask,scores,-np.inf)))
        prob = None
        if self.actor is not None:
            prob = float(1/np.exp(scores[mask]-scores[action]).sum())
        return action,prob

    def change(self, seg, sign):
        span = slice(seg.begin,seg.end)
        self.used[span,seg.node,seg.pool] += sign*seg.physical
        self.effective[span,seg.node] += sign*seg.rate
        self.link[span] += sign*seg.cross_gb
        work = sign*seg.rate*(seg.end-seg.begin)
        self.committed_efslots += work
        if DOM[seg.pool]:
            self.domestic_efslots += work

    def place(self,j,action,features,valid,start,prob=None):
        if j.id not in self.decisions:
            self.decisions[j.id] = (np.packbits(valid),self.plan)
        if action < 0 or not valid[action]:
            self.costs[j.id] = True
            return -5.,1.
        n,m = divmod(action,M)
        lat = int(LAT[j.src,n])
        sla_cost = float(lat > j.latency or start+j.duration > j.deadline)
        seg = Segment(j.id,n,m,start,start+j.duration,j.rate,j.rate/ETA[j.kind,m],
                      j.rate*GB_PER_EF*bool(CROSS[j.src,n]),lat,
                      float(self.plan.resource[n]) if self.plan else 0.,
                      float(self.plan.carbon[n]) if self.plan else 0.,prob)
        self.change(seg,1)
        self.segments.append(seg)
        self.book[j.id] = seg
        self.costs[j.id] = self.costs.get(j.id,False) or bool(sla_cost)
        f = features[action]
        reward = (2.2*f[0] - .65*f[12] - .40*f[1]*f[12] + .65*f[2] -
                  .45*f[3] + .8*f[4] - .1*f[7] + .45*f[9] - .05*f[11] - 3*sla_cost)
        return float(reward),sla_cost

    def dispatch(self,j):
        f, valid, start = self.candidates(j)
        a,p = self.select(j,f,valid)
        return self.place(j,a,f,valid,start,p)

    def inject(self, slot, city, kind, severity, length):
        begin = perf_counter()
        n = CITIES.index(city)
        end = min(self.slots,slot+length)
        if kind == "pue":
            self.pue_extra[slot:end,n] += severity
        else:
            self.health[slot:end,n] *= 0 if kind=="outage" else 1-severity
        self.advance(slot,force=True)
        affected = [s for s in self.book.values() if s.node==n and s.end>slot and s.begin<end]
        jobs = self.trace.by_id
        paths = []
        for old in affected:
            if kind != "pue" and np.all(self.used[max(slot,old.begin):min(end,old.end),n]
                    <= self.health[max(slot,old.begin):min(end,old.end),n,None]*CAP[n]+1e-8):
                continue
            original_end = old.end
            cut = max(old.begin,slot)
            self.change(replace(old,begin=cut),-1)
            old.end = cut
            del self.book[old.task]
            j = replace(jobs[old.task],slot=cut,duration=original_end-cut)
            self.dispatch(j)
            dest = self.book.get(j.id)
            paths.append(dict(task_id=j.id, source=city,target=CITIES[dest.node] if dest else None,
                              checkpoint_slots=max(0,cut-old.begin),remaining_slots=j.duration,
                              operation="checkpoint" if j.kind<2 else "reroute",
                              sla_met=not self.costs[j.id]))
        result = dict(slot=slot,city=city,kind=kind,severity=severity,duration_slots=end-slot,
                      elapsed_s=perf_counter()-begin, trajectories=paths)
        self.faults.append(result)
        return result


def run(trace,strategy,weights=None,fault=None):
    sim = Calendar(trace,strategy,weights)
    events = {}
    if trace.scenario=="fault_stress" and trace.hours>74:
        events[72*SLOTS] = (CITIES[0],"outage",1.,3*SLOTS)
        events[74*SLOTS] = (CITIES[5],"pue",.35,4*SLOTS)
    if fault:
        slot,city,kind,severity,length = fault
        events[slot] = (city,kind,severity,length)
    cursor = 0
    for slot in range(sim.slots):
        if slot in events:
            sim.inject(slot,*events[slot])
        while cursor<len(trace.jobs) and trace.jobs[cursor].slot==slot:
            sim.advance(slot)
            sim.dispatch(trace.jobs[cursor])
            cursor += 1
    return sim


class ComputeEnv(gym.Env):
    """One event per step. Info exposes the CMDP cost and physical action mask."""
    metadata = {"render_modes":[]}
    def __init__(self, hours=12, scenario="normal_weekday", macro=False):
        self.hours,self.scenario,self.macro = hours,scenario,macro
        self.action_space = spaces.Discrete(A)
        self.observation_space = spaces.Box(-np.inf,np.inf,(A,len(FEATURES)),np.float32)

    def observe(self):
        j = self.sim.trace.jobs[self.cursor]
        self.sim.advance(j.slot)
        self.features,self.valid,self.start = self.sim.candidates(j)
        return self.features,{"action_mask":self.valid.copy()}

    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed)
        actual = int(self.np_random.integers(2**31)) if seed is None else seed
        self.sim = Calendar(Trace(actual,self.scenario,self.hours),"MILP-only" if self.macro else "Least-Loaded")
        self.cursor = 0
        return self.observe()

    def step(self,action):
        j = self.sim.trace.jobs[self.cursor]
        reward,cost = self.sim.place(j,int(action),self.features,self.valid,self.start)
        self.cursor += 1
        done = self.cursor==len(self.sim.trace.jobs)
        obs,info = (np.zeros_like(self.features),{}) if done else self.observe()
        return obs,reward,done,False,dict(info,cost=cost)
