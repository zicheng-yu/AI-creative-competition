"""Programmatic GB/T 4728-like glyphs.

Coordinates are millimetres, y up, origin at the symbol centre.
Shapes are benchmark approximations of the usual single-line / ladder
symbols, not copies of the published standard plates.
"""

from __future__ import annotations

from dataclasses import dataclass

import ezdxf
from ezdxf.document import Drawing as EzDrawing

FONT_FILE = "wqy-microhei.ttc"
LAYER_SYMBOL = "SYMBOL"
LINEWEIGHT = 35


@dataclass(frozen=True)
class Glyph:
    code: str
    # Local bbox (minx, miny, maxx, maxy).
    bbox: tuple[float, float, float, float]
    ports: dict[str, tuple[float, float]]
    # ("L", x1, y1, x2, y2) | ("R", x, y, w, h) | ("C", x, y, r)
    # | ("P", ((x, y), ...)) | ("T", text, x, y, height)
    entities: tuple


def _g(code: str, bbox, ports, entities) -> Glyph:
    return Glyph(code=code, bbox=bbox, ports=dict(ports), entities=tuple(entities))


def _contact(code: str, *, nc: bool, stem: bool, thermal: bool, delay: bool) -> Glyph:
    ents: list = [
        ("L", -8, 0, -2.2, 0),
        ("L", -2.2, 0, 2.4, 3.4),
        ("L", 3.2, 0, 8, 0),
        ("C", 3.2, 0, 0.6),
    ]
    if nc:
        ents.append(("L", -1.2, -2.4, 3.4, 3.6))
    if stem:
        ents.append(("L", 0.2, 2.2, 0.2, 6.2))
    if thermal:
        ents.append(("P", ((-4.5, 1.5), (-3.2, 3.2), (-2.0, 1.6), (-0.8, 3.2))))
    if delay:
        ents.append(("C", 5.5, 3.2, 1.6))
    top = 7.0 if stem or delay or thermal else 4.2
    return _g(code, (-8, -3.2, 8, top), {"left": (-8, 0), "right": (8, 0)}, ents)


def _coil(code: str, shape: str, label: str) -> Glyph:
    ents: list = [("L", -8, 0, -5, 0), ("L", 5, 0, 8, 0)]
    if shape == "circle":
        ents.append(("C", 0, 0, 5))
    else:
        ents.append(("R", -5, -4, 10, 8))
    ents.append(("T", label, -1.6, -1.3, 2.6))
    if shape == "timer":
        ents.append(("C", 0, 5.2, 1.5))
    top = 6.8 if shape == "timer" else 5
    return _g(code, (-8, -5, 8, top), {"left": (-8, 0), "right": (8, 0)}, ents)


def _fuse_vertical() -> Glyph:
    return _g(
        "FU",
        ( -2.4, -8, 2.4, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("L", 0, 8, 0, 4),
            ("R", -2, -4, 4, 8),
            ("L", 0, -4, 0, -8),
        ),
    )


