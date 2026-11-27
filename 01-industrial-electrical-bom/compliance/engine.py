"""Evaluate a drawing without reading its expected defects or logic truth table."""

from collections import Counter
from collections.abc import Mapping

from .control_checks import control_checks
from .equipment_checks import equipment_checks
from .power_checks import power_checks
from .normalize import number, poles
from .repairs import BOM_KEY, anchor, bom_rows
from .rulebook import RULES, MV
from .topology import Drawing
from electrobench.catalog import BY_CODE


def _bbox_union(boxes):
    if not boxes:
        return None
    x = min(b[0] for b in boxes)
    y = min(b[1] for b in boxes)
    return [round(value, 4) for value in
            [x, y, max(b[0] + b[2] for b in boxes) - x, max(b[1] + b[3] for b in boxes) - y]]


def bom_checks(drawing, check):
    grouped = {}
    for node, item in drawing.items.items():
        check("symbol_class_unknown", item["class_code"] not in BY_CODE, [node],
              {"class_code": item["class_code"]})
        if not anchor(item):
            continue
        specs = item["specs"]
        check("bom_anchor_tag_missing", not item["tag"], [node], {"tag": item["tag"]})
        check("bom_anchor_spec_missing", not any(specs.get(key) for key in ("spec", "model")),
              [node], {"model": specs.get("model"), "spec": specs.get("spec")})
        if item["tag"]:
            grouped.setdefault((item.get("cabinet", ""), item["tag"]), []).append(node)
        if item["class_code"] == "QF":
            check("bom_breaker_poles_missing", poles(specs.get("poles")) is None,
                  [node], {"poles": specs.get("poles")})
        if item["class_code"] in {"QF", "FU"}:
            rated = number(specs.get("In_A"))
            check("bom_rated_current_missing", rated is None or rated <= 0, [node], {"In_A": rated})
    for (cabinet, tag), nodes in sorted(grouped.items()):
        check("duplicate_bom_tag", len(nodes) > 1, nodes, {"tag": tag, "cabinet": cabinet, "count": len(nodes)})
    details, summary = bom_rows(drawing)
    if isinstance(drawing.data.get("bom"), list):
        fields = ("instance_id", "tag", "model", "spec", "qty")
        expected = Counter(tuple(r.get(f) for f in fields) for r in details)
        actual = Counter(tuple(r.get(f) for f in fields) for r in drawing.data["bom"])
        changed = sorted({r[0] for r in (expected - actual) + (actual - expected)
                          if r[0] in drawing.items})
        check("bom_detail_anchor_mismatch", expected != actual,
              changed or [r["instance_id"] for r in details],
              {"expected_rows": expected.total(), "actual_rows": actual.total(),
               "unmatched_expected": (expected - actual).total(),
               "unmatched_actual": (actual - expected).total()}, [{"op": "rebuild_bom"}])
    if isinstance(drawing.data.get("bom_summary"), list):
        def totals(rows):
            result = Counter()
            for row in rows:
                result[tuple(row.get(k) for k in BOM_KEY)] += number(row.get("qty")) or 0
            return result

        expected = totals(summary)
        actual = totals(drawing.data["bom_summary"])
        changed = {key for key in expected.keys() | actual.keys() if expected[key] != actual[key]}
        check("bom_summary_quantity_mismatch", bool(changed),
              [r["instance_id"] for r in details if not changed or tuple(r[k] for k in BOM_KEY) in changed],
              {"expected_qty": expected.total(), "actual_qty": actual.total(),
               "mismatched_groups": len(changed)}, [{"op": "rebuild_bom"}])
    for edge in drawing.invalid_edges:
        check("netlist_dangling_edge", True,
              [i for i in (edge["source"], edge["target"]) if i in drawing.items],
              {"source": edge["source"], "target": edge["target"], "edge_id": edge.get("id")})


def evaluate(data: Mapping, *, enabled_rules=None, disabled_rules=()):
    """Return deterministic observations. Unobserved rules stay untested."""
    enabled = set(RULES) if enabled_rules is None else set(enabled_rules)
    disabled = set(disabled_rules)
    unknown = (enabled | disabled) - RULES.keys()
    if unknown:
        raise ValueError(f"unknown rules: {', '.join(sorted(unknown))}")
    enabled -= disabled
    drawing = Drawing(data)
    findings = []

    def check(rule_id, violation, nodes, evidence, operations=(), *, refs=None):
        if rule_id not in enabled:
            return
        rule = RULES[rule_id]
        nodes = list(dict.fromkeys(nodes))
        locations = [{"instance_id": i, "tag": drawing.tag(i),
                      "bbox_px": drawing.box(i, "px"), "bbox_mm": drawing.box(i, "mm")}
                     for i in nodes]
        boxes = {unit: _bbox_union([loc[unit] for loc in locations if loc[unit] is not None])
                 for unit in ("bbox_px", "bbox_mm")}
        severity = rule.severity if violation else "pass"
        if refs is None and data.get("cabinet") == "KYN28" and rule.family == "selectivity":
            refs = (MV,)
        findings.append({"rule_id": rule_id, "family": rule.family, "severity": severity,
                         "message": rule.title, "instance_ids": nodes,
                         "tags": [loc["tag"] for loc in locations], "locations": locations,
                         **boxes, "evidence": evidence, "standard_refs": list(refs or rule.refs),
                         "fix_suggestion": {"action": rule.action if violation else None,
                                            "operations": [op for op in operations if op] if violation else []}})

    power_checks(drawing, check)
    equipment_checks(drawing, check)
    control_checks(drawing, check)
    bom_checks(drawing, check)
    findings.sort(key=lambda f: (f["rule_id"], f["instance_ids"]))
    totals = Counter(f["severity"] for f in findings)
    observed = {finding["rule_id"] for finding in findings}
    return {"schema_version": "1.0.0", "drawing_id": data.get("id"),
            "status": "error" if totals["error"] else
                      "warning" if totals["warning"] or not findings else "pass",
            "counts": {level: totals[level] for level in ("error", "warning", "pass")},
            "not_evaluated_rule_ids": sorted(enabled - observed), "findings": findings}
