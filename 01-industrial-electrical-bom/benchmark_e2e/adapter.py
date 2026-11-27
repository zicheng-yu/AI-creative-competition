"""Only drawing assets cross the inference boundary."""

from contextlib import contextmanager
from copy import deepcopy
from math import dist, hypot
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np
from PIL import Image, ImageFilter
import pymupdf

from compliance.engine import evaluate
from compliance.kg import cable_table, material_code
from compliance.normalize import normalize_instance
from compliance.repairs import apply_fix, bom_rows
from compliance.topology import Drawing
from netlist import build_bom, reconstruct
from symbol_parser.engine import parse_drawing
from symbol_parser.labels import specs as parse_specs, split_tag

SUFFIXES = frozenset({".dxf", ".png", ".pdf"})
SCORING_FILES = {"annotations.json", "bom.csv", "bom_summary.csv", "manifest.json",
                 "coco.json", "labels.txt", "electrobench_coco.json", "classes.txt"}
CONTROL = frozenset({"KA_COIL", "KA_NO", "KA_NC", "KM_COIL", "KM_NO", "KM_NC",
                     "KT_COIL", "KT_NO", "FR_NC", "TC", "HL", "HA", "SB_NO", "SB_NC",
                     "SA", "SQ", "XT", "YC", "YO"})
BUS_SPEC = re.compile(
    r"(?:(?:TMY|LMY)(?:\s*[-–]?\s*\d+(?:\.\d+)?\s*[×xX*]\s*\d+(?:\.\d+)?)?"
    r"|(?:铜排|铝排)\s*\d+(?:\.\d+)?\s*[×xX*]\s*\d+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?\s*[×xX*]\s*\d+(?:\.\d+)?\s*(?:mm)?\s*(?:铜排|铝排))",
    re.IGNORECASE,
)


@contextmanager
def source_only(path):
    """Stage exactly one asset under a neutral name, with no annotation siblings."""
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in SUFFIXES or source.resolve().name.lower() in SCORING_FILES:
        raise ValueError("inference accepts only original DXF, PNG or PDF assets")
    with source.open("rb") as stream:
        header = stream.read(256)
    signatures = {".png": b"\x89PNG\r\n\x1a\n", ".pdf": b"%PDF-"}
    valid = header.startswith(signatures[suffix]) if suffix in signatures else b"SECTION" in header
    if not valid:
        raise ValueError("drawing content does not match its format")
    with TemporaryDirectory(prefix="source-", dir=Path(__file__).parent) as temporary:
        staged = Path(temporary) / ("drawing" + suffix)
        shutil.copyfile(source, staged)
        yield staged


def _mid(bbox):
    x, y, w, h = bbox
    return x + w / 2, y + h / 2


def prepare_raster(asset):
    """Enhance pale PNG ink without translating, rotating or resizing the sheet."""
    if asset.suffix.lower() != ".png":
        return asset, None
    with Image.open(asset) as source:
        rgba = source.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        gray_image = background.convert("L")
    gray = np.asarray(gray_image)
    minimum = int(gray.min())
    dark_tail, low, high = (float(v) for v in np.percentile(gray, [0.1, 1, 99]))
    low_ink = minimum >= 25 or (low >= 100 and dark_tail >= 30)
    info = {"applied": False, "min_gray": minimum, "p01_gray": low}
    if not low_ink or high - low < 12:
        return asset, info
    # Recover edges before clipping so adjacent glyph strokes retain their
    # separation. A low ink percentile avoids thickening a whole text line.
    sharp = gray_image.filter(ImageFilter.UnsharpMask(radius=1.6, percent=220, threshold=1))
    clip_low, clip_high = (float(v) for v in np.percentile(np.asarray(sharp), [0.1, 99]))
    if clip_high <= clip_low:
        clip_low, clip_high = dark_tail, high
    stretch = np.clip((np.arange(256, dtype=float) - clip_low) * 255 / (clip_high - clip_low), 0, 255)
    restored = sharp.point(np.rint(stretch).astype(int).tolist())
    enhanced = asset.with_name("enhanced.png")
    restored.save(enhanced)
    return enhanced, info | {"applied": True, "clip_low_gray": clip_low, "clip_high_gray": clip_high}


def _point_to_box(point, bbox):
    px, py = point
    x, y, w, h = bbox
    return hypot(max(x-px, px-x-w, 0), max(y-py, py-y-h, 0))


