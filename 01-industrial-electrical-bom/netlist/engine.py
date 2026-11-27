"""Attach recognized components, infer device edges, and build circuit views."""

from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass
from heapq import heappop, heappush
from math import dist, isfinite
from pathlib import Path

from .drawing import read_dxf, read_raster
from .geometry import DrawingWires, Point, Route, Vertex, WireGraph, simplify

_MEASUREMENT = {"PA", "PV", "PJ"}
_CONTROL = {
    "KA_COIL",
    "KA_NO",
    "KA_NC",
    "KM_COIL",
    "KM_NO",
    "KM_NC",
    "KT_COIL",
    "KT_NO",
    "FR_NC",
    "TC",
    "HL",
    "HA",
    "SB_NO",
    "SB_NC",
    "SA",
    "SQ",
    "XT",
    "YC",
    "YO",
}


def _point(value) -> Point:
    x, y = value
    if not isfinite(x) or not isfinite(y):
        raise ValueError("coordinates must be finite")
    return float(x), float(y)


def _wires(sheet: dict, base: Path) -> DrawingWires:
    if "wires" in sheet:
        if "file" in sheet:
            raise ValueError("choose either wires or file for a sheet")
        return DrawingWires(
            [(_point(a), _point(b)) for a, b in sheet["wires"]],
            [_point(p) for p in sheet.get("junctions", [])],
            [tuple(_point(p) for p in path) for path in sheet.get("bridges", [])],
        )
    path = base / sheet["file"]
    if path.suffix.lower() == ".dxf":
        wires = read_dxf(
            path,
            sheet.get("wire_layers", ["WIRE"]),
            sheet.get("junction_layers", ["JUNCTION"]),
        )
    elif path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        wires = read_raster(path, sheet)
    else:
        raise ValueError(f"unsupported drawing format: {path.suffix}")
    wires.junctions.extend(_point(point) for point in sheet.get("junctions", []))
    wires.bridges.extend(
        tuple(_point(p) for p in path) for path in sheet.get("bridges", [])
    )
    return wires


@dataclass(frozen=True, order=True)
class Terminal:
    node: str
    port: str


def _port_axis(symbol: dict, port: str, point: Point) -> str | None:
    explicit = symbol.get("port_axes", {}).get(port)
    if explicit in {"h", "v"}:
        return explicit
    bbox = symbol.get("bbox")
    if bbox is None:
        return None
    x, y, w, h = bbox
    dx, dy = abs(point[0] - (x + w / 2)), abs(point[1] - (y + h / 2))
    nx, ny = dx / max(w, 1e-9), dy / max(h, 1e-9)
    if nx != ny:
        return "h" if nx > ny else "v"
    return None


def _edge_kind(a: Terminal, b: Terminal, nodes: dict[str, dict]) -> str:
    left, right = nodes[a.node], nodes[b.node]
    classes = {left["class_code"], right["class_code"]}
    if "PE" in classes:
        return "pe"
    if {a.port, b.port} & {"sec", "tap", "tv"} or classes & _MEASUREMENT:
        return "branch"
    if classes & _CONTROL or any(
        node["circuit_kind"] == "control" for node in (left, right)
    ):
        return "control"
    return "power"


def _rank(terminal: Terminal, kind: str, nodes: dict[str, dict], point: Point):
    port = terminal.port.lower()
    node = nodes[terminal.node]
    explicit = node["port_roles"].get(terminal.port)
    if explicit in {"out", "in"}:
        role = -2 if explicit == "out" else 2
    elif node["class_code"] == "WB":
        role = 1 if port == "src" else -1
    elif (
        node["class_code"] == "PE"
        or kind == "branch"
        and node["class_code"] in _MEASUREMENT
    ):
        role = 1
    elif port.startswith("out") or port in {"sec", "tap", "right"}:
        role = -1
    elif port.startswith("in") or port == "left":
        role = 1
    else:
        role = 0
    if kind == "control":
        return role, point[0], -point[1], terminal
    return role, -point[1], point[0], terminal


def _walk(start: Vertex, graph: dict[Vertex, dict[Vertex, Route]], boundary):
    queue = [(0.0, start)]
    predecessors: dict[Vertex, tuple[Vertex, Route]] = {}
    best = {start: 0.0}
    while queue:
        length, here = heappop(queue)
        if length != best[here]:
            continue
        if here in boundary:
            yield here, predecessors
        if here in boundary and here != start:
            continue
        for neighbor, route in graph[here].items():
            length_to_neighbor = length + sum(
                dist(a, b) for a, b in itertools.pairwise(route)
            )
            if length_to_neighbor < best.get(neighbor, float("inf")):
                best[neighbor] = length_to_neighbor
                predecessors[neighbor] = here, route
                heappush(queue, (length_to_neighbor, neighbor))


