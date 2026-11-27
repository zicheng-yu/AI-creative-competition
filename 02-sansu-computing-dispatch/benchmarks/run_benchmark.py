"""Recompute the evidence package and static twin; no network or training required."""
import argparse
import csv
import hashlib
import json
import platform
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
import torch

from backend.models import ROOT, WEIGHTS
from backend.replay import replay
from backend.report import METRICS, Meter, topology
from backend.simulation import run
from backend.world import SCENARIOS, STRATEGIES, Trace

def save_json(path,data,pretty=False):
    with path.open("w",encoding="utf-8",newline="\n") as f:
        json.dump(data,f,ensure_ascii=False,allow_nan=False,
                  indent=2 if pretty else None,separators=None if pretty else (",",":"))
        f.write("\n")


def figures(rows, path):
    fig, axes = plt.subplots(2,3,figsize=(15,8),layout="constrained")
    colors = ["#507594","#e59533","#8a789a","#088169","#aec7bb","#a5b6d8"]
    for ax,key,title in zip(axes.flat,METRICS,("Powered-bank utilization","SLA attainment",
            "Energy / effective work (kWh/EF·h)","Energy-weighted PUE","Renewable energy share",
            "Carbon intensity (kg/EF·h)")):
        for i,strategy in enumerate(STRATEGIES):
            values = [r[key] for r in rows if r["strategy"]==strategy]
            ax.bar(np.arange(4)+(i-2.5)*.13,values,.13,label=strategy,color=colors[i])
        ax.set_xticks(range(4),["Normal","Renewables","Peak","Fault"])
        ax.set_title(title)
        ax.grid(axis="y",alpha=.2)
    handles,labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="outside lower center",ncol=6)
    fig.savefig(path/"comparison.png",dpi=200)
    plt.close(fig)
    with (WEIGHTS/"ppo_training.csv").open() as f:
        logs = list(csv.DictReader(f))
    fig,axes = plt.subplots(1,3,figsize=(12,3.6),layout="constrained")
    for ax,key in zip(axes,("mean_reward","lagrange_multiplier","violation_rate")):
        vals = [float(r[key]) for r in logs]
        ax.plot(np.arange(1,len(vals)+1),vals,color="#638599",alpha=.5)
        ax.plot(np.arange(10,len(vals)+1),np.convolve(vals,np.ones(10)/10,"valid"),color="#08785c")
        ax.set(xlabel="PPO update",title=key.replace("_"," "))
        if key=="violation_rate":
            ax.axhline(.005,color="darkred",ls="--")
    fig.savefig(path/"training.png",dpi=200)
    plt.close(fig)