def _bind_bus_specs(sheet):
    """Associate visible bus material labels with the nearest unfilled bus."""
    used = {tuple(mark["bbox_top_left"]) for item in sheet["symbols"]
            for mark in item.get("evidence", {}).values() if "bbox_top_left" in mark}
    scale = sheet["coordinate_space"].get("stencil_pixels_per_mm") or 1
    candidates = []
    for bus in sheet["symbols"]:
        if bus["class_code"] != "WB" or bus["specs"].get("spec"):
            continue
        bbox = bus["bbox_top_left"]
        if bbox[2] < 5 * bbox[3]:
            continue
        for mark in sheet["source_text"]:
            box = tuple(mark["bbox_top_left"])
            if box in used or not BUS_SPEC.fullmatch(mark["text"].strip()):
                continue
            distance = _point_to_box(_mid(box), bbox)
            if distance <= 15 * scale:
                candidates.append((distance, bus["id"], box, bus, mark))
    for _, _, box, bus, mark in sorted(candidates, key=lambda candidate: candidate[:3]):
        if box in used or bus["specs"].get("spec"):
            continue
        bus["specs"].update(parse_specs(mark["text"], bus["specs"].get("model", "")))
        bus.setdefault("evidence", {})["spec"] = {"raw_text": mark["text"], "bbox_top_left": list(box)}
        used.add(box)


def _repair_voltage_tag(sheet):
    """Disambiguate a coil's visible AC/DC rating from a nearby reference label."""
    used = {s["tag"] for s in sheet["symbols"]}
    choices = [(m, p) for m in sheet["source_text"]
               if (p := split_tag(m["text"])) and p[1] not in used]
    for part in sheet["symbols"]:
        if part["class_code"] not in {"YC", "YO"} or not re.search(r"(?:AC|DC)\d+V$", part["tag"]):
            continue
        box = part["bbox_top_left"]
        scale = sheet["coordinate_space"].get("stencil_pixels_per_mm") or 1
        candidates = [(dist(_mid(m["bbox_top_left"]), _mid(box)), m, p)
                      for m, p in choices if p[0] == part["class_code"] and p[1] not in used
                      and re.fullmatch(r"(?:YC|YO)\d+", p[1])]
        if not candidates:
            continue
        distance, mark, parsed = min(candidates, key=lambda row: row[0])
        if distance > 21 * scale:
            continue
        rating = part["evidence"].get("tag", {}).get("raw_text", "")
        used.add(parsed[1])
        part["tag"] = parsed[1]
        if rating:
            part["specs"].update(parse_specs(rating, part["specs"].get("model", "")))
            part["evidence"]["spec"] = part["evidence"]["tag"]
        part["evidence"]["tag"] = {"raw_text": mark["text"], "bbox_top_left": mark["bbox_top_left"]}


def _observations(sheet, kg):
    _repair_voltage_tag(sheet)
    _bind_bus_specs(sheet)
    for item in sheet["symbols"]:
        raw = item.get("evidence", {})
        item["raw_spec"] = raw.get("spec", {}).get("raw_text", item["specs"].get("spec", ""))
        raw_tag = raw.get("tag", {}).get("raw_text", "")
        # A combined tag/spec mark can contain both fields.
        parsed = split_tag(raw_tag)
        if parsed and parsed[2] and raw.get("spec") == raw.get("tag"):
            item["raw_spec"] = parsed[2]
        if not kg and parsed:
            item["tag"] = raw_tag.split()[0]
            if item["raw_spec"]:
                item["specs"]["spec"] = item["raw_spec"]
        if not kg:
            continue
        normalized = normalize_instance(item)
        item.update(normalized)
        spec = item["specs"]
        if "Icu_kA" in spec:
            spec.setdefault("icu_kA", spec["Icu_kA"])
        if item["class_code"] != "WL":
            continue
        material = material_code(spec.get("material"))
        if material and spec.get("model") in {"YJV", "YJLV"}:
            iz = cable_table(material).get(spec.get("section_mm2"))
            if iz is not None:
                spec["Iz_A"] = iz
                item["extra"]["ampacity_source"] = "ElectroBench screening table"


def _cad_dimensions(sheet):
    space = sheet["coordinate_space"]
    if space.get("insunits") != 4:
        return None, None
    # Recover the sheet by its outer drawing frame and the observed margins.
    outer = [part for part in sheet["primitives"] if part["layer"].upper() == "TITLE"
             and part["type"] in {"LWPOLYLINE", "POLYLINE"}]
    if not outer:
        return None, None
    points = max(outer, key=lambda part: len(part["points"]))["points"]
    xs, ys = zip(*points)
    if min(xs) < 0 or min(ys) < 0 or max(xs) <= min(xs) or max(ys) <= min(ys):
        return None, None
    return max(xs) + min(xs), max(ys) + min(ys)


