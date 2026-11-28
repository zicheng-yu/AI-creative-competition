"""Control path checks derived from netlist reachability and contact ownership."""

import networkx as nx

from .normalize import canonical_tag
from .repairs import insert_series


def _mandatory(d, coil, contacts):
    return bool(contacts and d.control_path(coil) and not d.control_path(coil, excluding=contacts))


def _reverse_pairs(d):
    coils = list(d.of("KM_COIL"))
    pairs = {coil: canonical_tag(d.branches.get(d.tag(coil), {}).get("pair_tag"))
             for coil in coils}
    for coil in coils:
        explicit = d.items[coil]["extra"].get("pair_tag")
        if explicit:
            pairs[coil] = explicit
    for motor in d.of("M"):
        mains = {d.tag(n) for n in d.nearest(motor, "KM_MAIN")}
        paired = [i for i in coils if d.tag(i) in mains]
        if len(paired) == 2:
            for first, second in (paired, reversed(paired)):
                pairs[first] = pairs[first] or d.tag(second)
    if len(coils) == 2:
        first, second = coils
        tags = {d.tag(first), d.tag(second)}
        reverse_ink = {str(d.items[i]["specs"].get("spec", "")) for i in d.of("SB_NO")}
        has_reverse = any("正转" in label for label in reverse_ink) and any("反转" in label for label in reverse_ink)
        if d.data.get("circuit_kind") == "reversing" or tags == {"KMF", "KMR"} or has_reverse:
            pairs[first] = pairs[first] or d.tag(second)
            pairs[second] = pairs[second] or d.tag(first)
    return {coil: tag for coil, tag in pairs.items() if tag and tag != d.tag(coil)}


def _interlock(d, coil, pair, check):
    candidates = [i for i in d.control_ancestors(coil) if d.cls(i) == "KM_NC"
                  and (d.items[i]["extra"].get("interlocks") or d.tag(i)) == pair]
    ok = _mandatory(d, coil, candidates)
    ops = []
    if not ok and d.control_path(coil):
        ops = [insert_series(d, coil, "KM_NC", pair, "control", extra={"interlocks": pair})]
    check("interlock_missing", not ok, [coil],
          {"coil_tag": d.tag(coil), "pair_tag": pair, "matching_contact_ids": candidates,
           "bypass_path": d.control_path(coil, excluding=candidates)}, ops)


def _self_hold(d, coil, starts, holds):
    graph = d.control
    pairs = []
    for start in starts:
        for contact in holds:
            before = set(graph.predecessors(start)) & set(graph.predecessors(contact))
            after = set(graph.successors(start)) & set(graph.successors(contact))
            if before and after and d.control_path(coil, excluding=starts):
                pairs.append([start, contact])
    return pairs


def _coil_checks(d, check):
    reversing = _reverse_pairs(d)
    coils = list(d.of("KM_COIL", "YC"))
    emergency = [i for i in d.of("SB_NC", "SB_NO")
                 if d.items[i]["extra"].get("role") == "emergency_stop"
                 or "急停" in (d.items[i]["specs"].get("spec") or "")]
    for coil in coils:
        path = d.control_path(coil)
        nodes = d.control_ancestors(coil)
        check("control_coil_unreachable", not path, [coil],
              {"source_ids": d.control_sources(coil), "path": path})
        if coil in reversing:
            _interlock(d, coil, reversing[coil], check)
        if not path:
            continue
        fuses = [i for i in nodes if d.cls(i) == "FU"]
        check("control_fuse_missing", not _mandatory(d, coil, fuses), [coil, *fuses],
              {"fuse_ids": fuses, "unfused_path": d.control_path(coil, excluding=fuses)})
        if d.has_control_edges:
            terminals = sorted(i for i in nx.descendants(d.control, coil) if d.cls(i) == "XT")
            check("control_return_missing", not terminals, [coil, *terminals],
                  {"reachable_terminal_count": len(terminals)})
        relevant_emergency = [i for i in emergency if not d.items[i]["extra"].get("applies_to")
                              or d.tag(coil) in d.items[i]["extra"]["applies_to"]]
        if relevant_emergency or d.data.get("requires_emergency_stop"):
            bypasses = {i: d.control_path(coil, excluding=[i]) for i in relevant_emergency}
            invalid = [i for i in relevant_emergency if bypasses[i] or d.cls(i) != "SB_NC"]
            check("control_emergency_stop_priority", not relevant_emergency or bool(invalid),
                  [coil, *relevant_emergency],
                  {"required_count": max(1, len(relevant_emergency)), "invalid_ids": invalid,
                   "bypass_paths": {i: bypasses[i] for i in invalid}})
        if d.cls(coil) != "KM_COIL":
            continue
        starts = [i for i in nodes if d.cls(i) == "SB_NO" and i not in emergency]
        hits_dol = d.data.get("circuit_kind") in {"reversing", "dol_self_hold"} or bool(starts) or coil in reversing
        if not hits_dol:
            continue
        stops = [i for i in nodes if d.cls(i) == "SB_NC" and i not in emergency]
        check("control_stop_bypass", not _mandatory(d, coil, stops), [coil, *stops],
              {"stop_ids": stops, "bypass_path": d.control_path(coil, excluding=stops)})
        holds = [i for i in nodes if d.cls(i) == "KM_NO" and d.tag(i) == d.tag(coil)]
        if d.has_control_edges:
            parallel = _self_hold(d, coil, starts, holds)
            check("control_self_hold_missing", not parallel, [coil, *starts, *holds],
                  {"start_count": len(starts), "hold_contact_count": len(holds),
                   "parallel_instance_ids": parallel})
        if coil not in reversing:
            all_fr = {d.tag(n) for n in d.of("FR")}
            relays = [i for i in nodes if d.cls(i) == "FR_NC" and (not all_fr or d.tag(i) in all_fr)]
            if all_fr:
                check("control_overload_contact", not _mandatory(d, coil, relays), [coil, *relays],
                      {"overload_contact_ids": relays, "unprotected_path": d.control_path(coil, excluding=relays)})


