"""Interval energy integration and canonical SHA256 accounting receipts."""
import csv
import hashlib
import io
import json
from collections import defaultdict

import numpy as np
from .power import powered_banks

from .world import (BASE_PUE, BW, CAP, CENTRES, CITIES, CROSS, DOM, EF, ETA, GRID,
                    KINDS, KW_PER_EF, LAT, PEAK_HOURS, POOLS, SLOTS)

COORDS = [(118.80,32.06),(120.59,31.30),(120.31,31.49),(119.97,31.81),(119.45,32.20),
          (120.89,31.98),(119.42,32.39),(119.92,32.45),(120.16,33.35),(119.02,33.61),
          (117.28,34.21),(119.22,34.60),(118.28,33.96),(121.47,31.23),(120.16,30.27),
          (118.38,31.33)]
METRICS = ("utilization","sla","kwh_per_efh","pue","green_share","kgco2_per_efh")


# Prose and flags added for the audit drawer. They are not part of the voucher.
DISPLAY_FIELDS = ("sha256","selection_reason","cross_region")


def receipt_hash(payload):
    data = {k:v for k,v in payload.items() if k not in DISPLAY_FIELDS}
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,
                          separators=(",",":"),allow_nan=False).encode()).hexdigest()


def is_cross_region(receipt):
    """True when any executed segment uses the 10 ms Yangtze River Delta link."""
    return any(bool(CROSS[receipt["source"],segment["node"]]) for segment in receipt["segments"])


LEDGER_COLUMNS = (
    ("task_id","任务编号"),("scenario","场景"),("strategy","策略"),("seed","种子"),
    ("source_city","来源城市"),("dest_city","目的城市"),("cross_region","是否跨域"),
    ("task_class","任务类型"),("effective_efh","算力当量EF·h"),("energy_kwh","电量kWh"),
    ("electricity_cny","电费元"),("co2_kg","碳排kg"),("avoided_vs_grid_kg","减排kg"),
    ("sla_met","SLA达成"),("pool","芯片池"),("affinity","亲和度"),("latency_ms","时延ms"),
    ("pue","PUE"),("green_share","绿电占比"),("probability","动作概率"),
    ("resource_shadow","资源影子价格"),("carbon_shadow","碳影子价格"),
    ("sha256","凭证SHA256"),("selection_reason","选中理由"),
)


def ledger_row(receipt,selection_reason=""):
    segment = receipt["segments"][0] if receipt["segments"] else None
    score = latency = pue = green = probability = resource = carbon = None
    pool = dest = ""
    if segment:
        pool = segment["pool"]
        dest = CITIES[segment["node"]]
        latency = segment["latency_ms"]
        pue = segment["pue"]
        green = segment["green_share"]
        probability = segment["probability"]
        resource = segment["resource_shadow"]
        carbon = segment["carbon_shadow"]
        if receipt.get("candidate_affinity"):
            chosen = receipt["candidate_affinity"][segment["node"]]
            score = chosen["scores"][POOLS.index(pool)]
        else:
            score = float(ETA[KINDS.index(receipt["task_class"]),POOLS.index(pool)])
    values = dict(task_id=receipt["task_id"],scenario=receipt["scenario"],strategy=receipt["strategy"],
                  seed=receipt["seed"],source_city=CITIES[receipt["source"]],dest_city=dest,
                  cross_region="是" if is_cross_region(receipt) else "否",task_class=receipt["task_class"],
                  effective_efh=receipt["effective_efh"],energy_kwh=receipt["energy_kwh"],
                  electricity_cny=receipt["electricity_cny"],co2_kg=receipt["co2_kg"],
                  avoided_vs_grid_kg=receipt["avoided_vs_grid_kg"],
                  sla_met="达成" if receipt["sla_met"] else "未达成",pool=pool,affinity=score,
                  latency_ms=latency,pue=pue,green_share=green,probability=probability,
                  resource_shadow=resource,carbon_shadow=carbon,sha256=receipt["sha256"],
                  selection_reason=selection_reason)
    return {label:values[key] for key,label in LEDGER_COLUMNS}