def _route(start: Vertex, end: Vertex, predecessors) -> list[dict]:
    if start == end:
        return [{"sheet_id": start[0], "points": [start[1]]}]
    steps = []
    while end != start:
        before, points = predecessors[end]
        steps.append((before[0], end[0], points, before[1], end[1]))
        end = before
    parts = [{"sheet_id": start[0], "points": [start[1]]}]
    for source_sheet, target_sheet, points, source_point, target_point in reversed(
        steps
    ):
        if source_sheet == target_sheet:
            parts[-1]["points"].extend(points[1:])
        else:
            if parts[-1]["points"][-1] != source_point:
                parts[-1]["points"].append(source_point)
            parts.append({"sheet_id": target_sheet, "points": [target_point]})
    for part in parts:
        part["points"] = simplify(tuple(part["points"]))
    return parts


def _device_edges(graph, terminals, nodes) -> list[dict]:
    result = {}
    for start, start_terminals in sorted(terminals.items()):
        for end, predecessors in _walk(start, graph, terminals):
            for origin in start_terminals:
                for destination in terminals[end]:
                    one, two = origin, destination
                    if one.node == two.node:
                        continue
                    key = tuple(sorted((one, two)))
                    if key in result:
                        continue
                    kind = _edge_kind(one, two, nodes)
                    parts = _route(start, end, predecessors)
                    if _rank(one, kind, nodes, start[1]) > _rank(
                        two, kind, nodes, end[1]
                    ):
                        one, two = two, one
                        parts = [
                            {
                                "sheet_id": part["sheet_id"],
                                "points": part["points"][::-1],
                            }
                            for part in reversed(parts)
                        ]
                    result[key] = {
                        "source": one.node,
                        "target": two.node,
                        "source_port": one.port,
                        "target_port": two.port,
                        "kind": kind,
                        "origin": "geometry",
                        "route": parts,
                        "points": parts[0]["points"] if len(parts) == 1 else (),
                    }
    return [
        {"id": f"e{index:03d}", **edge} for index, edge in enumerate(result.values(), 1)
    ]


def _add_labeled_cables(nodes: dict[str, dict], edges: list[dict]) -> None:
    # Some drawings show only a circuit label for the cable. Attach it as a
    # logical relationship when that circuit names exactly one protection device.
    attached = {node for edge in edges for node in (edge["source"], edge["target"])}
    protection = defaultdict(list)
    for node in nodes.values():
        if node["class_code"] in {"QF", "FU"} and "out" in node["ports"]:
            protection[node["sheet_id"], node["cabinet"], node["circuit"]].append(
                node["id"]
            )
    for cable in nodes.values():
        circuit = cable["circuit"]
        if (
            cable["class_code"] != "WL"
            or not circuit
            or cable["id"] in attached
            or cable["tag"].strip().casefold() != circuit.strip().casefold()
            or "in" not in cable["ports"]
        ):
            continue
        candidates = protection[cable["sheet_id"], cable["cabinet"], circuit]
        if len(candidates) == 1 and candidates[0] in attached:
            edges.append(
                {
                    "id": f"e{len(edges) + 1:03d}",
                    "source": candidates[0],
                    "target": cable["id"],
                    "source_port": "out",
                    "target_port": "in",
                    "kind": "power",
                    "origin": "circuit_label",
                    "route": [],
                    "points": [],
                }
            )


def _circuit_views(nodes: dict[str, dict], edges: list[dict]) -> dict:
    children = defaultdict(set)
    control_in = defaultdict(set)
    control_out = defaultdict(set)
    groups = defaultdict(set)
    for edge in edges:
        origin, destination = edge["source"], edge["target"]
        if edge["kind"] == "power":
            children[origin].add(destination)
        if edge["kind"] == "control":
            control_in[destination].add(origin)
            control_out[origin].add(destination)
    power_targets = set().union(*children.values())
    for node in nodes.values():
        kind = node["circuit_kind"]
        if node["id"] in control_in or node["id"] in control_out:
            kind = "control"
        group = node["circuit"] or ("CONTROL" if kind == "control" else "POWER")
        groups[node["cabinet"], group, kind].add(node["id"])
    circuits = []
    for (cabinet, label, kind), members in sorted(groups.items()):
        touching = [
            e["id"] for e in edges if e["source"] in members or e["target"] in members
        ]
        circuit = {
            "id": f"c{len(circuits) + 1:03d}",
            "cabinet": cabinet,
            "label": label,
            "kind": kind,
            "node_ids": sorted(members),
            "edge_ids": touching,
            "entry_nodes": sorted(
                members - (control_in.keys() if kind == "control" else power_targets)
            ),
        }
        if kind == "control":
            circuit["parallel_splits"] = sorted(
                node for node in members if len(control_out.get(node, ())) > 1
            )
            circuit["parallel_merges"] = sorted(
                node for node in members if len(control_in.get(node, ())) > 1
            )
        circuits.append(circuit)
    return {
        "circuits": circuits,
        "children": {
            node: sorted(destinations)
            for node, destinations in sorted(children.items())
        },
        "roots": sorted(nodes.keys() - power_targets),
    }


