#!/usr/bin/env python3
"""Build the track-02 plan and evidence PDFs from a reproduced benchmark.

Numbers in the HTML come from deliverables/repro, which is the output of:

    python weights/verify_weights.py
    python scripts/run_baselines.py --seed 313
    python benchmarks/run_benchmark.py --seed 313 --workers 2 --out <repro>

The frozen files under benchmarks/ stay untouched. Wall-clock seconds are
this host's measurement. Weekly percentages are read back from the report
this command wrote.
"""

from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

TRACK = Path(__file__).resolve().parents[1]
DELIV = TRACK / "deliverables"
REPRO = DELIV / "repro"
SRC = Path("/tmp/sucompute-repro")
STYLE = DELIV / "src" / "style.css"
BUILD = DELIV / "src" / "rendered"
PREFIX = "“三苏”创新应用赛道-苏算绿枢（SuCompute-Opt）-盼盼法式小面包"
FROZEN_SHA = "07625d6e37ac223cf1d6b936b6cc3b972d0b16c0ceb32d21cefc413e09437f7d"
FROZEN_SOLVE = "0.0891"
FROZEN_FAIL = "0.0803"
CITIES = (
    "南京", "苏州", "无锡", "常州", "镇江", "南通", "扬州", "泰州", "盐城",
    "淮安", "徐州", "连云港", "宿迁", "上海", "浙江", "安徽芜湖",
)


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def copy_repro() -> None:
    REPRO.mkdir(parents=True, exist_ok=True)
    bench = SRC / "benchmarks"
    if not (bench / "results_summary.json").exists():
        raise SystemExit(f"missing reproduction at {bench}; rerun run_benchmark.py first")
    for name in ("results_report.md", "results_summary.json", "results_detail.csv",
                 "comparison.png", "training.png"):
        shutil.copy2(bench / name, REPRO / name)
    shutil.copy2(SRC / "baseline_seed313.md", REPRO / "baseline_seed313.md")
    ledger = SRC / "frontend_demo_data" / "ledger_sample.json"
    if ledger.exists():
        shutil.copy2(ledger, REPRO / "ledger_sample.json")


def load() -> dict:
    summary = json.loads((REPRO / "results_summary.json").read_text(encoding="utf-8"))
    report = (REPRO / "results_report.md").read_text(encoding="utf-8")
    manifest = json.loads((TRACK / "weights" / "manifest.json").read_text(encoding="utf-8"))
    forecast = json.loads((TRACK / "weights" / "forecast_metrics.json").read_text(encoding="utf-8"))
    verify = subprocess.check_output(
        [sys.executable, str(TRACK / "weights" / "verify_weights.py")],
        cwd=TRACK, text=True,
    ).strip()
    (REPRO / "verify_weights.txt").write_text(verify + "\n", encoding="utf-8")
    baseline = (REPRO / "baseline_seed313.md").read_text(encoding="utf-8")
    ledger = json.loads((REPRO / "ledger_sample.json").read_text(encoding="utf-8"))
    receipt = next(
        r for r in ledger["receipts"]
        if r["scenario"] == "normal_weekday" and r["strategy"] == "SuCompute" and r["task_id"] == 1
    )
    return dict(summary=summary, report=report, manifest=manifest, forecast=forecast,
                verify=verify, baseline=baseline, receipt=receipt)


def parse_md_table(report: str, heading: str) -> list[list[str]]:
    lines = report.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(heading))
    rows = []
    for line in lines[start + 1:]:
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if set(cells) <= {"---", ":---", "---:"} or all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    return rows


def zh_figure(summary: dict, path: Path) -> None:
    font_path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    font_manager.fontManager.addfont(font_path)
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["WenQuanYi Micro Hei"]
    plt.rcParams["axes.unicode_minus"] = False
    order = ["RR-Local", "Least-Loaded", "Cost-First", "SuCompute"]
    labels = ["RR", "少负载", "成本", "绿枢"]
    colors = ["#507594", "#e59533", "#8a789a", "#08785c"]
    mean = summary["mean"]
    specs = [
        ("utilization", "有效在线利用率", True),
        ("sla", "SLA 达标率", True),
        ("kwh_per_efh", "单位能耗（kWh/EF·h）", False),
        ("kgco2_per_efh", "碳强度（kgCO₂/EF·h）", False),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(7.4, 4.8), layout="constrained")
    for ax, (key, title, pct) in zip(axes.flat, specs):
        vals = [mean[name][key] * (100 if pct else 1) for name in order]
        ax.bar(range(4), vals, color=colors, width=0.72)
        ax.set_title(title, fontsize=11, color="#143044", pad=6)
        ax.set_xticks(range(4), labels, fontsize=9)
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(axis="y", alpha=0.25)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def money_table(summary: dict) -> tuple[str, list[list[str]]]:
    rr = summary["mean"]["RR-Local"]["kwh_per_efh"]
    ours = summary["mean"]["SuCompute"]["kwh_per_efh"]
    precise = 1 - ours / rr
    # Money uses the report's printed percentage so a reader can recompute it.
    rate = 0.2123
    price = 0.6263
    rows = []
    for label, yi in (("低", 0.5), ("基准", 2.0), ("高", 8.0)):
        yuan = yi * 1e8 * price * rate
        rows.append([label, f"{yi:.1f} 亿 kWh", f"{yuan / 1e4:,.0f}"])
    note = (f"本次复现的精确降幅是 {precise:.6%}（{ours:.4f} / {rr:.4f}）。"
            f"金额表用报告印出的 21.23%，电价用 0.6263 元/kWh。")
    return note, rows


def receipt_bits(receipt: dict) -> dict:
    seg = receipt["segments"][0]
    return dict(
        city=CITIES[seg["node"]],
        pool=seg["pool"],
        prob=f"{seg['probability']:.3f}",
        green=f"{seg['green_share']:.2%}",
        pue=f"{seg['pue']:.3f}",
        efh=f"{receipt['effective_efh']:.3f}",
        kwh=f"{receipt['energy_kwh']:,.0f}",
        cny=f"{receipt['electricity_cny']:,.0f}",
        co2=f"{receipt['co2_kg']:,.1f}",
        avoid=f"{receipt['avoided_vs_grid_kg']:,.0f}",
        sha=receipt["sha256"],
        sla="满足" if receipt["sla_met"] else "未满足",
        src=CITIES[receipt["source"]],
        klass=receipt["task_class"],
        slots=f"{seg['start_slot']}–{seg['end_slot']}",
    )


