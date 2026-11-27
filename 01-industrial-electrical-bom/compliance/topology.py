"""Topology adapters for the v1.0.0 instance-level netlist."""

from collections import deque
import math

import networkx as nx

from .normalize import canonical_tag, normalize_instance, number


class Drawing:
    def __init__(self, data):
        self.data = data
        self.items = {}
        for raw in data["instances"]:
            item = normalize_instance(raw)
            if not isinstance(item["id"], str) or item["id"] in self.items:
                raise ValueError(f"invalid or duplicate instance id: {item['id']}")
            self.items[item["id"]] = item
        self.netlist = data.get("netlist") or {}
        self.edges = self.netlist.get("edges") or []
        self.power = nx.DiGraph()
        self.power.add_nodes_from(self.items)
        self.control = nx.DiGraph()
        self.measure = nx.Graph()
        self.invalid_edges = []
        for edge in self.edges:
            src, target = edge["source"], edge["target"]
            if src not in self.items or target not in self.items:
                self.invalid_edges.append(edge)
                continue
            kind = edge.get("kind")
            if kind == "power":
                self.power.add_edge(src, target)
            if kind == "control":
                self.control.add_edge(src, target)
            if kind == "branch":
                self.measure.add_edge(src, target)
        self.has_control_edges = bool(self.control.edges)
        self.branches = {canonical_tag(b["coil_tag"]): b for b in data.get("control_branches") or []}
        if not self.has_control_edges:
            for branch in self.branches.values():
                series = [i for i in branch["series_ids"] if i in self.items]
                self.control.add_edges_from(zip(series, series[1:]))

    def of(self, *classes):
        return (i for i, item in self.items.items() if item["class_code"] in classes)

    def cls(self, node):
        return self.items[node]["class_code"]

    def tag(self, node):
        return self.items[node]["tag"]

    def value(self, node, field):
        return number(self.items[node]["specs"].get(field))

    def nearest(self, node, *classes):
        """Match nearest upstream devices by hop count, as in ElectroBench."""
        queue = deque((p, 1) for p in self.power.predecessors(node))
        visited = {node}
        found = []
        best = float("inf")
        while queue:
            parent, distance = queue.popleft()
            if distance > best:
                break
            if parent in visited:
                continue
            visited.add(parent)
            if self.cls(parent) in classes:
                best = distance
                found.append(parent)
            else:
                queue.extend((p, distance + 1) for p in self.power.predecessors(parent))
        return sorted(found)

    def ancestors(self, node, *classes):
        return sorted(i for i in nx.ancestors(self.power, node) if not classes or self.cls(i) in classes)

    def control_sources(self, coil):
        if coil not in self.control:
            return []
        upstream = nx.ancestors(self.control, coil)
        graph = self.control.subgraph(upstream | {coil})
        configured = set(self.netlist.get("control_sources") or [])
        sources = upstream & configured
        if not sources:
            sources = {n for n in upstream if self.cls(n) == "TC"}
        if not sources:
            sources = {n for n in upstream if graph.in_degree(n) == 0}
        return sorted(sources)

    def control_path(self, coil, *, excluding=()):
        sources = self.control_sources(coil)
        keep = set(self.control) - set(excluding)
        graph = self.control.subgraph(keep)
        if coil in graph:
            for src in sources:
                if src in graph and nx.has_path(graph, src, coil):
                    return nx.shortest_path(graph, src, coil)
        return []

    def control_ancestors(self, coil):
        return sorted(nx.ancestors(self.control, coil)) if coil in self.control else []

    def box(self, node, unit):
        item = self.items[node]
        sheet = self.data.get("sheet") or {}
        bbox = item.get("bbox_" + unit)
        if bbox is not None:
            return list(bbox)
        scale = sheet.get("px_per_mm")
        height = sheet.get("height_mm")
        if not scale or not height:
            return None
        skew = self.data.get("degradation") or {}
        if unit == "px" and item.get("bbox_mm"):
            x, y, w, h = item["bbox_mm"]
            box = [x * scale, (height - y - h) * scale, w * scale, h * scale]
            if skew.get("type") == "skew":
                angle = math.radians(skew["angle_deg"])
                cx, cy = skew["source_image_width"] / 2, skew["source_image_height"] / 2
                ox, oy = sheet["image_width"] / 2, sheet["image_height"] / 2
                x, y, w, h = box
                corners = [(ox + (a-cx)*math.cos(angle) + (b-cy)*math.sin(angle),
                            oy - (a-cx)*math.sin(angle) + (b-cy)*math.cos(angle))
                           for a in (x, x+w) for b in (y, y+h)]
                xs, ys = zip(*corners)
                box = [min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)]
            return [round(v, 4) for v in box]
        if unit == "mm" and item.get("bbox_px") and skew.get("type") != "skew":
            x, y, w, h = item["bbox_px"]
            return [round(v, 4) for v in (x/scale, height-(y+h)/scale, w/scale, h/scale)]
        return None