def ledger_csv(rows):
    buffer = io.StringIO()
    fields = [label for _,label in LEDGER_COLUMNS]
    writer = csv.DictWriter(buffer,fieldnames=fields,lineterminator="\r\n",extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return "\ufeff"+buffer.getvalue()


def topology():
    return dict(core="江苏省级调度核心",simulator="JS-ComputeSim-313",version=1,
                pools=POOLS,task_classes=KINDS,affinity=ETA.tolist(),latency_ms=LAT.tolist(),
                wan_gb_per_slot=BW,slot_minutes=5, nodes=[
                dict(id=i,city=name,lon=COORDS[i][0],lat=COORDS[i][1],centres=int(CENTRES[i]),
                     external=i>=13,peak_eflops=float(EF[i]),pools_eflops=CAP[i].tolist(),
                     base_pue=float(BASE_PUE[i])) for i,name in enumerate(CITIES)])


class Meter:
    def __init__(self, sim):
        self.sim = sim
        tr = sim.trace
        self.raw = sim.used.sum(axis=2).clip(0)
        # Identical power management for all policies: eight switchable banks per pool.
        capacity = sim.health[:,:,None]*CAP
        fill = np.divide(sim.used,capacity,out=np.zeros_like(sim.used),where=capacity>0)
        needed = np.ceil(np.round(fill.clip(0,1)*8,9))/8 * capacity
        active = powered_banks(needed,capacity).sum(axis=2)
        u = self.raw/np.maximum(1e-9,active)
        temp = np.repeat(tr.tariffs[2],SLOTS,axis=0)
        self.pue = BASE_PUE+sim.pue_extra+.035*(1-u)+.003*(temp-24)
        self.it = KW_PER_EF*(active*(.32+.68*u**1.55)+.018*(EF*sim.health-active))/SLOTS
        self.energy = self.it*self.pue
        available = np.repeat(tr.series[48:,:,1],SLOTS,axis=0)*EF*KW_PER_EF/SLOTS
        self.green = np.minimum(self.energy,available)
        self.carbon = (self.energy-self.green)*GRID
        self.price = np.repeat(tr.tariffs[0],SLOTS,axis=0)
        self.money = self.price*self.energy
        self.eff = sim.effective.clip(0)/SLOTS
        self.powered = active
        self.arrived = np.zeros(tr.hours)
        self.met = np.zeros(tr.hours)
        self.segments = defaultdict(list)
        self.flylines = defaultdict(lambda:[0,0])
        for s in sim.segments:
            if s.end<=s.begin:
                continue
            self.segments[s.task].append(s)
            j = tr.by_id[s.task]
            if j.src!=s.node:
                value = self.flylines[s.begin//SLOTS,j.src,s.node]
                value[0] += 1
                value[1] = j.id
        for j in tr.jobs:
            self.arrived[j.slot//SLOTS] += 1
            self.met[j.slot//SLOTS] += not sim.costs[j.id]

    def kpi(self,begin,end):
        span = slice(begin*SLOTS,end*SLOTS)
        def total(a):
            return a[span].sum()
        energy,work = total(self.energy),total(self.eff)
        peak = np.isin(np.arange(begin,end)%24,PEAK_HOURS)
        return dict(utilization=float(work*SLOTS/max(1e-9,total(self.powered))),
                    physical_online_utilization=float(total(self.raw)/max(1e-9,total(self.powered))),
                    powered_efh=float(total(self.powered)/SLOTS),
                    peak_sla=float(self.met[begin:end][peak].sum()/max(1,self.arrived[begin:end][peak].sum())) if peak.any() else None,
                    sla=float(self.met[begin:end].sum()/max(1,self.arrived[begin:end].sum())),
                    kwh_per_efh=float(energy/max(1e-9,work)),
                    pue=float(energy/max(1e-9,total(self.it))),
                    green_share=float(total(self.green)/max(1e-9,energy)),
                    kgco2_per_efh=float(total(self.carbon)/max(1e-9,work)),
                    installed_utilization=float(total(self.raw)/(EF.sum()*(end-begin)*SLOTS)),
                    effective_installed_utilization=float(work/(EF.sum()*(end-begin))),
                    effective_efh=float(work),energy_kwh=float(energy),tasks=int(self.arrived[begin:end].sum()))

    def series(self):
        return [self.kpi(h,h+1) for h in range(self.sim.trace.hours)]

    def node_series(self):
        def hourly(a):
            return a.reshape(-1,SLOTS,16).sum(1)
        return {k:np.round(a,4).tolist() for k,a in dict(
                utilization=hourly(self.raw)/(SLOTS*EF),
                pue=hourly(self.energy)/np.maximum(1e-9,hourly(self.it)),
                green_share=hourly(self.green)/np.maximum(1e-9,hourly(self.energy)),
                renewable_kw=self.sim.trace.series[48:,:,1]*EF*KW_PER_EF,
                health=hourly(self.sim.health)/SLOTS).items()}

    def audit(self,task_id):
        tr = self.sim.trace
        j = tr.by_id[task_id]
        packed,plan = self.sim.decisions[j.id]
        feasible = np.unpackbits(packed).reshape(16,6).astype(bool)
        segments = []
        energy = carbon = money = work = raw = 0.
        for s in self.segments[task_id]:
            n = s.node
            idx = (slice(s.begin,s.end),n)
            share = s.physical/self.raw[idx]
            e = float(self.energy[idx]@share)
            co2 = float(self.carbon[idx]@share)
            energy += e
            carbon += co2
            money += self.money[idx]@share
            work += s.rate*(s.end-s.begin)/SLOTS
            raw += s.physical*(s.end-s.begin)/SLOTS
            segments.append(dict(node=n,pool=POOLS[s.pool],start_slot=s.begin,end_slot=s.end,
                                 latency_ms=s.latency,green_share=float(self.green[idx]@share/e),
                                 pue=float(e/(self.it[idx]@share)),probability=s.probability,
                                 resource_shadow=s.resource_dual,carbon_shadow=s.carbon_dual))
        record = dict(task_id=task_id,scenario=tr.scenario,seed=tr.seed,strategy=self.sim.strategy,
                      source=j.src,task_class=KINDS[j.kind],release_slot=j.slot,deadline_slot=j.deadline,
                      latency_limit_ms=j.latency,required_efh=j.rate*j.duration/SLOTS,
                      candidate_affinity=[dict(node=i,scores=ETA[j.kind].tolist(),
                                            feasible=feasible[i].tolist(),latency_ms=int(LAT[j.src,i]),
                                            resource_shadow=float(plan.resource[i]) if plan else None,
                                            carbon_shadow=float(plan.carbon[i]) if plan else None)
                                          for i in range(16)],
                      segments=segments,effective_efh=work,physical_efh=raw,energy_kwh=energy,
                      electricity_cny=float(money),co2_kg=carbon,
                      avoided_vs_grid_kg=energy*GRID-carbon,sla_met=not self.sim.costs[j.id])
        return dict(record,sha256=receipt_hash(record))

    def export_csv(self,path):
        with open(path,"w",newline="",encoding="utf-8") as f:
            writer = None
            for j in self.sim.trace.jobs:
                row = self.audit(j.id)
                if writer is None:
                    writer = csv.DictWriter(f,fieldnames=row.keys())
                    writer.writeheader()
                writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,list) else v
                                 for k,v in row.items()})