def pages_plan(data: dict) -> list[dict]:
    summary = data["summary"]
    report_rows = parse_md_table(data["report"], "| 策略 |")
    delta_rows = parse_md_table(data["report"], "| 对照 |")
    goal_rows = parse_md_table(data["report"], "| 相对 RR-Local")
    main = [r for r in report_rows if r[0] in ("RR-Local", "Least-Loaded", "Cost-First", "SuCompute")]
    main_view = [[r[0], r[1], r[2], r[3], r[4], r[5], r[6]] for r in main]
    money_note, money_rows = money_table(summary)
    solve = "0.0957"
    fail = "0.0629"
    for line in data["report"].splitlines():
        if line.startswith("全体滚动规划最长"):
            solve = line.split("全体滚动规划最长", 1)[1].split("秒", 1)[0].strip()
            fail = line.split("SuCompute 故障编排最长", 1)[1].split("秒", 1)[0].strip()
    fc = data["forecast"]["validation"]
    return [
        {
            "cover": True,
            "doc": "项目计划书",
            "sub": "行业解决方案白皮书 · 异构算力调度与能效",
            "metrics": [
                (main_view[3][2], "四场景等权 SLA"),
                (main_view[3][1], "有效在线利用率"),
                (delta_rows[0][3].lstrip("+"), "单位能耗降幅，相对 RR-Local"),
            ],
            "foot": "2026 年 11 月 · 初筛版 · 报名编号 REG-2026-000524",
        },
        {
            "title": "对准赛题原文，而不是全省成绩单",
            "blocks": [
                {"t": "p", "text": "苏算绿枢（SuCompute-Opt）是面向赛题 AI-JIANGSU-Q36 的调度策略引擎、离线仿真和本地边车。命题单位是江苏省数据集团有限公司，团队盼盼法式小面包，组别为创新组。它给出可复算的策略对比，不代替省一体化算力监测调度平台，也不把合成周的指标写成全省已经实现的运行成绩。"},
                {"t": "h3", "text": "命题原文里的规模"},
                {"t": "p", "text": "challenge_raw.json 的命题背景写明：平台已形成“省级调度核心 + 13 个市级节点”，纳管 313 个在用数据中心，总算力规模 271.8 EFlops，面向地市开放子门户，并与上海、浙江、安徽互联，作为中国算力网江苏分平台与国家平台贯通。这几项按命题原文引用。"},
                {"t": "h3", "text": "原文里的四件调度难事"},
                {"t": "ul", "items": [
                    "异构资源统一难：通算、智算、超算并存，国产与进口芯片混合，口径不一，匹配依赖人工经验。",
                    "供需错配与空转并存：训练、微调、推理特征不同，闲时空转和高峰排队同时存在。",
                    "绿色算力量化难：PUE、能耗和算力产出缺少统一的在线度量，绿电与能耗双控进不了调度。",
                    "跨域协同复杂：长三角多主体的交易、计费、SLA 和故障切换缺少智能决策。",
                ]},
                {"t": "note", "text": "分市机房座数、分市 EFlops、芯片份额和各市 PUE 都不在命题原文里。仓库里的小时环境按 GDP 份额分配，五分钟引擎按另一组座数向量分配，两套都是假设。城域 1 ms、省内 5 ms、长三角 10 ms 是仿真设计时延，DATA_CONSTRUCTION 写明不是实测 RTT。"},
            ],
        },
        {
            "title": "白皮书口径：能引用的数，和必须标预估的数",
            "blocks": [
                {"t": "p", "text": "行业方案只使用仓库已经写明出处的公开数。下面的链接和表格抄自 docs/DATA_CONSTRUCTION.md 与 configs/energy.yaml。本次写计划书时没有逐条重新打开政府网页，页面是否仍可访问，标为待核实。"},
                {"t": "table", "headers": ["量", "仓库中的取值", "性质"], "rows": [
                    ["313 座、271.8 EFlops、1+13、沪浙皖", "命题原文", "按 challenge_raw 引用"],
                    ["13 市 GDP", "2024 年 1–12 月分市表，13 市合计 137291.46 亿元", "只作小时环境的比例，不是算力普查"],
                    ["2025-08 110 kV 两部制", "谷 0.3485 / 平 0.6263 / 峰 0.9682 / 尖 1.1221 元/kWh", "小时环境使用。五分钟引擎的电价是另一条演示曲线"],
                    ["2022 年电力碳因子", "华东 0.5617；苏 0.5978；沪 0.5849；浙 0.5153；皖 0.6782", "年平均因子。五分钟引擎用演示值 0.55，不写成 0.5617"],
                    ["盐城、南通、连云港风光装机", "时点分别为 2024-08、2024 年末、2025-05", "资源禀赋，不是机房绿电合同"],
                ]},
                {"t": "p", "text": "小时环境把江苏 271.8 EFlops 按 GDP 份额分到 13 市，尾差补在宿迁；三个枢纽各设 12 EFlops。五分钟引擎把 313 座按代码中的座数向量拆开，再乘 271.8/313，枢纽另设上海 26、浙江 20、芜湖 18 EFlops，全网装机 335.8 EFlops。MODEL.md 写明枢纽容量是假设。"},
                {"t": "note", "text": "challenge_info 审题笔记中的“2025 年 11 月平台上线”和“2026 年 11 月 18 日省政府办公厅文件”没有收进 challenge_raw。这两条标为待核实，不作为本计划书的论据。方案目标里的利用率 +15% 至 +22%、能耗降低 12% 至 18% 等，是 solution.md 的设计区间，不是已验证的全省幅度。"},
            ],
        },
        {
            "title": "代码里接通的五段，不是概念词堆叠",
            "blocks": [
                {"t": "p", "text": "solution.md 初稿写过 Transformer / PatchTST。仓库里实际训练并用于五分钟评测的预报器是季节残差时间卷积（backend/models.py 的 Forecaster），不是 PatchTST，也不是 LightGBM。权重说明里的 “seasonal residual TCN” 与此一致。"},
                {"t": "stack", "items": [
                    ("拓扑", "16 个节点、6 类芯片池、5 类任务。推理受 1/5/10 ms 设计时延圈约束，江苏城市之间默认 5 ms，跨到沪浙皖为 10 ms。"),
                    ("预报", f"共享卷积，三层 Conv1d。输入 [16,4,24]，输出未来 24 小时的到达和绿电比例。参数 {data['manifest']['forecast']['parameters']} 个。"),
                    ("宏观 MILP", "每小时用 scipy.optimize.milp 做 24 期滚动配额。目标含电费、碳、网络、利用率和拒单，国产有效份额有 30% 下限。先取 LP 对偶，再解整数规划。"),
                    ("微观 Safe-RL", f"PPO 对候选节点打分，拉格朗日约束把采样违约率压向 0.5%。部署取可行域内的最大分。参数 {data['manifest']['policy']['parameters']} 个，另导出 ONNX opset 17。"),
                    ("解释与账本", "默认定模板，读亲和度、影子价格、PUE、绿电和动作概率。可选的大模型只改写叙述。每条任务有 SHA-256 凭证。"),
                ]},
                {"t": "note", "text": "小时级 Gym（js_computesim）只比较 random 和 least-loaded greedy。它的 planning_snapshot() 把生成器剩余到达原样交给外部读取方，这条路径不是五分钟引擎里的卷积预报。两套结果不能拼进同一张百分比表。"},
            ],
        },
        {
            "title": "预报很粗，安全约束写在训练目标里",
            "blocks": [
                {"t": "p", "text": "预报训练集种子 41–43，验证种子 72，评测种子 313。训练从独立的 120 小时轨迹取窗，预报只能看到切点之前 48 小时。MAPE 去掉真实值为 0 的点。下表是 weights/forecast_metrics.json 的验证集，本次 verify_weights.py 只检查权重能否前向，没有重训。"},
                {"t": "table", "headers": ["验证变量", "MAE", "MAPE", "非零样本"], "rows": [
                    ["到达（作业/小时）", f"{fc['arrivals_jobs_per_hour']['mae']:.3f}",
                     f"{fc['arrivals_jobs_per_hour']['mape_pct']:.2f}%",
                     f"{fc['arrivals_jobs_per_hour']['nonzero_targets']:,}"],
                    ["绿电占峰值功率", f"{fc['renewable_peak_fraction']['mae']:.4f}",
                     f"{fc['renewable_peak_fraction']['mape_pct']:.2f}%",
                     f"{fc['renewable_peak_fraction']['nonzero_targets']:,}"],
                ], "caption": "训练 18 个 epoch。到达 MAPE 约 44%，逐小时作业数仍然粗糙。绿电比例的 MAPE 约 12.5%。"},
                {"t": "p", "text": "PPO 日志 weights/ppo_training.csv 有 160 次更新。违约率目标是 0.5%，图中的红色虚线就是这根线。训练初期有探索性时延违约，末段乘子多次回到 0。这是训练曲线，不是四场景周 SLA。周 SLA 以评测报告为准。"},
                {"t": "p", "text": "功耗在两套模型里不是同一个系数。五分钟引擎取峰值 10,000 kW/EF，空闲系数 0.32，保活 15 分钟，碳核算乘演示值 0.55 kgCO₂/kWh。小时环境取 1,000 kW/EFlops，并使用分省年平均因子。绝对电量、电费和吨碳都随系数线性放大。同一系数下比策略才有意义，不能换成全省能源平衡。"},
                {"t": "note", "text": "因此后文所有“降低百分之几”都是合成负载上的相对差。外推到江苏省电费时单独列表，并写成预估。"},
            ],
        },
        {
            "title": "沙盘、归因和碳足迹凭证",
            "blocks": [
                {"t": "p", "text": "数字孪生沙盘读取 frontend_demo_data 的静态回放，页面在 shared-workbench/frontend/sucompute.html。地图是 13 个设区市加上海、浙江、芜湖。它回放仿真，不是省平台的实时监视画面。"},
                {"t": "p", "text": "本地边车是无状态的 FastAPI：python -m uvicorn server:app。指令解析是确定性文法。仓库预设四句：迎峰度夏把碳排权重调到 0.6、注入南京 30% 算力故障、优先绿电消纳、解释调度。带百分数的“宕机”按容量损失解析，不带百分数才是整节点离线。调权重或注入故障后按同一输入重算。"},
                {"t": "p", "text": "账本来自 PR #19。每条任务记录有效 EF·h、分摊电费、碳排、相对“同等电量全购电网”的减排、SLA，以及去掉展示字段后的 SHA-256。绿电只抵扣碳排，不抵扣电费。电价用 world.py 的 weather() 演示曲线，碳因子用 GRID=0.55。代码注释写明不要把 0.55 说成公告里的 0.5617。"},
                {"t": "note", "text": "同时设置环境变量 LLM_BASE_URL 和 LLM_API_KEY 时，才把单任务叙述交给兼容 OpenAI Chat Completions 的接口改写；超时、失败或回复丢失原凭证哈希，就退回模板。本次复现没有设置这两项，实际路径是模板。没有调用外部大模型。"},
            ],
        },
        {
            "title": "同一合成周上的四种策略",
            "blocks": [
                {"t": "p", "text": "下表是本次 python benchmarks/run_benchmark.py --seed 313 --workers 2 写出的四场景等权均值，保留报告原文的四舍五入。对照还包括消融，完整六行在佐证材料里。有效在线利用率的分母含 15 分钟保活。"},
                {"t": "table", "headers": ["策略", "利用率", "SLA", "kWh/EF·h", "PUE", "绿电", "kgCO₂/EF·h"],
                 "rows": main_view,
                 "numeric": list(range(1, 7)),
                 "caption": "RR-Local 是轮询并保留就近溢出；Least-Loaded 选负载最低池；Cost-First 选最低电价。三者与 SuCompute 接受同一批任务和故障。"},
                {"t": "fig", "src": "kpi_zh.png", "cap": "由本次 results_summary.json 绘制。横轴依次为 RR-Local、Least-Loaded、Cost-First、SuCompute。脚本原图见佐证材料。", "cls": "chart"},
                {"t": "note", "text": f"相对 RR-Local，报告印出的利用率差是 {delta_rows[0][1]}，SLA 差 {delta_rows[0][2]} 个百分点，单位能耗 {delta_rows[0][3]}，碳强度 {delta_rows[0][6]}。这些是合成周结果。脚本把它们和方案目标的下限作了比较，并印出“达到”；那只说明仿真内越过了脚本里的下限，不是江苏省已验收的运行指标。"},
            ],
        },
        {
            "title": "竞品对照停在公开材料",
            "blocks": [
                {"t": "p", "text": "下表归纳 research.md 对公开产品定位的整理。本队没有做联合评测，没有这些产品的采购记录或客户名单，也不引用市占率。"},
                {"t": "table", "headers": ["产品", "公开定位", "和本赛题并排时看不到的部分"], "rows": [
                    ["Run:ai", "GPU 切分与集群配额", "省级多品牌芯片当量、绿电和跨省碳凭证"],
                    ["Cast AI", "多云成本与竞价实例", "国产智算卡、城域时延圈、PUE 与绿电移峰"],
                    ["阿里云灵骏", "自有云万卡与故障恢复", "厂商中立的省级跨运营主体调度"],
                    ["华为云昇腾", "昇腾栈、Volcano、液冷", "全省多厂商混部的同一套配额"],
                    ["无问芯穹", "多品牌芯片上的模型服务", "分时电价、苏北绿电和跨主体结算"],
                    ["国家超算互联网", "全国算力门户与供需对接", "细到任务槽的多目标调度引擎"],
                ]},
                {"t": "p", "text": "苏算绿枢放在这一列里，只表示它的代码边界：不绑定单一芯片厂商，策略以边车形式输出，仿真里同时看时延、电价、碳和故障。它还没有接到省平台，因此不是上述产品的替代部署。"},
                {"t": "note", "text": "research.md 还列出 HAMi、Volcano、Koordinator、Kueue 作为将来集群侧执行器的候选。本仓库没有集成它们。写进部署方案时只作为后续选项，不作为已接入组件。"},
            ],
        },
        {
            "title": "经济效益是假设情景，社会效益只报仿真内的差",
            "blocks": [
                {"t": "p", "text": "仓库没有江苏省数据中心用电统计，也没有可调度电量占比。电费不能从仿真周的绝对 kWh 直接除出来：五分钟引擎的 10,000 kW/EF 会把电量线性放大。下面只做一件事：把本次相对 RR-Local 的单位能耗降幅，乘到三档假设年用电上。"},
                {"t": "p", "text": "公式：预估年电费变化 = E × 0.6263 元/kWh × 21.23%。21.23% 是本次报告相对 RR-Local 印出的单位能耗降幅。0.6263 是小时环境引用的 2025 年 8 月 110 kV 两部制平段电价，不是五分钟引擎的演示电价，也不是企业到户账单。三档 E 都是假设，不是统计公报。"},
                {"t": "table", "headers": ["情景", "假设年用电 E", "预估年电费变化（万元）"],
                 "rows": money_rows, "numeric": [2],
                 "caption": money_note + " 未使用碳价，也没有把碳强度降幅再乘一次电费。"},
                {"t": "p", "text": f"社会侧只复述仿真内已经分开计量的两项。四场景等权 SLA：SuCompute {main_view[3][2]}，RR-Local {main_view[0][2]}。绿电占设施用电：{main_view[3][5]} 对 {main_view[0][5]}。后者是沙盘里就地消纳的份额，不是全省可再生能源利用率，也不能换成弃风弃光的实物电量。就业人数、签约客户和财政贡献，仓库里没有，这里不估。"},
                {"t": "note", "text": "上表全部是预估。若试点测到真实可调度电量和到户电价，应替换 E 和 0.6263，而不是沿用这三档。"},
            ],
        },
        {
            "title": "商业设想与还没有发生的对接",
            "blocks": [
                {"t": "p", "text": "没有签约客户，也没有报价。若命题方组织试点，费用按部署联调、接口适配和年度运维分列，价格另行核定。本计划书不写单价，避免把设想写成合同。"},
                {"t": "h3", "text": "三阶段都还是计划"},
                {"t": "ul", "items": [
                    "阶段 0，仓库内已有：合成仿真、权重、静态回放、本机无状态 API。评测可以断网重跑。",
                    "阶段 1，计划：只读影子。边车订阅平台已经采集的负载、电价和健康度，只写建议，不发调度指令。",
                    "阶段 2，计划：建议单由值班员确认后，才进入现有工单或集群队列。",
                    "阶段 3，计划：在书面 SLA 约束内闭环。进入这一阶段之前，需要生产日志上的对照，而不是再引用本仿真。",
                ]},
                {"t": "p", "text": "阶段 1 依赖省平台或地市子门户提供只读指标。仓库没有这份接口说明书，字段映射写在佐证材料的部署章，未对接的部分标为待联调。"},
                {"t": "note", "text": "商业上可复用的是策略计算和凭证，不是把 271.8 EFlops 重新包一层售卖。算力商品、绿证交易和跨省结算规则都不在本仓库的实现范围内。"},
            ],
        },
        {
            "title": "分工、路线和会失真的地方",
            "blocks": [
                {"t": "p", "text": "仓库没有编制和职务表。下面按已合并的工作包划分，不表示对外头衔。"},
                {"t": "table", "headers": ["工作包", "仓库中的位置", "状态"], "rows": [
                    ["小时级 Gym 与数据口径", "js_computesim/、docs/DATA_CONSTRUCTION.md", "可复跑 random / greedy"],
                    ["五分钟引擎、卷积、MILP、PPO", "backend/、weights/、benchmarks/", "权重已校验，周评测已复跑"],
                    ["Copilot 与碳足迹账本", "backend/copilot.py，PR #19", "默认模板；外部模型本次未调用"],
                    ["1+13 回放沙盘", "frontend_demo_data/、sucompute.html", "静态回放，不是省平台实况"],
                    ["计划书与佐证", "deliverables/，YOU-284", "本文件"],
                ]},
                {"t": "p", "text": "赛程以仓库 README 为准：初赛材料在 2026-11-30 截止，12 月 1–3 日线上评审，12 月中旬路演。技术路线不把这些日期写成系统上线日。阶段 1 以后的试点没有开始日期，因为还没有联调环境。"},
                {"t": "ul", "items": [
                    "合成轨迹不是江苏生产日志。到达验证 MAPE 约 44%，移峰质量受此限制。",
                    "两套功率系数不能相加，绝对电量和电费不能外推全省。",
                    f"墙钟随机器变化。本次滚动规划最长 {solve} 秒，SuCompute 故障编排最长 {fail} 秒。仓库冻结报告中的 {FROZEN_SOLVE} 秒和 {FROZEN_FAIL} 秒是另一台机器的记录，本次没有复现这两个原数。",
                    "本次逐小时 CSV 的 SHA-256 与冻结包不同，差异在苏算绿枢小时电量的数值噪声，周报表的四舍五入仍一致。详见佐证。",
                    "未接入省平台，没有试点合同。Copilot 的外接大模型本次没有运行。",
                ]},
            ],
        },
        {
            "title": "材料索引",
            "blocks": [
                {"t": "p", "text": "阅读顺序按“命题原文 → 口径 → 代码 → 本次复现”排列。政府网页的可访问性本次未复核。"},
                {"t": "ol", "items": [
                    "challenge_raw.json：313 座、271.8 EFlops、1+13 与长三角互联的命题原文。",
                    "docs/DATA_CONSTRUCTION.md、configs/energy.yaml：GDP、电价、碳因子、风光装机和全部假设旋钮。",
                    "MODEL.md、API_CONTRACT.md：五分钟引擎的指标分母、预报、账本和边车接口。",
                    "weights/manifest.json、weights/forecast_metrics.json、本次 verify_weights.txt。",
                    "deliverables/repro/results_report.md 与 results_summary.json：本次 seed 313 复现。",
                    "deliverables/repro/baseline_seed313.md：小时环境的 random 与 greedy，单独成表。",
                    "research.md：竞品与开源栈的公开材料归纳。",
                    "佐证材料 PDF：评测全文、权重和边车部署步骤。",
                ]},
                {"t": "note", "text": "答辩 PPT 和演示视频不在本文件范围内。百度网盘链接尚未填写。"},
            ],
        },
    ]