def benchmark(seed,out):
    torch.set_num_threads(1)
    demo = out/"frontend_demo_data"
    dest = out/"benchmarks"
    for directory in (dest,demo):
        directory.mkdir(exist_ok=True,parents=True)
    save_json(demo/"topology.json",topology(),True)
    scenarios, all_rows, faults, samples, hours = {},[],[],[],[]
    for scenario in SCENARIOS:
        tr = Trace(seed,scenario,168)
        cases = {}
        for strategy in STRATEGIES:
            sim = run(tr,strategy)
            meter = Meter(sim)
            scores = meter.kpi(0,168)
            row = dict(scenario=scenario,strategy=strategy,**scores,
                       solve_max_s=max(sim.solves,default=None),
                       failover_max_s=max((e["elapsed_s"] for e in sim.faults),default=None),
                       measured_solves=len(sim.solves))
            all_rows.append(row)
            hourly = meter.series()
            hours.extend(dict(scenario=scenario,strategy=strategy,hour=h,**v)
                         for h,v in enumerate(hourly))
            if strategy in STRATEGIES[:4]:
                cases[strategy] = replay(meter)
                ids = [tr.jobs[0].id]
                # One selectable cross-domain receipt per day plus each fault's first migration.
                days = set()
                for (h,s,d),(_,task_id) in meter.flylines.items():
                    if (s>=13 or d>=13) and h//24 not in days:
                        ids.append(task_id)
                        days.add(h//24)
                ids.extend(e["trajectories"][0]["task_id"] for e in sim.faults if e["trajectories"])
                cases[strategy]["sample_task_ids"] = list(dict.fromkeys(ids))
                samples.extend(meter.audit(i) for i in dict.fromkeys(ids))
            if strategy=="SuCompute":
                faults.extend(dict(scenario=scenario,strategy=strategy,**e) for e in sim.faults)
            print(scenario,strategy,round(scores["sla"],4),round(scores["utilization"],4),flush=True)
        scenarios[scenario]=cases
    keys = list(hours[0])
    with (dest/"results_detail.csv").open("w",newline="",encoding="utf-8") as f:
        writer = csv.DictWriter(f,keys)
        writer.writeheader()
        writer.writerows(hours)
    average = {s:{k:float(np.mean([r[k] for r in all_rows if r["strategy"]==s]))
                  for k in METRICS} for s in STRATEGIES}
    # Digest all deterministic KPI rows, excluding wall-clock measurements.
    digest = hashlib.sha256((dest/"results_detail.csv").read_bytes()).hexdigest()
    summary = dict(version=1,seed=seed,hours=168,scenarios=SCENARIOS,strategies=STRATEGIES,
                   aggregation="unweighted mean of four week-level metrics",mean=average,
                   detail_sha256=digest,runs=all_rows,
                   runtime=dict(python=platform.python_version(),cpu=platform.machine(),
                                scipy=scipy.__version__,torch=torch.__version__))
    save_json(dest/"results_summary.json",summary,True)
    report = ["# SuCompute 七天离线评测","",
              f"四场景各运行 168 小时，seed 为 {seed}。表中数值为四个周指标的等权均值。","",
              "| 策略 | 启用容量利用率 | SLA | kWh/EF·h | PUE | 绿电占比 | kgCO₂/EF·h |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for label,k in average.items():
        report.append(f"| {label} | {k['utilization']:.2%} | {k['sla']:.2%} | "
                      f"{k['kwh_per_efh']:.1f} | {k['pue']:.4f} | {k['green_share']:.2%} | "
                      f"{k['kgco2_per_efh']:.1f} |")
    ours = average["SuCompute"]
    report += ["","## SuCompute 对各基线的变化","",
               "| 对照 | 利用率相对提升 | SLA 差值（百分点） | 能耗降低 | PUE 降低 | 绿电相对提升 | 碳强度降低 |",
               "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for label in STRATEGIES[:3]:
        b = average[label]
        report.append(f"| {label} | {ours['utilization']/b['utilization']-1:+.2%} | "
                      f"{100*(ours['sla']-b['sla']):+.2f} | {1-ours['kwh_per_efh']/b['kwh_per_efh']:+.2%} | "
                      f"{b['pue']-ours['pue']:+.4f} | {ours['green_share']/b['green_share']-1:+.2%} | "
                      f"{1-ours['kgco2_per_efh']/b['kgco2_per_efh']:+.2%} |")
    report += ["","## 目标核对","",
               "| 相对 RR-Local 的方案目标 | 实测 | 下限验收 |","| --- | ---: | --- |"]
    b = average["RR-Local"]
    for label,value,threshold in [
            ("利用率 +15%～22%",ours["utilization"]/b["utilization"]-1,.15),
            ("各场景 SLA ≥99.2%",min(r["sla"] for r in all_rows if r["strategy"]=="SuCompute"),.992),
            ("单位能耗降低 12%～18%",1-ours["kwh_per_efh"]/b["kwh_per_efh"],.12),
            ("绿电相对提升 18%～25%",ours["green_share"]/b["green_share"]-1,.18),
            ("碳强度降低 15%～22%",1-ours["kgco2_per_efh"]/b["kgco2_per_efh"],.15)]:
        report.append(f"| {label} | {value:.2%} | {'达到' if value>=threshold else '未达到'} |")
    max_solve = max(r["solve_max_s"] for r in all_rows if r["solve_max_s"] is not None)
    report += ["", f"全体滚动规划最长 {max_solve:.4f} 秒。SuCompute 故障编排最长 "
               f"{max(e['elapsed_s'] for e in faults):.4f} 秒。数字是本机墙钟测量。","",
               f"该负载下 RR-Local 已达 {b['utilization']:.2%} 利用率，相对提升的数学上限为 "
               f"{1/b['utilization']-1:.2%}。全装机与有效吞吐口径见 results_summary.json。","",
               "输入构造、指标分母和凭证口径见 MODEL.md 与 API_CONTRACT.md。"]
    (dest/"results_report.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    save_json(demo/"benchmarks_summary.json",summary,True)
    save_json(demo/"scenarios_4x4.json",dict(version=1,seed=seed,scenarios=scenarios))
    save_json(demo/"fault_failover_trace.json",dict(version=1,seed=seed,events=faults),True)
    save_json(demo/"ledger_sample.json",dict(version=1,receipts=samples),True)
    figures(all_rows,dest)
    print("detail_sha256",digest,flush=True)


if __name__=="__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed",type=int,default=313)
    p.add_argument("--out",type=Path,default=ROOT)
    args = p.parse_args()
    benchmark(args.seed,args.out)
