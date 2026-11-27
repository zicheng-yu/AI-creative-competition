"""Equipment and assembly checks that expose missing evidence explicitly."""

import re

import networkx as nx

from .normalize import number
from .repairs import insert_series

FIVE_PREVENTIONS = (
    "breaker_misoperation", "isolator_under_load", "earth_on_live",
    "energize_while_earthed", "enter_live_compartment",
)


def _grounded(d, node):
    ground = nx.DiGraph()
    ground.add_edges_from((e["source"], e["target"]) for e in d.edges
                          if e.get("kind") in {"pe", "power"} and e["target"] in d.items
                          and (e.get("kind") == "pe" or d.cls(e["target"]) == "PE"))
    return node in ground and any(i in d.items and d.cls(i) == "PE"
                                 for i in nx.descendants(ground, node))


def _motors(d, check):
    for motor in d.of("M"):
        ancestors = d.ancestors(motor)
        # Remove each required class in turn to expose a parallel unprotected feed.
        roots = [i for i in ancestors if d.power.in_degree(i) == 0]
        required = (("overload_FR", {"FR"}), ("short_circuit_QF_or_FU", {"QF", "FU"}),
                    ("control_KM", {"KM_MAIN"}))
        missing = []
        for name, classes in required:
            matches = {i for i in ancestors if d.cls(i) in classes}
            graph = d.power.subgraph(set(d.power) - matches)
            if not matches or any(i in graph and nx.has_path(graph, i, motor) for i in roots):
                missing.append(name)
        operations = []
        if missing == ["overload_FR"] and list(d.power.predecessors(motor)):
            if all(d.cls(i) == "KM_MAIN" for i in d.power.predecessors(motor)):
                suffix = d.tag(motor)[1:]
                existing = {d.tag(i) for i in d.of("FR")}
                tag = f"FR{suffix}"
                if tag in existing:
                    tag = next(f"FR{i}" for i in range(1, len(existing) + 2) if f"FR{i}" not in existing)
                rated = d.value(motor, "In_A")
                specs = {"model": "选型待确认", "spec": "整定电流待核对"}
                if rated:
                    specs.update(Ir_A=rated, spec=f"整定{rated:g}A")
                operations = [insert_series(d, motor, "FR", tag, "power", specs=specs)]
        check("motor_protection_missing", bool(missing), [motor],
              {"missing": missing, "power_ancestor_count": len(ancestors)}, operations)
        grounded = _grounded(d, motor)
        check("motor_pe_missing", not grounded, [motor], {"has_pe_path": grounded})
        rated = d.value(motor, "In_A")
        if not rated:
            continue
        for contactor in d.nearest(motor, "KM_MAIN"):
            ie = d.value(contactor, "Ie_A")
            if ie is not None:
                check("motor_contactor_rating", ie < rated, [contactor, motor],
                      {"contactor_Ie_A": ie, "motor_In_A": rated})
        for relay in d.nearest(motor, "FR"):
            setting = d.value(relay, "Ir_A")
            if setting is not None:
                low = d.value(motor, "overload_min_A") or rated * 0.9
                high = d.value(motor, "overload_max_A") or rated * 1.1
                check("motor_overload_setting", not low <= setting <= high, [relay, motor],
                      {"motor_In_A": rated, "Ir_A": setting, "range_A": [round(low, 4), round(high, 4)]})


def _ratio(value):
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*", str(value))
    return tuple(map(float, match.groups())) if match else (None, None)