def pages_evidence(data: dict) -> list[dict]:
    summary = data["summary"]
    report_rows = parse_md_table(data["report"], "| 策略 |")
    delta_rows = parse_md_table(data["report"], "| 对照 |")
    goal_rows = parse_md_table(data["report"], "| 相对 RR-Local")
    mech_rows = parse_md_table(data["report"], "| 场景 | 策略 |")
    solve = fail = ""
    sha = summary["detail_sha256"]
    for line in data["report"].splitlines():
        if line.startswith("全体滚动规划最长"):
            solve = line.split("全体滚动规划最长", 1)[1].split("秒", 1)[0].strip()
            fail = line.split("SuCompute 故障编排最长", 1)[1].split("秒", 1)[0].strip()
    runs = {(r["scenario"], r["strategy"]): r for r in summary["runs"]}
    scene_rows = []
    for scene, label in (
        ("normal_weekday", "常规工作日"),
        ("high_renewable", "绿电大发"),
        ("peak_shaving", "尖峰保电"),
        ("fault_stress", "故障压测"),
    ):
        row = runs[(scene, "SuCompute")]
        scene_rows.append([
            label, f"{row['sla']:.2%}", f"{row['peak_sla']:.2%}",
            f"{row['utilization']:.2%}", str(row["batch_jobs_shifted_2h"]),
            str(row["pending_repacked"]),
            "—" if row["solve_max_s"] is None else f"{row['solve_max_s']:.4f}",
        ])
    fault = runs[("fault_stress", "SuCompute")]
    base_rows = []
    # Parse gym markdown table body.
    for line in data["baseline"].splitlines():
        if not line.startswith("|") or "scenario" in line or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        base_rows.append([cells[0], cells[1], cells[2], cells[3], cells[4], cells[7], cells[8]])
    rec = receipt_bits(data["receipt"])
    files = data["manifest"]["files"]
    file_rows = [[f["path"], f"{f['size']:,}", f["sha256"][:16] + "…", f["description"]] for f in files]
    fc = data["forecast"]
    return [
        {
            "cover": True,
            "doc": "佐证材料",
            "sub": "仿真评测 · 权重说明 · 边车部署方案",
            "metrics": [
                ("seed 313", "四场景 × 168 小时"),
                (f"{solve} 秒", "本次滚动规划最长"),
                (f"{fail} 秒", "本次故障编排最长"),
            ],
            "foot": "2026 年 11 月 · 复现主机 4 vCPU · Python "
                    + summary["runtime"]["python"] + " · torch " + summary["runtime"]["torch"],
        },
        {
            "title": "两次命令，两套不能混用的模型",
            "blocks": [
                {"t": "p", "text": "评测在 02-sansu-computing-dispatch 目录执行。依赖见 requirements.txt。本次使用仓库内已训练权重，没有重训。"},
                {"t": "ul", "items": [
                    "python weights/verify_weights.py",
                    "python scripts/run_baselines.py --seed 313",
                    "python benchmarks/run_benchmark.py --seed 313 --workers 2 --out <目录>",
                ]},
                {"t": "p", "text": "第一条检查五份权重的 SHA-256、ONNX 与 PyTorch  logits，并做一次卷积前向。第二条只跑小时级 Gym 的 random 和 least-loaded greedy。第三条才产生 RR-Local、Least-Loaded、Cost-First、SuCompute、MILP-only、Safe-RL-only。"},
                {"t": "table", "headers": ["沙盘", "步长", "功率系数", "碳因子", "策略"], "rows": [
                    ["js_computesim", "1 小时", "1,000 kW/EFlops", "分省年平均", "random、greedy"],
                    ["backend 五分钟引擎", "5 分钟", "10,000 kW/EF", "演示值 0.55", "六策略，含三条基线"],
                ]},
                {"t": "p", "text": f"本次 verify 输出：{data['verify']}。运行环境见 results_summary.json：Python {summary['runtime']['python']}，{summary['runtime']['cpu']}，scipy {summary['runtime']['scipy']}，torch {summary['runtime']['torch']}。"},
                {"t": "note", "text": f"逐小时 CSV 的 SHA-256 本次为 {sha}。仓库冻结 benchmarks/results_detail.csv 为 {FROZEN_SHA}。周报表四舍五入一致，但哈希不同，原因见后文，不以冻结哈希冒充本次复现。"},
            ],
        },
        {
            "title": "六策略周指标",
            "blocks": [
                {"t": "p", "text": "四个场景等权。有效在线利用率 = 按 η 折算的有效工作量 / 含保活的已通电容量时。SLA 分母是到达任务数，拒单计入违约。国产有效份额的约束下限是 30%，表中是实际份额。"},
                {"t": "table", "headers": ["策略", "利用率", "SLA", "kWh/EF·h", "PUE", "绿电", "碳强度", "高峰 SLA", "国产份额"],
                 "rows": report_rows, "numeric": list(range(1, 9)),
                 "caption": "高峰时段为每日 09–11 与 17–19 时到达的任务。碳强度单位是 kgCO₂/EF·h。"},
                {"t": "fig", "src": "kpi_zh.png", "cap": "四条策略的中文图，数值来自本次 results_summary.json。横轴依次为 RR-Local、Least-Loaded、Cost-First、SuCompute。消融留在上表。", "cls": "chart"},
            ],
        },
        {
            "title": "脚本直接保存的对比图",
            "blocks": [
                {"t": "p", "text": "下图是 benchmarks/run_benchmark.py 写出的 comparison.png，没有在画布上改数。英文标题是脚本原文。六组柱从左到右为 RR-Local、Least-Loaded、Cost-First、SuCompute、MILP-only、Safe-RL-only。横轴四个场景为常规工作日、绿电大发、尖峰保电、故障压测。"},
                {"t": "fig", "src": "comparison.png", "cap": "同一脚本还写出 training.png，见权重一节。周指标的中文读数在上一页和下一页。"},
            ],
        },
        {
            "title": "相对差和脚本里的下限",
            "blocks": [
                {"t": "table", "headers": ["对照", "利用率", "SLA 百分点", "能耗", "PUE", "绿电", "碳强度"],
                 "rows": delta_rows, "numeric": list(range(1, 7)),
                 "caption": "利用率、能耗、绿电、碳强度是相对变化。SLA 是百分点差。PUE 是绝对差。能耗列的正号表示苏算绿枢更低。"},
                {"t": "table", "headers": ["脚本中的下限", "本次印出值", "脚本结论"],
                 "rows": goal_rows, "numeric": [1],
                 "caption": "“达到”是脚本相对 RR-Local 的下限判断，作用域是这次合成周。最后一行的秒数是本机墙钟，不是冻结报告里的 0.0891 / 0.0803。"},
            ],
        },
        {
            "title": "移峰、重排和本机墙钟",
            "blocks": [
                {"t": "p", "text": "MILP-only 保留同一套滚动计划和重排，用配额贪心代替 PPO。Safe-RL-only 加载同一个 PPO，但没有预报、移峰和逐小时重排。批任务“推迟至少 2 小时”只统计预训练和微调里首次开工推迟不少于 24 个五分钟槽的作业。"},
                {"t": "table", "headers": ["场景", "策略", "推迟≥2h", "重排次数", "高峰 SLA", "全装机有效利用率"],
                 "rows": [[r[0], r[1], r[2], r[3], r[4], r[5]] for r in mech_rows],
                 "numeric": [2, 3, 4, 5],
                 "caption": "Safe-RL-only 的推迟和重排为 0，因为它不移动批任务的开工时刻。全装机口径的分母含未通电容量，所以远低于“有效在线利用率”。"},
                {"t": "p", "text": f"本次全体滚动规划最长 {solve} 秒，出现在故障场景的 MILP-only。SuCompute 在故障场景的编排最长 {fail} 秒，solve_max_s 为 {fault['solve_max_s']:.4f} 秒，measured_solves = {fault['measured_solves']}。故障轨迹的 elapsed_s 含计划重算和内存中的切流，不含生产环境的检查点字节复制。"},
                {"t": "note", "text": f"仓库冻结 results_report.md 写的是规划 {FROZEN_SOLVE} 秒、故障编排 {FROZEN_FAIL} 秒。那是生成冻结包的机器的墙钟。本机是 4 vCPU 的 Intel Xeon 虚拟机，两个数都变了，两个都仍小于脚本里的 3 秒和 1 秒门槛。引用时间以本页为准。"},
            ],
        },
        {
            "title": "小时级 Gym 是另一张表",
            "blocks": [
                {"t": "p", "text": "scripts/run_baselines.py 不产生 RR-Local、Cost-First 或 SuCompute。random 与 greedy 都不看电价和绿电，所以绿电大发日的放置与常规工作日相同，只有碳和绿电份额变化。绝对 MWh、吨和万元使用 1,000 kW/EFlops，脚本原文写明这不是全省能源平衡。"},
                {"t": "table", "headers": ["场景", "策略", "完成比", "SLA 违约", "平均利用率", "加权 PUE", "绿电份额"],
                 "rows": base_rows, "numeric": list(range(2, 7)),
                 "caption": "完成比是 served_ratio。SLA 违约是 sla_violation_ratio，方向与五分钟引擎的“SLA 达标率”相反。"},
                {"t": "p", "text": "常规工作日 greedy 的完成比是 0.9404，违约 0.0596；random 的完成比是 0.8109，违约 0.1891。尖峰保电日 greedy 违约升到 0.1957。这些数只说明该 Gym 在种子 313 下的放置，不能拿来和支持卷积预报的五分钟 SLA 99.83% 相减。"},
                {"t": "note", "text": "小时环境的预测接口当前等于生成器真值。把它换成真实预报器时，替换 planning_snapshot() 的到达数组即可。这次基线复现没有做这件替换。"},
            ],
        },
        {
            "title": "权重包是时间卷积和小型 PPO",
            "blocks": [
                {"t": "p", "text": "manifest.json 的 version 为 2。预报器是季节残差 TCN：Conv1d(4→24, k=5) 、Conv1d(24→16, k=3, dilation=2)、Conv1d(16→2, k=1)，残差接在滞后 24 小时与 48 小时的平均上，输出经 clamp 不低于 0。策略网是两层 Tanh 的候选打分器和价值头，输入 15 维特征，部署前还要加上 dispatch_bias 和可行性掩码。"},
                {"t": "table", "headers": ["文件", "字节", "SHA-256 前 16 位", "说明"], "rows": file_rows},
                {"t": "p", "text": f"五份文件合计 {data['verify'].split('Verified 5 hashes, ')[1].split(' bytes')[0]} 字节，低于仓库设定的 15 MB 上限。本次校验：{data['verify']}。ONNX 只导出策略 logits，预报仍用 PyTorch。"},
                {"t": "p", "text": "特征顺序与代码 FEATURES 一致：eta、tariff、green_fraction、pue_excess、pool_fill、marginal_powered_efh_per_efh、latency_ratio、cross、domestic、quota、sla_risk、wait_fraction_of_6h、energy_per_work、available、urgent。"},
                {"t": "note", "text": "不要把这套权重描述成 PatchTST 或 LightGBM。research.md 和 solution.md 里出现过这两个名字，是选型笔记，不是已发布权重。重新训练的入口是 benchmarks/train_forecast.py 与 train_policy.py，训练后再跑 verify_weights.py --release。本次没有执行训练。"},
            ],
        },
        {
            "title": "预报误差和 PPO 曲线",
            "blocks": [
                {"t": "table", "headers": ["划分", "变量", "MAE", "MAPE", "非零样本"], "rows": [
                    ["训练", "到达（作业/小时）",
                     f"{fc['train']['arrivals_jobs_per_hour']['mae']:.3f}",
                     f"{fc['train']['arrivals_jobs_per_hour']['mape_pct']:.2f}%",
                     f"{fc['train']['arrivals_jobs_per_hour']['nonzero_targets']:,}"],
                    ["训练", "绿电比例",
                     f"{fc['train']['renewable_peak_fraction']['mae']:.4f}",
                     f"{fc['train']['renewable_peak_fraction']['mape_pct']:.2f}%",
                     f"{fc['train']['renewable_peak_fraction']['nonzero_targets']:,}"],
                    ["验证", "到达（作业/小时）",
                     f"{fc['validation']['arrivals_jobs_per_hour']['mae']:.3f}",
                     f"{fc['validation']['arrivals_jobs_per_hour']['mape_pct']:.2f}%",
                     f"{fc['validation']['arrivals_jobs_per_hour']['nonzero_targets']:,}"],
                    ["验证", "绿电比例",
                     f"{fc['validation']['renewable_peak_fraction']['mae']:.4f}",
                     f"{fc['validation']['renewable_peak_fraction']['mape_pct']:.2f}%",
                     f"{fc['validation']['renewable_peak_fraction']['nonzero_targets']:,}"],
                ], "caption": "验证种子 72。评测周使用种子 313，不在这张误差表里。"},
                {"t": "fig", "src": "training.png", "cap": "run_benchmark.py 按 weights/ppo_training.csv 绘制。绿线是 10 次更新的滑动平均，红虚线是违约率 0.5%。", "cls": "short"},
                {"t": "note", "text": "验证集到达 MAPE 43.96% 说明卷积只抓住了日周期的一部分。周评测里的移峰仍然使用这份预报，因此利用率优势不能解释成“预报已经准确”。"},
            ],
        },
        {
            "title": "边车怎么接到省平台：现在能做的和还不能做的",
            "blocks": [
                {"t": "p", "text": "部署形态是策略边车，不是替换省级调度核心。计算放在只读副本旁边：读指标、出建议、写凭证。执行仍走平台现有队列。本仓库的 server.py 是这个边车的本地、无状态版本，注释写明 Optional stateless sidecar。"},
                {"t": "h3", "text": "本机已经能启动的部分"},
                {"t": "ul", "items": [
                    "用 CPU 加载 policy.onnx 与 forecast.pt。本次校验在 CPUExecutionProvider 上完成，logit 最大误差 3.81e-06。",
                    "POST /api/v1/simulate 在独立内存日历上从种子重放，默认种子 313，小时数 1–168。",
                    "POST /api/v1/fault/inject 注入离线、容量损失或 PUE 抬升。",
                    "POST /api/v1/copilot/command 解析中文指令并重算。",
                    "POST /api/v1/ledger 与 /api/v1/ledger/csv 导出凭证。",
                ]},
                {"t": "h3", "text": "三阶段的进入条件（计划，尚未开始）"},
                {"t": "ul", "items": [
                    "影子：平台提供至少 14 天只读时序，边车每天出一份与现行策略并列的建议。不对生产队列写指令。",
                    "人工确认：建议单包含任务标识、目的节点、预计时延圈、演示电价下的电费和凭证哈希。值班员否决时保留否决原因。",
                    "闭环：先在书面变更里限定任务类型和回退开关。生产检查点复制的耗时要单独计量，不能沿用仿真 elapsed_s。",
                ]},
                {"t": "note", "text": "仓库没有省平台或 13 个地市子门户的接口文档。上表的进入条件是对接方案，不是已完成的联调记录。"},
            ],
        },
        {
            "title": "建议映射、一张真实凭证和上线前要改的默认值",
            "blocks": [
                {"t": "p", "text": "下表是边车希望读取的量。右列只说明仓库里用什么字段模拟它。省平台的真实字段名待联调时替换，不能把仿真字段名当成接口规范。"},
                {"t": "table", "headers": ["边车要读的量", "仿真里对应的来源", "对接状态"], "rows": [
                    ["任务类型、到达、时延上限、截止期", "Trace 的五类任务", "待联调"],
                    ["节点健康、PUE、队列", "world.health 与功率模型", "待联调"],
                    ["分时电价", "weather() 演示曲线；公告价只在小时环境", "待核实到户电价"],
                    ["绿电可用功率", "场景参数，不是机房电表", "待联调"],
                    ["跨域带宽与时延", "设计矩阵 1/5/10 ms，带宽为假设", "待核实"],
                    ["回写调度指令", "无。API 不发生产指令", "阶段 1 保持不回写"],
                ]},
                {"t": "p", "text": f"本次账本样例取自这次 run_benchmark 写出的 ledger_sample.json，不是冻结前端包。常规工作日、SuCompute、任务 1：{rec['klass']}，来源{rec['src']}，槽 {rec['slots']}，节点{rec['city']} / {rec['pool']}，动作概率 {rec['prob']}，绿电份额 {rec['green']}，PUE {rec['pue']}。有效 {rec['efh']} EF·h，分摊电量 {rec['kwh']} kWh，演示电价下 {rec['cny']} 元，碳排 {rec['co2']} kg，相对全购电少 {rec['avoid']} kg，SLA {rec['sla']}。SHA-256 {rec['sha']}。"},
                {"t": "note", "text": "这张凭证的电量和电费随 10,000 kW/EF 放大，不能当成账单或碳资产。server.py 当前把 CORS 设为允许任意来源，只适合本机演示；接到平台前必须改成指定源，并把 LLM 密钥留在环境变量里，不写入仓库。"},
            ],
        },
        {
            "title": "验收时对照什么",
            "blocks": [
                {"t": "ul", "items": [
                    "权重：verify_weights.py 通过，五份 SHA-256 与 manifest.json 一致。",
                    "周指标：复跑 run_benchmark.py 后，四场景等权表与当时的 results_report.md 一致；墙钟允许变化，并写明主机。",
                    "哈希：逐小时 CSV 的 SHA-256 与当次 summary 的 detail_sha256 一致。不要要求它等于冻结包的 " + FROZEN_SHA + "，除非在同一数值路径上复现到逐小时电量。",
                    "账本：抽一条凭证，用 backend.report.receipt_hash 重算。展示字段 selection_reason 不进入哈希。",
                    "影子试点：连续只读运行，建议单可导出 CSV，生产队列无写入。这项尚未开始。",
                ]},
                {"t": "p", "text": "本次复现已经完成前三项里的权重校验和周评测。逐小时哈希等于本次 summary，不等于冻结包。第四项的哈希算法在代码和 API_CONTRACT 里，计划书引用的那条样例来自本次账本文件。第五项没有环境，不能勾。"},
                {"t": "note", "text": "PPT、录屏和网盘链接不在这份佐证里。优化幅度若没有出现在本次 results_report.md，就不能写成已验证。"},
            ],
        },
    ]


