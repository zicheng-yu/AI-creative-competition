"""Native drawing primitives and known or semantically tagged DXF blocks."""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf
import pymupdf
from ezdxf.path import make_path

from .labels import CLASSES, Component, TextMark, normal_text, split_tag

_GEOMETRY = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE"}


def polygon_box(points):
    left, right = min(p[0] for p in points), max(p[0] for p in points)
    top, bottom = min(p[1] for p in points), max(p[1] for p in points)
    return float(left), float(top), float(right - left), float(bottom - top)


def _dxf_text(entity):
    from ezdxf import bbox

    words = entity.plain_text() if hasattr(entity, "plain_text") else entity.dxf.text
    words = normal_text(words)
    if not words:
        return None
    placement = entity.dxf.insert
    extents = bbox.extents([entity], fast=True)
    if extents.has_data:
        p, q = extents.extmin, extents.extmax
        box = (float(p.x), -float(q.y), float(q.x - p.x), float(q.y - p.y))
    else:
        height = float(entity.dxf.get("height", 2.3))
        box = (
            float(placement.x),
            -float(placement.y) - height,
            height * len(words) * 0.55,
            height,
        )
    return TextMark(words, box)


def _dxf_primitive(entity):
    shape = make_path(entity)
    points = [(float(p.x), -float(p.y)) for p in shape.flattening(0.12)]
    if not points:
        return None
    return {"type": entity.dxftype(), "layer": entity.dxf.layer, "points": points}


def _block(entity):
    attributes = {
        attrib.dxf.tag.upper(): normal_text(attrib.dxf.text)
        for attrib in entity.attribs
    }
    code = attributes.get("CLASS", entity.dxf.name).upper()
    if code not in CLASSES or not CLASSES[code]["bbox"]:
        return None
    definition = CLASSES[code]
    left, bottom, right, top = definition["bbox"]
    transform = entity.matrix44()
    block = entity.block()
    bx, by, bz = block.block.dxf.base_point if block is not None else (0.0, 0.0, 0.0)

    def point(px, py):
        result = transform.transform((px + bx, py + by, bz))
        return float(result.x), -float(result.y)

    bbox = polygon_box([point(x, y) for x in (left, right) for y in (bottom, top)])
    ports = {name: point(*xy) for name, xy in definition["ports"].items()}
    raw_tag = attributes.get("TAG") or attributes.get("REFDES") or ""
    parsed = split_tag(raw_tag)
    return Component(
        code,
        bbox,
        ports,
        0.99,
        "dxf-block",
        tag=parsed[1] if parsed else raw_tag,
        spec=attributes.get("SPEC", ""),
        model=attributes.get("MODEL", ""),
    )


def read_dxf(path: Path):
    document = ezdxf.readfile(path)
    components, parts, marks, buses = [], [], [], []
    warnings = []
    for entity in document.modelspace():
        name = entity.dxftype()
        if name == "INSERT":
            for insert in entity.multi_insert() if entity.mcount > 1 else [entity]:
                candidate = _block(insert)
                if candidate is not None:
                    components.append(candidate)
                else:
                    warnings.append(f"unmapped_dxf_block:{insert.dxf.name}")
                    for member in insert.virtual_entities():
                        if member.dxftype() in _GEOMETRY and (
                            primitive := _dxf_primitive(member)
                        ):
                            parts.append(
                                {
                                    **primitive,
                                    "source_layer": primitive["layer"],
                                    "layer": "SYMBOL",
                                }
                            )
        elif name in {"TEXT", "MTEXT"}:
            mark = _dxf_text(entity)
            if mark:
                marks.append(mark)
        elif name in _GEOMETRY:
            primitive = _dxf_primitive(entity)
            if primitive is not None:
                parts.append(primitive)
                if primitive["layer"].upper() == "BUS":
                    buses.append(primitive["points"])

    for points in buses:
        left, top, width, height = polygon_box(points)
        if width <= 0:
            continue
        y = top + height / 2
        from .labels import tag_distance

        labels = [
            (mark, parsed)
            for mark in marks
            if (parsed := split_tag(mark.text)) and parsed[0] == "WB"
        ]
        mark, parsed = min(
            labels,
            key=lambda pair: tag_distance((left, y - 0.8, width, 1.6), pair[0]),
            default=(None, None),
        )
        if mark and tag_distance((left, y - 0.8, width, 1.6), mark) > 12:
            mark, parsed = None, None
        wire_ends = {
            p
            for primitive in parts
            if primitive["layer"].upper() == "WIRE"
            for p in (primitive["points"][0], primitive["points"][-1])
            if abs(p[1] - y) <= 0.2 and left - 0.2 <= p[0] <= left + width + 0.2
        }
        port_names = {}
        for index, point in enumerate(sorted(wire_ends), 1):
            above = sum(
                last[1] < y - 0.2
                for segment in parts
                if segment["layer"].upper() == "WIRE"
                for first, last in (
                    (segment["points"][0], segment["points"][-1]),
                    (segment["points"][-1], segment["points"][0]),
                )
                if math.dist(first, point) <= 0.2
            )
            if above and "src" not in port_names:
                port_names["src"] = point
            else:
                port_names[f"tap{index}"] = point
        candidate = Component(
            "WB", (left, y - 0.8, width, 1.6), port_names, 0.95, "dxf-bus"
        )
        if mark:
            candidate.tag = parsed[1]
            candidate.label_anchor = mark
            candidate.bindings["tag"] = mark
        components.append(candidate)

    return document, components, marks, parts, warnings


