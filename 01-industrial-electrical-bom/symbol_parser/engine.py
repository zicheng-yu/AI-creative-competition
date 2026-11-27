"""Route native DXF, digital PDF, and scanned drawings to their parsing paths."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path
from urllib.error import URLError

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageOps

from .labels import (
    CLASSES,
    Component,
    TextMark,
    bind_labels,
    check_rated_spec,
    normalize_spec,
    specs,
    split_tag,
)
from .raster import intersection_over_union, proposals, read_ocr, read_spec_line
from .vector import dxf_preview, pdf_marks, pdf_primitives, read_dxf

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def _estimate_scale(image):
    return round(max(1.0, min(image.shape) / 297.0), 3)


def _read_image(path):
    with Image.open(path) as image:
        rgba = ImageOps.exif_transpose(image).convert("RGBA")
        original_size = rgba.size
        white = Image.new("RGBA", rgba.size, "white")
        white.alpha_composite(rgba)
        if max(white.size) > 2800:
            white.thumbnail((2800, 2800))
        return np.asarray(white.convert("L")), original_size


def _text_features(components, marks, scale, image=None):
    seen = {
        component.label_anchor for component in components if component.label_anchor
    }
    for mark in marks:
        if mark in seen:
            continue
        label = split_tag(mark.text)
        x, y, w, h = mark.bbox
        code = None
        ports = {}
        if label and label[0] == "WL":
            code = "WL"
            h = max(h * 2.15, scale * 5.5)
            ports = {"in": (x, y + h * 0.43), "out": (x, y + h * 0.43)}
        elif label and label[0] == "WB" and image is not None:
            left = max(0, round(x - 4 * scale))
            top = max(0, round(y + h))
            bottom = min(image.shape[0], round(top + 8 * scale))
            area = image[top:bottom, left:]
            if area.size:
                lines = cv2.morphologyEx(
                    (area < 180).astype(np.uint8),
                    cv2.MORPH_OPEN,
                    np.ones((1, max(4, round(scale * 35))), np.uint8),
                )
                if lines.any():
                    row = int(np.argmax(lines.sum(axis=1)))
                    locations = np.flatnonzero(lines[row])
                    right = left + locations[-1]
                    x = left + locations[0]
                    code, y, w, h = (
                        "WB",
                        top + row - scale * 0.8,
                        right - x,
                        scale * 1.6,
                    )
        elif mark.text.isdecimal() and 1 <= len(mark.text) <= 3 and h <= scale * 4.5:
            code = "WIRE_NO"
            label = code, "W" + mark.text, ""
        if code:
            candidate = Component(
                code, (x, y, w, h), ports, mark.confidence * 0.9, "text-label"
            )
            candidate.tag = label[1]
            candidate.label_anchor = mark
            candidate.bindings["tag"] = mark
            components.append(candidate)


def _recover_ratings(components, marks, scale, image):
    pending = [
        item
        for item in components
        if item.label_anchor and not check_rated_spec(item.code, item.spec)
    ]
    for item in pending[:8]:
        x, y, w, h = item.label_anchor.bbox
        old = item.bindings.get("spec")
        if old:
            sx, sy, sw, sh = old.bbox
            window = sx - 2, sy - 1, sx + sw + 3, sy + sh + 1
        elif x + w < item.box[0] + scale:
            window = x + w - 36 * scale, y + h, x + w + 0.6 * scale, y + h + 3.8 * scale
        else:
            window = x - 0.7 * scale, y + h, x + 39 * scale, y + h + 3.8 * scale
        replacement = read_spec_line(image, window)
        if (
            replacement
            and not split_tag(replacement.text)
            and check_rated_spec(item.code, replacement.text)
        ):
            item.spec = normalize_spec(replacement.text)
            item.bindings["spec"] = replacement
            marks.append(replacement)


def _attach_text(components, marks, scale, image=None, retry_ocr=False):
    _text_features(components, marks, scale, image=image)
    bind_labels(components, marks, scale)
    if retry_ocr:
        _recover_ratings(components, marks, scale, image)
    for item in components:
        # The cable callout's footprint includes both rendered lines.
        if item.code != "WL" or "spec" not in item.bindings:
            continue
        x, y, w, h = item.box
        sx, sy, sw, sh = item.bindings["spec"].bbox
        left, top = min(x, sx), min(y, sy)
        item.box = left, top, max(x + w, sx + sw) - left, max(y + h, sy + sh) - top


def _record(component, frame, height):
    definition = CLASSES[component.code]
    bbox = component.box
    output = {
        "id": f"symbol-{frame:03d}",
        "class_code": component.code,
        "name_zh": definition["name_zh"],
        "tag": component.tag,
        "specs": specs(component.spec, component.model),
        "unit": definition["unit"],
        "bbox": [
            round(float(v), 4)
            for v in (bbox[0], height - bbox[1] - bbox[3], bbox[2], bbox[3])
        ],
        "bbox_top_left": [round(float(v), 4) for v in bbox],
        "ports": {
            key: [round(float(x), 4), round(float(height - y), 4)]
            for key, (x, y) in component.ports.items()
        },
        "confidence": round(component.confidence, 4),
        "source": component.source,
        "bom_anchor": definition["bom_anchor"],
        "in_netlist": definition["in_netlist"],
        "review_required": component.refined
        or component.confidence < 0.72
        or not check_rated_spec(component.code, component.spec)
        or (not component.tag and component.code not in {"PE", "WB"}),
        "vlm_refined": component.refined,
        "evidence": {
            key: {
                "raw_text": mark.text,
                "bbox_top_left": [round(float(v), 4) for v in mark.bbox],
                "confidence": round(mark.confidence, 4),
            }
            for key, mark in component.bindings.items()
        },
    }
    return output


def _page(
    components, marks, primitives, name, method, width, height, denominator, warnings
):
    ordered = sorted(components, key=lambda item: (item.box[1], item.box[0], item.code))
    records = [_record(item, index, height) for index, item in enumerate(ordered, 1)]
    raw_primitives = [
        {
            **primitive,
            "points": [
                [round(float(x), 4), round(float(height - y), 4)]
                for x, y in primitive["points"]
            ],
        }
        for primitive in primitives
    ]
    return {
        "id": name,
        "channel": method,
        "coordinate_space": {
            "origin": "drawing" if method == "dxf-vector" else "bottom_left",
            "unit": "dxf_unit" if method == "dxf-vector" else "px",
            "width": width,
            "height": height if width else None,
            "stencil_pixels_per_mm": denominator,
        },
        "symbols": records,
        "primitives": raw_primitives,
        "source_text": [
            {"text": m.text, "bbox_top_left": [round(float(v), 4) for v in m.bbox]}
            for m in marks
        ],
        "warnings": list(dict.fromkeys(warnings)),
    }


def _raster_marks(image, ocr, warnings):
    if ocr is None:
        warnings.append("ocr_disabled")
        return []
    try:
        return ocr(image)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        warnings.append(f"ocr_unavailable:{type(exc).__name__}")
        return []


def _refine(refiner, image, components, warnings, limit):
    if refiner is None:
        return
    pending = sorted(
        (
            item
            for item in components
            if item.code not in {"WIRE_NO", "PE"}
            and (
                item.confidence < 0.72
                or not check_rated_spec(item.code, item.spec)
                or not item.tag
                or any(mark.confidence < 0.6 for mark in item.bindings.values())
            )
        ),
        key=lambda item: item.confidence,
    )
    for item in pending[:limit]:
        try:
            refiner(image, item)
        except (URLError, TimeoutError, KeyError, TypeError, ValueError) as exc:
            warnings.append(f"vlm_unavailable:{type(exc).__name__}")
            if isinstance(exc, (URLError, TimeoutError)):
                break


def _visual_components(image, marks, scale, detector):
    return detector(image) if detector is not None else proposals(image, marks, scale)


def _vector_canvas(parts, marks):
    all_points = [point for part in parts for point in part["points"]]
    if not all_points:
        return None
    left = min(x for x, _ in all_points) - 3
    top = min(y for _, y in all_points) - 3
    width = max(x for x, _ in all_points) - left + 3
    height = max(y for _, y in all_points) - top + 3
    factor = min(4.0, 2000 / max(width, height))
    image = np.full(
        (round(height * factor), round(width * factor)), 255, dtype=np.uint8
    )
    for part in parts:
        points = np.asarray(
            [((x - left) * factor, (y - top) * factor) for x, y in part["points"]]
        )
        cv2.polylines(
            image, [np.rint(points).astype(np.int32)], False, 0, 1, cv2.LINE_AA
        )
    projected = [
        TextMark(
            mark.text,
            ((x - left) * factor, (y - top) * factor, w * factor, h * factor),
            mark.confidence,
        )
        for mark in marks
        for x, y, w, h in [mark.bbox]
    ]
    return image, projected, left, top, factor


def _dxf_components(path, detector, refiner, refine_limit):
    document, components, marks, parts, warnings = read_dxf(path)
    if not components or any(part["layer"].upper() == "SYMBOL" for part in parts):
        geometry = [
            part for part in parts if part["layer"].upper() not in {"TEXT", "TITLE"}
        ]
        stencil_canvas = _vector_canvas(geometry, marks)
        if stencil_canvas is not None:
            image, projected, left, top, factor = stencil_canvas
            loose = _visual_components(image, projected, factor, detector)
            original_marks = dict(zip(projected, marks, strict=True))
            for item in loose:
                x, y, w, h = item.box
                item.box = x / factor + left, y / factor + top, w / factor, h / factor
                item.ports = {
                    name: (px / factor + left, py / factor + top)
                    for name, (px, py) in item.ports.items()
                }
                item.source = "dxf-loose-geometry"
                if item.label_anchor:
                    item.label_anchor = original_marks[item.label_anchor]
                    item.bindings = {
                        key: original_marks[mark] for key, mark in item.bindings.items()
                    }
                if all(
                    intersection_over_union(item.box, old.box) < 0.3
                    for old in components
                ):
                    components.append(item)
    _attach_text(components, marks, 1.0)
    if refiner:
        preview = dxf_preview(document)
        if preview is None:
            warnings.append("vlm_dxf_preview_not_available")
        else:
            image, project = preview
            images = [
                replace(
                    item,
                    box=project(item.box),
                    bindings={
                        field: replace(mark, bbox=project(mark.bbox))
                        for field, mark in item.bindings.items()
                    },
                )
                for item in components
            ]
            _refine(refiner, image, images, warnings, refine_limit)
            for item, image_item in zip(components, images, strict=True):
                if image_item.refined:
                    item.tag, item.spec, item.refined = (
                        image_item.tag,
                        image_item.spec,
                        True,
                    )
    page = _page(
        components, marks, parts, path.stem, "dxf-vector", None, 0.0, None, warnings
    )
    page["coordinate_space"]["insunits"] = int(document.units)
    return [page]


def parse_drawing(
    path: Path,
    *,
    ocr=read_ocr,
    detector=None,
    refiner=None,
    refine_limit=2,
    pixels_per_mm=None,
):
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".dxf":
        sheets = _dxf_components(path, detector, refiner, refine_limit)
    elif ext == ".pdf":
        sheets = []
        with pymupdf.open(path) as document:
            for index, page in enumerate(document, 1):
                zoom = min(2.0, 1680 / max(page.rect.width, page.rect.height))
                pix = page.get_pixmap(
                    matrix=pymupdf.Matrix(zoom, zoom),
                    colorspace=pymupdf.csGRAY,
                    alpha=False,
                )
                image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width
                )
                parts = pdf_primitives(page)
                parts = [
                    {
                        **part,
                        "points": [(x * zoom, y * zoom) for x, y in part["points"]],
                    }
                    for part in parts
                ]
                marks = pdf_marks(page, zoom=zoom)
                warnings = []
                usable_native = sum(1 for mark in marks if split_tag(mark.text))
                if not usable_native:
                    marks = _raster_marks(image, ocr, warnings)
                scale = pixels_per_mm or _estimate_scale(image)
                components = _visual_components(image, marks, scale, detector)
                _attach_text(
                    components,
                    marks,
                    scale,
                    image=image,
                    retry_ocr=ocr is read_ocr and bool(marks) and not usable_native,
                )
                _refine(refiner, image, components, warnings, refine_limit)
                photo_coverage = max(
                    (
                        pymupdf.Rect(item["bbox"]).get_area() / page.rect.get_area()
                        for item in page.get_image_info()
                    ),
                    default=0.0,
                )
                method = (
                    "pdf-vector"
                    if parts and (photo_coverage < 0.8 or len(parts) > 8)
                    else "pdf-scan"
                )
                sheets.append(
                    _page(
                        components,
                        marks,
                        parts,
                        f"{path.stem}-{index}",
                        method,
                        pix.width,
                        pix.height,
                        scale,
                        warnings,
                    )
                )
                sheets[-1]["coordinate_space"]["raster_pixels_per_pdf_point"] = zoom
    elif ext in _IMAGE_EXTS:
        image, original_size = _read_image(path)
        warnings = []
        marks = _raster_marks(image, ocr, warnings)
        scale = pixels_per_mm or _estimate_scale(image)
        components = _visual_components(image, marks, scale, detector)
        _attach_text(
            components,
            marks,
            scale,
            image=image,
            retry_ocr=ocr is read_ocr and bool(marks),
        )
        _refine(refiner, image, components, warnings, refine_limit)
        sheets = [
            _page(
                components,
                marks,
                [],
                path.stem,
                "raster",
                image.shape[1],
                image.shape[0],
                scale,
                warnings,
            )
        ]
        sheets[0]["coordinate_space"]["source_pixels"] = list(original_size)
    else:
        raise ValueError(f"unsupported drawing format {ext!r}")
    return {
        "schema_version": "1.0.0",
        "input": path.name,
        "sheets": sheets,
        "counts": dict(Counter(s["channel"] for s in sheets)),
    }
