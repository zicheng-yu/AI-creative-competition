"""Test the topology stage against ElectroBench-JS with oracle recognition inputs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import build_bom, reconstruct


def _edges(edges):
    return {
        tuple(
            sorted(
                (
                    (edge["source"], edge["source_port"]),
                    (edge["target"], edge["target_port"]),
                )
            )
        )
        for edge in edges
    }


def _items(rows):
    return Counter(
        (row["class_code"], row["tag"], row["model"], row["spec"], row["qty"])
        for row in rows
    )


def recognize_fixture(annotation: dict, path: Path, channel: str) -> dict:
    """Adapt only per-symbol fields. Test labels stay on the scoring side."""
    symbols = []
    text_boxes = []
    for raw in annotation["instances"]:
        symbol = {
            field: raw[field]
            for field in (
                "id",
                "class_code",
                "tag",
                "ports",
                "specs",
                "circuit",
                "bom_anchor",
                "in_netlist",
            )
        }
        symbol["bbox"] = raw["bbox_mm"]
        if raw["class_code"] == "WIRE_NO":
            text_boxes.append(raw["bbox_mm"])
        symbols.append(symbol)
    return {
        "sheets": [
            {
                "id": annotation["id"],
                "cabinet": annotation["cabinet"] or "",
                "file": str(path.resolve()),
                "symbols": symbols,
                "text_boxes": text_boxes,
                "pixels_per_unit": annotation["sheet"]["px_per_mm"],
                "port_tolerance": 4 / annotation["sheet"]["px_per_mm"]
                if channel == "raster"
                else 0.2,
            }
        ]
    }


def _summary(counts: Counter) -> dict:
    tp, fp, fn = (counts[key] for key in ("tp", "fp", "fn"))
    return {
        "drawings": counts["drawings"],
        "edge_tp": tp,
        "edge_fp": fp,
        "edge_fn": fn,
        "edge_f1": round(2 * tp / (2 * tp + fp + fn), 6) if tp + fp + fn else None,
        "bom_matched": counts["bom_matched"],
        "bom_expected": counts["bom_expected"],
        "bom_completeness": round(counts["bom_matched"] / counts["bom_expected"], 6)
        if counts["bom_expected"]
        else None,
    }


def run(samples: Path, channel: str, subsets: set[str]) -> dict:
    results = []
    totals = defaultdict(Counter)
    for annotation_path in sorted(samples.glob("*/*/annotations.json")):
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        subset = annotation["subset"]
        if subset not in subsets:
            continue
        path = annotation_path.with_name(
            "drawing.dxf" if channel == "dxf" else "drawing.png"
        )
        if (
            not path.exists()
            or (annotation.get("degradation") or {}).get("type") == "skew"
        ):
            continue
        recognized = recognize_fixture(annotation, path, channel)
        result = reconstruct(recognized)
        got = _edges(result["edges"])
        expected = _edges(annotation["netlist"]["edges"])
        bom = _items(build_bom(recognized)["items"])
        truth = _items(annotation["bom"])
        counts = Counter(
            drawings=1,
            tp=len(got & expected),
            fp=len(got - expected),
            fn=len(expected - got),
            bom_matched=sum((bom & truth).values()),
            bom_expected=sum(truth.values()),
        )
        totals[subset].update(counts)
        totals["all"].update(counts)
        results.append(
            {
                "drawing": annotation["id"],
                "subset": subset,
                **_summary(counts),
                "warnings": result["warnings"],
            }
        )
    if not results:
        raise ValueError(f"no matching samples at {samples}")
    return {
        "channel": channel,
        "edge_scoring": "undirected_instance_and_port_pair_micro_average",
        "recognition_input": "oracle_symbols_ports_and_specs",
        "subsets": {name: _summary(totals[name]) for name in sorted(totals)},
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path)
    parser.add_argument("--channel", choices=("dxf", "raster"), default="dxf")
    parser.add_argument(
        "--subsets",
        nargs="+",
        choices=("primary", "secondary", "defect", "degraded"),
        default=("primary", "secondary", "defect"),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.samples, args.channel, set(args.subsets)),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