def coordinate_space(sheet):
    space = sheet["coordinate_space"]
    if sheet["channel"] == "dxf-vector":
        width, height = _cad_dimensions(sheet)
        return width, height, 4
    return space["width"], space["height"], space["stencil_pixels_per_mm"] or 4


def _compliance_input(sheet, graph, metadata):
    width, height, scale = coordinate_space(sheet)
    native = sheet["channel"] == "dxf-vector"
    instances = []
    for symbol in sheet["symbols"]:
        x, y, w, h = symbol["bbox"]
        item = {k: deepcopy(v) for k, v in symbol.items() if k != "evidence"}
        if native:
            item["bbox_mm"] = [x, y, w, h]
            item["bbox_px"] = [x * scale, (height-y-h)*scale, w*scale, h*scale] if height else None
        else:
            item["bbox_px"] = deepcopy(symbol["bbox_top_left"])
            item["bbox_mm"] = [x/scale, y/scale, w/scale, h/scale]
            item["ports"] = {name: [v/scale for v in point] for name, point in item["ports"].items()}
        instances.append(item)
    netlist = deepcopy(graph)
    if not native:
        # Keep geometric fields in the same millimetre space as the port map.
        for node in netlist["nodes"]:
            node["ports"] = {name: [v/scale for v in pt] for name, pt in node["ports"].items()}
            if node.get("bbox") is not None:
                node["bbox"] = [v/scale for v in node["bbox"]]
        for edge in netlist["edges"]:
            edge["points"] = [[v/scale for v in pt] for pt in edge["points"]]
            for part in edge["route"]:
                part["points"] = [[v/scale for v in pt] for pt in part["points"]]
    data = {"schema_version": "1.0.0", "instances": instances, "netlist": netlist,
            "sheet": {"width_mm": width if native else width/scale,
                      "height_mm": height if native else height/scale, "px_per_mm": scale,
                      "image_width": width*scale if width and native else width,
                      "image_height": height*scale if height and native else height}, **metadata}
    return data


def _metadata(sheet):
    text = " ".join(mark["text"] for mark in sheet["source_text"])
    cabinet = re.search(r"(?<![A-Z0-9])(?:GGD|MNS|GCS|KYN28)(?![A-Z0-9])", text, re.I)
    voltage = re.search(r"\b(?:AC|DC)\s*\d+(?:\.\d+)?\s*k?V\b", text, re.I)
    return {"cabinet": cabinet[0].upper() if cabinet else None,
            "voltage": voltage[0] if voltage else None}


def _attach_cable_labels(sheet, graph):
    """Connect a detached cable callout to the vertically aligned protection stack."""
    symbols = {item["id"]: item for item in sheet["symbols"]}
    scale = sheet["coordinate_space"].get("stencil_pixels_per_mm") or 1
    edges = graph["edges"]
    active = {e[k] for e in edges if e["kind"] == "power" for k in ("source", "target")}
    if not active:
        return
    for label in sheet["symbols"]:
        if label["class_code"] != "WL" or label["id"] in active or not label["tag"]:
            continue
        x, y, _, height = label["bbox"]
        candidates = []
        output_class = {"QF", "FU", "ATS"}
        for node_id in active:
            other = symbols[node_id]
            port = other["ports"].get("out")
            if port and other["class_code"] in output_class and other["bbox"][2] <= 30 * scale:
                dx, dy = abs(x - port[0]), port[1] - (y + height/2)
                if dx <= 44 * scale and -2 * scale <= dy <= 150 * scale:
                    candidates.append((2.5 * dx + 0.15 * dy, node_id))
        candidates.sort()
        if not candidates or (len(candidates) > 1 and candidates[1][0] - candidates[0][0] < 3 * scale):
            continue
        _, protector_id = candidates[0]
        protector = symbols[protector_id]
        # A two-input transfer switch protects the downstream relationship as an
        # assembly when the callout lies immediately beside its output.
        label["circuit"] = label["tag"]
        protector.setdefault("circuit", label["tag"])
        edges.append({"id": f"label-{label['id']}", "source": protector_id, "target": label["id"],
                      "kind": "power", "source_port": "out", "target_port": "in",
                      "points": [], "route": [], "origin": "visible_cable_callout"})


