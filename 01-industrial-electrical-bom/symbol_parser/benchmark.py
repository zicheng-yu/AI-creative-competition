"""Score original ElectroBench-JS drawings after inference, using annotations only to grade."""

import json
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.optimize import linear_sum_assignment

from .engine import parse_drawing
from .labels import normalize_spec
from .raster import TiledYolo, intersection_over_union


def _total(counters, latency):
    tp, fp, fn = (counters[name] for name in ("tp", "fp", "fn"))
    tag_n, spec_n = counters["tag_expected"], counters["spec_expected"]
    return {
        "drawings": len(latency),
        "average_seconds": round(sum(latency) / len(latency), 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "symbol_f1": round(2 * tp / (2 * tp + fp + fn), 6) if tp + fp + fn else None,
        "tag_correct": counters["tag_correct"],
        "tags_expected": tag_n,
        "spec_correct": counters["spec_correct"],
        "spec_expected": spec_n,
        "spec_exact_on_all_ground_truth": round(counters["spec_correct"] / spec_n, 6)
        if spec_n
        else None,
        "spec_exact_when_detected": round(
            counters["spec_correct"] / counters["spec_detected"], 6
        )
        if counters["spec_detected"]
        else None,
    }


def _score(sheet, annotations, extension):
    expected = annotations["instances"]
    detected = sheet["symbols"]
    scale_x = scale_y = 1
    if extension != "dxf":
        space = sheet["coordinate_space"]
        scale_x = space["width"] / annotations["sheet"]["image_width"]
        scale_y = space["height"] / annotations["sheet"]["image_height"]
    boxes = []
    for item in expected:
        if extension == "dxf":
            boxes.append(item["bbox_mm"])
        else:
            x, y, w, h = item["bbox_px"]
            boxes.append([x * scale_x, y * scale_y, w * scale_x, h * scale_y])
    matches = []
    if expected and detected:
        weights = np.zeros((len(expected), len(detected)))
        for i, target in enumerate(expected):
            for j, pred in enumerate(detected):
                if target["class_code"] == pred["class_code"]:
                    p_box = (
                        pred["bbox"] if extension == "dxf" else pred["bbox_top_left"]
                    )
                    iou = intersection_over_union(boxes[i], p_box)
                    if iou >= 0.5:
                        weights[i, j] = 1 + iou
        rows, cols = linear_sum_assignment(weights, maximize=True)
        matches = [
            (expected[i], detected[j])
            for i, j in zip(rows, cols, strict=True)
            if weights[i, j]
        ]
    return Counter(
        tp=len(matches),
        fp=len(detected) - len(matches),
        fn=len(expected) - len(matches),
        tag_expected=sum(bool(item["tag"]) for item in expected),
        tag_correct=sum(
            truth["tag"] == pred["tag"] for truth, pred in matches if truth["tag"]
        ),
        spec_expected=sum(bool(item["specs"].get("spec")) for item in expected),
        spec_detected=sum(bool(truth["specs"].get("spec")) for truth, _ in matches),
        spec_correct=sum(
            normalize_spec(truth["specs"]["spec"]).casefold()
            == pred["specs"].get("spec", "").casefold()
            for truth, pred in matches
            if truth["specs"].get("spec")
        ),
    )


def run(samples: Path, extension: str, subsets: set[str], *, detector=None):
    latency = []
    points = []
    combined = Counter()
    for anno in sorted(samples.glob("*/*/annotations.json")):
        metadata = json.loads(anno.read_text(encoding="utf-8"))
        drawing = anno.with_name(f"drawing.{extension}")
        if not drawing.exists() or metadata["subset"] not in subsets:
            continue
        start = perf_counter()
        payload = parse_drawing(drawing, detector=detector)
        json.dumps(payload, allow_nan=False)
        sheets = payload["sheets"]
        duration = perf_counter() - start
        latency.append(duration)
        grade = _score(sheets[0], metadata, extension)
        combined.update(grade)
        points.append(
            {
                "drawing": metadata["id"],
                "warnings": sheets[0]["warnings"],
                **_total(grade, [duration]),
            }
        )
    if not latency:
        raise ValueError("no drawings found for this format and subset")
    return {
        "input_format": extension,
        "summary": _total(combined, latency),
        "sample_results": points,
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path)
    parser.add_argument("--format", choices=("dxf", "pdf", "png"), required=True)
    parser.add_argument(
        "--subsets",
        nargs="+",
        choices=("primary", "secondary", "defect", "degraded"),
        default=("primary", "secondary", "defect"),
    )
    parser.add_argument("--yolo-weights", type=Path)
    parser.add_argument("--yolo-confidence", type=float, default=0.30)
    args = parser.parse_args()
    detector = (
        TiledYolo(args.yolo_weights, args.yolo_confidence)
        if args.yolo_weights
        else None
    )
    print(
        json.dumps(
            run(args.samples, args.format, set(args.subsets), detector=detector),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