def render_blocks(blocks: list[dict]) -> str:
    parts = []
    for block in blocks:
        kind = block["t"]
        if kind == "p":
            parts.append(f"<p>{esc(block['text'])}</p>")
        elif kind == "h3":
            parts.append(f"<h3>{esc(block['text'])}</h3>")
        elif kind == "ul":
            items = "".join(f"<li>{esc(item)}</li>" for item in block["items"])
            parts.append(f"<ul>{items}</ul>")
        elif kind == "ol":
            items = "".join(f"<li>{esc(item)}</li>" for item in block["items"])
            parts.append(f"<ol>{items}</ol>")
        elif kind == "note":
            parts.append(f"<div class=\"note\">{esc(block['text'])}</div>")
        elif kind == "stack":
            rows = "".join(
                f"<div><b>{esc(name)}</b><span>{esc(text)}</span></div>"
                for name, text in block["items"]
            )
            parts.append(f"<div class=\"stack\">{rows}</div>")
        elif kind == "table":
            nums = set(block.get("numeric") or [])
            heads = "".join(
                f"<th class=\"{'num' if i in nums else ''}\">{esc(cell)}</th>"
                for i, cell in enumerate(block["headers"])
            )
            body = []
            for row in block["rows"]:
                tds = "".join(
                    f"<td class=\"{'num' if i in nums else ''}\">{esc(cell)}</td>"
                    for i, cell in enumerate(row)
                )
                body.append(f"<tr>{tds}</tr>")
            cap = f"<p class=\"caption\">{esc(block['caption'])}</p>" if block.get("caption") else ""
            parts.append(f"<table><thead><tr>{heads}</tr></thead><tbody>{''.join(body)}</tbody></table>{cap}")
        elif kind == "fig":
            cls = "fig " + block.get("cls", "")
            parts.append(
                f"<img class=\"{cls.strip()}\" src=\"{esc(block['src'])}\" alt=\"{esc(block['cap'])}\"/>"
                f"<p class=\"caption\">{esc(block['cap'])}</p>"
            )
        else:
            raise KeyError(kind)
    return "".join(parts)