def _instrument(d, check):
    for node in d.of("TA", "TV"):
        item = d.items[node]
        specs = item["specs"]
        zone = nx.node_connected_component(d.measure, node) - {node} if node in d.measure else set()
        current = d.cls(node) == "TA"
        meters = sorted(i for i in zone if d.cls(i) in ({"PA", "PJ"} if current else {"PV", "PJ"}))
        primary, secondary = _ratio(specs.get("ratio"))
        if current:
            load = d.value(node, "load_A")
            if load is None:
                load = max((d.value(i, "Ib_A") or 0 for i in nx.descendants(d.power, node)
                            if d.cls(i) == "WL" and d.items[i].get("circuit") == item.get("circuit")), default=0)
            if primary is not None and load:
                check("ct_ratio_load", not load <= primary <= 2 * load, [node],
                      {"primary_A": primary, "load_A": load, "screening_max_ratio": 2})
            closed = item["extra"].get("secondary_closed")
            shorted = item["extra"].get("secondary_shorted") is True
            check("ct_secondary_open", not shorted and closed is not True, [node, *meters],
                  {"secondary_closed": closed, "secondary_shorted": shorted, "meter_count": len(meters)})
            for meter in meters:
                rated = d.value(meter, "input_A")
                if rated is None and d.cls(meter) == "PA":
                    match = re.search(r"(\d+(?:\.\d+)?)\s*A\b", d.items[meter]["specs"].get("spec", ""))
                    rated = number(match[1]) if match else None
                if rated is not None and secondary is not None:
                    check("ct_meter_rating", rated != secondary, [node, meter],
                          {"secondary_A": secondary, "meter_input_A": rated})
        else:
            voltage = d.value(node, "circuit_V")
            if primary is not None and voltage:
                primary_v = primary * (1000 if "KV" in specs.get("spec", "").upper() else 1)
                primary_v = d.value(node, "primary_V") or primary_v
                check("vt_ratio_voltage", abs(primary_v - voltage) > 0.1 * voltage, [node],
                      {"primary_V": primary_v, "circuit_V": voltage})
            check("vt_meter_missing", not meters, [node, *meters], {"meter_count": len(meters)})


def _assemblies(d, check):
    for node in d.of("C"):
        reactors = d.nearest(node, "L")
        protectors = d.nearest(node, "QF", "FU")
        switches = d.nearest(node, "KM_MAIN", "QF")
        check("capacitor_reactor_missing", not reactors, [node, *reactors], {"reactor_count": len(reactors)})
        check("capacitor_switch_protection", not (protectors and switches), [node, *protectors, *switches],
              {"protector_count": len(protectors), "switch_count": len(switches)})
    for node in d.of("SPD"):
        source_bus = set(d.ancestors(node, "WB"))
        protectors = [i for i in d.nearest(node, "QF", "FU")
                      if source_bus & nx.ancestors(d.power, i)]
        integrated = d.items[node]["extra"].get("integral_backup") is True
        check("spd_backup_missing", not (protectors or integrated), [node, *protectors],
              {"dedicated_protector_count": len(protectors), "integral_backup": integrated})
        grounded = _grounded(d, node)
        check("spd_pe_missing", not grounded, [node], {"has_pe_path": grounded})
    if d.data.get("cabinet") != "KYN28":
        return
    qfs, isolators, earth = (list(d.of(code)) for code in ("QF", "QS", "QE"))
    for node in qfs:
        specs = d.items[node]["specs"]
        vacuum = specs.get("technology") == "vacuum" or bool(re.search(r"\b(?:VCB|VD4)\b", specs.get("model", "")))
        rated = d.value(node, "voltage_V")
        check("kyn_vacuum_breaker", not vacuum or rated is not None and rated < 10000, [node],
              {"vacuum": vacuum, "rated_V": rated, "system_V": 10000})
    check("kyn_switchgear_members", not (qfs and isolators and earth), qfs + isolators + earth,
          {"breaker_count": len(qfs), "isolator_count": len(isolators), "earthing_switch_count": len(earth)})
    evidence = (d.data.get("assembly") or {}).get("five_preventions") or {}
    missing = [key for key in FIVE_PREVENTIONS if evidence.get(key) is not True]
    check("kyn_five_preventions", bool(missing), qfs + isolators + earth,
          {"required_count": len(FIVE_PREVENTIONS), "missing_or_unverified": missing})
    for node in earth:
        grounded = _grounded(d, node)
        check("kyn_earthing_path", not grounded, [node], {"has_pe_path": grounded})


def equipment_checks(drawing, check):
    _motors(drawing, check)
    _instrument(drawing, check)
    _assemblies(drawing, check)