GLYPHS: dict[str, Glyph] = {
    "QF": _g(
        "QF",
        (-4.2, -8, 4.2, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("L", 0, 8, 0, 4.2),
            ("R", -3.4, -4.2, 6.8, 8.4),
            ("L", -3.4, -4.2, 3.4, 4.2),
            ("L", -3.4, 4.2, 3.4, -4.2),
            ("L", 0, -4.2, 0, -8),
        ),
    ),
    "QS": _g(
        "QS",
        (-2.5, -8, 5.5, 8),
        {"in": (0, 8), "out": (0, -8), "tap": (0, 2)},
        (
            ("L", 0, 8, 0, 2),
            ("L", 0, 2, 5, -4),
            ("L", -2.2, -5, 2.2, -5),
            ("L", 0, -5, 0, -8),
        ),
    ),
    "QE": _g(
        "QE",
        (-5.5, -14, 5.5, 8),
        {"in": (0, 8), "out": (0, -14)},
        (
            ("L", 0, 8, 0, 2),
            ("L", 0, 2, 5, -3),
            ("L", -2.2, -4.2, 2.2, -4.2),
            ("L", 0, -4.2, 0, -8),
            ("L", -5, -9, 5, -9),
            ("L", -3, -11.2, 3, -11.2),
            ("L", -1.4, -13.2, 1.4, -13.2),
        ),
    ),
    "KM_MAIN": _g(
        "KM_MAIN",
        (-4.2, -8, 4.2, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("L", 0, 8, 0, 5),
            ("R", -4, -5, 8, 10),
            ("L", -2.2, 1.2, 2.2, 1.2),
            ("L", -2.2, -1.2, 2.2, -1.2),
            ("L", 0, -5, 0, -8),
        ),
    ),
    "FR": _g(
        "FR",
        (-4.2, -8, 4.2, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("L", 0, 8, 0, 5),
            ("R", -4, -5, 8, 10),
            ("P", ((-2.4, 3), (2.2, 1.2), (-2.4, -0.6), (2.2, -2.6))),
            ("L", 0, -5, 0, -8),
        ),
    ),
    "FU": _fuse_vertical(),
    "TA": _g(
        "TA",
        (-5, -8, 6.5, 8),
        {"in": (0, 8), "out": (0, -8), "sec": (5, 0)},
        (
            ("L", 0, 8, 0, -8),
            ("C", 0, 0, 5),
            ("T", "I", -0.7, -1.2, 2.4),
        ),
    ),
    "TV": _g(
        "TV",
        (-4.4, -8, 6.2, 8),
        {"in": (0, 8), "out": (0, -8), "sec": (4.4, 0)},
        (
            ("L", 0, 8, 0, 6.2),
            ("C", 0, 2.6, 3.6),
            ("C", 0, -2.6, 3.6),
            ("L", 0, -6.2, 0, -8),
        ),
    ),
    "SPD": _g(
        "SPD",
        (-5, -13, 5, 8),
        {"in": (0, 8), "out": (0, -13)},
        (
            ("L", 0, 8, 0, 3),
            ("R", -3, -2, 6, 5),
            ("L", -1.6, 1.6, 1.6, -0.6),
            ("L", 0, -2, 0, -7),
            ("L", -5, -8, 5, -8),
            ("L", -3, -10.2, 3, -10.2),
            ("L", -1.4, -12.2, 1.4, -12.2),
        ),
    ),
    "T": _g(
        "T",
        (-4.4, -8, 4.4, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("L", 0, 8, 0, 6.4),
            ("C", 0, 2.8, 3.6),
            ("C", 0, -2.8, 3.6),
            ("L", 0, -6.4, 0, -8),
        ),
    ),
    "TC": _g(
        "TC",
        (-4.2, -8, 4.2, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("L", 0, 8, 0, 6.2),
            ("C", 0, 2.6, 3.4),
            ("C", 0, -2.6, 3.4),
            ("L", 0, -6.0, 0, -8),
            ("T", "TC", -1.8, -1.0, 2.0),
        ),
    ),
    "M": _g(
        "M",
        (-6, -8, 6, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("L", 0, 8, 0, 6),
            ("C", 0, 0, 6),
            ("T", "M", -1.8, -1.4, 3.2),
            ("L", 0, -6, 0, -8),
        ),
    ),
    "PA": _g(
        "PA",
        (-5.5, -8, 5.5, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("L", 0, 8, 0, 5.5),
            ("C", 0, 0, 5.5),
            ("T", "A", -1.4, -1.3, 2.8),
            ("L", 0, -5.5, 0, -8),
        ),
    ),
    "PV": _g(
        "PV",
        (-5.5, -8, 5.5, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("L", 0, 8, 0, 5.5),
            ("C", 0, 0, 5.5),
            ("T", "V", -1.4, -1.3, 2.8),
            ("L", 0, -5.5, 0, -8),
        ),
    ),
    "PJ": _g(
        "PJ",
        (-5.5, -8, 5.5, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("L", 0, 8, 0, 5.5),
            ("C", 0, 0, 5.5),
            ("T", "Wh", -2.2, -1.1, 2.2),
            ("L", 0, -5.5, 0, -8),
        ),
    ),
    "C": _g(
        "C",
        (-4.5, -8, 4.5, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("L", 0, 8, 0, 2),
            ("L", -4, 2, 4, 2),
            ("L", -4, -2, 4, -2),
            ("L", 0, -2, 0, -8),
        ),
    ),
    "L": _g(
        "L",
        (-3.5, -8, 3.5, 8),
        {"in": (0, 8), "out": (0, -8)},
        (
            ("P", ((0, 8), (0, 4), (-3, 2), (0, 0), (-3, -2), (0, -4), (0, -8))),
        ),
    ),
    "HL": _g(
        "HL",
        (-8, -5, 8, 5),
        {"left": (-8, 0), "right": (8, 0)},
        (
            ("L", -8, 0, -5, 0),
            ("C", 0, 0, 5),
            ("L", -3.2, -3.2, 3.2, 3.2),
            ("L", -3.2, 3.2, 3.2, -3.2),
            ("L", 5, 0, 8, 0),
        ),
    ),
    "HA": _g(
        "HA",
        (-8, -5, 8, 5),
        {"left": (-8, 0), "right": (8, 0)},
        (
            ("L", -8, 0, -5, 0),
            ("C", 0, 0, 5),
            ("C", 1.2, 0, 2.4),
            ("L", 5, 0, 8, 0),
        ),
    ),
    "SA": _g(
        "SA",
        (-8, -4, 8, 6),
        {"left": (-8, 0), "right": (8, 0)},
        (
            ("L", -8, 0, -4, 0),
            ("C", 0, 0, 4),
            ("L", 0, 0, 4.5, 4.5),
            ("L", 4, 0, 8, 0),
        ),
    ),
    "SQ": _g(
        "SQ",
        (-8, -3.2, 8, 7.5),
        {"left": (-8, 0), "right": (8, 0)},
        (
            ("L", -8, 0, -2.2, 0),
            ("L", -2.2, 0, 2.4, 3.2),
            ("L", 3.2, 0, 8, 0),
            ("L", -1.0, -2.2, 3.2, 3.4),
            ("P", ((-1.2, 4.2), (1.6, 4.2), (0.2, 7.0))),
        ),
    ),
    "XT": _g(
        "XT",
        (-6, -2.4, 6, 2.4),
        {"left": (-6, 0), "right": (6, 0)},
        (
            ("L", -6, 0, -2.2, 0),
            ("C", 0, 0, 2.2),
            ("L", 2.2, 0, 6, 0),
        ),
    ),
    "YC": _coil("YC", "circle", "YC"),
    "YO": _coil("YO", "circle", "YO"),
    "KM_COIL": _coil("KM_COIL", "circle", "K"),
    "KA_COIL": _coil("KA_COIL", "rect", "K"),
    "KT_COIL": _coil("KT_COIL", "timer", "KT"),
    "KM_NO": _contact("KM_NO", nc=False, stem=False, thermal=False, delay=False),
    "KM_NC": _contact("KM_NC", nc=True, stem=False, thermal=False, delay=False),
    "KA_NO": _contact("KA_NO", nc=False, stem=False, thermal=False, delay=False),
    "KA_NC": _contact("KA_NC", nc=True, stem=False, thermal=False, delay=False),
    "KT_NO": _contact("KT_NO", nc=False, stem=False, thermal=False, delay=True),
    "FR_NC": _contact("FR_NC", nc=True, stem=False, thermal=True, delay=False),
    "SB_NO": _contact("SB_NO", nc=False, stem=True, thermal=False, delay=False),
    "SB_NC": _contact("SB_NC", nc=True, stem=True, thermal=False, delay=False),
    "ATS": _g(
        "ATS",
        (-10, -8, 10, 8),
        {"in1": (-10, 4), "in2": (-10, -4), "out": (10, 0)},
        (
            ("R", -8, -7, 16, 14),
            ("L", -10, 4, -8, 4),
            ("L", -10, -4, -8, -4),
            ("L", -6, 4, 2, -1),
            ("L", -6, -4, -2, -4),
            ("L", 6, 0, 10, 0),
            ("T", "ATS", -3.2, -1.2, 2.4),
        ),
    ),
    "PE": _g(
        "PE",
        (-5, -6, 5, 4),
        {"in": (0, 4)},
        (
            ("L", 0, 4, 0, 0),
            ("L", -5, 0, 5, 0),
            ("L", -3, -2.2, 3, -2.2),
            ("L", -1.4, -4.2, 1.4, -4.2),
        ),
    ),
}


