from .report import Meter
from .world import ETA, KINDS, LAT


def compact_receipt(receipt):
    """Losslessly factor topology constants out of the signed receipt."""
    compact = receipt.copy()
    candidates = compact.pop("candidate_affinity")
    compact["feasible_bits"] = [sum(int(ok)<<i for i,ok in enumerate(c["feasible"])) for c in candidates]
    for key in ("resource_shadow","carbon_shadow"):
        compact[key] = [c[key] for c in candidates] if candidates[0][key] is not None else None
    return compact


def expand_receipt(compact):
    receipt = compact.copy()
    bits = receipt.pop("feasible_bits")
    resource = receipt.pop("resource_shadow")
    carbon = receipt.pop("carbon_shadow")
    affinity = ETA[KINDS.index(receipt["task_class"])].tolist()
    receipt["candidate_affinity"] = [dict(node=n,scores=affinity,
        feasible=[bool(mask & (1<<m)) for m in range(len(affinity))],
        latency_ms=int(LAT[receipt["source"],n]),
        resource_shadow=resource[n] if resource is not None else None,
        carbon_shadow=carbon[n] if carbon is not None else None) for n,mask in enumerate(bits)]
    return receipt


def replay(meter):
    sim = meter.sim
    hours = sim.trace.hours
    return dict(kpis=meter.kpi(0,hours), hourly=meter.series(),
                daily=[meter.kpi(h,min(h+24,hours)) for h in range(0,hours,24)],
                nodes=meter.node_series(), flights=[[h,s,d,count,example] for
                (h,s,d),(count,example) in sorted(meter.flylines.items())])
