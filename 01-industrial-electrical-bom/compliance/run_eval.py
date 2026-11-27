"""Offline evaluation and deterministic frontend export for ElectroBench-JS."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .engine import evaluate
from .explainer import DeterministicRAGExplainer
from .kg import export_kg
from .repairs import apply_fix
from .rulebook import RULES

TRACK = Path(__file__).resolve().parents[1]
CORE = {"selectivity_inversion", "ampacity_insufficient", "motor_protection_missing", "interlock_missing"}
SUBSETS = {"primary": 4, "secondary": 3, "defect": 4, "degraded": 3}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data, *, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, ensure_ascii=False, sort_keys=True, indent=indent,
                                 allow_nan=False, separators=(",", ":") if indent is None else None)
                      + "\n").encode("utf-8"))


def _key(finding):
    return finding["rule_id"], tuple(sorted(finding["instance_ids"]))


def _behavior(report, *, only_red=False):
    return Counter((_key(f), f["severity"], tuple(f["tags"])) for f in report["findings"]
                   if not only_red or f["severity"] == "error")


def _parser_view(data, *, alias_labels=False):
    copies = [dict(i) for i in data["instances"]]
    if alias_labels:
        for item in copies:
            item["tag"] = item["label_tag"]
            item["specs"] = {k: v for k, v in item["specs"].items() if k not in
                             {"spec", "In_A", "poles", "icu_kA", "section_mm2"}}
    return {"id": data["id"], "sheet": data["sheet"], "instances": copies, "netlist": data["netlist"]}


def _report_text(summary):
    totals = summary["totals"]
    lines = [
        "# ElectroBench-JS v1.0.0 合规实测",
        "",
        f"- 4 类红灯 Precision **{totals['precision']:.0%}**，Recall **{totals['recall']:.0%}**。",
        f"- 匹配 {totals['tp']} 条，额外红灯 {totals['fp']} 条，漏检 {totals['fn']} 条。",
        f"- 7 张 primary + secondary 标准图红灯误报 **{totals['conforming_errors']}**。",
        "- 匹配键为 rule_id 与排序后的 instance_ids。每条误报均计入 Precision。",
        "- 退化对比使用冻结标注及同构网表。非标简写对比另走 OCR 标签归一化路径。",
        "- 黄灯包括图纸证据不足和项目筛查阈值。各红灯预测独立于标注 defects。",
        "",
        "| 图纸 | 子集 | 真值 | TP | FP | FN | 黄灯 | 绿灯 | 预测红灯 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary["drawings"]:
        labels = ", ".join(f"{f['rule_id']} ({'/'.join(f['instance_ids'])})" for f in row["errors"]) or "—"
        lines.append(f"| {row['id']} | {row['subset']} | {row['expected']} | {row['tp']} | {row['fp']} | "
                     f"{row['fn']} | {row['warning']} | {row['pass']} | {labels} |")
    lines.extend(["", "## 规则注册和触发统计", "",
                  "| 类别 | 规则 ID | 规则 | 红 | 黄 | 绿 |",
                  "| --- | --- | --- | ---: | ---: | ---: |"])
    for row in summary["rules"]:
        lines.append(f"| {row['family']} | {row['id']} | {row['title']} | "
                     f"{row['error']} | {row['warning']} | {row['pass']} |")
    lines.extend(["", "## 退化、纯网表和修复复检", ""])
    for row in summary["degradation_checks"]:
        lines.append(f"- {row['id']} 对比 {row['source_id']}，规则、分级及位号一致。")
    lines.append(f"- 全部 {len(summary['drawings'])} 张纯 instances + netlist 输入的红灯结果一致。")
    lines.append("- 四张缺陷图分别应用全部红灯语义补丁后复检，红灯均清零。")
    return "\n".join(lines) + "\n"


def run(samples, compliance_out, frontend_out):
    manifest = _read(samples / "manifest.json")
    entries = {row["id"]: row for row in manifest["drawings"]}
    paths = sorted(samples.glob("*/*/annotations.json"))
    if Counter(p.parent.parent.name for p in paths) != SUBSETS or len(entries) != 14:
        raise ValueError("expected the frozen 4+3+4+3 ElectroBench-JS set")
    if manifest["schema_version"] != "1.0.0":
        raise ValueError("expected ElectroBench-JS schema 1.0.0")
    docs = {}
    for path in paths:
        data = _read(path)
        entry = entries.get(data["id"])
        if not entry or data["id"] != path.parent.name or data["subset"] != path.parent.parent.name:
            raise ValueError(f"manifest identity mismatch: {path}")
        # ElectroBench hashes the stored JSON bytes. Git may check out CRLF.
        digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if digest != entry["annotations_sha256"]:
            raise ValueError(f"frozen annotation hash mismatch: {path}")
        docs[data["id"]] = data
    explainer = DeterministicRAGExplainer()
    rows, repairs, reports = [], [], {}
    rule_stats = {rid: Counter() for rid in RULES}
    for key in sorted(docs):
        data = docs[key]
        report = evaluate(data)
        errors = [f for f in report["findings"] if f["severity"] == "error"]
        predicted = Counter(map(_key, errors))
        expected = Counter(map(_key, data["defects"]))
        tp = sum((predicted & expected).values())
        if any(not f["locations"] or any(loc["bbox_px"] is None or loc["bbox_mm"] is None
                                         for loc in f["locations"]) for f in errors):
            raise AssertionError(f"{key}: error coordinate missing")
        if _behavior(evaluate(_parser_view(data)), only_red=True) != _behavior(report, only_red=True):
            raise AssertionError(f"{key}: pure netlist error behavior differs")
        if errors:
            repaired = data
            for finding in errors:
                repaired = apply_fix(repaired, finding["fix_suggestion"])
            remaining = evaluate(repaired)["counts"]["error"]
            repairs.append({"id": key, "applied": len(errors), "remaining_errors": remaining})
            if remaining:
                raise AssertionError(f"{key}: errors after all patches: {remaining}")
        rows.append({"id": key, "subset": data["subset"], "expected": sum(expected.values()),
                     "tp": tp, "fp": sum(predicted.values()) - tp, "fn": sum(expected.values()) - tp,
                     **report["counts"],
                     "errors": [{"rule_id": f["rule_id"], "instance_ids": f["instance_ids"]} for f in errors]})
        for finding in report["findings"]:
            rule_stats[finding["rule_id"]][finding["severity"]] += 1
            if finding["severity"] != "pass":
                response = explainer.explain_finding(finding)
                finding["rag"] = {"answer": response["answer"], "clause_ids": response["clause_ids"]}
        reports[key] = report | {"subset": data["subset"], "title": data["title"], "sheet": data["sheet"],
                                 "drawing_asset": f"samples/{data['subset']}/{key}/drawing.png"}
    degradation = []
    for key, data in docs.items():
        if data["subset"] != "degraded":
            continue
        metadata = data["degradation"]
        source = metadata.get("source_id") or metadata["source_template"]
        if _behavior(reports[key]) != _behavior(reports[source]):
            raise AssertionError(f"{key}: degraded behavior differs from {source}")
        if metadata["type"] == "alias":
            alias = evaluate(_parser_view(data, alias_labels=True))
            canonical = evaluate(_parser_view(docs[source]))
            def core(report):
                return _behavior({"findings": [f for f in report["findings"] if f["rule_id"] in CORE]})
            if core(alias) != core(canonical):
                raise AssertionError(f"{key}: parser alias behavior differs")
        degradation.append({"id": key, "source_id": source, "behavior_match": True})
    tp, fp, fn = (sum(row[k] for row in rows) for k in ("tp", "fp", "fn"))
    conforming = sum(row["error"] for row in rows if row["subset"] in {"primary", "secondary"})
    families = {rid: {k: 0 for k in ("tp", "fp", "fn")} for rid in sorted(CORE)}
    for key, data in docs.items():
        actual = Counter(_key(f) for f in reports[key]["findings"] if f["severity"] == "error")
        expected = Counter(map(_key, data["defects"]))
        for label, counter in (("tp", actual & expected), ("fp", actual - expected), ("fn", expected - actual)):
            for (rid, _), value in counter.items():
                if rid in families:
                    families[rid][label] += value
    if fp or fn or conforming or any(not stats["tp"] for stats in families.values()):
        raise AssertionError(f"acceptance failed: TP={tp}, FP={fp}, FN={fn}, clean errors={conforming}")
    summary = {"dataset_version": "1.0.0", "drawings": rows, "defect_metrics": families,
               "totals": {"tp": tp, "fp": fp, "fn": fn, "precision": tp/(tp+fp), "recall": tp/(tp+fn),
                          "conforming_errors": conforming},
               "rules": [{"id": rule.id, "family": rule.family, "title": rule.title,
                          "failure_severity": rule.severity,
                          **{level: rule_stats[rule.id][level] for level in ("error", "warning", "pass")}}
                         for rule in RULES.values()],
               "degradation_checks": sorted(degradation, key=lambda x: x["id"]), "repair_checks": repairs}
    _write(compliance_out / "eval_summary.json", summary)
    (compliance_out / "eval_report.md").write_bytes(_report_text(summary).encode("utf-8"))
    _write(frontend_out / "compliance_reports.json", {
        "schema_version": "1.0.0", "reports": reports,
        "clauses": {c["clause_id"]: c for c in explainer.index.clauses},
    }, indent=None)
    _write(frontend_out / "electrical_kg.json", export_kg(explainer.index.graph), indent=None)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, default=TRACK / "samples")
    parser.add_argument("--compliance-out", type=Path, default=TRACK / "compliance")
    parser.add_argument("--frontend-out", type=Path, default=TRACK / "frontend_demo_data")
    args = parser.parse_args()
    summary = run(args.samples, args.compliance_out, args.frontend_out)
    totals = summary["totals"]
    print(f"{len(summary['drawings'])} drawings | {len(summary['rules'])} rules | "
          f"precision={totals['precision']:.0%} recall={totals['recall']:.0%} "
          f"conforming_errors={totals['conforming_errors']}")


if __name__ == "__main__":
    main()
