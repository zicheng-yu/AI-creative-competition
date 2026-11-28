"""Ground-truth loading, matching and micro-averaged metrics.

This is the only benchmark module that reads reference annotations or BOM CSV.
"""

from collections import Counter
import csv
from dataclasses import dataclass
from hashlib import sha256
import json
import re

import numpy as np
from scipy.optimize import linear_sum_assignment

from compliance.normalize import normalize_instance, poles
from electrobench.catalog import BY_CODE
from symbol_parser.labels import normalize_spec
from symbol_parser.raster import intersection_over_union

CORE = {"selectivity_inversion", "ampacity_insufficient", "motor_protection_missing", "interlock_missing"}
SPLITS = {"primary": 4, "secondary": 3, "defect": 4, "degraded": 3}
RATINGS = {"In_A", "Ie_A", "Ir_A", "icu_kA", "icn_kA", "kW", "section_mm2", "ratio", "poles", "frame_A"}
QF_SPEC = re.compile(
    r"(?:塑壳断路器)?(?:IN=)?\d+(?:\.\d+)?A(?:/\d+(?:\.\d+)?A)?(?:[1-4]P(?:\+N)?)?(?:ICU=\d+(?:\.\d+)?KA)?"
)
FU_SPEC = re.compile(r"(?:IN=)?\d+(?:\.\d+)?A")


@dataclass(frozen=True)
class Reference:
    sample: dict
    detail: list
    summary: list


