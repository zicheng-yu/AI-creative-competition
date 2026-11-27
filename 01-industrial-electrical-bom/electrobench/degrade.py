"""Raster degradation: Gaussian blur and a small rotation (skew).

The rotation math follows Pillow's ``Image.rotate(..., expand=True)`` so the
stored boxes land on the same pixels as the transformed drawing.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageFilter


BLUR_RADIUS = 1.8
SKEW_DEG = 3.5


def _dest_to_source_matrix(angle_deg: float, width: int, height: int) -> tuple[list[float], int, int]:
    """Pillow AFFINE matrix (destination -> source) and the expanded size."""
    angle = angle_deg % 360.0
    w, h = float(width), float(height)
    center = (w / 2.0, h / 2.0)
    ang = -math.radians(angle)
    matrix = [
        round(math.cos(ang), 15),
        round(math.sin(ang), 15),
        0.0,
        round(-math.sin(ang), 15),
        round(math.cos(ang), 15),
        0.0,
    ]

    def apply(x: float, y: float, mat: list[float]) -> tuple[float, float]:
        a, b, c, d, e, f = mat
        return a * x + b * y + c, d * x + e * y + f

    matrix[2], matrix[5] = apply(-center[0], -center[1], matrix)
    matrix[2] += center[0]
    matrix[5] += center[1]
    xs: list[float] = []
    ys: list[float] = []
    for x, y in ((0, 0), (w, 0), (w, h), (0, h)):
        tx, ty = apply(x, y, matrix)
        xs.append(tx)
        ys.append(ty)
    new_w = int(math.ceil(max(xs)) - math.floor(min(xs)))
    new_h = int(math.ceil(max(ys)) - math.floor(min(ys)))
    matrix[2], matrix[5] = apply(-(new_w - w) / 2.0, -(new_h - h) / 2.0, matrix)
    return matrix, new_w, new_h


def _source_to_dest(matrix: list[float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    det = a * e - b * d
    xd = (e * (x - c) - b * (y - f)) / det
    yd = (-d * (x - c) + a * (y - f)) / det
    return xd, yd


def transform_box(box: list[float], angle_deg: float, width: int, height: int) -> tuple[list[float], int, int]:
    matrix, new_w, new_h = _dest_to_source_matrix(angle_deg, width, height)
    x, y, w, h = box
    corners = ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
    mapped = [_source_to_dest(matrix, px, py) for px, py in corners]
    xs = [pt[0] for pt in mapped]
    ys = [pt[1] for pt in mapped]
    out = [round(min(xs), 2), round(min(ys), 2), round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2)]
    return out, new_w, new_h


def blur_image(src: Path, dest: Path, radius: float = BLUR_RADIUS) -> tuple[int, int]:
    image = Image.open(src).convert("RGB")
    image = image.filter(ImageFilter.GaussianBlur(radius=radius))
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest)
    return image.size


def skew_image(src: Path, dest: Path, angle_deg: float = SKEW_DEG) -> tuple[int, int]:
    image = Image.open(src).convert("RGB")
    rotated = image.rotate(angle_deg, expand=True, fillcolor=(255, 255, 255), resample=Image.Resampling.BILINEAR)
    dest.parent.mkdir(parents=True, exist_ok=True)
    rotated.save(dest)
    return rotated.size
