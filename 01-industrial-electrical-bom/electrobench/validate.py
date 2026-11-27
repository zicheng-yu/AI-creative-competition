"""Check that symbol classes, netlist nodes and BOM rollups describe one drawing."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image

from .canvas import SHEET_H, SHEET_W
from .catalog import BY_CODE, BY_ID, CLASSES
from .degrade import transform_box
from .logic import build_logic
from .model import ControlBranch, DrawingRecord, Edge, Instance
from .render import mm_box_to_px
from .rules import evaluate


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _record_from_json(data: dict) -> DrawingRecord:
    record = DrawingRecord(
        id=data["id"],
        subset=data["subset"],
        title=data["title"],
        seed=data["seed"],
        cabinet=data.get("cabinet"),
        circuit_kind=data.get("circuit_kind"),
        voltage=data["voltage"],
        sheet_w=data["sheet"]["width_mm"],
        sheet_h=data["sheet"]["height_mm"],
        logic=data.get("logic"),
        interlock=bool(data.get("interlock", True)),
        alias=bool(data.get("alias")),
        degradation=data.get("degradation"),
        notes=list(data.get("notes") or []),
    )
    for item in data["instances"]:
        record.instances.append(
            Instance(
                id=item["id"],
                tag=item["tag"],
                class_code=item["class_code"],
                bom_anchor=item["bom_anchor"],
                in_netlist=item["in_netlist"],
                bbox_mm=tuple(item["bbox_mm"]),
                ports={name: tuple(pt) for name, pt in item["ports"].items()},
                specs=item["specs"],
                label_tag=item["label_tag"],
                label_spec=item["label_spec"],
                circuit=item.get("circuit", ""),
                extra=item.get("extra") or {},
            )
        )
    for edge in data["netlist"]["edges"]:
        record.edges.append(
            Edge(
                id=edge["id"],
                source=edge["source"],
                target=edge["target"],
                kind=edge["kind"],
                points=[tuple(pt) for pt in edge["points"]],
                source_port=edge["source_port"],
                target_port=edge["target_port"],
            )
        )
    for branch in data.get("control_branches") or []:
        record.control_branches.append(
            ControlBranch(
                id=branch["id"],
                coil_tag=branch["coil_tag"],
                pair_tag=branch.get("pair_tag"),
                series_ids=list(branch["series_ids"]),
            )
        )
    return record


def _close(a: float, b: float, tol: float = 0.051) -> bool:
    return abs(a - b) <= tol


def validate_drawing(folder: Path, data: dict) -> list[str]:
    errors: list[str] = []
    drawing_id = data.get("id", folder.name)

    def fail(message: str) -> None:
        errors.append(f"{drawing_id}: {message}")

    if data.get("schema_version") != "1.0.0":
        fail("schema_version 不是 1.0.0")
    ids = [item["id"] for item in data["instances"]]
    if len(ids) != len(set(ids)):
        fail("实例 id 重复")
    by_id = {item["id"]: item for item in data["instances"]}
    sheet = data["sheet"]
    img_w, img_h = sheet["image_width"], sheet["image_height"]
    png = folder / "drawing.png"
    if not png.exists():
        fail("缺少 drawing.png")
    else:
        with Image.open(png) as image:
            if image.size != (img_w, img_h):
                fail(f"PNG 尺寸 {image.size} 与标注 {img_w}x{img_h} 不一致")
    degradation = data.get("degradation") or {}
    kind = degradation.get("type")
    if kind in (None, "alias", "blur"):
        for name in ("drawing.dxf", "drawing.pdf"):
            if kind in (None, "alias") and not (folder / name).exists():
                fail(f"缺少 {name}")
        if kind in (None, "alias") and (folder / "drawing.pdf").exists():
            if not (folder / "drawing.pdf").read_bytes().startswith(b"%PDF"):
                fail("PDF 文件头不是 %PDF")
    for inst in data["instances"]:
        symbol = BY_CODE.get(inst["class_code"])
        if symbol is None or symbol.class_id != inst["class_id"]:
            fail(f"{inst['id']} 类别 {inst['class_code']} 不在目录或 id 不一致")
            continue
        if BY_ID[inst["class_id"]].code != inst["class_code"]:
            fail(f"{inst['id']} class_id 与代号不一致")
        x, y, w, h = inst["bbox_mm"]
        if w <= 0 or h <= 0:
            fail(f"{inst['id']} 毫米框尺寸无效")
        if x < -1 or y < -1 or x + w > SHEET_W + 1 or y + h > SHEET_H + 1:
            fail(f"{inst['id']} 毫米框超出图幅 {inst['bbox_mm']}")
        px = inst["bbox_px"]
        if px[2] <= 0 or px[3] <= 0:
            fail(f"{inst['id']} 像素框尺寸无效")
        if px[0] < -1 or px[1] < -1 or px[0] + px[2] > img_w + 1.5 or px[1] + px[3] > img_h + 1.5:
            fail(f"{inst['id']} 像素框超出图像 {px}")
        if kind == "skew":
            expected, new_w, new_h = transform_box(
                inst["bbox_px_source"],
                degradation["angle_deg"],
                degradation["source_image_width"],
                degradation["source_image_height"],
            )
            if [round(v, 2) for v in expected] != [round(v, 2) for v in px]:
                fail(f"{inst['id']} 倾斜框与旋转公式不一致")
            if (new_w, new_h) != (img_w, img_h):
                fail("倾斜后图像尺寸与公式不一致")
        else:
            expected_px = mm_box_to_px(tuple(inst["bbox_mm"]), img_w, img_h)
            if expected_px != px:
                fail(f"{inst['id']} 像素框与毫米框换算不一致 {expected_px} != {px}")

    net_nodes = data["netlist"]["nodes"]
    node_ids = [node["id"] for node in net_nodes]
    expected_nodes = [inst["id"] for inst in data["instances"] if inst["in_netlist"]]
    if node_ids != expected_nodes:
        fail("Netlist 节点与 in_netlist 实例不一致")
    node_set = set(node_ids)
    for edge in data["netlist"]["edges"]:
        if edge["source"] not in node_set or edge["target"] not in node_set:
            fail(f"边 {edge['id']} 端点不在节点集中")
            continue
        src = by_id[edge["source"]]
        dst = by_id[edge["target"]]
        if edge["source_port"] not in src["ports"] or edge["target_port"] not in dst["ports"]:
            fail(f"边 {edge['id']} 端口名不存在")
            continue
        if not edge["points"]:
            fail(f"边 {edge['id']} 没有点列")
            continue
        start = edge["points"][0]
        end = edge["points"][-1]
        sp = src["ports"][edge["source_port"]]
        tp = dst["ports"][edge["target_port"]]
        if not (_close(start[0], sp[0]) and _close(start[1], sp[1]) and _close(end[0], tp[0]) and _close(end[1], tp[1])):
            fail(f"边 {edge['id']} 端点与端口坐标不一致")

    record = _record_from_json(data)
    recomputed = evaluate(record)
    if recomputed != data["defects"]:
        fail(f"缺陷真值与规则重算不一致: 标注 {data['defects']} 重算 {recomputed}")

    if data.get("logic"):
        kind_name = data["logic"]["kind"]
        interlock = data["logic"].get("interlock", True)
        if build_logic(kind_name, interlock=interlock) != data["logic"]:
            fail("逻辑真值表与方程重算不一致")
        if kind_name == "ats":
            both = [row for row in data["logic"]["rows"] if row["qf1_close"] and row["qf2_close"]]
            if both:
                fail("双电源真值表出现两侧同时合闸")

    known = set(by_id)
    for branch in data.get("control_branches") or []:
        missing = [item for item in branch["series_ids"] if item not in known]
        if missing:
            fail(f"控制支路 {branch['id']} 引用了不存在的实例 {missing}")

    anchors = [inst for inst in data["instances"] if inst["bom_anchor"]]
    bom = data["bom"]
    if len(bom) != len(anchors):
        fail(f"BOM 明细 {len(bom)} 行，锚点实例 {len(anchors)} 个")
    bom_ids = [row["instance_id"] for row in bom]
    anchor_ids = [inst["id"] for inst in anchors]
    if bom_ids != anchor_ids:
        fail("BOM 明细与锚点实例顺序或 id 不一致")
    for row, inst in zip(bom, anchors):
        symbol = BY_CODE[inst["class_code"]]
        if row["tag"] != inst["tag"] or row["bom_letter"] != symbol.bom_letter:
            fail(f"BOM 行 {row['instance_id']} 与实例代号不一致")
        if int(row["qty"]) != 1:
            fail(f"BOM 明细 {row['tag']} 数量不是 1")
        if row["spec"] != inst["specs"].get("spec", "") or row["model"] != inst["specs"].get("model", ""):
            fail(f"BOM 行 {row['tag']} 规格与实例 specs 不一致")
    grouped: dict[tuple, int] = {}
    for row in bom:
        key = (row["bom_letter"], row["name_zh"], row["model"], row["spec"], row["unit"])
        grouped[key] = grouped.get(key, 0) + int(row["qty"])
    summary_keys = []
    for row in data["bom_summary"]:
        key = (row["bom_letter"], row["name_zh"], row["model"], row["spec"], row["unit"])
        summary_keys.append(key)
        if grouped.get(key) != int(row["qty"]):
            fail(f"BOM 汇总 {key} 数量 {row['qty']} 与明细 {grouped.get(key)} 不一致")
    if len(summary_keys) != len(grouped):
        fail("BOM 汇总分组数量与明细不一致")

    detail_csv = _read_csv(folder / "bom.csv")
    if [row["instance_id"] for row in detail_csv] != bom_ids:
        fail("bom.csv 与 annotations.json 的明细不一致")
    summary_csv = _read_csv(folder / "bom_summary.csv")
    if [int(row["qty"]) for row in summary_csv] != [int(row["qty"]) for row in data["bom_summary"]]:
        fail("bom_summary.csv 与 annotations.json 的汇总不一致")

    coco = _load(folder / "coco.json")
    if len(coco["annotations"]) != len(data["instances"]):
        fail("COCO 标注条数与实例数不一致")
    if [item["name"] for item in coco["categories"]] != [item.code for item in CLASSES]:
        fail("COCO 类别表与目录不一致")
    for ann, inst in zip(coco["annotations"], data["instances"]):
        if ann["category_id"] != inst["class_id"] or ann["bbox"] != inst["bbox_px"]:
            fail(f"COCO 框与实例 {inst['id']} 不一致")
    yolo_lines = (folder / "labels.txt").read_text(encoding="utf-8").splitlines()
    if len(yolo_lines) != len(data["instances"]):
        fail("YOLO 行数与实例数不一致")
    for line, inst in zip(yolo_lines, data["instances"]):
        parts = line.split()
        if int(parts[0]) != inst["class_id"]:
            fail(f"YOLO 类别与实例 {inst['id']} 不一致")
        x, y, w, h = inst["bbox_px"]
        cx = (x + w / 2) / img_w
        cy = (y + h / 2) / img_h
        nums = [float(part) for part in parts[1:]]
        expected = [cx, cy, w / img_w, h / img_h]
        if any(abs(a - b) > 1e-4 for a, b in zip(nums, expected)):
            fail(f"YOLO 框与实例 {inst['id']} 不一致")
    return errors


def validate_dataset(root: Path) -> tuple[list[str], str]:
    root = Path(root)
    manifest = _load(root / "manifest.json")
    errors: list[str] = []
    payloads = []
    seen = set()
    for entry in manifest["drawings"]:
        folder = root / entry["subset"] / entry["id"]
        data = _load(folder / "annotations.json")
        if data["id"] != entry["id"]:
            errors.append(f"{entry['id']}: 标注 id 与 manifest 不一致")
        if data["id"] in seen:
            errors.append(f"{data['id']}: 图纸 id 重复")
        seen.add(data["id"])
        errors.extend(validate_drawing(folder, data))
        payloads.append(data)
    if manifest.get("preset") == "sample":
        present = {inst["class_code"] for data in payloads for inst in data["instances"]}
        missing = [item.code for item in CLASSES if item.code not in present]
        if missing:
            errors.append("样例卷未覆盖类别: " + ", ".join(missing))
        rules = {"selectivity_inversion", "ampacity_insufficient", "motor_protection_missing", "interlock_missing"}
        fired = {finding["rule_id"] for data in payloads for finding in data["defects"]}
        if fired != rules:
            errors.append(f"缺陷类型集合不是四类规则: {sorted(fired)}")
        for data in payloads:
            subset = data["subset"]
            count = len(data["defects"])
            if subset in {"primary", "secondary", "degraded"} and count:
                errors.append(f"{data['id']}: {subset} 子集不应含缺陷，实际 {count}")
            if subset == "defect" and count == 0:
                errors.append(f"{data['id']}: 缺陷子集没有任何缺陷")
    report = _report(manifest, payloads, errors)
    return errors, report


def _report(manifest: dict, payloads: list[dict], errors: list[str]) -> str:
    class_counts: dict[str, int] = {}
    defect_counts: dict[str, int] = {}
    for data in payloads:
        for inst in data["instances"]:
            class_counts[inst["class_code"]] = class_counts.get(inst["class_code"], 0) + 1
        for finding in data["defects"]:
            defect_counts[finding["rule_id"]] = defect_counts.get(finding["rule_id"], 0) + 1
    lines = [
        f"ElectroBench-JS validate preset={manifest.get('preset')} seed={manifest.get('seed')}",
        f"drawings={len(payloads)} instances={sum(class_counts.values())} classes={len(class_counts)}/{len(CLASSES)}",
        "subsets: "
        + ", ".join(
            f"{name}={sum(1 for item in payloads if item['subset'] == name)}"
            for name in ("primary", "secondary", "defect", "degraded")
        ),
        "defects: " + ", ".join(f"{key}={defect_counts.get(key, 0)}" for key in (
            "selectivity_inversion",
            "ampacity_insufficient",
            "motor_protection_missing",
            "interlock_missing",
        )),
        "RESULT: PASS" if not errors else f"RESULT: FAIL ({len(errors)})",
    ]
    lines.extend(errors[:30])
    return "\n".join(lines)
