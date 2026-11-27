"""Write the human report, evaluation tables and workbench import points."""

import csv
import json

from .charts import METRICS, VARIANTS, eligible, metric, render_charts
from .metrics import summarize

WORKBENCH_FIELDS = ("chart_id","kind","title","unit","category","series","value","maximum")
METRIC_NAMES = ("综合解析","符号 F1","规格语义","无向边 F1","BOM 明细（规格必对）","BOM 汇总（图纸可见）")
FORMATS = ("full","dxf","png","pdf","b1","b2","b3","no_topology","no_kg")


def pct(value):
    return "—" if value is None else f"{value:.2%}"


def sec(value):
    return "—" if value is None else f"{value:.3f}"


def _json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _csv(path, headers, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _outcomes(group):
    return {name: metric(group,name) for name in METRICS} | {
        "spec_raw_exact": group["spec_raw_exact"], "spec_emitted_exact": group["spec_emitted_exact"],
        "directed_edge": group["directed_edge"]["f1"], "tag_exact": group["tag_exact"],
        "bom_model_summary": group["bom_model_summary"]["recall"],
        "pipeline_core_defect_recall": group["pipeline_core_defect_recall"],
        "bom_detail_precision": group["bom_detail"]["precision"],
        "bom_summary_precision": group["bom_summary"]["precision"],
        "compliance_precision": group["compliance"]["precision"] if group["compliance"] else None,
        "compliance_recall": group["compliance"]["recall"] if group["compliance"] else None,
    }


def drawing_table(result):
    rows = []
    keys = ("symbol_tp","symbol_fp","symbol_fn","spec_expected","spec_raw_correct","spec_semantic_correct",
            "edge_tp","edge_fp","edge_fn","directed_edge_tp","directed_edge_fp","directed_edge_fn",
            "bom_detail_tp","bom_detail_fp","bom_detail_fn","bom_summary_tp","bom_summary_fp","bom_summary_fn",
            "bom_model_summary_tp","bom_model_summary_fp","bom_model_summary_fn","core_defects_expected",
            "compliance_tp","compliance_fp","compliance_fn","standard_red","extra_red")
    for row in result["per_drawing"]:
        group = summarize([row])
        outcomes = {key: row["counts"].get(key, 0) if (row["compliance_run"] or
                    not (key.startswith("compliance_") or key in {"standard_red","extra_red"}))
                    else None for key in keys}
        rows.append({key: row[key] for key in ("lane","drawing_id","subset","degradation","format","channel")} |
                    {"raster_enhanced": (row.get("raster_preprocessing") or {}).get("applied")} |
                    _outcomes(group) |
                    (row["timing"] or dict.fromkeys(("parse_s","topology_s","compliance_s","total_s"))) | outcomes)
    return rows


def ablations(result):
    contrasts = []
    configs = [(variant, "full_main", result["lanes"]["full"]["main"], result["lanes"][variant]["main"])
               for variant in VARIANTS]
    configs.append(("degraded_no_kg", "png_degraded", result["lanes"]["png"]["degraded"],
                    result["lanes"]["degraded_no_kg"]["degraded"]))
    alias = {lane: summarize([r for r in result["per_drawing"] if r["lane"] == lane
                              and r["degradation"] == "alias"]) for lane in ("png", "degraded_no_kg")}
    if all(alias.values()):
        configs.append(("alias_no_kg", "png_alias", alias["png"], alias["degraded_no_kg"]))
    for lane_id, comparison, base, current in configs:
        expected, observed = _outcomes(base), _outcomes(current)
        row = {"lane": lane_id, "comparison": comparison, "drawings": current["drawings"],
               "compliance_enabled": current["compliance"] is not None}
        row.update({f"delta_{k}": expected[k]-observed[k] if None not in (expected[k],observed[k]) else None
                    for k in expected})
        row["delta_mean_time_s"] = base["timing"]["total_s"]["mean"]-current["timing"]["total_s"]["mean"]
        contrasts.append(row)
    return contrasts


def workbench_points(result):
    rows = []
    for lane in ("b1","b2","b3","full"):
        if not eligible(result,lane):
            continue
        group = result["lanes"][lane]["main"]
        if any(metric(group,k) is None for k in METRICS):
            continue
        for field, label in zip(METRICS,METRIC_NAMES,strict=True):
            rows.append(dict(chart_id="track01-e2e-radar",kind="radar",title="主验收集基线对比",
                             unit="%",category=label,series=lane.upper(),
                             value=round(100*metric(group,field),4),maximum=100))
    measured = {name: result["lanes"][name]["main"]["timing"]["total_s"] for name in ("full","dxf","png","pdf")}
    ceiling = max(15., *(row["p95"] for row in measured.values()))
    for name, times in measured.items():
        for stat, label in (("mean","均值"),("p50","P50"),("p95","P95")):
            rows.append(dict(chart_id="track01-e2e-latency",kind="bar",title="主验收集通道耗时",
                             unit="s",category=name.upper(),series=label,value=round(times[stat],4),
                             maximum=round(ceiling,4)))
    return rows


def _line(entries):
    return "| " + " | ".join(str(entry) for entry in entries) + " |"


def _summary_rows(result):
    for lane_id in FORMATS:
        lane = result["lanes"][lane_id]
        group = lane["main"]
        if group is None:
            if lane_id == "b3":
                yield _line([lane["title"], 0, *(["—"]*9)])
            continue
        timing = group["timing"]
        yield _line([lane["title"],group["drawings"],pct(group["composite"]),pct(group["symbol"]["f1"]),
                     pct(group["spec_raw_exact"]),pct(group["spec_semantic"]),pct(group["edge"]["f1"]),
                     pct(group["directed_edge"]["f1"]),pct(group["bom_detail"]["recall"]),
                     pct(group["bom_summary"]["recall"]),
                     sec(timing["total_s"]["mean"] if timing else None)])


def markdown_report(result):
    full = result["lanes"]["full"]["main"]
    status = result["acceptance"]
    control = full["compliance"]

    def gate(flag):
        return "通过" if flag else "未达"

    md = [
        "# ElectroBench-JS v1.0.0 端到端离线评测", "",
        f"完整系统在 11 张主验收图上的综合解析为 **{pct(full['composite'])}**，"
        f"严格采购明细完整率为 **{pct(full['bom_detail']['recall'])}**，"
        f"图纸可见字段汇总完整率为 **{pct(full['bom_summary']['recall'])}**，"
        f"平均耗时为 **{sec(full['timing']['total_s']['mean'])} 秒/张**。", "",
        f"- 93% 综合门槛{gate(status['composite_pass'])}，95.5% 主集综合目标{gate(status['composite_target_pass'])}，"
        f"95% 严格明细门槛{gate(status['bom_detail_pass'])}，95% 可见字段汇总门槛{gate(status['bom_summary_pass'])}，"
        f"15 秒耗时目标{gate(status['latency_pass'])}。",
        f"- 明细 Precision {pct(full['bom_detail']['precision'])}，汇总 Precision {pct(full['bom_summary']['precision'])}。"
        f"含采购目录号的扩展诊断完整率为 {pct(full['bom_model_summary']['recall'])}。原图缺少的目录号需由 ERP 或选型目录补充。",
        f"- 四类合规红灯 Precision **{pct(control['precision'])}**，Recall **{pct(control['recall'])}**，"
        f"{control['tp']} TP、{control['fp']} FP、{control['fn']} FN。7 张标准图全部规则的红灯误报 "
        f"**{control['standard_red']}**。",
        f"- Full 14 张全集综合 **{pct(result['lanes']['full']['all']['composite'])}**，"
        f"93% 全集目标{gate(status['all_composite_pass'])}。", "",
        "## 主验收集与通道对比", "",
        "| 组别 | 图数 | 综合 | 符号 F1 | 规格原始精确 | 规格语义 | 无向边 F1 | 有向边 F1 | BOM 严格明细 | BOM 可见字段汇总 | 均值秒 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        *_summary_rows(result),"",
        "主验收集包含 4 张一次、3 张二次、4 张缺陷图。Full 在主集自动选 DXF，全集还含光栅退化输入。"
        "纯 PDF 先走 PDF 页的文字和原语解析，再从同一页的渲染图追踪导线。",
        "B1 仅从原始 PNG 做 OCR 和文本规格抽取。其文字框无法替代器件定位，明细仍逐条核对真值规格。", "",
        "## 分层与退化对照", "",
        "| 组别 | 图数 | 综合 | 符号 F1 | 规格语义 | 输出规格精确 | 拓扑 F1 | BOM 严格明细 | BOM 可见字段汇总 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for lane_id, group in (("full","primary"),("full","secondary"),("full","defect"),("full","degraded"),
                           ("full","all"),("png","main"),("png","degraded"),("degraded_no_kg","degraded")):
        s = result["lanes"][lane_id][group]
        md.append(_line([lane_id+"/"+group,s["drawings"],pct(s["composite"]),pct(s["symbol"]["f1"]),
                         pct(s["spec_semantic"]),pct(s["spec_emitted_exact"]),pct(s["edge"]["f1"]),
                         pct(s["bom_detail"]["recall"]),pct(s["bom_summary"]["recall"])]))
    md.extend(["","| 退化图 | 模式 | 综合 | 规格原始精确 | 输出规格精确 | 规格语义 | BOM 明细 |",
               "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for r in result["per_drawing"]:
        if r["lane"] in {"png","degraded_no_kg"} and r["subset"] == "degraded":
            v = summarize([r])
            md.append(_line([f"{r['drawing_id']}（{r['degradation']}）",r["lane"],pct(v["composite"]),
                             pct(v["spec_raw_exact"]),pct(v["spec_emitted_exact"]),
                             pct(v["spec_semantic"]),pct(v["bom_detail"]["recall"])]))
    main_png = [r for r in result["per_drawing"] if r["lane"] == "png" and r["subset"] != "degraded"]
    triggered = sum(bool((r["raster_preprocessing"] or {}).get("applied")) for r in main_png)
    md.extend(["","### 低清 PNG 前后对照","",
               f"主验收 PNG 中 {triggered}/{len(main_png)} 张触发增强。两路解析共用增强后的同尺寸像素网格。",
               "", "| 图纸 | 模式 | 符号 F1 | 规格语义 | BOM 严格明细 | 无向边 F1 | 真边 / 误连 / 漏边 | 误报红灯 | 综合 |",
               "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for sample in result["raster_recovery"]:
        threshold = sample["preprocessing"].get("wire_ink_threshold")
        variants = (("raw","原始输入"),("enhanced_default_wires","增强输入 · 默认追线"),
                    ("enhanced",f"增强输入 · 追线阈值 {threshold}" if threshold is not None else "增强输入"))
        for kind, label in variants:
            if kind + "_counts" not in sample:
                continue
            group = summarize([{"counts":sample[kind+"_counts"],"timing":None,"compliance_run":True}])
            edge, red = group["edge"], group["compliance"]
            md.append(_line([sample["drawing_id"],label,pct(group["symbol"]["f1"]),
                             pct(group["spec_semantic"]),pct(group["bom_detail"]["recall"]),
                             pct(edge["f1"]),f"{edge['tp']} / {edge['fp']} / {edge['fn']}",
                             red["fp"] + red["extra_red"],pct(group["composite"])]))
    md.extend(["","## 消融贡献","",
               "各列为完整模式减对应消融组。退化去 KG 行使用同一组 3 张原始 PNG，简写行仅比较 alias 图。"
               "YOU-263 自身会解析常见别名，关闭 KG 时保留其内置解析能力，并以可获取的 OCR 原文输出位号与规格。",
               "端到端红灯 Recall 衡量管线实际发出的告警。A3 关闭合规模块，因此没有发出告警，模块自身 Precision/Recall 仍留空。",
               "", "| 消融 | 图数 | 综合 pp | 拓扑 F1 pp | BOM 明细 pp | BOM 汇总 pp | 输出规格精确 pp | 红灯 Recall pp | 均值秒差 |",
               "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for row in ablations(result):
        deltas = [f"{100*row['delta_'+name]:+.2f}" if row["delta_"+name] is not None else "—"
                  for name in ("composite","edge","bom_detail","bom_summary","spec_emitted_exact",
                               "pipeline_core_defect_recall")]
        md.append(_line([row["lane"],row["drawings"],*deltas,f"{row['delta_mean_time_s']:+.3f}"]))
    md.extend(["","## 合规与耗时","",
               "| Full 主集红灯 | TP | FP | FN | Precision | Recall |",
               "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for rid,data in control["by_rule"].items():
        md.append(_line([rid,data["tp"],data["fp"],data["fn"],pct(data["precision"]),pct(data["recall"])]))
    md.extend(["","| 主集通道 | 阶段 | 均值秒 | P50 秒 | P95 秒 |",
               "| --- | --- | ---: | ---: | ---: |"])
    for lane in ("full","dxf","png","pdf"):
        for phase,row in result["lanes"][lane]["main"]["timing"].items():
            md.append(_line([lane,phase,sec(row["mean"]),sec(row["p50"]),sec(row["p95"])]))
    md.extend(["","## 误差归因","",
               "定位先核对符号命中，再核对规格和端口边。疑似 OCR 混淆、串位或断线的分类是自动归因线索，"
               "需回到原图框和连线复核。差错计数允许同一器件在不同阶段出现。","",
               "| 阶段与归因 | 数量 |","| --- | ---: |"])
    md.extend(_line([name,count]) for name,count in result["error_analysis"]["by_cause"].items())
    for label,key in (("符号漏检","symbol_false_negative_top"),("符号误检","symbol_false_positive_top")):
        values = "、".join(f"{r['class_code']} {r['count']}" for r in result["error_analysis"][key]) or "0"
        md.extend(["",f"- {label} Top-K 为 {values}。"])
    md.extend(["","### 可复核案例",""])
    for i,case in enumerate(result["error_analysis"]["cases"],1):
        expected = json.dumps(case["expected"],ensure_ascii=False,separators=(",",":"))
        actual = json.dumps(case["predicted"],ensure_ascii=False,separators=(",",":"))
        quote = chr(96)
        md.append(f"{i}. {case['drawing_id']} / {case['instance_id']} / {case['cause']}。"
                  f"真值 {quote}{expected}{quote}，预测 {quote}{actual}{quote}，"
                  f"像素框 {quote}{case['bbox_px']}{quote}。{case['improvement']}")
    md.extend(["","### 各通道合规误判追踪","",
               "| 通道 | 图纸 | 规则 | 自动归因 |",
               "| --- | --- | --- | --- |"])
    for case in result["error_analysis"]["compliance_cases_by_lane"]:
        md.append(_line([case["lane"],case["drawing_id"],case["expected"] or case["predicted"],case["cause"]]))
    md.extend(["","## 评分与复现边界","",
               "- 推理暂存目录只有原始图纸，评分器验证 manifest 记录的标注 SHA-256 后读取标签。"
               "综合指标分母包含漏检器件，所有通道共用同一评分器。",
               "- 明细项要求类别与数量一致，且位号或定位匹配。真值有规格时，语义规格也必须一致。"
               "主汇总按采购类别、规格语义、单位及总数量匹配。目录号诊断另存为 bom_model_summary。",
               "- 母排规格只从邻近的可见文本补绑。主集 7 张带母排的 DXF 正文没有 TMY 或 LMY 标注，"
               "对应规格保留空值并计入遗漏。",
               "- B1 的框是 OCR 文字框，B2 和 A2 的边使用邻近端口，A3 关闭合规引擎。"
               "四类缺陷用规则 ID 和映射后的实例 ID 匹配，额外规则红灯单列。",
               "- Cu/Al 查表按 YOU-265 的项目筛查配置。载流量条件可由已观察到的 In > Iz 单独证伪。"
               "无 Ib 的图纸不发完整载流量绿灯。",
               "- 耗时包含解析、连接/BOM 及合规，采用本机单进程顺序测量。复现比较数值指标，耗时单独记录。","",
               f"- B3 状态为 {result['vlm_baseline']['status']}。配置环境后先运行以下第一条命令生成预测，再运行第二条重评。","",
               "~~~bash",result["vlm_baseline"]["run"],result["vlm_baseline"]["rescore"],"~~~",""])
    if result.get("repeatability"):
        md += ["两次完整运行的非耗时评测载荷规范化为 UTF-8 JSON 后逐字节一致。"
               f"SHA-256 为 {result['repeatability']['canonical_metrics_sha256']}。",""]
    md += ["## 上游代码",""]
    md.extend(f"- PR #{n} · {sha}" for n,sha in result["upstream_commits"].items())
    return "\n".join(md) + "\n"


def export_results(result, output, frontend):
    output.mkdir(parents=True,exist_ok=True)
    frontend.mkdir(parents=True,exist_ok=True)
    result = result | {"ablation_comparison": ablations(result)}
    _json(output/"eval_summary.json",result)
    per = drawing_table(result)
    _csv(output/"per_drawing_metrics.csv",tuple(per[0]),per)
    ablation = result["ablation_comparison"]
    _csv(output/"ablation_comparison.csv",tuple(ablation[0]),ablation)
    (output/"eval_report.md").write_text(markdown_report(result),encoding="utf-8")
    render_charts(result,output/"figures")
    dashboard = {k: result[k] for k in ("schema_version","dataset","upstream_commits","thresholds",
                                        "acceptance","vlm_baseline","ablation_comparison","error_analysis",
                                        "raster_recovery")}
    dashboard["lanes"] = result["lanes"]
    dashboard["per_drawing"] = per
    _json(frontend/"eval_dashboard.json",dashboard)
    _csv(frontend/"eval_charts_workbench.csv",WORKBENCH_FIELDS,workbench_points(result))