def reconstruct(project: dict, base: Path = Path(".")) -> dict:
    """Return a netlist and diagnostic warnings for a recognized drawing package."""
    sheets = project["sheets"]
    if not sheets:
        raise ValueError("at least one sheet is required")
    sheet_ids = [sheet["id"] for sheet in sheets]
    if len(set(sheet_ids)) != len(sheet_ids) or not all(sheet_ids):
        raise ValueError("sheet ids must be nonempty and unique")
    nodes: dict[str, dict] = {}
    terminals = defaultdict(list)
    graph = {}
    labels = defaultdict(lambda: defaultdict(set))
    warnings = []
    for sheet in sheets:
        sheet_id = sheet["id"]
        symbols = [
            symbol for symbol in sheet["symbols"] if symbol.get("in_netlist", True)
        ]
        wire_labels = sheet.get("wire_labels", [])
        tolerance = sheet.get("tolerance", 0.15)
        port_tolerance = sheet.get("port_tolerance", tolerance)
        if not all(
            isfinite(value) and value >= 0 for value in (tolerance, port_tolerance)
        ):
            raise ValueError(
                "tolerance and port_tolerance must be finite and nonnegative"
            )
        port_points = {
            _point(p) for symbol in symbols for p in symbol.get("ports", {}).values()
        }
        anchors = port_points | {_point(label["point"]) for label in wire_labels}
        wires = _wires(sheet, base)
        if any(len(bridge) < 3 for bridge in wires.bridges):
            raise ValueError(
                "a bridge requires endpoints and at least one intermediate point"
            )
        sheet_graph = WireGraph(sheet_id, wires, anchors, tolerance)
        ends_only = sheet.get(
            "ports_on_stroke_ends",
            Path(sheet.get("file", "")).suffix.lower() == ".dxf",
        )
        graph.update(sheet_graph.edges)
        for symbol in symbols:
            local_id = symbol["id"]
            node_id = local_id if len(sheets) == 1 else f"{sheet_id}/{local_id}"
            if not local_id or "/" in local_id or "/" in sheet_id or node_id in nodes:
                raise ValueError(f"invalid or repeated symbol id {node_id}")
            ports = {name: _point(p) for name, p in symbol.get("ports", {}).items()}
            klass = symbol["class_code"]
            nodes[node_id] = {
                "id": node_id,
                "tag": symbol.get("tag", ""),
                "class_code": klass,
                "sheet_id": sheet_id,
                "cabinet": symbol.get("cabinet", sheet.get("cabinet", "")),
                "circuit": symbol.get("circuit", ""),
                "circuit_kind": symbol.get(
                    "circuit_kind",
                    "control" if klass in _CONTROL else "power",
                ),
                "bbox": symbol.get("bbox"),
                "ports": ports,
                "port_roles": symbol.get("port_roles", {}),
            }
            by_vertex = defaultdict(list)
            for name, point in ports.items():
                vertex = sheet_graph.attach(
                    point,
                    _port_axis(symbol, name, point),
                    port_tolerance,
                    ends_only=ends_only,
                )
                if vertex is not None:
                    by_vertex[vertex].append(name)
            for vertex, names in by_vertex.items():
                if len(names) > 1:
                    preferred = symbol.get(
                        "primary_port", "in" if klass == "WL" else ""
                    )
                    if preferred not in names:
                        warnings.append(
                            {"type": "ambiguous_ports", "node": node_id, "ports": names}
                        )
                        continue
                    names = [preferred]
                terminals[vertex].append(Terminal(node_id, names[0]))
            if ports and not by_vertex and klass != "WL":
                warnings.append({"type": "unattached_symbol", "node": node_id})
        for label in wire_labels:
            point = _point(label["point"])
            vertex = sheet_graph.attach(point, label.get("axis"), port_tolerance)
            scope = label.get("scope", sheet.get("cabinet") or "")
            number = str(label["number"]).strip().casefold()
            if vertex is not None and number:
                labels[scope, number][sheet_id].add(vertex)
            else:
                warnings.append(
                    {
                        "type": "unattached_wire_label",
                        "sheet": sheet_id,
                        "number": number,
                    }
                )

    for (scope, number), by_sheet in sorted(labels.items()):
        if any(len(vertices) > 1 for vertices in by_sheet.values()):
            warnings.append(
                {"type": "ambiguous_wire_label", "number": number, "scope": scope}
            )
            continue
        vertices = [next(iter(points)) for _, points in sorted(by_sheet.items())]
        for a, b in itertools.pairwise(vertices):
            graph[a][b] = graph[b][a] = ()

    edges = _device_edges(graph, terminals, nodes)
    _add_labeled_cables(nodes, edges)
    views = _circuit_views(nodes, edges)
    for node in nodes.values():
        del node["port_roles"]
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        **views,
        "warnings": warnings,
    }
