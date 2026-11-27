import csv
import hashlib
import json
from backend.models import ROOT
from backend.report import METRICS, receipt_hash
from backend.replay import expand_receipt
from backend.world import SCENARIOS, STRATEGIES


def read(name):
    return json.loads((ROOT/"frontend_demo_data"/(name+".json")).read_text(encoding="utf-8"))


def test_static_release_is_complete_and_matches_benchmark():
    summary=read("benchmarks_summary")
    assert summary==json.loads((ROOT/"benchmarks/results_summary.json").read_text(encoding="utf-8"))
    detail=ROOT/"benchmarks/results_detail.csv"
    assert summary["detail_sha256"]==hashlib.sha256(detail.read_bytes()).hexdigest()
    with detail.open(encoding="utf-8") as f:
        assert sum(1 for _ in csv.DictReader(f))==4*6*168
    assert len(summary["runs"])==24
    runs={(r["scenario"],r["strategy"]):r for r in summary["runs"]}
    ledger = ROOT/"frontend_demo_data/ledger_sample.json"
    assert ledger.stat().st_size<=250_000
    receipts=[expand_receipt(c) for c in read("ledger_sample")["receipts"]]
    lookup={(r["scenario"],r["strategy"],r["task_id"]) for r in receipts}
    assert all(r["sha256"]==receipt_hash(r) for r in receipts)
    weeks=read("scenarios_4x4")["scenarios"]
    for scene in SCENARIOS:
        assert len({r["trace_sha256"] for r in summary["runs"] if r["scenario"]==scene})==1
        shard=json.loads((ROOT/"frontend_demo_data"/weeks[scene]).read_text(encoding="utf-8"))
        assert shard["version"]==2 and shard["scenario"]==scene
        for strategy in STRATEGIES[:4]:
            week=shard["strategies"][strategy]
            assert len(week["hourly"])==168 and len(week["daily"])==7
            assert all(week["kpis"][key]==runs[scene,strategy][key] for key in METRICS)
            assert all(len(matrix)==168 and all(len(row)==16 for row in matrix)
                       for matrix in week["nodes"].values())
            assert all(0<=h<168 and s!=d and count>=1 for h,s,d,count,_ in week["flights"])
            assert week["sample_task_ids"] and all((scene,strategy,i) in lookup for i in week["sample_task_ids"])
    events=read("fault_failover_trace")["events"]
    assert {e["kind"] for e in events}=={"outage","pue"}
    assert all(e["elapsed_s"]<3 for e in events)
    assert any(t["source"]!=t["target"] and t["target"] for e in events for t in e["trajectories"])


def test_policy_out_of_sample_sla_and_times():
    summary = read("benchmarks_summary")
    full = summary["mean"]["SuCompute"]
    baseline = summary["mean"]["RR-Local"]
    assert full["utilization"]>=.78 and full["utilization"]>=1.15*baseline["utilization"]
    assert full["kwh_per_efh"]<=.88*baseline["kwh_per_efh"]
    assert full["pue"]<=baseline["pue"]-.06
    assert full["green_share"]>=1.18*baseline["green_share"]
    assert full["kgco2_per_efh"]<=.85*baseline["kgco2_per_efh"]
    for r in summary["runs"]:
        assert r["domestic_share"]>=.30-1e-8
        if r["strategy"]=="SuCompute":
            assert r["sla"]>=.995
            assert r["solve_max_s"]<1 and r["measured_solves"]>=168
            assert r["batch_jobs_shifted_2h"]>0
