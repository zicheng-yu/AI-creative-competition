"""Protection coordination and conductor sizing checks."""

import re
import networkx as nx

from electrobench.ampacity import cable_spec
from .kg import cable_table, material_code, select_breakers, select_cable
from .normalize import number, poles
from .repairs import update_specs

MARGIN = 1.6


def _voltage(drawing, node):
    voltage = drawing.value(node, "voltage_V")
    if voltage:
        return voltage
    match = re.search(r"(\d+(?:\.\d+)?)\s*(kV|V)", drawing.data.get("voltage") or "", re.I)
    return float(match[1]) * (1000 if match[2].lower() == "kv" else 1) if match else None


def _upstream_change(drawing, up, required):
    specs = drawing.items[up]["specs"]
    current = drawing.value(up, "In_A")
    if current is None:
        return []
    # Account for all immediate protected branches before proposing a current change.
    for down in drawing.of("QF"):
        if up in drawing.nearest(down, "QF"):
            required = max(required, MARGIN * (drawing.value(down, "In_A") or 0))
    cables = [i for i in drawing.of("WL") if up in drawing.nearest(i, "QF", "FU")]
    limits = [drawing.value(i, "Iz_A") for i in cables]
    if any(v is None for v in limits):
        return []
    required = max([required] + [drawing.value(i, "Ib_A") or 0 for i in cables])
    upper = min(limits, default=float("inf"))
    upstream = [drawing.value(i, "In_A") for i in drawing.nearest(up, "QF")]
    if any(v is None for v in upstream):
        return []
    if upstream:
        upper = min(upper, min(upstream) / MARGIN)
    for parent in drawing.nearest(up, "QS"):
        limit = drawing.value(parent, "In_A")
        if limit:
            upper = min(upper, limit)
    model = specs.get("model") or ""
    # ElectroBench synthetic part numbers support a repeatable preview of the
    # fault repair. Manufacturer-backed candidates use their catalog ratings.
    if re.fullmatch(r"EB-(?:MCCB|ACB)-\d+/\d+", model):
        capacities = (100, 125, 160, 200, 225, 250, 315, 400, 500, 630, 800, 1000, 1250)
        existing_frame = drawing.value(up, "frame_A") or current
        rating = next((amp for amp in capacities if required <= amp <= upper), None)
        frame = next((amp for amp in capacities if rating is not None and amp >= max(existing_frame, rating)), None)
        if frame is not None:
            spec = re.sub(r"\bIn=\d+A", f"In={rating}A", specs["spec"])
            return [update_specs(drawing, up, {"In_A": rating, "frame_A": frame,
                                               "model": model.split("-")[0] + "-" + model.split("-")[1]
                                               + f"-{frame}/{rating}", "spec": spec})]
        return []
    if not poles(specs.get("poles")) or not drawing.value(up, "icu_kA") or not _voltage(drawing, up):
        return []
    candidates = select_breakers(min_current=required, max_current=upper, voltage=_voltage(drawing, up),
                                 minimum_breaking=drawing.value(up, "icu_kA"),
                                 poles_required=specs.get("poles"), device_type="MCCB")
    if not candidates:
        return []
    part = candidates[0]
    values = {k: part[k] for k in ("model", "In_A", "frame_A", "icu_kA", "poles")}
    return [update_specs(drawing, up, values | {"spec": part["model"]})]


def _breaker_checks(d, check):
    for node in d.of("QF"):
        current, frame, icu, ik = (d.value(node, key) for key in ("In_A", "frame_A", "icu_kA", "Ik_kA"))
        if current is not None and frame is not None:
            check("breaker_frame_overload", current > frame, [node], {"In_A": current, "Inm_A": frame})
        metric = "icu_kA"
        capacity = icu
        for alternative in ("breaking_kA", "icn_kA"):
            if capacity is None and d.value(node, alternative) is not None:
                metric, capacity = alternative, d.value(node, alternative)
        if capacity is not None and ik is not None:
            check("breaker_short_circuit_rating", capacity < ik, [node], {metric: capacity, "Ik_kA": ik})
        for up in d.nearest(node, "QF"):
            upstream_icu = d.value(up, "icu_kA")
            if icu is not None and upstream_icu is not None:
                check("breaking_coordination_review", upstream_icu < icu, [up, node],
                      {"upstream_Icu_kA": upstream_icu, "downstream_Icu_kA": icu})
            upstream_in = d.value(up, "In_A")
            if current is None or current <= 0 or upstream_in is None:
                continue
            evidence = {"upstream_In_A": upstream_in, "downstream_In_A": current,
                        "ratio": round(upstream_in / current, 6), "screening_min_ratio": MARGIN}
            inversion = upstream_in < current
            low = not inversion and upstream_in < MARGIN * current
            ops = _upstream_change(d, up, MARGIN * current) if inversion or low else []
            check("selectivity_inversion", inversion, [up, node], evidence, ops)
            if not inversion:
                check("selectivity_margin_low", low, [up, node], evidence, ops)
        if not d.data.get("cabinet") or not any(d.cls(n) == "WB" for n in nx.descendants(d.power, node)):
            continue
        switches = d.nearest(node, "QS")
        downstream = sorted(n for n in nx.descendants(d.power, node) if d.cls(n) == "QS"
                            and any(nx.has_path(d.power, n, wb) for wb in d.of("WB")))
        integrated = d.items[node]["specs"].get("isolation_rated") is True
        check("incoming_isolation_missing", not (switches or downstream or integrated), [node],
              {"upstream_isolator_count": len(switches), "downstream_isolator_count": len(downstream),
               "integral_isolation": integrated})
        if switches or downstream:
            check("incoming_isolation_order", not switches and bool(downstream), [node, *switches, *downstream],
                  {"upstream_count": len(switches), "downstream_count": len(downstream)})
        for switch in switches:
            rated = d.value(switch, "In_A")
            if rated is not None and current is not None:
                check("isolator_current_rating", rated < current, [switch, node],
                      {"isolator_In_A": rated, "breaker_In_A": current})


