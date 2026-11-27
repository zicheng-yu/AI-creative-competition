"""Comparison lanes with explicit differences in routing and processing."""

from dataclasses import dataclass
from math import hypot
from pathlib import Path
import re

from electrobench.catalog import BY_CODE
from symbol_parser.engine import _read_image
from symbol_parser.raster import read_ocr

from .adapter import CONTROL, predict, reconstruct_sheet

TAG = re.compile(r"^(QF|QS|QE|KM|KA|KT|FR|FU|TA|TV|SPD|TC|T|M|PA|PV|PJ|C|L|HL|HA|SB|SA|SQ|XT|WB|YC|YO|ATS|WL)([A-Z]?\d{1,5}|[FR])(?:\s+(.+))?$")
RATING = re.compile(r"\d\s*(?:[aA]|V|kW|kA|[P极])\b|[YVJ][A-Z]{1,6}-")
GENERIC = {"KM": "KM_MAIN", "KA": "KA_COIL", "KT": "KT_COIL", "SB": "SB_NO"}


@dataclass(frozen=True)
class Lane:
    id: str
    title: str
    format: str
    kg: bool = True
    topology: str = "reconstruct"
    scope: str = "all"


LANES = (
    Lane("full", "Full 完整系统", "auto"),
    Lane("dxf", "纯 DXF", "dxf", scope="main"),
    Lane("png", "A1 全光栅", "png"),
    Lane("pdf", "纯 PDF", "pdf", scope="main"),
    Lane("b1", "B1 OCR 正则", "png", False, "none"),
    Lane("b2", "B2 纯光栅", "png", False, "nearest"),
    Lane("no_topology", "A2 朴素连线", "dxf", True, "nearest", "main"),
    Lane("no_kg", "A3 去 KG", "dxf", False, "reconstruct", "main"),
    Lane("degraded_no_kg", "退化 PNG 去 KG", "png", False, "reconstruct", "degraded"),
)


def originals(directory):
    directory = Path(directory)
    return {kind: path for kind in ("dxf", "png", "pdf")
            if (path := directory / ("drawing." + kind)).is_file()}


def asset_for(lane, assets):
    if lane.format == "auto":
        return assets.get("dxf") or assets.get("png") or assets.get("pdf")
    return assets.get(lane.format)


def _empty_graph(_path, _sheet):
    return {"nodes": [], "edges": [], "children": {}, "roots": [], "circuits": [], "warnings": []}


def _nearest_graph(_path, sheet):
    """Connect nearest compatible output to input along reading direction.

    No pixel/spline tracing, junction detection, or connectivity through a bus.
    """
    graph = _empty_graph(_path, sheet)
    scale = sheet["coordinate_space"].get("stencil_pixels_per_mm") or 1
    items = [i for i in sheet["symbols"] if i.get("in_netlist")]
    graph["nodes"] = [{k: i[k] for k in ("id", "tag", "class_code", "ports", "bbox")} for i in items]
    for origin in items:
        for port, (x, y) in origin["ports"].items():
            if not port.startswith(("out", "tap", "right")):
                continue
            control = origin["class_code"] in CONTROL or port == "right"
            choices = []
            for target in items:
                if target is origin:
                    continue
                for incoming, (xx, yy) in target["ports"].items():
                    if not incoming.startswith(("in", "left", "src")):
                        continue
                    longitudinal, lateral = (xx-x, abs(yy-y)) if control else (y-yy, abs(xx-x))
                    if 0 < longitudinal <= 33*scale and lateral <= 6*scale:
                        choices.append((hypot(longitudinal, 2*lateral), target["id"], incoming, xx, yy,
                                        target["class_code"]))
            if not choices:
                continue
            _, target, incoming, xx, yy, code = min(choices)
            kind = ("pe" if code == "PE" else "branch" if code in {"PA", "PV", "PJ"}
                    else "control" if control or code in CONTROL else "power")
            graph["edges"].append(dict(id=f"near-{len(graph['edges'])+1}", source=origin["id"],
                                       target=target, source_port=port, target_port=incoming, kind=kind,
                                       origin="geometric_nearest", points=[[x, y], [xx, yy]], route=[]))
    return graph


def ocr_template(path):
    """B1 outputs OCR text boxes, not component localization proposals."""
    image, size = _read_image(path)
    height, width = image.shape
    marks = read_ocr(image)
    symbols = []
    for mark in marks:
        match = TAG.fullmatch(mark.text.strip())
        if not match:
            continue
        prefix, suffix, text = match.groups()
        x, y, w, h = mark.bbox
        if not text:
            below = [(other.bbox[1]-y + abs(other.bbox[0]-x), other.text) for other in marks
                     if 0 < other.bbox[1]-y <= 24 and abs(other.bbox[0]-x) <= 12
                     and RATING.search(other.text) and not TAG.fullmatch(other.text)]
            text = min(below)[1] if below else ""
        code = GENERIC.get(prefix, prefix)
        definition = BY_CODE[code]
        attributes = {"spec": text} if text else {}
        if (model := re.search(r"\b(?:YJV|YJLV|NSX|C65N|NXB|NXM)[-\w]*", text)) is not None:
            attributes["model"] = model[0].split("-")[0]
        for key, match_pattern in (("In_A", r"(?<![A-Za-z])In\s*=?\s*(\d+(?:\.\d+)?)\s*A\b"),
                                   ("poles", r"\b([1-4])\s*[P极]\b")):
            match_value = re.search(match_pattern, text, re.I)
            if match_value:
                attributes[key] = float(match_value[1])
        symbols.append({"class_code": code, "id": f"text-{len(symbols)+1}", "tag": prefix+suffix,
                        "name_zh": definition.name_zh, "unit": definition.unit, "specs": attributes,
                        "bbox": [x, height-y-h, w, h], "bbox_top_left": [x,y,w,h], "ports": {},
                        "bom_anchor": definition.default_bom_anchor, "in_netlist": False,
                        "evidence": {"spec": {"raw_text": text}}})
    return {"sheets": [{"id": "sheet", "channel": "ocr-template", "symbols": symbols,
                        "source_text": [{"text": m.text, "bbox_top_left": m.bbox} for m in marks],
                        "coordinate_space": {"width": width, "height": height, "source_pixels": size,
                                             "stencil_pixels_per_mm": max(width, height)/420}}]}


def execute(path, lane):
    if lane.topology == "none":
        return predict(path, topology=_empty_graph, kg=False, parser=ocr_template)
    topology = _nearest_graph if lane.topology == "nearest" else reconstruct_sheet
    return predict(path, topology=topology, kg=lane.kg)
