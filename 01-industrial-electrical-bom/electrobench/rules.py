"""Deterministic compliance rules shared by the generator and the validator.

A clean drawing stores an empty finding list. A defect drawing stores exactly
the findings these functions return, so the validator can recompute them.
"""

from __future__ import annotations

from collections import defaultdict, deque

from .model import DrawingRecord, Instance

# Cited because the clauses exist. The operational tests under them are the
# ElectroBench benchmark definitions, spelled out in docs/SCHEMA.md.
REF_SELECTIVITY = "GB 50054-2011 6.1.2"
REF_AMPACITY = "GB 50054-2011 6.3.3"
REF_MOTOR = "GB/T 5226.1-2019 7.2; GB/T 5226.1-2019 7.3; GB 50054-2011 6.1.1"
REF_INTERLOCK = "GB/T 5226.1-2019 9.3"


def _parents(drawing: DrawingRecord) -> dict[str, list[str]]:
    parents: dict[str, list[str]] = defaultdict(list)
    for edge in drawing.edges:
        if edge.kind == "power":
            parents[edge.target].append(edge.source)
    return parents


def _nearest(start: str, parents: dict[str, list[str]], pred) -> list[str]:
    """All matches at the minimum hop distance. Do not search past a match."""
    best: int | None = None
    found: list[str] = []
    seen: set[str] = set()
    queue: deque[tuple[str, int]] = deque((parent, 1) for parent in parents.get(start, []))
    while queue:
        node, dist = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        if pred(node):
            if best is None or dist < best:
                best = dist
                found = [node]
            elif dist == best:
                found.append(node)
            continue
        if best is not None and dist >= best:
            continue
        for parent in parents.get(node, []):
            queue.append((parent, dist + 1))
    return found


def _ancestors(start: str, parents: dict[str, list[str]]) -> list[str]:
    seen: list[str] = []
    known: set[str] = set()
    queue = deque(parents.get(start, []))
    while queue:
        node = queue.popleft()
        if node in known:
            continue
        known.add(node)
        seen.append(node)
        queue.extend(parents.get(node, []))
    return seen


def evaluate(drawing: DrawingRecord) -> list[dict]:
    by_id = drawing.by_id()
    parents = _parents(drawing)
    findings: list[dict] = []

    def inst(node_id: str) -> Instance:
        return by_id[node_id]

    for item in drawing.instances:
        if item.class_code != "QF":
            continue
        upstream = _nearest(item.id, parents, lambda node: inst(node).class_code == "QF")
        down_in = int(item.specs["In_A"])
        for up_id in upstream:
            up = inst(up_id)
            up_in = int(up.specs["In_A"])
            if down_in > up_in:
                findings.append(
                    {
                        "rule_id": "selectivity_inversion",
                        "severity": "error",
                        "instance_ids": [up.id, item.id],
                        "tags": [up.tag, item.tag],
                        "standard_refs": [REF_SELECTIVITY],
                        "message": (
                            f"上级断路器 {up.tag} In={up_in}A 小于下级 {item.tag} In={down_in}A"
                        ),
                        "evidence": {"upstream_In_A": up_in, "downstream_In_A": down_in},
                    }
                )

    for item in drawing.instances:
        if item.class_code != "WL":
            continue
        iz = int(item.specs["Iz_A"])
        ib = int(item.specs["Ib_A"])
        protectors = _nearest(
            item.id,
            parents,
            lambda node: inst(node).class_code in {"QF", "FU"},
        )
        for prot_id in protectors:
            prot = inst(prot_id)
            current = int(prot.specs["In_A"])
            if current > iz or ib > iz:
                findings.append(
                    {
                        "rule_id": "ampacity_insufficient",
                        "severity": "error",
                        "instance_ids": [prot.id, item.id],
                        "tags": [prot.tag, item.tag],
                        "standard_refs": [REF_AMPACITY],
                        "message": (
                            f"{item.tag} 载流量 Iz={iz}A，保护 {prot.tag} In={current}A，"
                            f"计算电流 Ib={ib}A，不满足 Ib≤In≤Iz"
                        ),
                        "evidence": {"In_A": current, "Ib_A": ib, "Iz_A": iz, "section_mm2": item.specs["section_mm2"]},
                    }
                )

    for item in drawing.instances:
        if item.class_code != "M":
            continue
        ancestor_ids = _ancestors(item.id, parents)
        classes = {inst(node).class_code for node in ancestor_ids}
        missing = []
        if "FR" not in classes:
            missing.append("overload_FR")
        if "QF" not in classes and "FU" not in classes:
            missing.append("short_circuit_QF_or_FU")
        if missing:
            findings.append(
                {
                    "rule_id": "motor_protection_missing",
                    "severity": "error",
                    "instance_ids": [item.id],
                    "tags": [item.tag],
                    "standard_refs": [REF_MOTOR],
                    "message": f"电动机 {item.tag} 保护缺配: {', '.join(missing)}",
                    "evidence": {"missing": missing},
                }
            )

    if drawing.circuit_kind == "reversing":
        for branch in drawing.control_branches:
            series = [by_id[node_id] for node_id in branch.series_ids]
            ok = any(
                node.class_code == "KM_NC" and node.extra.get("interlocks") == branch.pair_tag
                for node in series
            )
            if not ok:
                findings.append(
                    {
                        "rule_id": "interlock_missing",
                        "severity": "error",
                        "instance_ids": [node.id for node in series if node.class_code == "KM_COIL"],
                        "tags": [branch.coil_tag],
                        "standard_refs": [REF_INTERLOCK],
                        "message": f"{branch.coil_tag} 支路缺少对 {branch.pair_tag} 的常闭电气互锁",
                        "evidence": {"coil_tag": branch.coil_tag, "pair_tag": branch.pair_tag},
                    }
                )

    findings.sort(key=lambda item: (item["rule_id"], tuple(item["instance_ids"]), item["message"]))
    return findings
