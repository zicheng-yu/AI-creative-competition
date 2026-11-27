"""Build the frozen sample volume and optional seeded random drawings."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from . import DATASET_NAME, SCHEMA_VERSION, __version__
from .catalog import CLASSES
from .degrade import BLUR_RADIUS, SKEW_DEG, blur_image, skew_image, transform_box
from .export import (
    DETAIL_FIELDS,
    SUMMARY_FIELDS,
    coco_categories,
    coco_for_drawing,
    serialize,
    write_csv,
    write_json,
    write_yolo,
)
from .glyphs import require_font
from .primary import build_gcs, build_ggd, build_kyn28, build_mns, build_random_primary
from .render import render_drawing
from .secondary import build_ats, build_dol, build_reversing

PUBLISHED_SEED = 262


def sample_records(seed: int):
    records = [
        build_ggd(seed),
        build_mns(seed),
        build_gcs(seed),
        build_kyn28(seed),
        build_dol(seed),
        build_reversing(seed),
        build_ats(seed),
        build_ggd(seed, inverted=True, drawing_id="EBJS-D-SEL-001", subset="defect"),
        build_ggd(seed, thin_cable=True, drawing_id="EBJS-D-AMP-002", subset="defect"),
        build_mns(seed, missing_fr=True, drawing_id="EBJS-D-MOT-003", subset="defect"),
        build_reversing(seed, interlock=False, drawing_id="EBJS-D-ILK-004", subset="defect"),
        build_ggd(seed, alias=True, drawing_id="EBJS-G-ALIAS-003", subset="degraded"),
    ]
    records[-1].degradation = {
        "type": "alias",
        "source_template": "EBJS-P-GGD-001",
        "description": "图面文字改为非标简写，class_code 与 specs 仍是规范真值",
    }
    return records


def _write_drawing(record, folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    dxf_path = folder / "drawing.dxf"
    png_path = folder / "drawing.png"
    pdf_path = folder / "drawing.pdf"
    record.doc.saveas(dxf_path)
    img_w, img_h = render_drawing(record.doc, png_path, pdf_path)
    payload = serialize(record, img_w, img_h)
    _write_sidecars(folder, payload, relative_png="drawing.png")
    return payload


def _write_sidecars(folder: Path, payload: dict, relative_png: str) -> None:
    write_json(folder / "annotations.json", payload)
    write_csv(folder / "bom.csv", payload["bom"], DETAIL_FIELDS)
    write_csv(folder / "bom_summary.csv", payload["bom_summary"], SUMMARY_FIELDS)
    write_yolo(folder / "labels.txt", payload)
    coco = coco_for_drawing(payload, 1, relative_png)
    write_json(folder / "coco.json", coco)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _degrade_from(source: dict, source_png: Path, folder: Path, kind: str, drawing_id: str) -> dict:
    import copy

    payload = copy.deepcopy(source)
    payload["id"] = drawing_id
    payload["subset"] = "degraded"
    payload["cabinet"] = source.get("cabinet")
    if kind == "blur":
        img_w, img_h = blur_image(source_png, folder / "drawing.png", BLUR_RADIUS)
        payload["degradation"] = {
            "type": "blur",
            "radius_px": BLUR_RADIUS,
            "source_id": source["id"],
            "description": "高斯模糊，模拟扫描发虚。框仍对应未位移的符号。",
        }
    elif kind == "skew":
        img_w, img_h = skew_image(source_png, folder / "drawing.png", SKEW_DEG)
        src_w = source["sheet"]["image_width"]
        src_h = source["sheet"]["image_height"]
        for inst in payload["instances"]:
            transformed, new_w, new_h = transform_box(inst["bbox_px"], SKEW_DEG, src_w, src_h)
            inst["bbox_px_source"] = inst["bbox_px"]
            inst["bbox_px"] = transformed
            img_w, img_h = new_w, new_h
        payload["degradation"] = {
            "type": "skew",
            "angle_deg": SKEW_DEG,
            "source_id": source["id"],
            "source_image_width": src_w,
            "source_image_height": src_h,
            "description": "整图逆时针微旋，模拟扫描倾斜。bbox_px 已随旋转更新。",
        }
    else:
        raise ValueError(kind)
    payload["sheet"]["image_width"] = img_w
    payload["sheet"]["image_height"] = img_h
    payload["notes"] = list(source.get("notes") or []) + [payload["degradation"]["description"]]
    _write_sidecars(folder, payload, relative_png="drawing.png")
    return payload


def _stats(payloads: list[dict]) -> str:
    by_subset: dict[str, int] = {}
    class_counts: dict[str, int] = {}
    defect_counts: dict[str, int] = {}
    for payload in payloads:
        by_subset[payload["subset"]] = by_subset.get(payload["subset"], 0) + 1
        for inst in payload["instances"]:
            class_counts[inst["class_code"]] = class_counts.get(inst["class_code"], 0) + 1
        for finding in payload["defects"]:
            defect_counts[finding["rule_id"]] = defect_counts.get(finding["rule_id"], 0) + 1
    lines = [
        f"# {DATASET_NAME} 样例统计",
        "",
        f"- 规范版本：`{SCHEMA_VERSION}`",
        f"- 生成器：`{__version__}`",
        f"- 图纸数：{len(payloads)}",
        f"- 符号实例：{sum(class_counts.values())}",
        f"- 符号类别：{len(class_counts)} / 目录 {len(CLASSES)}",
        "",
        "## 分层",
        "",
    ]
    for name in ("primary", "secondary", "defect", "degraded"):
        lines.append(f"- {name}: {by_subset.get(name, 0)}")
    lines.extend(["", "## 缺陷规则命中（条）", ""])
    for rule in (
        "selectivity_inversion",
        "ampacity_insufficient",
        "motor_protection_missing",
        "interlock_missing",
    ):
        lines.append(f"- {rule}: {defect_counts.get(rule, 0)}")
    lines.extend(["", "## 类别计数", ""])
    for item in CLASSES:
        lines.append(f"- `{item.code}` {item.name_zh}: {class_counts.get(item.code, 0)}")
    lines.append("")
    return "\n".join(lines)


def generate(out_dir: Path, *, preset: str = "sample", seed: int = PUBLISHED_SEED, count: int = 2) -> dict:
    require_font()
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    if preset == "sample":
        records = sample_records(seed)
    elif preset == "random":
        records = build_random_primary(seed, count)
    else:
        raise SystemExit(f"unknown preset {preset}")

    payloads = []
    folders = []
    for record in records:
        folder = out_dir / record.subset / record.id
        payloads.append(_write_drawing(record, folder))
        folders.append(folder)

    if preset == "sample":
        by_id = {payload["id"]: (payload, folder) for payload, folder in zip(payloads, folders)}
        ggd_payload, ggd_folder = by_id["EBJS-P-GGD-001"]
        dol_payload, dol_folder = by_id["EBJS-S-DOL-001"]
        blur = _degrade_from(ggd_payload, ggd_folder / "drawing.png", out_dir / "degraded" / "EBJS-G-BLUR-001", "blur", "EBJS-G-BLUR-001")
        skew = _degrade_from(dol_payload, dol_folder / "drawing.png", out_dir / "degraded" / "EBJS-G-SKEW-002", "skew", "EBJS-G-SKEW-002")
        payloads.extend([blur, skew])

    images = []
    annotations = []
    ann_id = 1
    manifest_drawings = []
    for image_id, payload in enumerate(payloads, start=1):
        folder = out_dir / payload["subset"] / payload["id"]
        file_name = f"{payload['subset']}/{payload['id']}/drawing.png"
        coco = coco_for_drawing(payload, image_id, file_name)
        images.extend(coco["images"])
        for ann in coco["annotations"]:
            ann["id"] = ann_id
            ann_id += 1
            annotations.append(ann)
        manifest_drawings.append(
            {
                "id": payload["id"],
                "subset": payload["subset"],
                "title": payload["title"],
                "defects": sorted({item["rule_id"] for item in payload["defects"]}),
                "degradation": None if not payload.get("degradation") else payload["degradation"]["type"],
                "instances": len(payload["instances"]),
                "annotations_sha256": _sha256(folder / "annotations.json"),
            }
        )
    combined = {
        "info": {"description": DATASET_NAME, "version": SCHEMA_VERSION},
        "licenses": [{"id": 1, "name": "CC-BY-4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}],
        "images": images,
        "annotations": annotations,
        "categories": coco_categories(),
    }
    write_json(out_dir / "electrobench_coco.json", combined)
    (out_dir / "classes.txt").write_text("\n".join(item.code for item in CLASSES) + "\n", encoding="utf-8")
    stats = _stats(payloads)
    (out_dir / "STATS.md").write_text(stats, encoding="utf-8")
    manifest = {
        "dataset": DATASET_NAME,
        "schema_version": SCHEMA_VERSION,
        "generator_version": __version__,
        "preset": preset,
        "seed": seed,
        "drawings": manifest_drawings,
    }
    write_json(out_dir / "manifest.json", manifest)
    return manifest
