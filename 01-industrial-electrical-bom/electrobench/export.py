"""JSON, CSV, COCO and YOLO writers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from . import DATASET_NAME, SCHEMA_VERSION, __version__
from .canvas import SHEET_H, SHEET_W
from .catalog import BY_CODE
from .model import DrawingRecord
from .render import PX_PER_MM, mm_box_to_px
from .rules import evaluate

STANDARDS = {
    "graphical_symbols": "GB/T 4728 / IEC 60617（简图近似，非标准图版复制）",
    "designations": "图面文字代号沿用成套行业习惯；iec81346 字段为 IEC 81346-2:2019 表1 类字母",
    "structuring": "GB/T 5094（对应 IEC 81346 的结构与参照代号原则）",
}


def _round_point(pt: tuple[float, float]) -> list[float]:
    return [round(pt[0], 2), round(pt[1], 2)]


def build_bom(record: DrawingRecord) -> tuple[list[dict], list[dict]]:
    detail = []
    for inst in record.instances:
        if not inst.bom_anchor:
            continue
        symbol = BY_CODE[inst.class_code]
        detail.append(
            {
                "line_no": len(detail) + 1,
                "instance_id": inst.id,
                "tag": inst.tag,
                "class_code": inst.class_code,
                "bom_letter": symbol.bom_letter,
                "name_zh": symbol.bom_name_zh,
                "model": inst.specs.get("model", ""),
                "spec": inst.specs.get("spec", ""),
                "qty": 1,
                "unit": symbol.unit,
                "circuit": inst.circuit,
            }
        )
    groups: dict[tuple, dict] = {}
    for row in detail:
        key = (row["bom_letter"], row["name_zh"], row["model"], row["spec"], row["unit"])
        bucket = groups.get(key)
        if bucket is None:
            bucket = {
                "bom_letter": row["bom_letter"],
                "name_zh": row["name_zh"],
                "model": row["model"],
                "spec": row["spec"],
                "qty": 0,
                "unit": row["unit"],
                "tags": [],
            }
            groups[key] = bucket
        bucket["qty"] += 1
        bucket["tags"].append(row["tag"])
    summary = []
    for index, bucket in enumerate(groups.values(), start=1):
        bucket["line_no"] = index
        bucket["tags"] = sorted(bucket["tags"])
        summary.append(bucket)
    return detail, summary


def serialize(record: DrawingRecord, img_w: int, img_h: int) -> dict:
    findings = evaluate(record)
    instances = []
    for inst in record.instances:
        symbol = BY_CODE[inst.class_code]
        instances.append(
            {
                "id": inst.id,
                "tag": inst.tag,
                "class_id": symbol.class_id,
                "class_code": inst.class_code,
                "name_zh": symbol.name_zh,
                "bom_letter": symbol.bom_letter,
                "iec81346": symbol.iec81346,
                "bom_anchor": inst.bom_anchor,
                "in_netlist": inst.in_netlist,
                "bbox_mm": list(inst.bbox_mm),
                "bbox_px": mm_box_to_px(inst.bbox_mm, img_w, img_h),
                "ports": {name: _round_point(pt) for name, pt in inst.ports.items()},
                "specs": inst.specs,
                "label_tag": inst.label_tag,
                "label_spec": inst.label_spec,
                "circuit": inst.circuit,
                "extra": inst.extra,
            }
        )
    nodes = [
        {
            "id": inst.id,
            "tag": inst.tag,
            "class_code": inst.class_code,
            "circuit": inst.circuit,
        }
        for inst in record.instances
        if inst.in_netlist
    ]
    node_ids = {node["id"] for node in nodes}
    edges = []
    children: dict[str, list[str]] = {}
    has_parent: set[str] = set()
    for edge in record.edges:
        edges.append(
            {
                "id": edge.id,
                "source": edge.source,
                "target": edge.target,
                "kind": edge.kind,
                "source_port": edge.source_port,
                "target_port": edge.target_port,
                "points": [list(pt) for pt in edge.points],
            }
        )
        if edge.kind == "power":
            children.setdefault(edge.source, []).append(edge.target)
            has_parent.add(edge.target)
    roots = [node["id"] for node in nodes if node["id"] not in has_parent]
    detail, summary = build_bom(record)
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": DATASET_NAME,
        "generator_version": __version__,
        "id": record.id,
        "subset": record.subset,
        "title": record.title,
        "seed": record.seed,
        "cabinet": record.cabinet,
        "circuit_kind": record.circuit_kind,
        "voltage": record.voltage,
        "alias": record.alias,
        "interlock": record.interlock,
        "degradation": record.degradation,
        "notes": record.notes,
        "standards": STANDARDS,
        "sheet": {
            "width_mm": SHEET_W,
            "height_mm": SHEET_H,
            "px_per_mm": PX_PER_MM,
            "image_width": img_w,
            "image_height": img_h,
        },
        "instances": instances,
        "netlist": {"nodes": nodes, "edges": edges, "children": children, "roots": roots},
        "control_branches": [
            {
                "id": branch.id,
                "coil_tag": branch.coil_tag,
                "pair_tag": branch.pair_tag,
                "series_ids": list(branch.series_ids),
            }
            for branch in record.control_branches
        ],
        "logic": record.logic,
        "bom": detail,
        "bom_summary": summary,
        "defects": findings,
        "_node_ids": node_ids,
    }


def write_json(path: Path, payload: dict) -> None:
    body = {key: value for key, value in payload.items() if not key.startswith("_")}
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            if isinstance(out.get("tags"), list):
                out["tags"] = " ".join(out["tags"])
            writer.writerow(out)


def write_yolo(path: Path, payload: dict) -> None:
    img_w = payload["sheet"]["image_width"]
    img_h = payload["sheet"]["image_height"]
    lines = []
    for inst in payload["instances"]:
        x, y, w, h = inst["bbox_px"]
        cx = (x + w / 2) / img_w
        cy = (y + h / 2) / img_h
        lines.append(f"{inst['class_id']} {cx:.6f} {cy:.6f} {w / img_w:.6f} {h / img_h:.6f}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def coco_categories() -> list[dict]:
    from .catalog import CLASSES

    return [
        {"id": item.class_id, "name": item.code, "supercategory": item.supercategory}
        for item in CLASSES
    ]


def coco_for_drawing(payload: dict, image_id: int, file_name: str) -> dict:
    annotations = []
    for index, inst in enumerate(payload["instances"], start=1):
        x, y, w, h = inst["bbox_px"]
        annotations.append(
            {
                "id": index,
                "image_id": image_id,
                "category_id": inst["class_id"],
                "bbox": [x, y, w, h],
                "area": round(w * h, 2),
                "iscrowd": 0,
                "attributes": {"tag": inst["tag"], "instance_id": inst["id"]},
            }
        )
    return {
        "info": {"description": DATASET_NAME, "version": SCHEMA_VERSION},
        "licenses": [{"id": 1, "name": "CC-BY-4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}],
        "images": [
            {
                "id": image_id,
                "file_name": file_name,
                "width": payload["sheet"]["image_width"],
                "height": payload["sheet"]["image_height"],
            }
        ],
        "annotations": annotations,
        "categories": coco_categories(),
    }


DETAIL_FIELDS = [
    "line_no",
    "instance_id",
    "tag",
    "class_code",
    "bom_letter",
    "name_zh",
    "model",
    "spec",
    "qty",
    "unit",
    "circuit",
]
SUMMARY_FIELDS = ["line_no", "bom_letter", "name_zh", "model", "spec", "qty", "unit", "tags"]