def render_html(pages: list[dict], title: str, running: str) -> str:
    total = f"{len(pages):02d}"
    sheets = []
    for index, page in enumerate(pages, start=1):
        if page.get("cover"):
            metrics = "".join(f"<div><b>{esc(value)}</b><span>{esc(label)}</span></div>"
                               for value, label in page["metrics"])
            sheets.append(f"""
            <section class="sheet cover">
              <div class="cover-bar"></div>
              <p class="kicker">2026 江苏“人工智能+”创新应用大赛<br/>“三苏”创新应用赛道 · AI-JIANGSU-Q36</p>
              <h1>苏算绿枢</h1>
              <p class="en">SuCompute-Opt</p>
              <h2>{esc(page['doc'])}</h2>
              <p class="sub">{esc(page['sub'])}</p>
              <div class="metrics">{metrics}</div>
              <div class="cover-foot">盼盼法式小面包<small>{esc(page['foot'])}</small></div>
            </section>""")
            continue
        body = render_blocks(page["blocks"])
        sheets.append(f"""
        <section class="sheet body">
          <div class="head"><span>苏算绿枢 · SuCompute-Opt</span><span>{esc(running)}</span></div>
          <h2>{esc(page['title'])}</h2>
          {body}
          <div class="foot"><span>盼盼法式小面包 · AI-JIANGSU-Q36</span><span>{index:02d} / {total}</span></div>
        </section>""")
    css = STYLE.read_text(encoding="utf-8")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>{esc(title)}</title>