def _adapt_edges(sheet, graph):
    """Electrical power/measurement semantics layered on geometric connections."""
    symbols = {i["id"]: i for i in sheet["symbols"]}
    result = []
    seen = set()
    for edge in graph["edges"]:
        left, right = symbols[edge["source"]], symbols[edge["target"]]
        a, b = edge["source_port"], edge["target_port"]
        codes = {left["class_code"], right["class_code"]}
        if codes == {"WB", "TV"}:
            edge["kind"] = "branch"
            if right["class_code"] == "WB":
                edge["source"], edge["target"] = edge["target"], edge["source"]
                edge["source_port"], edge["target_port"] = b, a
                edge["points"] = edge["points"][::-1]
                edge["route"] = [part | {"points": part["points"][::-1]} for part in edge["route"][::-1]]
        elif "QE" in codes and "QS" in codes:
            edge["kind"] = "power"
        elif edge["kind"] == "pe" and codes & {"QE", "SPD"}:
            edge["kind"] = "power"  # auxiliary earthing branch endpoints in the board topology
        # Shared input/return terminals are one electrical junction, not a
        # series dependency from one device to the other.
        if edge["kind"] == "power" and a.startswith("in") and b.startswith("in"):
            continue
        key = (edge["source"], edge["target"], edge["kind"])
        if key not in seen:
            seen.add(key)
            result.append(edge)
    graph["edges"] = result
    _attach_cable_labels(sheet, graph)
    children = {}
    for e in graph["edges"]:
        if e["kind"] == "power":
            children.setdefault(e["source"], set()).add(e["target"])
    graph["children"] = {k: sorted(v) for k, v in sorted(children.items())}
    targets = {n for downstream in children.values() for n in downstream}
    graph["roots"] = sorted(n["id"] for n in graph["nodes"] if n["id"] not in targets)


def _pdf_wires(path, sheet, destination):
    """Render the same native PDF page for wire extraction in parser pixel space."""
    zoom = sheet["coordinate_space"]["raster_pixels_per_pdf_point"]
    with pymupdf.open(path) as document:
        pixels = document[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom),
                                        colorspace=pymupdf.csGRAY, alpha=False)
    pixels.save(destination)
    return destination


def reconstruct_sheet(path, sheet):
    for key in ("text_boxes", "port_tolerance", "tolerance", "pixels_per_unit", "file"):
        sheet.pop(key, None)
    native = sheet["channel"] == "dxf-vector"
    sheet["file"] = str(path)
    if not native:
        image = Path(path)
        if image.suffix.lower() == ".pdf":
            image = _pdf_wires(image, sheet, image.with_name("wire-render.png"))
        with Image.open(image) as raster:
            size = raster.size
            width, height, _scale = coordinate_space(sheet)
            if size != (width, height):
                resized = image.with_name("wire-resized.png")
                raster.resize((width, height)).save(resized)
                image = resized
        sheet["file"] = str(image)
        sheet["pixels_per_unit"] = 1
        sheet["port_tolerance"] = 5
        sheet["tolerance"] = 0.3
        height = sheet["coordinate_space"]["height"]
        sheet["text_boxes"] = [(x, height-y-h, w, h) for mark in sheet["source_text"]
                               for x, y, w, h in [mark["bbox_top_left"]]]
    graph = reconstruct({"sheets": [sheet]})
    _adapt_edges(sheet, graph)
    return graph


def predict(path, *, topology=reconstruct_sheet, kg=True, parser=parse_drawing, enhance=True):
    """Run one registered lane and time each actual phase."""
    with source_only(path) as asset:
        started = perf_counter()
        asset, preprocessing = prepare_raster(asset) if enhance else (asset, None)
        payload = parser(asset)
        if len(payload["sheets"]) != 1:
            raise ValueError("the frozen benchmark expects a single sheet")
        sheet = payload["sheets"][0]
        _observations(sheet, kg)
        metadata = _metadata(sheet)
        parsed = perf_counter()
        graph = topology(asset, sheet)
        bom = build_bom({"sheets": [sheet]})
        adapted = _compliance_input(sheet, graph, metadata)
        rebuilt_details, rebuilt_totals = bom_rows(Drawing(adapted)) if kg else ([], [])
        adapted.update(bom=rebuilt_details, bom_summary=rebuilt_totals)
        connected = perf_counter()
        compliance = evaluate(adapted) if kg else None
        finished = perf_counter()
    return {"channel": sheet["channel"], "coordinate_space": sheet["coordinate_space"],
            "symbols": sheet["symbols"], "graph": graph, "bom": bom, "compliance": compliance,
            "annotation": adapted, "warnings": sheet.get("warnings", []),
            "raster_preprocessing": preprocessing,
            "timing": {"parse_s": parsed-started, "topology_s": connected-parsed,
                       "compliance_s": finished-connected if kg else 0.0,
                       "total_s": finished-started}}


def preview_fix(prediction, finding):
    patched = apply_fix(prediction["annotation"], finding["fix_suggestion"])
    return evaluate(patched)