def define_blocks(doc: EzDrawing) -> None:
    if "CN" not in doc.styles:
        doc.styles.add("CN", font=FONT_FILE)
    if LAYER_SYMBOL not in doc.layers:
        doc.layers.add(LAYER_SYMBOL)
    for glyph in GLYPHS.values():
        if glyph.code in doc.blocks:
            continue
        block = doc.blocks.new(glyph.code)
        attrib = {"layer": LAYER_SYMBOL, "lineweight": LINEWEIGHT}
        for ent in glyph.entities:
            kind = ent[0]
            if kind == "L":
                _, x1, y1, x2, y2 = ent
                block.add_line((x1, y1), (x2, y2), dxfattribs=attrib)
            elif kind == "R":
                _, x, y, w, h = ent
                block.add_lwpolyline(
                    [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                    close=True,
                    dxfattribs=attrib,
                )
            elif kind == "C":
                _, x, y, r = ent
                block.add_circle((x, y), r, dxfattribs=attrib)
            elif kind == "P":
                block.add_lwpolyline(list(ent[1]), dxfattribs=attrib)
            elif kind == "T":
                _, text, x, y, height = ent
                entity = block.add_text(text, height=height, dxfattribs={"layer": LAYER_SYMBOL, "style": "CN"})
                entity.set_placement((x, y))
            else:
                raise ValueError(kind)


def require_font() -> None:
    from ezdxf.fonts import fonts

    try:
        fonts.resolve_font_face(FONT_FILE)
    except fonts.FontNotFoundError as exc:
        raise SystemExit(
            "缺少中文字体 wqy-microhei.ttc（Debian/Ubuntu 包 fonts-wqy-microhei）。"
            "图面中文标注无法绘制。"
        ) from exc
