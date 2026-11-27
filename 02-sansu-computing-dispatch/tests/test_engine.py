import csv
import json
import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env
from backend.models import ROOT, load_model, forecast
from backend.planner import DOM_FLOOR, solve
from backend.report import Meter, receipt_hash, topology
from backend.simulation import ComputeEnv, run
from backend.world import BW, CAP, CENTRES, CITIES, DOM, EF, GB_PER_EF, GRID, SLOTS, Trace


def test_topology_env_and_trace():
    assert CENTRES.sum()==313 and np.isclose(EF[:13].sum(),271.8)
    assert len(topology()["nodes"])==16 and np.all(CAP>0)
    env = ComputeEnv(hours=2)
    check_env(env,skip_render_check=True)
    a,_ = env.reset(seed=99)
    b,_ = env.reset(seed=99)
    np.testing.assert_array_equal(a,b)
    assert Trace(23,"peak_shaving",3).jobs==Trace(23,"peak_shaving",3).jobs


def test_forecast_past_only_and_milp_constraints():
    tr = Trace(222,"normal_weekday",4)
    x = forecast(load_model("forecast"),tr.history_at(1))
    tr.series[49:]=0
    np.testing.assert_array_equal(x,forecast(load_model("forecast"),tr.history_at(1)))
    health = np.ones(16)
    health[1] = 0
    p = solve(x,1,tr.scenario,health,np.zeros(16))
    assert p.elapsed<1 and p.quota.shape==(24,16)
    assert p.domestic_share>=DOM_FLOOR-1e-7 and p.max_cross_flow*GB_PER_EF<=BW+1e-6
    assert not p.quota[:,1].any()
    assert np.all(p.quota+p.reserve<=EF*health+1e-6)
    assert p.timing.shape==(5,7) and np.all(p.timing>=-1e-7)
    assert all(not p.timing[tier,tier+3:].any() for tier in range(5))
    assert np.all(p.resource>=0) and np.all(p.carbon>=0)


@pytest.mark.parametrize("kind,severity", [("outage",1.),("capacity",.6),("pue",.4)])
def test_fault_conservation_and_receipts(kind,severity,tmp_path):
    tr = Trace(81,"normal_weekday",5)
    sim = run(tr,"SuCompute",fault=(15,CITIES[0],kind,severity,15))
    assert np.all(sim.used<=sim.health[:,:,None]*CAP+1e-7) and sim.used.min()>-1e-7
    assert np.all((sim.link>=-1e-7)&(sim.link<=BW+1e-7))
    assert sim.faults[0]["elapsed_s"]<3
    assert sim.domestic_efslots>=DOM_FLOOR*sim.committed_efslots-1e-7
    m = Meter(sim)
    completed = [m.audit(j.id) for j in tr.jobs]
    for a in completed:
        assert receipt_hash(a)==a["sha256"]
        assert a["effective_efh"]<=a["required_efh"]+1e-7
        if a["sla_met"]:
            assert np.isclose(a["effective_efh"],a["required_efh"])
            assert all(s["latency_ms"]<=a["latency_limit_ms"] and
                       s["end_slot"]<=a["deadline_slot"] for s in a["segments"])
    assert np.isclose(sum(a["effective_efh"] for a in completed),m.eff.sum())
    assert np.isclose(sum(a["energy_kwh"] for a in completed),m.energy[m.raw>1e-8].sum())
    assert np.allclose(m.carbon,(m.energy-m.green)*GRID)
    m.export_csv(tmp_path/"ledger.csv")
    with (tmp_path/"ledger.csv").open(encoding="utf-8") as f:
        assert len(list(csv.DictReader(f)))==len(tr.jobs)


def test_bank_hold_and_effective_online_denominator():
    from backend.simulation import Calendar
    from backend.world import KEEPALIVE
    tr = Trace(12,"normal_weekday",1)
    sim = Calendar(tr,"RR-Local")
    sim.costs = {j.id:True for j in tr.jobs}
    sim.used[2,0,0] = CAP[0,0]/8
    sim.effective[2,0] = .75*CAP[0,0]/8
    meter = Meter(sim)
    assert np.allclose(meter.powered[2:3+KEEPALIVE,0],CAP[0,0]/8)
    assert meter.powered[3+KEEPALIVE,0]==0
    assert np.isclose(meter.kpi(0,1)["utilization"],.75/(KEEPALIVE+1))
    sim.health[3,0] = 0
    assert not Meter(sim).powered[3:,0].any()


def test_failed_displacement_rolls_back_the_calendar():
    from backend.simulation import Calendar, Segment
    from backend.world import ETA, Job
    tr = Trace(51,"normal_weekday",2)
    # Only one online city. Six existing batches leave no alternative for a trial move.
    tr.jobs = [Job(m,0,0,0,CAP[0,m]*ETA[0,m],12,12,10,False) for m in range(6)]
    pinned = Job(6,1,0,2,1.,2,3,1,True)
    tr.jobs.append(pinned)
    sim = Calendar(tr,"Safe-RL-only")
    sim.health[:,1:] = 0
    sim.advance(1)
    for m,j in enumerate(tr.jobs[:6]):
        s = Segment(j.id,0,m,0,12,j.rate,CAP[0,m],0.,1,0.,0.,None)
        sim.change(s,1)
        sim.segments.append(s)
        sim.by_pool[0][m].append(s)
        sim.book[j.id] = s
    before = sim.used.copy()
    assert not sim.make_room(pinned)
    np.testing.assert_allclose(sim.used,before,atol=1e-12)
    assert len(sim.book)==len(sim.segments)==6
    assert all(s.end==12 for s in sim.segments)


@pytest.mark.parametrize("strategy",["RR-Local","Least-Loaded","Cost-First","SuCompute","MILP-only","Safe-RL-only"])
def test_shared_feasibility_and_no_forecast_leak(strategy):
    from backend.simulation import Calendar
    from backend.world import Job
    tr = Trace(61,"normal_weekday",8)
    sim = Calendar(tr,strategy)
    sim.advance(0)
    tight = Job(0,0,0,2,.5,2,2,1,False)
    _,mask,_ = sim.candidates(tight)
    assert mask.any() and not mask.reshape(16,6)[1:].any()
    assert not mask.reshape(16,6)[:,~DOM].any()
    flex = Job(1,0,0,0,.8,6,6+6*SLOTS,10,False)
    first = sim.candidates(flex)
    tr.series[49:] = 0  # Unobserved future weather and arrivals must not influence the action.
    second = sim.candidates(flex)
    for a,b in zip(first,second):
        np.testing.assert_array_equal(a,b)
    if strategy not in ("SuCompute","MILP-only"):
        assert not first[2].any()
