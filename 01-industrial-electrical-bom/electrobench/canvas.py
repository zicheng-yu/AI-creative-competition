"""DXF construction and millimetre-accurate symbol placement."""

from __future__ import annotations

import math
from datetime import datetime

import ezdxf
from ezdxf.enums import TextEntityAlignment
from ezdxf.tools.juliandate import juliandate

from . import SCHEMA_VERSION
from .catalog import BY_CODE, alias_spec, alias_tag
from .glyphs import FONT_FILE, GLYPHS, LAYER_SYMBOL, LINEWEIGHT, define_blocks
from .model import ControlBranch, DrawingRecord, Edge, Instance

SHEET_W = 420.0
SHEET_H = 297.0
# Fixed header dates so a regenerated DXF does not churn on the clock.
_FIXED_DATE = juliandate(datetime(2026, 11, 27, 0, 0, 0))


def _rot(x: float, y: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    return x * cos_a - y * sin_a, x * sin_a + y * cos_a


def text_width(text: str, height: float) -> float:
    width = 0.0
    for char in text:
        width += height if ord(char) > 127 else height * 0.55
    return width


class Canvas:
    def __init__(
        self,
        *,
        drawing_id: str,
        subset: str,
        title: str,
        seed: int,
        voltage: str,
        cabinet: str | None = None,
        circuit_kind: str | None = None,
        alias: bool = False,
        interlock: bool = True,
        notes: list[str] | None = None,
    ) -> None:
        self.record = DrawingRecord(
            id=drawing_id,
            subset=subset,
            title=title,
            seed=seed,
            cabinet=cabinet,
            circuit_kind=circuit_kind,
            voltage=voltage,
            sheet_w=SHEET_W,
            sheet_h=SHEET_H,
            interlock=interlock,
            alias=alias,
            notes=list(notes or []),
        )
        self.doc = ezdxf.new("R2010", setup=True)
        self.doc.units = ezdxf.units.MM
        for var in ("$TDCREATE", "$TDUCREATE", "$TDUPDATE", "$TDUUPDATE"):
            self.doc.header[var] = _FIXED_DATE
        self.doc.styles.add("CN", font=FONT_FILE)
        for layer in (LAYER_SYMBOL, "WIRE", "TEXT", "TITLE", "BUS"):
            if layer not in self.doc.layers:
                self.doc.layers.add(layer)
        define_blocks(self.doc)
        self.msp = self.doc.modelspace()
        self._seq = 0
        self._edge_seq = 0
        self.record.doc = self.doc  # type: ignore[attr-defined]
        self._draw_frame()

    def _draw_frame(self) -> None:
        rec = self.record
        self.msp.add_lwpolyline(
            [(5, 5), (415, 5), (415, 292), (5, 292)],
            close=True,
            dxfattribs={"layer": "TITLE", "lineweight": 25},
        )
        self.msp.add_line((5, 28), (415, 28), dxfattribs={"layer": "TITLE", "lineweight": 18})
        self.msp.add_line((248, 5), (248, 28), dxfattribs={"layer": "TITLE", "lineweight": 18})
        self._text(f"图枢电析  {rec.title}", 8, 19.5, 3.2)
        self._text(
            f"{rec.id}    {rec.voltage}    seed={rec.seed}    schema {SCHEMA_VERSION}",
            8,
            13.2,
            2.5,
        )
        self._text("图形符号按 GB/T 4728 / IEC 60617 简图近似；文字代号对照 GB/T 5094 / IEC 81346-2:2019", 8, 8.0, 2.2)
        self._text(rec.id, 252, 18.5, 3.0)
        cabinet = rec.cabinet or rec.subset
        self._text(str(cabinet), 252, 11.5, 2.6)

    def _text(self, content: str, x: float, y: float, height: float, layer: str = "TEXT") -> None:
        entity = self.msp.add_text(
            content,
            height=height,
            dxfattribs={"layer": layer, "style": "CN"},
        )
        entity.set_placement((x, y), align=TextEntityAlignment.LEFT)

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}{self._seq:03d}"

    def place(
        self,
        class_code: str,
        x: float,
        y: float,
        tag: str,
        specs: dict | None = None,
        *,
        rotation: float = 0.0,
        bom_anchor: bool | None = None,
        in_netlist: bool | None = None,
        circuit: str = "",
        label: bool = True,
        label_side: str = "right",
        extra: dict | None = None,
    ) -> Instance:
        if class_code not in GLYPHS:
            raise KeyError(f"no glyph for {class_code}")
        symbol = BY_CODE[class_code]
        glyph = GLYPHS[class_code]
        specs = dict(specs or {})
        corners = []
        minx, miny, maxx, maxy = glyph.bbox
        for px, py in ((minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)):
            rx, ry = _rot(px, py, rotation)
            corners.append((x + rx, y + ry))
        xs = [pt[0] for pt in corners]
        ys = [pt[1] for pt in corners]
        bbox = (round(min(xs), 2), round(min(ys), 2), round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2))
        ports = {}
        for name, (px, py) in glyph.ports.items():
            rx, ry = _rot(px, py, rotation)
            ports[name] = (round(x + rx, 2), round(y + ry, 2))
        self.msp.add_blockref(
            class_code,
            (x, y),
            dxfattribs={"rotation": rotation, "layer": LAYER_SYMBOL, "lineweight": LINEWEIGHT},
        )
        spec_text = str(specs.get("spec", ""))
        if self.record.alias:
            shown_tag = alias_tag(class_code, tag)
            shown_spec = alias_spec(spec_text) if spec_text else ""
        else:
            shown_tag = tag
            shown_spec = spec_text
        inst = Instance(
            id=self._next_id("i"),
            tag=tag,
            class_code=class_code,
            bom_anchor=symbol.default_bom_anchor if bom_anchor is None else bom_anchor,
            in_netlist=symbol.default_in_netlist if in_netlist is None else in_netlist,
            bbox_mm=bbox,
            ports=ports,
            specs=specs,
            label_tag=shown_tag,
            label_spec=shown_spec,
            circuit=circuit,
            extra=dict(extra or {}),
        )
        if label:
            self._label(inst, label_side)
        self.record.instances.append(inst)
        return inst

    def _label(self, inst: Instance, side: str) -> None:
        x, y, w, h = inst.bbox_mm
        height = 2.3
        if side == "above":
            self._text(inst.label_tag, x, y + h + 3.3, height)
            if inst.label_spec:
                self._text(inst.label_spec, x, y + h + 0.6, 2.0)
            return
        if side == "left":
            width = text_width(inst.label_tag, height)
            self._text(inst.label_tag, x - width - 1.2, y + h * 0.45, height)
            if inst.label_spec:
                spec_w = text_width(inst.label_spec, 2.0)
                self._text(inst.label_spec, x - spec_w - 1.2, y + h * 0.45 - 2.8, 2.0)
            return
        self._text(inst.label_tag, x + w + 1.0, y + h * 0.55, height)
        if inst.label_spec:
            self._text(inst.label_spec, x + w + 1.0, y + h * 0.55 - 2.8, 2.0)

    def add_bus(self, x1: float, x2: float, y: float, tag: str, port_xs: dict[str, float], *, circuit: str = "") -> Instance:
        self.msp.add_lwpolyline(
            [(x1, y), (x2, y)],
            format="xy",
            dxfattribs={"layer": "BUS", "const_width": 1.1},
        )
        ports = {name: (round(px, 2), round(y, 2)) for name, px in port_xs.items()}
        bbox = (round(min(x1, x2), 2), round(y - 0.8, 2), round(abs(x2 - x1), 2), 1.6)
        specs = {"spec": "TMY", "model": "EB-WB"}
        if self.record.alias:
            shown_tag = alias_tag("WB", tag)
            shown_spec = alias_spec("TMY")
        else:
            shown_tag = tag
            shown_spec = "TMY"
        inst = Instance(
            id=self._next_id("i"),
            tag=tag,
            class_code="WB",
            bom_anchor=True,
            in_netlist=True,
            bbox_mm=bbox,
            ports=ports,
            specs=specs,
            label_tag=shown_tag,
            label_spec=shown_spec,
            circuit=circuit,
        )
        self._text(inst.label_tag, x1 + 2, y + 2.2, 2.4)
        self.record.instances.append(inst)
        return inst

    def add_wl(
        self,
        x: float,
        y: float,
        tag: str,
        *,
        section_mm2: int,
        iz_a: int,
        ib_a: int,
        spec: str,
        circuit: str,
    ) -> Instance:
        specs = {
            "model": "YJV",
            "spec": spec,
            "section_mm2": section_mm2,
            "Iz_A": iz_a,
            "Ib_A": ib_a,
            "circuit": circuit,
        }
        shown_spec = alias_spec(spec) if self.record.alias else spec
        shown_tag = alias_tag("WL", tag) if self.record.alias else tag
        height = 2.4
        width = max(text_width(shown_tag, height), text_width(shown_spec, 2.1)) + 1.0
        bbox = (round(x, 2), round(y, 2), round(width, 2), 6.2)
        inst = Instance(
            id=self._next_id("i"),
            tag=tag,
            class_code="WL",
            bom_anchor=True,
            in_netlist=True,
            bbox_mm=bbox,
            # A cable label sits on the wire; both ports share the label origin
            # so the orthogonal router can terminate on the text.
            ports={"in": (round(x, 2), round(y + 3.0, 2)), "out": (round(x, 2), round(y + 3.0, 2))},
            specs=specs,
            label_tag=shown_tag,
            label_spec=shown_spec,
            circuit=circuit,
        )
        self._text(shown_tag, x, y + 3.2, height)
        self._text(shown_spec, x, y + 0.4, 2.1)
        self.record.instances.append(inst)
        return inst

    def add_wire_no(self, x: float, y: float, number: str) -> Instance:
        height = 2.2
        width = text_width(str(number), height) + 1.2
        bbox = (round(x, 2), round(y, 2), round(width, 2), round(height + 0.6, 2))
        inst = Instance(
            id=self._next_id("i"),
            tag=f"W{number}",
            class_code="WIRE_NO",
            bom_anchor=False,
            in_netlist=False,
            bbox_mm=bbox,
            ports={},
            specs={"wire_no": str(number)},
            label_tag=str(number),
            label_spec="",
            circuit="",
        )
        self._text(str(number), x + 0.4, y + 0.3, height)
        self.record.instances.append(inst)
        return inst

    def connect(
        self,
        source: Instance,
        source_port: str,
        target: Instance,
        target_port: str,
        *,
        kind: str = "power",
        bend: str = "auto",
        draw: bool = True,
    ) -> Edge:
        start = source.port(source_port)
        end = target.port(target_port)
        points = _route(start, end, bend)
        if draw:
            for p1, p2 in zip(points, points[1:]):
                if p1 == p2:
                    continue
                self.msp.add_line(p1, p2, dxfattribs={"layer": "WIRE", "lineweight": 25})
        self._edge_seq += 1
        edge = Edge(
            id=f"e{self._edge_seq:03d}",
            source=source.id,
            target=target.id,
            kind=kind,
            points=[(round(px, 2), round(py, 2)) for px, py in points],
            source_port=source_port,
            target_port=target_port,
        )
        self.record.edges.append(edge)
        return edge

    def add_branch(self, branch: ControlBranch) -> None:
        self.record.control_branches.append(branch)


def _route(start: tuple[float, float], end: tuple[float, float], bend: str) -> list[tuple[float, float]]:
    x1, y1 = start
    x2, y2 = end
    if abs(x1 - x2) < 0.2 or abs(y1 - y2) < 0.2:
        return [start, end]
    if bend == "hv":
        mid = (x2, y1)
    elif bend == "vh":
        mid = (x1, y2)
    elif bend == "auto":
        # Prefer a vertical-then-horizontal elbow when the drop is larger.
        mid = (x1, y2) if abs(y1 - y2) >= abs(x1 - x2) else (x2, y1)
    else:
        raise ValueError(bend)
    return [start, mid, end]
