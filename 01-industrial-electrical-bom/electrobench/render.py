"""Raster and PDF export with a fixed sheet-to-pixel mapping."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

from .canvas import SHEET_H, SHEET_W

PX_PER_MM = 4
DPI = 100


def render_drawing(doc, png_path: Path, pdf_path: Path | None) -> tuple[int, int]:
    img_w = int(SHEET_W * PX_PER_MM)
    img_h = int(SHEET_H * PX_PER_MM)
    fig = plt.figure(figsize=(img_w / DPI, img_h / DPI), dpi=DPI, facecolor="white")
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_facecolor("white")
    ax.set_xlim(0, SHEET_W)
    ax.set_ylim(0, SHEET_H)
    config = Configuration(
        background_policy=BackgroundPolicy.WHITE,
        color_policy=ColorPolicy.BLACK,
    )
    backend = MatplotlibBackend(ax, adjust_figure=False)
    Frontend(RenderContext(doc), backend, config).draw_layout(doc.modelspace(), finalize=True)
    ax.set_xlim(0, SHEET_W)
    ax.set_ylim(0, SHEET_H)
    ax.set_aspect("auto")
    ax.axis("off")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=DPI, facecolor="white")
    if pdf_path is not None:
        fig.savefig(pdf_path, facecolor="white")
    plt.close(fig)
    return img_w, img_h


def mm_box_to_px(box: tuple[float, float, float, float], img_w: int, img_h: int) -> list[float]:
    x, y, w, h = box
    px = x / SHEET_W * img_w
    pw = w / SHEET_W * img_w
    py = (SHEET_H - (y + h)) / SHEET_H * img_h
    ph = h / SHEET_H * img_h
    return [round(px, 2), round(py, 2), round(pw, 2), round(ph, 2)]