def _ats_checks(d, check):
    transfer = list(d.of("ATS"))
    if not transfer and d.data.get("circuit_kind") != "ats":
        return
    for node in transfer:
        feeds = sorted(d.power.predecessors(node))
        ports = {edge.get("target_port") for edge in d.edges if edge.get("kind") == "power"
                 and edge.get("target") == node and edge.get("target_port") is not None}
        check("ats_source_count", len(feeds) != 2 or bool(ports) and len(ports) != 2,
              [node, *feeds], {"input_count": len(feeds), "labeled_input_port_count": len(ports)})
        mechanical = d.items[node]["extra"].get("mechanical_interlock")
        check("ats_mechanical_interlock", mechanical is not True, [node], {"mechanical_interlock": mechanical})
    closing = list(d.of("YC"))
    for ordinal, coil in enumerate(closing):
        info = d.items[coil]["extra"]
        ancestors = d.control_ancestors(coil)
        pair = info.get("pair_tag") or canonical_tag(d.branches.get(d.tag(coil), {}).get("pair_tag"))
        if not pair and len(closing) == 2:
            other = d.tag(closing[1 - ordinal])
            pair = "QF" + other[2:] if other.startswith("YC") else other
        blocks = [i for i in ancestors if d.cls(i) in {"KA_NC", "KM_NC"}
                  and d.items[i]["extra"].get("interlocks") == pair and pair]
        integrated = info.get("controller_open_feedback") is True
        check("ats_electrical_interlock", not (integrated or _mandatory(d, coil, blocks)), [coil, *blocks],
              {"pair_tag": pair, "nc_contact_ids": blocks, "controller_open_feedback": integrated})
        if info.get("source_role") != "backup" and not (len(closing) == 2 and d.tag(coil) == "YC2"):
            continue
        contacts = [i for i in ancestors if d.cls(i) == "KT_NO"]
        timers = [i for i in ancestors if d.cls(i) == "KT_COIL" and d.tag(i) in {d.tag(n) for n in contacts}]
        delay = d.value(coil, "transfer_delay_s")
        check("ats_transfer_delay", not (delay and delay > 0 or (timers and _mandatory(d, coil, contacts))),
              [coil, *timers, *contacts], {"timer_count": len(timers), "controller_delay_s": delay})


def _wiring(d, check):
    for edge in d.edges:
        source, target = edge["source"], edge["target"]
        if edge.get("kind") != "control" or source not in d.items or target not in d.items:
            continue
        for node, side in ((source, "source"), (target, "target")):
            port = edge.get(side + "_port")
            ports = d.items[node].get("ports") or {}
            if d.cls(node) == "XT" and port and ports:
                check("control_terminal_missing", port not in ports, [node],
                      {"edge_id": edge.get("id"), "port": port, "available_ports": sorted(ports)})
        first, second = edge.get("source_wire_no"), edge.get("target_wire_no")
        expected = edge.get("wire_no")
        if first is not None and second is not None or expected is not None and (first is not None or second is not None):
            values = {str(n).strip().upper() for n in (first, second, expected) if n is not None}
            check("control_wire_number_mismatch", len(values) > 1, [source, target],
                  {"edge_id": edge.get("id"), "wire_numbers": sorted(values)})


def control_checks(drawing, check):
    _coil_checks(drawing, check)
    _ats_checks(drawing, check)
    _wiring(drawing, check)
