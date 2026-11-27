"""Extract conductors from layered DXF or from a masked raster drawing."""

from __future__ import annotations

import itertools
from collections import defaultdict
from math import ceil, floor
from pathlib import Path

from .geometry import DrawingWires, Point, simplify

_INK_DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
_DIAGONALS = ((1, 1), (-1, 1), (-1, -1), (1, -1))


def read_dxf(
    path: Path, wire_layers: list[str], junction_layers: list[str]
) -> DrawingWires:
    import ezdxf
    from ezdxf.path import Command, make_path

    wires = DrawingWires()
    layers = {layer.casefold() for layer in wire_layers}
    dots = {layer.casefold() for layer in junction_layers}

    def point(vertex) -> Point:
        return float(vertex.x), float(vertex.y)

    for entity in ezdxf.readfile(path).modelspace():
        layer = entity.dxf.layer.casefold()
        kind = entity.dxftype()
        if layer in dots and kind == "CIRCLE":
            wires.junctions.append(point(entity.ocs().to_wcs(entity.dxf.center)))
        elif layer in dots and kind == "POINT":
            wires.junctions.append(point(entity.dxf.location))
        elif layer in layers and kind in {"LINE", "LWPOLYLINE", "POLYLINE", "ARC"}:
            path_geometry = make_path(entity)
            start = path_geometry.start
            bridge = ezdxf.path.Path(start)
            for command in path_geometry:
                if command.type == Command.LINE_TO:
                    if len(bridge):
                        wires.bridges.append(
                            tuple(point(p) for p in bridge.flattening(0.05))
                        )
                    wires.segments.append((point(start), point(command.end)))
                    bridge = ezdxf.path.Path(command.end)
                elif command.type == Command.CURVE3_TO:
                    bridge.curve3_to(command.end, ctrl=command.ctrl)
                elif command.type == Command.CURVE4_TO:
                    bridge.curve4_to(
                        command.end, ctrl1=command.ctrl1, ctrl2=command.ctrl2
                    )
                start = command.end
            if len(bridge):
                # Attach only at the ends. A conductor crossing the arc midway
                # in the projection must remain isolated from the arc.
                wires.bridges.append(tuple(point(p) for p in bridge.flattening(0.05)))
    return wires


def _thin(ink):
    """Zhang–Suen thinning. Both deletion passes preserve end points."""
    import numpy as np

    image = np.pad(ink, 1)
    center = image[1:-1, 1:-1]
    while True:
        changed = False
        for first_pass in (True, False):
            p2, p3, p4, p5, p6, p7, p8, p9 = (
                image[:-2, 1:-1],
                image[:-2, 2:],
                image[1:-1, 2:],
                image[2:, 2:],
                image[2:, 1:-1],
                image[2:, :-2],
                image[1:-1, :-2],
                image[:-2, :-2],
            )
            neighbors = (p2, p3, p4, p5, p6, p7, p8, p9)
            total = sum(n.astype(np.uint8) for n in neighbors)
            rise = sum(
                ((~a) & b).astype(np.uint8)
                for a, b in zip(neighbors, neighbors[1:] + neighbors[:1])
            )
            if first_pass:
                protected = (p2 & p4 & p6) | (p4 & p6 & p8)
            else:
                protected = (p2 & p4 & p8) | (p2 & p6 & p8)
            remove = center & (total >= 2) & (total <= 6) & (rise == 1) & ~protected
            if remove.any():
                center[remove] = False
                changed = True
        if not changed:
            return center


def _skeleton_paths(skeleton):
    pixels = {(int(x), int(y)) for y, x in zip(*skeleton.nonzero())}
    neighbors = defaultdict(set)
    for x, y in pixels:
        for dx, dy in _INK_DIRECTIONS + _DIAGONALS:
            other = x + dx, y + dy
            redundant = dx and dy and ((x + dx, y) in pixels or (x, y + dy) in pixels)
            if other in pixels and not redundant:
                neighbors[x, y].add(other)

    visited = set()

    def trace(start, follow):
        path = [start, follow]
        visited.add(frozenset((start, follow)))
        while len(neighbors[follow]) == 2 and follow != path[0]:
            next_point = next(p for p in neighbors[follow] if p != start)
            edge = frozenset((follow, next_point))
            if edge in visited:
                break
            visited.add(edge)
            path.append(next_point)
            start, follow = follow, next_point
        return path

    branches = sorted(pixel for pixel, linked in neighbors.items() if len(linked) != 2)
    regular = sorted(pixel for pixel, linked in neighbors.items() if len(linked) == 2)
    paths = []
    for pixel in branches + regular:
        for other in sorted(neighbors[pixel]):
            if frozenset((pixel, other)) not in visited:
                paths.append(trace(pixel, other))
    return paths, [pixel for pixel in branches if len(neighbors[pixel]) == 4]


def _filled_junction(ink, x: int, y: int) -> bool:
    height, width = ink.shape
    if not (1 <= x < width - 1 and 1 <= y < height - 1):
        return False
    # Compare the diagonal ink near the centre to the stroke width sampled
    # along the four arms. A uniform thick cross does not count as a dot.
    arm_width = []
    for dx, dy in _INK_DIRECTIONS:
        ax, ay = x + 8 * dx, y + 8 * dy
        if not (3 <= ax < width - 3 and 3 <= ay < height - 3 and ink[ay, ax]):
            continue
        arm_width.append(
            1
            + sum(
                int(ink[ay + dx * offset, ax + dy * offset])
                for offset in (-3, -2, -1, 1, 2, 3)
            )
        )
    if not arm_width:
        return False
    radius = sorted(arm_width)[len(arm_width) // 2] // 2 + 1
    if not (radius <= x < width - radius and radius <= y < height - radius):
        return False
    return (
        sum(bool(ink[y + dy * radius, x + dx * radius]) for dx, dy in _DIAGONALS) >= 3
    )


def read_raster(path: Path, sheet: dict) -> DrawingWires:
    import numpy as np
    from PIL import Image

    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        gray = Image.new("RGBA", rgba.size, "white")
        gray.alpha_composite(rgba)
        ink = np.asarray(gray.convert("L")) < sheet.get("ink_threshold", 155)
    height, width = ink.shape
    scale = sheet.get("pixels_per_unit", 1)
    if scale <= 0:
        raise ValueError("pixels_per_unit must be positive")
    boxes = list(sheet.get("text_boxes", []))
    for symbol in sheet.get("symbols", []):
        box = symbol.get("bbox")
        if box is not None:
            boxes.append(box)
    for x, y, w, h in boxes:
        left = max(0, floor(x * scale) + 1)
        right = min(width, ceil((x + w) * scale))
        top = max(0, floor(height - (y + h) * scale) + 1)
        bottom = min(height, ceil(height - y * scale))
        if left < right and top < bottom:
            ink[top:bottom, left:right] = False

    def drawing_point(pixel) -> Point:
        x, y = pixel
        return x / scale, (height - y) / scale

    paths, crossings = _skeleton_paths(_thin(ink))
    wires = DrawingWires()
    for path_pixels in paths:
        points = simplify(tuple(drawing_point(pixel) for pixel in path_pixels))
        wires.segments.extend(itertools.pairwise(points))
    wires.junctions.extend(
        drawing_point((x, y)) for x, y in crossings if _filled_junction(ink, x, y)
    )
    return wires