def _cable_change(d, node, ib, currents, section, material):
    if ib is None or not currents or any(ib > current for current in currents):
        return []
    choice = select_cable(ib, max(currents), material, minimum_section=section or 0)
    if not choice:
        return []
    specs = d.items[node]["specs"]
    model = specs.get("model")
    if model not in {"YJV", "YJLV"} or material not in {"Cu", "Al"}:
        return []
    size = choice["section_mm2"]
    # Preserve the core arrangement and any explicitly larger PE.
    old = specs.get("spec", "")
    spec, changes = re.subn(r"([xX×乘])[\d.]+", lambda m: m[1] + str(size), old, count=1)
    if not changes:
        return []
    values = {"section_mm2": size, "Iz_A": choice["Iz_A"], "spec": spec}
    separate_pe = re.search(r"([+加]1[xX×乘])([\d.]+)", spec)
    if separate_pe:
        reference, _ = cable_spec(size)
        pe = max(float(separate_pe[2]), float(reference.rsplit("x", 1)[1]))
        values.update(pe_mm2=pe, spec=spec[:separate_pe.start(2)] + f"{pe:g}" + spec[separate_pe.end(2):])
    return [update_specs(d, node, values)]


def _cable_checks(d, check):
    for node in d.of("WL"):
        specs = d.items[node]["specs"]
        section, ib, declared_iz = (d.value(node, k) for k in ("section_mm2", "Ib_A", "Iz_A"))
        material = material_code(specs.get("material", "Cu"))
        tabulated = cable_table(material).get(section)
        iz = declared_iz if declared_iz is not None else tabulated
        protectors = d.nearest(node, "QF", "FU")
        currents = {p: d.value(p, "In_A") for p in protectors}
        all_rated = bool(currents) and all(v is not None and v > 0 for v in currents.values())
        check("cable_unprotected", not protectors, [node, *protectors], {"protector_count": len(protectors)})
        check("cable_rating_incomplete", not all_rated or ib is None or iz is None or section is None or not material,
              [node, *protectors], {"Ib_A": ib, "Iz_A": iz, "section_mm2": section,
                                   "material": material, "protector_In_A": currents})
        if declared_iz is not None and tabulated is not None:
            check("cable_ampacity_table_mismatch", abs(declared_iz - tabulated) > 0.01, [node],
                  {"declared_Iz_A": declared_iz, "table_Iz_A": tabulated, "section_mm2": section,
                   "profile": "ebjs_cu_xlpe" if material == "Cu" else "demo_al_xlpe_0.75"})
        if section is not None:
            minimum = d.value(node, "mechanical_min_mm2")
            if minimum is not None:
                check("cable_mechanical_minimum", section < minimum, [node],
                      {"section_mm2": section, "minimum_mm2": minimum})
            neutral = d.value(node, "neutral_mm2")
            if neutral is None and d.value(node, "cores") == 4 and specs.get("pe_mm2") is not None:
                neutral = section
            if neutral is not None:
                min_n = d.value(node, "neutral_min_mm2")
                if min_n is None and (section <= (16 if material == "Cu" else 25) or specs.get("high_harmonics")):
                    min_n = section
                if min_n is not None:
                    check("cable_neutral_section", neutral < min_n, [node],
                          {"neutral_mm2": neutral, "minimum_mm2": min_n})
            pe = d.value(node, "pe_mm2")
            if pe is not None:
                min_pe = d.value(node, "pe_min_mm2")
                if min_pe is None:
                    # ElectroBench cable construction uses next table size >= S/2.
                    min_pe = section / 2
                check("cable_pe_section", pe < min_pe, [node], {"PE_mm2": pe, "minimum_mm2": min_pe})
            energy = d.value(node, "let_through_A2s")
            k = d.value(node, "adiabatic_k")
            if energy is not None and k is not None:
                check("cable_short_circuit_thermal", energy > (k * section)**2, [node],
                      {"I2t_A2s": energy, "limit_A2s": (k * section)**2, "section_mm2": section})
        if iz is None:
            continue
        for protector, current in currents.items():
            if current is None:
                continue
            evidence = {"In_A": current, "Ib_A": ib, "Iz_A": iz, "section_mm2": section}
            if ib is None:
                # In > Iz disproves the inequality independently of the
                # load current. Keep otherwise indeterminate checks unscored.
                if current > iz:
                    check("ampacity_insufficient", True, [protector, node], evidence)
                continue
            bad = not 0 <= ib <= current <= iz
            margin = (iz - current) / current if current > 0 else None
            low = not bad and margin is not None and margin < 0.10
            ops = []
            if (bad or low) and all_rated:
                needed = max(currents.values()) * (1.1 if low else 1)
                ops = _cable_change(d, node, ib, [needed, *currents.values()], section, material)
            check("ampacity_insufficient", bad, [protector, node], evidence, ops)
            if not bad and margin is not None:
                check("ampacity_margin_low", low, [protector, node],
                      evidence | {"reserve_ratio": round(margin, 6)}, ops)
            i2 = d.value(protector, "I2_A")
            if i2 is not None:
                check("cable_conventional_trip_current", i2 > 1.45 * iz, [protector, node],
                      {"I2_A": i2, "limit_A": round(1.45 * iz, 6), "Iz_A": iz})


def power_checks(drawing, check):
    _breaker_checks(drawing, check)
    _cable_checks(drawing, check)