def _csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_references(samples):
    manifest = json.loads((samples / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema_version"] != "1.0.0":
        raise ValueError("expected ElectroBench-JS v1.0.0")
    entries = manifest["drawings"]
    if Counter(row["subset"] for row in entries) != SPLITS or len({r["id"] for r in entries}) != 14:
        raise ValueError("unexpected frozen sample manifest")
    directories = {p.parent.relative_to(samples).as_posix()
                   for p in samples.glob("*/*/annotations.json")}
    expected = {row["subset"] + "/" + row["id"] for row in entries}
    if directories != expected:
        raise ValueError("sample directories do not match the manifest")
    references = []
    for row in sorted(entries, key=lambda value: value["id"]):
        directory = samples / row["subset"] / row["id"]
        blob = (directory / "annotations.json").read_bytes().replace(b"\r\n", b"\n")
        if sha256(blob).hexdigest() != row["annotations_sha256"]:
            raise ValueError(f"annotation SHA-256 mismatch: {row['id']}")
        sample = json.loads(blob)
        if (sample["id"], sample["subset"]) != (row["id"], row["subset"]):
            raise ValueError("manifest and annotations disagree on drawing identity")
        references.append(Reference(sample, _csv(directory / "bom.csv"), _csv(directory / "bom_summary.csv")))
    return references


def _assign(matrix):
    if not matrix.size:
        return []
    left, right = linear_sum_assignment(matrix, maximize=True)
    return [(i, j) for i, j in zip(left, right, strict=True) if matrix[i, j] > 0]


def _box(item, predicted, source, sheet):
    if predicted["channel"] == "dxf-vector":
        return item["bbox_mm"] if source else item["bbox"]
    if not source:
        return item["bbox_top_left"]
    width = predicted["coordinate_space"]["width"] / sheet["image_width"]
    height = predicted["coordinate_space"]["height"] / sheet["image_height"]
    x, y, w, h = item["bbox_px"]
    return [x * width, y * height, w * width, h * height]


def match_symbols(prediction, truth):
    exp, obs = truth["instances"], prediction["symbols"]
    weights = np.zeros((len(exp), len(obs)))
    boxes = [_box(i, prediction, True, truth["sheet"]) for i in exp]
    candidate_boxes = [_box(i, prediction, False, truth["sheet"]) for i in obs]
    for i, a in enumerate(exp):
        for j, b in enumerate(obs):
            if a["class_code"] == b["class_code"] and candidate_boxes[j] is not None:
                overlap = intersection_over_union(boxes[i], candidate_boxes[j])
                if overlap >= 0.5:
                    # Maximize match count first, then break ties with total IoU.
                    weights[i, j] = 1 + min(overlap, 1) / (1 + min(len(exp), len(obs)))
    return [(exp[i], obs[j]) for i, j in _assign(weights)]


def format_spec(value):
    text = normalize_spec(str(value or "")).casefold()
    text = re.sub(r"(?<=\d)\s*极", "p", text)
    text = re.sub(r"(?<=\d)\s*(?:×|乘)\s*(?=\d)", "x", text)
    return re.sub(r"\s+", "", text)


def _signature(code, raw, values=None):
    specs = normalize_instance({"class_code": code, "label_spec": raw, "specs": values or {}})["specs"]
    if "Icu_kA" in specs:
        specs.setdefault("icu_kA", specs["Icu_kA"])
    if "poles" in specs:
        specs["poles"] = poles(specs["poles"])
    return {key: val for key, val in specs.items() if key in RATINGS and val is not None}


def _rated_spec(code, text):
    pattern = {"QF": QF_SPEC, "FU": FU_SPEC}.get(code)
    return _signature(code, text) if pattern and pattern.fullmatch(format_spec(text).upper()) else {}


def spec_semantic(code, expected, observed, values=None):
    if not expected:
        return False
    if observed and format_spec(expected) == format_spec(observed):
        return True
    # Ratings separated from the label count when the reference label is
    # fully represented by supported electrical fields.
    want = _rated_spec(code, expected)
    if not want:
        return False
    actual = _signature(code, observed, values)
    return all(actual.get(key) == val for key, val in want.items())


def _edge_pairs(rows, mapping=None, *, directed=False):
    pairs = set()
    for edge in rows:
        a, b = edge["source"], edge["target"]
        if mapping is not None:
            a, b = (mapping.get(i, "unmatched:" + i) for i in (a, b))
        pairs.add((a, b) if directed else tuple(sorted((a, b))))
    return pairs


def _findings(rows, mapping=None, *, core_only=True):
    counts = Counter()
    for finding in rows:
        if (core_only and finding["rule_id"] not in CORE) or finding.get("severity", "error") != "error":
            continue
        ids = finding["instance_ids"]
        if mapping is not None:
            ids = [mapping.get(node, "unmatched:" + node) for node in ids]
        counts[(finding["rule_id"], tuple(sorted(ids)))] += 1
    return counts


def _table_counts(counts, prefix, actual, expected):
    actual, expected = Counter(actual), Counter(expected)
    counts[prefix + "_tp"] = sum((actual & expected).values())
    counts[prefix + "_fp"] = sum((actual - expected).values())
    counts[prefix + "_fn"] = sum((expected - actual).values())


def _bom_detail(actual, expected, mapping):
    matrix = np.zeros((len(expected), len(actual)))
    for i, wanted in enumerate(expected):
        for j, seen in enumerate(actual):
            if wanted["class_code"] != seen["class_code"] or int(wanted["qty"]) != int(seen["qty"]):
                continue
            tag = seen["tag"] and seen["tag"].upper() == wanted["tag"].upper()
            position = any(mapping.get(a["instance_id"]) == wanted["instance_id"] for a in seen["anchors"])
            comparable = not wanted["spec"] or spec_semantic(wanted["class_code"], wanted["spec"],
                                                             seen["spec"], seen.get("ratings"))
            if (tag or position) and comparable:
                matrix[i, j] = 1 + 0.01 * position + 0.001 * bool(tag)
    return len(_assign(matrix))


def _summarized(rows, *, by_model):
    groups = Counter()
    for row in rows:
        symbol = BY_CODE.get(row.get("class_code"))
        family = row.get("bom_letter") or (symbol.bom_letter if symbol else "")
        model = str(row.get("model") or "").strip().casefold() if by_model else ""
        spec = row.get("spec") or ""
        ratings = _rated_spec(family, spec)
        spec_key = tuple(sorted(ratings.items())) if ratings else format_spec(spec)
        key = (family, model, spec_key, row.get("unit") or "")
        groups[key] += int(row["qty"])
    return Counter((key, qty) for key, qty in groups.items())


def score(prediction, reference):
    truth = reference.sample
    pairs = match_symbols(prediction, truth)
    seen = prediction["symbols"]
    mapping = {b["id"]: a["id"] for a, b in pairs}
    annotated = truth["instances"]
    specifications = [item for item in annotated if item["specs"].get("spec") or
                      RATINGS.intersection(item["specs"])]
    specified_ids = {s["id"] for s in specifications}
    counts = Counter(symbol_tp=len(pairs), symbol_fp=len(seen)-len(pairs),
                     symbol_fn=len(annotated)-len(pairs), spec_expected=len(specifications),
                     tags_expected=sum(bool(a["tag"]) for a in annotated))
    spec_misses = []
    for expected, observed in pairs:
        counts["tag_correct"] += bool(expected["tag"] and expected["tag"] == observed["tag"])
        if expected["id"] not in specified_ids:
            continue
        target = expected["specs"].get("spec", "")
        output = observed["specs"].get("spec", "")
        raw = observed.get("raw_spec", output)
        counts["spec_raw_correct"] += bool(target and raw == target)
        counts["spec_emitted_correct"] += bool(target and output == target)
        semantic = spec_semantic(expected["class_code"], target, output, observed["specs"]) if target else all(
            observed["specs"].get(key) == expected["specs"][key]
            for key in RATINGS.intersection(expected["specs"]))
        counts["spec_semantic_correct"] += semantic
        if not semantic:
            spec_misses.append({"expected": expected, "observed": observed})
    for directed, metric in ((False, "edge"), (True, "directed_edge")):
        expected_edges = _edge_pairs(truth["netlist"]["edges"], directed=directed)
        actual_edges = _edge_pairs(prediction["graph"]["edges"], mapping, directed=directed)
        _table_counts(counts, metric, actual_edges, expected_edges)
    actual_bom = prediction["bom"]["items"]
    hit = _bom_detail(actual_bom, reference.detail, mapping)
    counts.update(bom_detail_tp=hit, bom_detail_fp=len(actual_bom)-hit, bom_detail_fn=len(reference.detail)-hit)
    for by_model, name in ((False, "bom_summary"), (True, "bom_model_summary")):
        _table_counts(counts, name, _summarized(prediction["bom"]["summary"], by_model=by_model),
                      _summarized(reference.summary, by_model=by_model))
    red = prediction["compliance"]
    counts["core_defects_expected"] = sum(_findings(truth["defects"]).values())
    if red is not None:
        actual_findings = _findings(red["findings"], mapping)
        expected_findings = _findings(truth["defects"])
        _table_counts(counts, "compliance", actual_findings, expected_findings)
        counts["standard_red"] = red["counts"]["error"] if truth["subset"] in {"primary","secondary"} else 0
        counts["standard_core_red"] = sum(actual_findings.values()) if truth["subset"] in {"primary","secondary"} else 0
        counts["extra_red"] = red["counts"]["error"] - sum(actual_findings.values())
        for rule_id in sorted(CORE):
            _table_counts(counts, rule_id, {key: n for key, n in actual_findings.items() if key[0] == rule_id},
                          {key: n for key, n in expected_findings.items() if key[0] == rule_id})
    return counts, {"matched": pairs, "mapping": mapping, "spec_misses": spec_misses}


def _divide(numerator, denominator):
    return numerator / denominator if denominator else None


def _prf(counts, name):
    tp, fp, fn = (counts[name + "_" + k] for k in ("tp", "fp", "fn"))
    return {"tp": tp, "fp": fp, "fn": fn, "precision": _divide(tp, tp+fp),
            "recall": _divide(tp, tp+fn), "f1": _divide(2*tp, 2*tp+fp+fn)}


def summarize(rows):
    if not rows:
        return None
    counts = Counter()
    for row in rows:
        counts.update(row["counts"])
    observed = [row["timing"] for row in rows if row["timing"] is not None]
    timing = {k: {"mean": float(np.mean([r[k] for r in observed])),
                  "p50": float(np.percentile([r[k] for r in observed], 50)),
                  "p95": float(np.percentile([r[k] for r in observed], 95))}
              for k in ("parse_s", "topology_s", "compliance_s", "total_s")} if observed else None
    symbol = _prf(counts, "symbol")
    edge = _prf(counts, "edge")
    semantic = _divide(counts["spec_semantic_correct"], counts["spec_expected"])
    composite = composite_accuracy(symbol["f1"], semantic, edge["f1"])
    compliance = None
    if all(row["compliance_run"] for row in rows):
        compliance = _prf(counts, "compliance") | {
            "standard_red": counts["standard_red"], "standard_core_red": counts["standard_core_red"],
            "extra_red": counts["extra_red"], "by_rule": {rule: _prf(counts, rule) for rule in sorted(CORE)}}
    return {"drawings": len(rows), "composite": composite, "symbol": symbol, "edge": edge,
            "directed_edge": _prf(counts, "directed_edge"), "spec_semantic": semantic,
            "spec_raw_exact": _divide(counts["spec_raw_correct"], counts["spec_expected"]),
            "spec_emitted_exact": _divide(counts["spec_emitted_correct"], counts["spec_expected"]),
            "tag_exact": _divide(counts["tag_correct"], counts["tags_expected"]),
            "bom_detail": _prf(counts, "bom_detail"), "bom_summary": _prf(counts, "bom_summary"),
            "bom_model_summary": _prf(counts, "bom_model_summary"), "compliance": compliance,
            "pipeline_core_defect_recall": _divide(counts["compliance_tp"], counts["core_defects_expected"]),
            "timing": timing, "counts": dict(counts)}


def composite_accuracy(symbol_f1, spec_accuracy, topology_f1):
    if None in (symbol_f1, spec_accuracy, topology_f1):
        return None
    return .40*symbol_f1 + .35*spec_accuracy + .25*topology_f1
