"""Five-minute reservation calendar shared by every baseline, training and inference."""
from dataclasses import dataclass, replace
from time import perf_counter

import gymnasium as gym
import numpy as np
import torch
from gymnasium import spaces

from .models import FEATURES, dispatch_bias, forecast, load_model
from .planner import DEFAULT, DOM_FLOOR, solve
from .power import powered_banks
from .world import (BASE_PUE, BW, CAP, CITIES, CROSS, DOM, EF, ETA, GB_PER_EF,
                    GRID, KEEPALIVE, LAT, SLOTS, STRATEGIES, Trace)

N, M = CAP.shape
A = N*M


def marginal_resources(used,health,first,last,raw,rate,base,green_kw_per_ef):
    """Evaluate each possible placement against known reservations and idle tails.

    Returns mean extra facility power per effective EF, including the bank hold.
    All candidates at a site see the same background load and powered banks.
    """
    lo = max(0,first-KEEPALIVE)
    hi = min(len(used),last+KEEPALIVE)
    cap = health[lo:hi,:,None]*CAP
    bank = np.maximum(cap/8,1e-8)
    occupied = used[lo:hi].clip(0)
    active = np.ceil(np.round(occupied/bank,9))*bank
    extra = np.zeros((hi-lo,1,M))
    extra[first-lo:last-lo] = raw
    after = np.ceil(np.round((occupied+extra)/bank,9))*bank
    old = powered_banks(active,cap)
    delta = powered_banks(after,cap)-old
    online = old.sum(2,keepdims=True)
    load = occupied.sum(2,keepdims=True)
    def power(l,b):
        return .302*b+.68*l*(l/np.maximum(b,1e-8))**.55
    gain = power(load+extra,online+delta)-power(load,online)
    section = slice(first-lo,None)
    work = rate*(last-first)
    facility = gain[section]*base[None,:,None]
    background = (.018*cap.sum(axis=2,keepdims=True)+power(load,online))[section]*base[None,:,None]
    spare_green = np.maximum(0,green_kw_per_ef[:,:,None]-background)
    energy = facility.sum(0)
    clean = np.minimum(spare_green,facility.clip(0)).sum(0)/np.maximum(energy,1e-8)
    return energy/work,clean.clip(0,1),delta[section].sum(0)/work


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
        self.reclaimable = np.zeros_like(self.used)
        self.effective = np.zeros((self.slots,N))
        self.link = np.zeros(self.slots)
        self.health = np.ones((self.slots,N))
        self.pue_extra = np.zeros_like(self.health)
        self.segments = []
        self.by_pool = [[[] for _ in range(M)] for _ in range(N)]
        self.costs = {}
        self.decisions = {}
        self.book = {}
        self.plan = None
        self.hour = -1
        self.solves = []
        self.repacked = 0
        self.committed_efslots = 0.
        self.domestic_efslots = 0.
        self.faults = []
        self.rr = 0
        self.actor = load_model("policy") if strategy in ("SuCompute","Safe-RL-only") else None

    def advance(self, slot, force=False):
        previous_slot = getattr(self,"now",-1)
        self.now = slot
        h = slot//SLOTS
        previous = self.hour
        self.hour = h
        if self.strategy in ("SuCompute","MILP-only") and (force or h != previous):
            pred = forecast(load_model("forecast"),self.trace.history_at(h))
            known = self.used[h*SLOTS:(h+24)*SLOTS].sum(2).reshape(-1,SLOTS,N).mean(1)
            self.at_plan = self.effective[h*SLOTS:(h+24)*SLOTS].copy()
            booked = np.zeros((24,N))
            booked[:len(known)] = known
            self.plan = solve(pred,h,self.trace.scenario,self.health[slot],self.pue_extra[slot],
                              self.weights,booked)
            # Estimate which hour/site would spill renewable energy if yesterday's
            # spatial demand repeated. Only fully observed hours enter the calendar.
            expected = self.plan.reserve.copy()
            for delta in range(24):
                past = h+delta-24
                if 0<=past<h:
                    last_day = self.used[past*SLOTS:(past+1)*SLOTS].sum(2).mean(0)
                    expected[delta] = np.maximum(expected[delta],last_day)
            surplus = self.plan.renewable*EF-expected*(BASE_PUE+self.pue_extra[slot])
            self.spill = np.maximum(surplus,0)
            self.solves.append(self.plan.elapsed)
        if self.plan and slot!=previous_slot and slot%(SLOTS//2)==0 and not force:
            self.repack(slot)

    def candidates(self, j):
        """Select a legal start per node/pool, then let the dispatcher select placement."""
        h = self.hour
        slack = (j.deadline-j.duration-j.slot)//SLOTS
        times = [j.slot]
        if self.plan and j.kind<2:
            # Coordinate flexible arrivals on common hourly reservations.
            latest = min(j.slot+6*SLOTS,j.deadline-j.duration)
            half_hour = SLOTS//2
            times.extend(range((j.slot//half_hour+1)*half_hour,latest+1,half_hour))
        raw = j.rate/ETA[j.kind]
        lat = LAT[j.src]/j.latency
        cross = CROSS[j.src]
        allowed = (ETA[j.kind]>=.30) & (lat[:,None]<=1)
        if self.domestic_efslots+1e-10 < DOM_FLOOR*(self.committed_efslots+j.rate*j.duration):
            allowed &= DOM
        best = np.full((N,M),-np.inf)
        features = np.zeros((N,M,len(FEATURES)),np.float32)
        starts = np.full((N,M),j.slot)
        valid = np.zeros((N,M),bool)
        for start in times:
            offset = (start-j.slot)/SLOTS
            end = start+j.duration
            relative = min(23,start//SLOTS-h)
            span = slice(start,end)
            free = (self.health[span,:,None]*CAP-self.used[span]).min(axis=0)
            legal = allowed & (free+1e-9>=raw)
            legal &= (~cross | (self.link[span].max()+j.rate*GB_PER_EF<=BW+1e-8))[:,None]
            occupied = self.used[start].clip(0)
            city = occupied.sum(1)
            thermal_hour = start//SLOTS if self.plan else h
            base = BASE_PUE+self.pue_extra[start]+.003*(self.trace.tariffs[2][thermal_hour]-24)
            meter_slots = np.arange(start,min(self.slots,end+KEEPALIVE))
            available = np.broadcast_to(self.trace.series[48+h,:,1]*EF,(len(meter_slots),N))
            green = self.trace.series[48+h,:,1]
            price = self.trace.tariffs[0][h]
            q = np.zeros(N)
            pressure = np.zeros((N,M))
            mass = 0.
            if self.plan:
                last = min(23,(end-1)//SLOTS-h)
                ph = slice(relative,last+1)
                simulated_hours = np.clip(meter_slots//SLOTS-h,0,23)
                available = self.plan.renewable[simulated_hours]*EF
                available[simulated_hours==0] = green*EF
                # Previously booked jobs already contribute to the marginal meter.
                lead = np.maximum(0,meter_slots-self.now)
                future_local = (1-np.exp(-lead[:,None]/5))*self.plan.reserve[simulated_hours]
                available = np.maximum(0,available-future_local*base)
                price = self.plan.tariff[ph].mean(0)
                added = self.effective[start]-self.at_plan[start-h*SLOTS]
                q = np.clip((self.plan.quota[ph].mean(0)-added)/EF,-1,1)
                reserve = self.plan.reserve[ph].max(0)
                if (lat<=1).sum()>1:
                    # Reserve contiguous accelerator space: many small free fragments
                    # cannot admit the next indivisible local inference job.
                    # Checkpointable reservations can release part of the guard on demand.
                    flexible = self.reclaimable[span].min(axis=0)
                    room = ((free+.65*flexible)*ETA[2]).clip(0)
                    other = np.broadcast_to(room[:,None,:],(N,M,M)).copy()
                    other[:,np.arange(M),np.arange(M)] = 0
                    locked = .45 if j.kind<2 and not j.priority else 1.
                    remaining = np.maximum(other.max(axis=2),room-locked*raw*ETA[2])
                    target = np.minimum(CAP.max(1)*.94,1.5+.65*np.sqrt(reserve))
                    loss = (np.maximum(0,target[:,None]-remaining)-
                            np.maximum(0,target-room.max(1))[:,None])
                    pressure = loss+np.maximum(0,(reserve[:,None]+raw-free.sum(1)[:,None])*.25)
                if j.kind<2 and slack>=2:
                    shares = self.plan.timing[min(4,slack-2)]
                    mass = shares[round(offset)]/max(1e-8,shares.sum())
            energy,renewable,powered = marginal_resources(self.used,self.health,start,end,raw,j.rate,base,available)
            # Same marginal units as the macro objective; reservations are advisory
            # so unforeseen urgent jobs can still use any physically feasible pool.
            guidance = .5*q[:,None]-pressure
            if self.plan:
                # Best use otherwise-curtailed generation while a batch is still movable.
                spill = self.spill[ph].mean(0)/np.maximum(j.rate*energy.T,.01)
                guidance += self.weights["carbon"]*np.minimum(1,spill.T)*renewable
                # Unused wind/solar in the open slot expires. A forecast several
                # hours ahead cannot replace green electricity already spilled.
                now_spare = np.maximum(0,green*EF-base*(city+.018*EF))
                immediate = np.minimum(1,now_spare[:,None]/np.maximum(j.rate*energy,.01))
                guidance += 1.5*self.weights["carbon"]*immediate*renewable*np.exp(-offset)
            marginal = (self.weights["cost"]*price[:,None]+self.weights["carbon"]*
                        (1-renewable)*GRID)*energy
            preference = (-marginal - self.weights["utilization"]*powered + 1.4*guidance+
                          .08*mass-.004*offset)
            observation = np.empty_like(features)
            for i,v in enumerate((ETA[j.kind],price[:,None],renewable,(base-1)[:,None],
                                  occupied/CAP,powered,lat[:,None],cross[:,None],
                                  DOM,guidance,(lat>1)[:,None],offset/6,energy,legal,j.priority)):
                observation[:,:,i] = v
            if self.actor is not None and self.plan and len(times)>1:
                preference += self.actor_scores(observation.reshape(A,-1)).reshape(N,M)
            improve = legal & (preference>best)
            if start==j.slot:
                features[:] = observation
            else:
                features[improve] = observation[improve]
            np.copyto(best,preference,where=improve)
            starts[improve] = start
            valid |= legal
            if start==j.slot and start==self.now and len(times)>1:
                # Non-idling under renewable surplus. Retain an immediate route
                # when an efficient compatible bank can already cover the batch
                # with otherwise expiring green generation for its service span.
                clean_now = legal & (ETA[j.kind]>=.85) & (renewable>=.85) & (energy<1.6)
                if clean_now.any():
                    break
        return features.reshape(A,-1),valid.ravel(),starts.ravel()

    def actor_scores(self,features):
        with torch.inference_mode():
            scores = self.actor(torch.from_numpy(features)).numpy()
        return scores + dispatch_bias(features,self.weights)

    def select(self, j, features, valid):
        mask = valid.copy()
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
            scores = self.actor_scores(features)
        action = int(np.argmax(np.where(mask,scores,-np.inf)))
        prob = None
        if self.actor is not None:
            prob = float(1/np.exp(scores[mask]-scores[action]).sum())
        return action,prob

    def change(self, seg, sign):
        span = slice(seg.begin,seg.end)
        self.used[span,seg.node,seg.pool] += sign*seg.physical
        original = self.trace.by_id[seg.task]
        if original.kind<2 and not original.priority:
            self.reclaimable[span,seg.node,seg.pool] += sign*seg.physical
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
        start = int(start[action])
        n,m = divmod(action,M)
        lat = int(LAT[j.src,n])
        sla_cost = float(lat > j.latency or start+j.duration > j.deadline)
        seg = Segment(j.id,n,m,start,start+j.duration,j.rate,j.rate/ETA[j.kind,m],
                      j.rate*GB_PER_EF*bool(CROSS[j.src,n]),lat,
                      float(self.plan.resource[n]) if self.plan else 0.,
                      float(self.plan.carbon[n]) if self.plan else 0.,prob)
        self.change(seg,1)
        self.segments.append(seg)
        self.by_pool[n][m].append(seg)
        self.book[j.id] = seg
        self.costs[j.id] = self.costs.get(j.id,False) or bool(sla_cost)
        f = features[action]
        reward = (2.2*f[0] - 1.15*f[12] - .40*f[1]*f[12] - .95*(1-f[2])*f[12] -
                  .65*f[3] - .85*f[5] - .1*f[7] + .45*f[9] - .05*f[11] - 3*sla_cost)
        return float(reward),sla_cost

    def dispatch(self,j):
        f, valid, start = self.candidates(j)
        a,p = self.select(j,f,valid)
        if a<0 and self.strategy in ("SuCompute","MILP-only","Safe-RL-only") and j.kind==2:
            repaired = self.make_room(j)
            if repaired:
                f,valid,start = self.candidates(j)
                a,p = self.select(j,f,valid)
        return self.place(j,a,f,valid,start,p)

    def repack(self,slot):
        """Revisit pending reservations at half-hour boundaries, before execution."""
        pending = [s for s in self.book.values() if s.begin>=slot and
                   self.trace.by_id[s.task].slot<slot and self.trace.by_id[s.task].kind<2]
        # Largest reservations first; bound each recourse pass.
        pending.sort(key=lambda s:s.rate*(s.end-s.begin),reverse=True)
        for old in pending[:32]:
            original = self.trace.by_id[old.task]
            duration = old.end-old.begin
            job = replace(original,slot=slot,duration=duration)
            self.change(old,-1)
            f,valid,starts = self.candidates(job)
            incumbent = old.node*M+old.pool
            exact = replace(job,slot=old.begin,deadline=old.end)
            baseline = self.candidates(exact)[0][incumbent]
            def expense(v):
                w = self.weights
                return (w["cost"]*v[...,1]*v[...,12]+w["carbon"]*GRID*(1-v[...,2])*v[...,12]+
                        w["utilization"]*v[...,5]+.25*v[...,3]-w["sla"]*v[...,9])
            # Forecast recourse optimizes the entire pending reservation's marginal
            # cost. Online arrivals still use the learned or MILP-only dispatcher.
            action = int(np.argmin(np.where(valid,expense(f),np.inf))) if valid.any() else -1
            if action>=0 and expense(f[action])+.015<expense(baseline):
                old.end = old.begin
                self.place(job,action,f,valid,starts)
                self.repacked += 1
            else:
                self.change(old,1)

    def make_room(self,j):
        """Reclaim up to four movable reservations atomically for a pinned inference job."""
        slots = slice(j.slot,j.slot+j.duration)
        eligible = (LAT[j.src,:,None]<=j.latency) & (CAP*self.health[slots].min(0)[:,None]*
                                                     ETA[j.kind]>=j.rate)
        for n,m in zip(*np.nonzero(eligible)):
            victims = []
            trials = []
            for old in reversed(self.by_pool[n][m]):
                if old.end<=j.slot or old.begin>=slots.stop:
                    continue
                previous = self.trace.by_id[old.task]
                movable = (previous.kind<2 and not previous.priority) or (previous.kind==2 and
                           np.count_nonzero(LAT[previous.src]<=previous.latency)>1)
                if not movable or self.book.get(old.task) is not old:
                    continue
                tail = replace(old,begin=max(j.slot,old.begin))
                self.change(tail,-1)
                victims.append((old,tail))
                available = (self.health[slots,n]*CAP[n,m]-self.used[slots,n,m]).min()
                if available*ETA[j.kind,m]>=j.rate-1e-8 or len(victims)==4:
                    break
            if victims and self.candidates(j)[1][n*M+m]:
                reserved = Segment(j.id,n,m,j.slot,slots.stop,j.rate,j.rate/ETA[j.kind,m],
                                   j.rate*GB_PER_EF*CROSS[j.src,n],int(LAT[j.src,n]),0.,0.,None)
                self.change(reserved,1)
                for old,tail in victims:
                    remaining = replace(self.trace.by_id[old.task],slot=tail.begin,duration=tail.end-tail.begin)
                    f,valid,starts = self.candidates(remaining)
                    action,prob = self.select(remaining,f,valid)
                    if action<0:
                        break
                    self.place(remaining,action,f,valid,starts,prob)
                    trials.append((old,self.book[old.task]))
                self.change(reserved,-1)
                if len(trials)==len(victims) and self.candidates(j)[1].any():
                    for old,tail in victims:
                        old.end = tail.begin
                    return True
            # No partial migration survives a failed placement trial.
            for old,moved in reversed(trials):
                self.change(moved,-1)
                self.segments.pop()
                self.by_pool[moved.node][moved.pool].pop()
                self.book[old.task] = old
            for _,tail in victims:
                self.change(tail,1)
        return False

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
            if self.book.get(old.task) is not old or old.end<=max(old.begin,slot):
                continue  # A preceding recovery may already have moved this reservation.
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
    def __init__(self, hours=12, scenario="normal_weekday", macro=False,policy=None):
        self.hours,self.scenario,self.macro = hours,scenario,macro
        self.policy = policy
        self.action_space = spaces.Discrete(A)
        self.observation_space = spaces.Box(-np.inf,np.inf,(A,len(FEATURES)),np.float32)

    def observe(self):
        j = self.sim.trace.jobs[self.cursor]
        self.sim.advance(j.slot)
        self.features,self.valid,self.start = self.sim.candidates(j)
        if self.policy is not None and not self.valid.any() and j.kind==2 and self.sim.make_room(j):
            self.features,self.valid,self.start = self.sim.candidates(j)
        return self.features,{"action_mask":self.valid.copy()}

    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed)
        actual = int(self.np_random.integers(2**31)) if seed is None else seed
        self.sim = Calendar(Trace(actual,self.scenario,self.hours),"MILP-only" if self.macro else "Least-Loaded")
        if self.policy is not None:
            self.sim.actor = self.policy
            self.sim.strategy = "SuCompute" if self.macro else "Safe-RL-only"
        self.cursor = 0
        return self.observe()

    def step(self,action):
        j = self.sim.trace.jobs[self.cursor]
        reward,cost = self.sim.place(j,int(action),self.features,self.valid,self.start)
        self.cursor += 1
        done = self.cursor==len(self.sim.trace.jobs)
        obs,info = (np.zeros_like(self.features),{}) if done else self.observe()
        return obs,reward,done,False,dict(info,cost=cost)
