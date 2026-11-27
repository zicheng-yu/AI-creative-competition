"""Build a wire graph without passing through devices or unmarked crossings."""

from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass, field
from math import hypot

Point = tuple[float, float]
Segment = tuple[Point, Point]
Vertex = tuple[str, Point, str]
Route = tuple[Point, ...]


@dataclass
class DrawingWires:
    segments: list[Segment] = field(default_factory=list)
    junctions: list[Point] = field(default_factory=list)
    bridges: list[Route] = field(default_factory=list)


def _snap(values: set[float], tolerance: float) -> dict[float, float]:
    snapped = {}
    anchor = None
    for value in sorted(values):
        if anchor is None or value - anchor > tolerance:
            anchor = value
        snapped[value] = anchor
    return snapped


def simplify(points: Route) -> Route:
    result: list[Point] = []
    for point in points:
        if result and point == result[-1]:
            continue
        if len(result) >= 2:
            (ax, ay), (bx, by) = result[-2:]
            x, y = point
            if (ax == bx == x and min(ay, y) <= by <= max(ay, y)) or (
                ay == by == y and min(ax, x) <= bx <= max(ax, x)
            ):
                result.pop()
        result.append(point)
    return tuple(result)


def _axis(a: Point, b: Point) -> str:
    if a[1] == b[1]:
        return "h"
    if a[0] == b[0]:
        return "v"
    return ""


def _orthogonal_cuts(segments: set[Segment]) -> dict[Point, set[Point]]:
    rows = defaultdict(list)
    columns = defaultdict(list)
    adjacent: dict[Point, set[Point]] = defaultdict(set)
    for a, b in sorted(segments):
        adjacent[a]
        adjacent[b]
        if _axis(a, b) == "h":
            rows[a[1]].append((a[0], b[0]))
        elif _axis(a, b) == "v":
            columns[a[0]].append((a[1], b[1]))
        else:
            adjacent[a].add(b)
            adjacent[b].add(a)
    for x, vertical in columns.items():
        for y, horizontal in rows.items():
            if any(low <= x <= high for low, high in horizontal) and any(
                low <= y <= high for low, high in vertical
            ):
                adjacent[x, y]
    return adjacent


class WireGraph:
    def __init__(
        self, sheet: str, wires: DrawingWires, anchors: set[Point], tolerance: float
    ):
        self.sheet = sheet
        points = anchors | set(wires.junctions)
        points.update(point for segment in wires.segments for point in segment)
        points.update(
            point for bridge in wires.bridges for point in (bridge[0], bridge[-1])
        )
        self.x = _snap({x for x, _ in points}, tolerance)
        self.y = _snap({y for _, y in points}, tolerance)
        segments = {
            tuple(sorted((self.snap(a), self.snap(b)))) for a, b in wires.segments
        }
        segments = {(a, b) for a, b in segments if a != b}
        adjacent = _orthogonal_cuts(segments)
        junctions = {self.snap(point) for point in wires.junctions}
        bridge_ends = {
            self.snap(point) for path in wires.bridges for point in (path[0], path[-1])
        }
        for position in (
            {self.snap(point) for point in anchors} | junctions | bridge_ends
        ):
            adjacent[position]

        # Split runs at end points, anchors, Ts and crossings. Unioning subsegments
        # here also removes duplicated and partially overlapping collinear strokes.
        rows = defaultdict(list)
        columns = defaultdict(list)
        for x, y in sorted(adjacent):
            rows[y].append((x, y))
            columns[x].append((x, y))
        for a, b in sorted(segments):
            axis = _axis(a, b)
            if not axis:
                continue
            candidates = rows[a[1]] if axis == "h" else columns[a[0]]
            cuts = [point for point in candidates if a <= point <= b]
            for left, right in itertools.pairwise(cuts):
                adjacent[left].add(right)
                adjacent[right].add(left)

        crosses = set()
        for point, neighbors in adjacent.items():
            x, y = point
            arms = {(nx > x, ny > y, _axis(point, (nx, ny))) for nx, ny in neighbors}
            if (
                point not in junctions
                and {
                    (False, False, "h"),
                    (True, False, "h"),
                    (False, False, "v"),
                    (False, True, "v"),
                }
                <= arms
            ):
                crosses.add(point)

        self.edges: dict[Vertex, dict[Vertex, Route]] = defaultdict(dict)
        for point, neighbors in adjacent.items():
            for other in sorted(neighbors):
                axis = _axis(point, other)
                a = (sheet, point, axis if point in crosses else "")
                b = (sheet, other, axis if other in crosses else "")
                self.edges[a][b] = (point, other)
        for bridge in wires.bridges:
            a, b = self.snap(bridge[0]), self.snap(bridge[-1])
            if a == b:
                continue
            va = self._bridge_end(a, bridge[1], crosses)
            vb = self._bridge_end(b, bridge[-2], crosses)
            path = (a, *bridge[1:-1], b)
            self.edges[va][vb] = path
            self.edges[vb][va] = path[::-1]

        self.stroke_ends = (
            {point for segment in segments for point in segment}
            | bridge_ends
            | junctions
        )
        self.at: dict[Point, list[Vertex]] = defaultdict(list)
        for vertex in sorted(self.edges):
            self.at[vertex[1]].append(vertex)

    def _bridge_end(self, point: Point, inward: Point, crosses: set[Point]) -> Vertex:
        dx, dy = abs(point[0] - inward[0]), abs(point[1] - inward[1])
        axis = ("h" if dx >= dy else "v") if point in crosses else ""
        return self.sheet, point, axis

    def snap(self, point: Point) -> Point:
        return self.x[point[0]], self.y[point[1]]

    def attach(
        self,
        point: Point,
        axis: str | None,
        tolerance: float,
        *,
        ends_only: bool = False,
    ) -> Vertex | None:
        snapped = self.snap(point)
        positions = self.stroke_ends if ends_only else self.at
        candidates = self.at.get(snapped, []) if snapped in positions else []
        if not candidates and tolerance:
            distances = (
                (hypot(snapped[0] - pos[0], snapped[1] - pos[1]), pos)
                for pos in positions
                if pos in self.at
            )
            nearby = sorted(
                (distance, pos) for distance, pos in distances if distance <= tolerance
            )
            if nearby and (len(nearby) == 1 or nearby[0][0] < nearby[1][0]):
                candidates = self.at[nearby[0][1]]
        if len(candidates) == 1:
            return candidates[0]
        if axis:
            return next((vertex for vertex in candidates if vertex[2] == axis), None)
        return None
