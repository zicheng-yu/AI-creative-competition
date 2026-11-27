from .report import Meter


def replay(meter):
    sim = meter.sim
    hours = sim.trace.hours
    return dict(kpis=meter.kpi(0,hours), hourly=meter.series(),
                daily=[meter.kpi(h,min(h+24,hours)) for h in range(0,hours,24)],
                nodes=meter.node_series(), flights=[[h,s,d,count,example] for
                (h,s,d),(count,example) in sorted(meter.flylines.items())])