<style>{css}</style>
</head>
<body>
{''.join(sheets)}
</body>
</html>
"""


def set_run_font(run, size, bold=False, color=None):
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = "Noto Sans CJK SC"
    if color:
        run.font.color.rgb = RGBColor(*color)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")


def add_text(paragraph, text, size=11, bold=False, color=None):
    run = paragraph.add_run(text)
    set_run_font(run, size, bold, color)
    return run


def render_docx(pages: list[dict], path: Path, running: str) -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(1.7)
    section.right_margin = Cm(1.7)
    section.top_margin = Cm(1.6)
    section.bottom_margin = Cm(1.6)
    normal = doc.styles["Normal"]
    normal.font.name = "Noto Sans CJK SC"
    normal.font.size = Pt(11)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    for page in pages:
        if page.get("cover"):
            add_text(doc.add_paragraph(), "2026 江苏“人工智能+”创新应用大赛", 12, color=(20, 48, 68))
            add_text(doc.add_paragraph(), "“三苏”创新应用赛道 · AI-JIANGSU-Q36", 12)
            title = doc.add_paragraph()
            add_text(title, "苏算绿枢  " + page["doc"], 22, bold=True, color=(15, 44, 61))
            add_text(doc.add_paragraph(), page["sub"], 12)
            for value, label in page["metrics"]:
                line = doc.add_paragraph()
                add_text(line, f"{value}  ", 14, bold=True)
                add_text(line, label, 11)
            add_text(doc.add_paragraph(), "盼盼法式小面包 · " + page["foot"], 11)
            doc.add_page_break()
            continue
        heading = doc.add_heading(page["title"], level=1)
        for run in heading.runs:
            set_run_font(run, 16, bold=True, color=(20, 48, 68))
        for block in page["blocks"]:
            kind = block["t"]
            if kind in ("p", "note", "h3"):
                para = doc.add_paragraph()
                if kind == "h3":
                    add_text(para, block["text"], 12, bold=True, color=(14, 110, 120))
                elif kind == "note":
                    add_text(para, "说明：" + block["text"], 10)
                else:
                    add_text(para, block["text"], 11)
            elif kind in ("ul", "ol"):
                for item in block["items"]:
                    para = doc.add_paragraph(style="List Bullet" if kind == "ul" else "List Number")
                    add_text(para, item, 11)
            elif kind == "stack":
                for name, text in block["items"]:
                    para = doc.add_paragraph()
                    add_text(para, name + "  ", 11, bold=True, color=(14, 110, 120))
                    add_text(para, text, 11)
            elif kind == "table":
                table = doc.add_table(rows=1, cols=len(block["headers"]))
                table.style = "Table Grid"
                for idx, cell in enumerate(block["headers"]):
                    table.rows[0].cells[idx].text = ""
                    add_text(table.rows[0].cells[idx].paragraphs[0], cell, 9, bold=True)
                for row in block["rows"]:
                    cells = table.add_row().cells
                    for idx, value in enumerate(row):
                        cells[idx].text = ""
                        add_text(cells[idx].paragraphs[0], value, 8)
                if block.get("caption"):
                    cap = doc.add_paragraph()
                    add_text(cap, block["caption"], 9, color=(90, 100, 110))
            elif kind == "fig":
                picture = BUILD / block["src"]
                if picture.exists():
                    doc.add_picture(str(picture), width=Cm(16.5))
                cap = doc.add_paragraph()
                add_text(cap, block["cap"], 9, color=(90, 100, 110))
        doc.add_page_break()
    doc.save(path)


def print_pdf(html_path: Path, pdf_path: Path) -> None:
    tmp = Path("/tmp/sucompute-print.pdf")
    tmp.unlink(missing_ok=True)
    cmd = [
        "google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox",
        "--disable-dev-shm-usage", "--no-pdf-header-footer",
        "--font-render-hinting=none", f"--print-to-pdf={tmp}", html_path.as_uri(),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 45
    while time.time() < deadline:
        if tmp.exists() and tmp.stat().st_size > 2000:
            time.sleep(0.8)
            proc.kill()
            proc.wait(timeout=10)
            shutil.move(tmp, pdf_path)
            return
        if proc.poll() is not None and tmp.exists():
            shutil.move(tmp, pdf_path)
            return
        time.sleep(0.3)
    proc.kill()
    raise RuntimeError(f"Chrome did not write {pdf_path.name}")


def main() -> None:
    copy_repro()
    data = load()
    zh_figure(data["summary"], REPRO / "kpi_zh.png")
    BUILD.mkdir(parents=True, exist_ok=True)
    for name in ("comparison.png", "training.png", "kpi_zh.png"):
        shutil.copy2(REPRO / name, BUILD / name)
    plan_pages = pages_plan(data)
    evidence_pages = pages_evidence(data)
    plan_html = render_html(plan_pages, "苏算绿枢 项目计划书", "项目计划书")
    evidence_html = render_html(evidence_pages, "苏算绿枢 佐证材料", "佐证材料")
    plan_file = BUILD / "plan.html"
    evidence_file = BUILD / "evidence.html"
    plan_file.write_text(plan_html, encoding="utf-8")
    evidence_file.write_text(evidence_html, encoding="utf-8")
    plan_pdf = DELIV / f"{PREFIX}-计划书.pdf"
    evidence_pdf = DELIV / f"{PREFIX}-佐证材料.pdf"
    plan_docx = DELIV / f"{PREFIX}-计划书.docx"
    evidence_docx = DELIV / f"{PREFIX}-佐证材料.docx"
    print_pdf(plan_file, plan_pdf)
    print_pdf(evidence_file, evidence_pdf)
    render_docx(plan_pages, plan_docx, "项目计划书")
    render_docx(evidence_pages, evidence_docx, "佐证材料")
    print(plan_pdf.name, plan_pdf.stat().st_size)
    print(evidence_pdf.name, evidence_pdf.stat().st_size)
    print("plan_pages", len(plan_pages), "evidence_pages", len(evidence_pages))


if __name__ == "__main__":
    main()