def pdf_primitives(page):
    parts = []
    matrix = page.rotation_matrix
    for path in page.get_drawings():
        for typ, *values in path["items"]:
            if typ in {"l", "c"}:
                points = [tuple(point) for point in values]
            elif typ == "re":
                rect = values[0]
                points = [
                    tuple(point)
                    for point in (rect.tl, rect.tr, rect.br, rect.bl, rect.tl)
                ]
            elif typ == "qu":
                quad = values[0]
                points = [
                    tuple(point)
                    for point in (quad.ul, quad.ur, quad.lr, quad.ll, quad.ul)
                ]
            else:
                continue
            points = [tuple(pymupdf.Point(point) * matrix) for point in points]
            parts.append(
                {"type": typ, "layer": path.get("layer") or "", "points": points}
            )
    return parts


def pdf_marks(page, *, zoom: float):
    results = []
    for block in page.get_text(
        "dict", flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
    )["blocks"]:
        for line in block.get("lines", ()):
            for span in line["spans"]:
                # Glyphs can be either text or curve outlines in exported PDF.
                text = normal_text(span["text"])
                if text:
                    x0, y0, x1, y1 = pymupdf.Rect(span["bbox"]) * page.rotation_matrix
                    results.append(
                        TextMark(
                            text,
                            (x0 * zoom, y0 * zoom, (x1 - x0) * zoom, (y1 - y0) * zoom),
                        )
                    )
    return results


def dxf_preview(document):
    """Rasterize the plotted DXF and return a projection from native top-oriented boxes."""
    import numpy as np
    from ezdxf.addons.drawing import Frontend, RenderContext, layout
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
    from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend, get_coordinate_output_space

    backend = PyMuPdfBackend()
    config = Configuration(
        color_policy=ColorPolicy.BLACK, background_policy=BackgroundPolicy.WHITE
    )
    Frontend(RenderContext(document), backend, config).draw_layout(
        document.modelspace()
    )
    bounds = backend.player().bbox()
    if not bounds.has_data or min(bounds.size) <= 0:
        return None
    page = layout.Page(0, 0)
    settings = layout.Settings(scale=min(1.0, 420 / max(bounds.size)), fit_page=False)
    placement = layout.Layout(bounds, flip_y=True)
    final_page = placement.get_final_page(page, settings)
    pdf = backend.get_pdf_bytes(page, settings=settings, render_box=bounds)
    settings.output_coordinate_space = get_coordinate_output_space(final_page)
    matrix = placement.get_placement_matrix(final_page, settings, top_origin=True)
    with pymupdf.open(stream=pdf, filetype="pdf") as plotted:
        pdf_page = plotted[0]
        zoom = min(2.0, 1680 / max(pdf_page.rect.width, pdf_page.rect.height))
        pix = pdf_page.get_pixmap(
            matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY, alpha=False
        )
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width
        )

    def project(box):
        x, y, w, h = box
        a = matrix.transform((x, -y, 0))
        b = matrix.transform((x + w, -y - h, 0))
        return polygon_box([(a.x * zoom, a.y * zoom), (b.x * zoom, b.y * zoom)])

    return image, project
