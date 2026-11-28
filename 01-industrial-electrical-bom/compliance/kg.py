"""Three-layer electrical knowledge graph and deterministic selection queries."""

from functools import lru_cache
import json
from pathlib import Path

import networkx as nx

from electrobench.ampacity import AMPACITY_TABLE
from electrobench.catalog import ALIASES, CLASSES

from .normalize import poles

DATA = Path(__file__).with_name("kb_data")


def records(name):
    return json.loads((DATA / (name + ".json")).read_text(encoding="utf-8"))


def material_code(value):
    return {"cu": "Cu", "铜": "Cu", "copper": "Cu", "al": "Al", "铝": "Al",
            "aluminum": "Al", "aluminium": "Al"}.get(str(value).lower())


@lru_cache
def cable_table(material):
    if material == "Cu":
        return dict(AMPACITY_TABLE)
    if material == "Al":
        return {size: int(iz * 0.75) for size, iz in AMPACITY_TABLE}
    return {}


def select_cable(ib, protection, material="Cu", *, minimum_section=0):
    """Select the first passing section for the documented screening profile."""
    material = material_code(material)
    if ib is None or protection is None or ib < 0 or protection <= 0 or ib > protection:
        return None
    for size, iz in cable_table(material).items():
        if iz >= protection and size >= minimum_section:
            return {"material": material, "section_mm2": size, "Iz_A": iz,
                    "profile": "ebjs_cu_xlpe" if material == "Cu" else "demo_al_xlpe_0.75"}
    return None


def select_breakers(*, min_current, max_current=None, poles_required=None, voltage=None,
                    minimum_breaking=None, capacity_field="icu_kA", curve=None,
                    brand=None, device_type=None):
    """Filter candidate ratings using the same capacity metric and voltage."""
    if capacity_field not in {"icu_kA", "icn_kA", "breaking_kA"}:
        raise ValueError("unknown breaking-capacity metric")
    candidates = []
    for part in records("breakers"):
        current = part["In_A"]
        capacity = part[capacity_field]
        if current is None or current < min_current or max_current is not None and current > max_current:
            continue
        if poles_required and part["poles"] != poles(poles_required):
            continue
        if voltage and (part["voltage_V"] is None or part["voltage_V"] < voltage):
            continue
        if minimum_breaking and (not voltage or capacity is None or capacity < minimum_breaking):
            continue
        if curve and part["curve"] != curve or brand and part["brand"] != brand:
            continue
        if device_type and part["device_type"] != device_type:
            continue
        candidates.append(part)
    return sorted(candidates, key=lambda part: (part["In_A"], part["model"]))


def build_kg():
    from .engine import RULES

    graph = nx.MultiDiGraph(schema_version="1.0.0")
    for part in CLASSES:
        letter = part.bom_letter or part.code
        graph.add_node(f"symbol:{part.code}", layer=1, type="symbol", label=part.name_zh,
                       class_id=part.class_id, class_code=part.code, class_name_en=part.name_en,
                       workshop_code=letter, iec81346=part.iec81346,
                       bom_anchor=part.default_bom_anchor, in_netlist=part.default_in_netlist)
        if part.iec81346:
            iec_id = f"iec:{part.iec81346}"
            graph.add_node(iec_id, layer=1, type="reference_class", label=part.iec81346,
                           standard_code="IEC 81346-2:2019")
            graph.add_edge(f"symbol:{part.code}", iec_id, relation="classified_as")
        aliases = {part.name_zh, letter}
        if letter in ALIASES:
            aliases.add(ALIASES[letter])
        if part.code == "QF":
            aliases.update(("MCCB", "MCB", "塑壳断路器", "微型断路器"))
        for alias in sorted(aliases):
            graph.add_node(f"alias:{alias}", layer=1, type="alias", label=alias)
            graph.add_edge(f"alias:{alias}", f"symbol:{part.code}", relation="can_mean")
    for part in records("breakers"):
        identifier = "product:" + part["model"]
        graph.add_node(identifier, layer=2, type="breaker", label=part["model"], **part)
        graph.add_edge("symbol:QF", identifier, relation="has_catalog_candidate")
    for material in ("Cu", "Al"):
        for size, iz in cable_table(material).items():
            identifier = f"cable:{material}:{size}"
            graph.add_node(identifier, layer=2, type="cable_rating", label=f"{material} {size} mm²",
                           material=material, section_mm2=size, Iz_A=iz,
                           profile="ebjs_cu_xlpe" if material == "Cu" else "demo_al_xlpe_0.75")
            graph.add_edge("symbol:WL", identifier, relation="has_screening_rating")
    for clause in records("clauses"):
        identifier = "clause:" + clause["clause_id"]
        graph.add_node(identifier, layer=3, type="clause", label=clause["title"], **clause)
        classes = [p.code for p in CLASSES] if "*" in clause["applicable_classes"] else clause["applicable_classes"]
        for code in classes:
            graph.add_edge("symbol:" + code, identifier, relation="subject_to")
    for rule in RULES.values():
        identifier = "rule:" + rule.id
        graph.add_node(identifier, layer=3, type="rule", label=rule.title, family=rule.family,
                       failure_severity=rule.severity)
        for ref in rule.refs:
            graph.add_edge(identifier, "clause:" + ref, relation="interprets")
    return graph


def export_kg(graph, seeds=None, *, hops=2):
    """Return stable node-link records, optionally restricted by graph distance."""
    ordered = sorted(graph)
    if seeds is not None:
        undirected = graph.to_undirected(as_view=True)
        reached = set()
        for seed in seeds:
            if seed in graph:
                reached.update(nx.single_source_shortest_path_length(undirected, seed, cutoff=hops))
        ordered = sorted(reached)
    subgraph = graph.subgraph(ordered)
    return {
        "schema_version": "1.0.0", "directed": True, "multigraph": True,
        "nodes": [{"id": node, **graph.nodes[node]} for node in ordered],
        "edges": [{"source": a, "target": b, "key": k, **attributes}
                  for a, b, k, attributes in sorted(subgraph.edges(keys=True, data=True),
                                                    key=lambda e: e[:3])],
    }
