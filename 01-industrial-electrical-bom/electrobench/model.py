"""In-memory drawing records. JSON export happens after rasterisation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Instance:
    id: str
    tag: str
    class_code: str
    bom_anchor: bool
    in_netlist: bool
    # Axis-aligned bbox in sheet millimetres, origin bottom-left, y up: x, y, w, h.
    bbox_mm: tuple[float, float, float, float]
    ports: dict[str, tuple[float, float]]
    specs: dict
    label_tag: str
    label_spec: str
    circuit: str = ""
    extra: dict = field(default_factory=dict)

    def port(self, name: str) -> tuple[float, float]:
        try:
            return self.ports[name]
        except KeyError as exc:
            raise KeyError(f"{self.tag} ({self.class_code}) has no port {name}") from exc


@dataclass
class Edge:
    id: str
    source: str
    target: str
    kind: str  # power | control | pe | branch
    points: list[tuple[float, float]]
    source_port: str
    target_port: str


@dataclass
class ControlBranch:
    id: str
    coil_tag: str
    pair_tag: str | None
    # Instance ids that must lie on the coil circuit, in reading order.
    series_ids: list[str]


@dataclass
class DrawingRecord:
    id: str
    subset: str
    title: str
    seed: int
    cabinet: str | None
    circuit_kind: str | None
    voltage: str
    sheet_w: float
    sheet_h: float
    instances: list[Instance] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    control_branches: list[ControlBranch] = field(default_factory=list)
    logic: dict | None = None
    interlock: bool = True
    alias: bool = False
    degradation: dict | None = None
    notes: list[str] = field(default_factory=list)

    def by_id(self) -> dict[str, Instance]:
        return {item.id: item for item in self.instances}

    def by_tag(self) -> dict[str, list[Instance]]:
        grouped: dict[str, list[Instance]] = {}
        for item in self.instances:
            grouped.setdefault(item.tag, []).append(item)
        return grouped
