"""Attribute measured discrepancies using matched observations and reference evidence."""

from collections import Counter
from difflib import SequenceMatcher
from math import dist
import re

from .metrics import CORE, _edge_pairs, _findings, format_spec


def _position(item):
    x, y, w, h = item["bbox_mm"]
    return [x+w/2, y+h/2]


def drawing_errors(prediction, reference, matches):
    truth = reference.sample
    expected = {i["id"]: i for i in truth["instances"]}
    observed = {i["id"]: i for i in prediction["symbols"]}
    map_to_truth = matches["mapping"]
    map_to_prediction = {a["id"]: b["id"] for a, b in matches["matched"]}
    wrong_specs = {miss["expected"]["id"] for miss in matches["spec_misses"]}
    groups = Counter()
    class_misses, class_false = Counter(), Counter()
    examples = []

    def record(group, cause, ids, want, actual, tip, *, px=None):
        groups[group, cause] += 1
        locations = [expected[n]["bbox_px"] for n in ids if n in expected]
        examples.append({"drawing_id": truth["id"], "subset": truth["subset"], "stage": group,
                         "cause": cause, "instance_id": ids[0] if ids else None,
                         "instance_ids": list(ids), "expected": want, "predicted": actual,
                         "bbox_px": locations or ([px] if px else []), "improvement": tip})

    for node, item in expected.items():
        if node not in map_to_prediction:
            class_misses[item["class_code"]] += 1
            record("symbol", "missed", [node], f"{item['class_code']} {item['tag']}", None,
                   "检查训练或模板中该符号的尺寸、方向及遮挡条件。")
    for node, item in observed.items():
        if node not in map_to_truth:
            class_false[item["class_code"]] += 1
            if prediction["channel"] == "dxf-vector":
                px = next((i["bbox_px"] for i in prediction["annotation"]["instances"] if i["id"] == node), None)
            else:
                px = item.get("bbox_top_left")
                if px:
                    frame = prediction["coordinate_space"]
                    sx = truth["sheet"]["image_width"] / frame["width"]
                    sy = truth["sheet"]["image_height"] / frame["height"]
                    px = [float(v)*scale for v, scale in zip(px, (sx, sy, sx, sy), strict=True)]
            record("symbol", "false_detection", [node], None, f"{item['class_code']} {item['tag']}",
                   "增加无符号线段和文字区域负例，并检查重叠框抑制。", px=px)
    for pair in matches["spec_misses"]:
        a, b = pair["expected"], pair["observed"]
        want, seen = a["specs"].get("spec", ""), b["specs"].get("spec", "")
        norm = format_spec(seen)
        neighbors = [item for item in expected.values() if item["id"] != a["id"]
                     and dist(_position(a), _position(item)) <= 30 and
                     norm and norm == format_spec(item["specs"].get("spec"))]
        resemblance = SequenceMatcher(None, format_spec(want), norm).ratio()
        if neighbors:
            cause = "neighbor_label_candidate"
        elif not seen:
            cause = "absent_spec_text"
        elif re.search(r"[\u3400-\u9fff]", seen) and (truth.get("degradation") or {}).get("type") == "alias":
            cause = "possible_alias_gap"
        elif resemblance >= .6 and prediction["channel"] != "dxf-vector":
            cause = "possible_ocr_confusion"
        else:
            cause = "spec_binding_or_content"
        record("spec", cause, [a["id"]], want, seen,
               "核对原图字形与位号周围规格框，联合检查文字行分割和规格绑定。")
    expected_edges = _edge_pairs(truth["netlist"]["edges"])
    actual_edges = _edge_pairs(prediction["graph"]["edges"], map_to_truth)
    edge_types = {tuple(sorted((e["source"], e["target"]))): e["kind"] for e in truth["netlist"]["edges"]}
    for endpoints in sorted(expected_edges - actual_edges):
        kinds = edge_types[endpoints]
        if not all(i in map_to_prediction for i in endpoints):
            cause = "missing_endpoint"
        elif any(expected[i]["class_code"] == "WB" for i in endpoints):
            cause = "bus_tap_missing"
        elif prediction["channel"] in {"raster","pdf-vector","pdf-scan"}:
            cause = "possible_raster_break"
        else:
            cause = "logical_branch_or_port_missing"
        record("topology", cause, endpoints, {"connection": endpoints, "kind": kinds}, None,
               "检查端口挂接、母线分支、线段连续性或电缆标注的逻辑连接。")
    for endpoints in sorted(actual_edges - expected_edges):
        cause = "unmatched_endpoint" if any(i not in expected for i in endpoints) else "extra_connection"
        record("topology", cause, endpoints, None, {"connection": endpoints},
               "核对交叉处的接点证据，检查密集线路中端口连接是否串位。")
    if prediction["compliance"] is not None:
        expected_findings = _findings(truth["defects"])
        actual_findings = _findings(prediction["compliance"]["findings"], map_to_truth)
        disconnected = {n for pair in expected_edges - actual_edges for n in pair}
        non_core = _findings(
            [f for f in prediction["compliance"]["findings"] if f["rule_id"] not in CORE],
            map_to_truth, core_only=False)
        for label, difference in (("false_negative", expected_findings-actual_findings),
                                  ("false_positive", actual_findings-expected_findings),
                                  ("additional_red", non_core)):
            for (rule, nodes), times in sorted(difference.items()):
                if any(n not in map_to_prediction for n in nodes):
                    root = "symbol"
                elif wrong_specs.intersection(nodes):
                    root = "spec"
                elif disconnected.intersection(nodes) or any(set(nodes) & set(edge) for edge in actual_edges-expected_edges):
                    root = "topology"
                else:
                    root = "insufficient_rule_evidence"
                for _ in range(times):
                    record("compliance", label + "/" + root, nodes, rule if label == "false_negative" else None,
                           rule if label != "false_negative" else None,
                           "对照匹配框、规格与路径证据，补齐可观测字段后再运行确定性规则。")
    return {"counts": {f"{stage}/{cause}": n for (stage, cause), n in sorted(groups.items())},
            "symbol_fn": dict(class_misses), "symbol_fp": dict(class_false), "cases": examples}


def aggregate(records, *, limit=15):
    totals, misses, extras = Counter(), Counter(), Counter()
    cases = []
    for item in records:
        totals.update(item["counts"])
        misses.update(item["symbol_fn"])
        extras.update(item["symbol_fp"])
        cases.extend(item["cases"])
    by_stage = Counter()
    for key, value in totals.items():
        by_stage[key.split("/")[0]] += value
    chosen, buckets = [], {}
    for case in cases:
        if case["bbox_px"]:
            key = (case["stage"], case["subset"] == "degraded")
            buckets.setdefault(key, []).append(case)
    # Preserve variety across stages, draws and degradation.
    seen = set()
    while buckets and len(chosen) < limit:
        for key in sorted(list(buckets)):
            queue = buckets[key]
            if len(chosen) >= limit:
                break
            i = next((i for i, row in enumerate(queue) if (row["drawing_id"], row["stage"]) not in seen), 0)
            case = queue.pop(i)
            chosen.append(case)
            seen.add((case["drawing_id"], case["stage"]))
            if not queue:
                del buckets[key]
    ordered = lambda counter: [{"class_code": k, "count": n}
                               for k, n in sorted(counter.items(), key=lambda x: (-x[1], x[0]))[:10]]
    return {"by_stage": dict(sorted(by_stage.items())), "by_cause": dict(sorted(totals.items())),
            "symbol_false_negative_top": ordered(misses), "symbol_false_positive_top": ordered(extras),
            "cases": chosen}
