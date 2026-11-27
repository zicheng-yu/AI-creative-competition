"""Primary single-line diagrams for GGD, MNS, GCS and KYN28."""

from __future__ import annotations

import random

from .ampacity import cable_spec, select_section, undersized_section
from .canvas import Canvas
from .model import DrawingRecord, Instance


def qf_specs(in_a: int, *, icu: int = 50, mv: bool = False) -> dict:
    if mv:
        kind, frame = "VCB", 1250 if in_a > 630 else 630
    elif in_a <= 63:
        kind, frame = "MCB", 63
    elif in_a <= 250:
        kind, frame = "MCCB", 250
    elif in_a <= 400:
        kind, frame = "MCCB", 400
    else:
        kind, frame = "ACB", 630
    return {
        "model": f"EB-{kind}-{frame}/{in_a}",
        "spec": f"In={in_a}A 3P Icu={icu}kA",
        "In_A": in_a,
        "frame_A": frame,
        "poles": "3P",
        "icu_kA": icu,
    }


def fu_specs(in_a: int) -> dict:
    return {"model": f"EB-FU-{in_a}", "spec": f"In={in_a}A", "In_A": in_a}


def km_specs(ie_a: int) -> dict:
    return {"model": f"EB-KM-{ie_a}", "spec": f"Ie={ie_a}A AC220V", "Ie_A": ie_a}


def fr_specs(ir_a: int) -> dict:
    return {"model": f"EB-FR-{ir_a}", "spec": f"整定{ir_a}A", "Ir_A": ir_a}


def motor_specs(kw: int) -> dict:
    return {"model": f"EB-M-{kw}kW", "spec": f"{kw}kW 380V 4P", "kW": kw}


def _cable(section: int, ib: int) -> dict:
    spec, iz = cable_spec(section)
    return {"section": section, "iz": iz, "ib": ib, "spec": spec}


def _attach_cable(canvas: Canvas, protector: Instance, tag: str, cable: dict, circuit: str, x: float, y: float) -> None:
    wl = canvas.add_wl(
        x,
        y,
        tag,
        section_mm2=cable["section"],
        iz_a=cable["iz"],
        ib_a=cable["ib"],
        spec=cable["spec"],
        circuit=circuit,
    )
    # Logical protection link. The cable callout is text beside the feeder;
    # the drawn wires follow the device stack.
    canvas.connect(protector, "out", wl, "in", kind="power", draw=False)


def _stack(canvas: Canvas, items: list[tuple], x: float) -> list[Instance]:
    placed: list[Instance] = []
    previous: Instance | None = None
    for code, y, tag, specs, circuit, extra in items:
        inst = canvas.place(
            code,
            x,
            y,
            tag,
            specs,
            circuit=circuit,
            label_side="right",
            extra=extra,
        )
        if previous is not None:
            canvas.connect(previous, "out", inst, "in", kind="power")
        previous = inst
        placed.append(inst)
    return placed


def _lv_drawing(
    *,
    drawing_id: str,
    subset: str,
    title: str,
    cabinet: str,
    seed: int,
    alias: bool,
    voltage: str,
    in_a: int,
    with_qs: bool,
    feeders: list[dict],
    notes: list[str],
) -> DrawingRecord:
    canvas = Canvas(
        drawing_id=drawing_id,
        subset=subset,
        title=title,
        seed=seed,
        voltage=voltage,
        cabinet=cabinet,
        alias=alias,
        notes=notes,
    )
    xs = [118, 176, 234, 292, 350]
    port_xs = {"src": 48.0, "spd": 86.0, "tv": 400.0}
    for index, feeder in enumerate(feeders):
        port_xs[f"f{index}"] = float(xs[index])
    bus = canvas.add_bus(40, 408, 172, "WB1", port_xs, circuit="BUS")

    y_qf = 230
    y_ta = 196
    if with_qs:
        qs = canvas.place("QS", 48, 264, "QS1", {"model": "EB-QS-630", "spec": "630A 3P"}, circuit="IN", label_side="left")
        qf = canvas.place("QF", 48, y_qf, "QF1", qf_specs(in_a), circuit="IN", label_side="left")
        canvas.connect(qs, "out", qf, "in", kind="power")
    else:
        qf = canvas.place("QF", 48, 250, "QF1", qf_specs(in_a, icu=65), circuit="IN", label_side="left")
    ta = canvas.place(
        "TA",
        48,
        y_ta if with_qs else 210,
        "TA1",
        {"model": "EB-TA-600/5", "spec": "600/5A 0.5", "ratio": "600/5"},
        circuit="IN",
        label_side="left",
    )
    canvas.connect(qf, "out", ta, "in", kind="power")
    canvas.connect(ta, "out", bus, "src", kind="power")

    pa = canvas.place(
        "PA",
        86,
        236,
        "PA1",
        {"model": "EB-PA-5A", "spec": "5A"},
        circuit="IN",
        label_side="above",
    )
    canvas.connect(ta, "sec", pa, "in", kind="branch", bend="hv")
    tv = canvas.place(
        "TV",
        400,
        214,
        "TV1",
        {"model": "EB-TV-380/100", "spec": "380/100V"},
        circuit="IN",
        label_side="left",
    )
    canvas.connect(bus, "tv", tv, "out", kind="branch")
    pv = canvas.place("PV", 400, 258, "PV1", {"model": "EB-PV-500V", "spec": "500V"}, circuit="IN", label_side="left")
    canvas.connect(tv, "in", pv, "out", kind="branch")
    pj = canvas.place(
        "PJ",
        348,
        258,
        "PJ1",
        {"model": "EB-PJ-3X5", "spec": "3x380V 5A"},
        circuit="IN",
        label_side="above",
    )
    canvas.connect(tv, "sec", pj, "in", kind="branch", bend="hv")

    spd = canvas.place("SPD", 86, 130, "SPD1", {"model": "EB-SPD-40", "spec": "In=40kA"}, circuit="SPD", label_side="above")
    pe = canvas.place("PE", 86, 100, "PE1", {}, label=False, circuit="SPD")
    canvas.connect(bus, "spd", spd, "in", kind="power")
    canvas.connect(spd, "out", pe, "in", kind="power")

    for index, feeder in enumerate(feeders):
        _draw_feeder(canvas, bus, f"f{index}", xs[index], feeder)
    return canvas.record


def _draw_feeder(canvas: Canvas, bus: Instance, port: str, x: float, feeder: dict) -> None:
    kind = feeder["kind"]
    circuit = feeder["circuit"]
    cable = feeder["cable"]
    if kind == "motor":
        qf = canvas.place("QF", x, 142, feeder["qf"], qf_specs(feeder["in_a"]), circuit=circuit)
        km = canvas.place("KM_MAIN", x, 110, feeder["km"], km_specs(feeder["in_a"]), circuit=circuit)
        canvas.connect(bus, port, qf, "in", kind="power")
        canvas.connect(qf, "out", km, "in", kind="power")
        previous = km
        if feeder.get("fr", True):
            fr = canvas.place("FR", x, 78, feeder["fr_tag"], fr_specs(feeder["fr_a"]), circuit=circuit)
            canvas.connect(previous, "out", fr, "in", kind="power")
            previous = fr
            motor_y = 56
        else:
            motor_y = 78
        motor = canvas.place("M", x, motor_y, feeder["motor"], motor_specs(feeder["kw"]), circuit=circuit)
        canvas.connect(previous, "out", motor, "in", kind="power")
        _attach_cable(canvas, qf, feeder["wl"], cable, circuit, x + 16, 32)
        return
    if kind == "fused":
        fu = canvas.place("FU", x, 136, feeder["fu"], fu_specs(feeder["in_a"]), circuit=circuit)
        canvas.connect(bus, port, fu, "in", kind="power")
        _attach_cable(canvas, fu, feeder["wl"], cable, circuit, x + 12, 96)
        return
    if kind == "capacitor":
        qf = canvas.place("QF", x, 142, feeder["qf"], qf_specs(feeder["in_a"]), circuit=circuit)
        reactor = canvas.place("L", x, 108, feeder["reactor"], {"model": "EB-L-7", "spec": "7% 串联"}, circuit=circuit)
        cap = canvas.place("C", x, 74, feeder["cap"], {"model": feeder["cap_model"], "spec": feeder["cap_spec"]}, circuit=circuit)
        canvas.connect(bus, port, qf, "in", kind="power")
        canvas.connect(qf, "out", reactor, "in", kind="power")
        canvas.connect(reactor, "out", cap, "in", kind="power")
        _attach_cable(canvas, qf, feeder["wl"], cable, circuit, x + 12, 46)
        return
    if kind == "metered":
        qf = canvas.place("QF", x, 142, feeder["qf"], qf_specs(feeder["in_a"]), circuit=circuit)
        ta = canvas.place(
            "TA",
            x,
            104,
            feeder["ta"],
            {"model": f"EB-TA-{feeder['ratio']}", "spec": f"{feeder['ratio']}A 0.5", "ratio": feeder["ratio"]},
            circuit=circuit,
        )
        canvas.connect(bus, port, qf, "in", kind="power")
        canvas.connect(qf, "out", ta, "in", kind="power")
        _attach_cable(canvas, qf, feeder["wl"], cable, circuit, x + 12, 70)
        return
    qf = canvas.place("QF", x, 136, feeder["qf"], qf_specs(feeder["in_a"]), circuit=circuit)
    canvas.connect(bus, port, qf, "in", kind="power")
    _attach_cable(canvas, qf, feeder["wl"], cable, circuit, x + 12, 96)


def ggd_feeders(*, inverted: bool = False, thin_cable: bool = False) -> tuple[int, list[dict]]:
    if inverted:
        in_a = 100
        f1_in, f1_section, f1_ib = 160, 70, 120
        f2 = {"kind": "motor", "circuit": "WL2", "qf": "QF3", "in_a": 63, "km": "KM1", "fr": True, "fr_tag": "FR1", "fr_a": 40, "motor": "M1", "kw": 15, "wl": "WL2", "cable": _cable(16, 40)}
    elif thin_cable:
        in_a = 630
        f1_in, f1_section, f1_ib = 250, undersized_section(250)[0], 180
        f2 = {"kind": "motor", "circuit": "WL2", "qf": "QF3", "in_a": 100, "km": "KM1", "fr": True, "fr_tag": "FR1", "fr_a": 63, "motor": "M1", "kw": 30, "wl": "WL2", "cable": _cable(35, 80)}
    else:
        in_a = 630
        f1_in, f1_section, f1_ib = 250, 150, 200
        f2 = {"kind": "motor", "circuit": "WL2", "qf": "QF3", "in_a": 100, "km": "KM1", "fr": True, "fr_tag": "FR1", "fr_a": 63, "motor": "M1", "kw": 30, "wl": "WL2", "cable": _cable(35, 80)}
    feeders = [
        {"kind": "plain", "circuit": "WL1", "qf": "QF2", "in_a": f1_in, "wl": "WL1", "cable": _cable(f1_section, f1_ib)},
        f2,
        {"kind": "metered", "circuit": "WL3", "qf": "QF4", "in_a": 63 if inverted else 160, "ta": "TA2", "ratio": "150/5" if not inverted else "75/5", "wl": "WL3", "cable": _cable(16 if inverted else 70, 40 if inverted else 120)},
        {"kind": "fused", "circuit": "WL4", "fu": "FU1", "in_a": 32 if inverted else 63, "wl": "WL4", "cable": _cable(6 if inverted else 16, 20 if inverted else 50)},
        {"kind": "plain", "circuit": "WL5", "qf": "QF5", "in_a": 32 if inverted else 63, "wl": "WL5", "cable": _cable(6 if inverted else 16, 20 if inverted else 40)},
    ]
    if inverted:
        # QF5 is 32 < incomer 100; QF4 is 63 < 100; QF2 is the inverted 160.
        pass
    return in_a, feeders


def build_ggd(seed: int, *, inverted: bool = False, thin_cable: bool = False, alias: bool = False, drawing_id: str | None = None, subset: str = "primary") -> DrawingRecord:
    in_a, feeders = ggd_feeders(inverted=inverted, thin_cable=thin_cable)
    if drawing_id is None:
        drawing_id = "EBJS-P-GGD-001"
    notes = ["GGD 固定式低压柜一次系统图，进线隔离开关 + 断路器。"]
    if inverted:
        notes.append("注入缺陷：WL1 断路器额定电流高于进线断路器。")
    if thin_cable:
        notes.append("注入缺陷：WL1 电缆截面按评测载流量表低于断路器 In。")
    if alias:
        notes.append("图面文字使用非标简写，真值规格仍为规范代号。")
    return _lv_drawing(
        drawing_id=drawing_id,
        subset=subset,
        title="GGD 低压配电柜一次系统图",
        cabinet="GGD",
        seed=seed,
        alias=alias,
        voltage="AC380V TN-S",
        in_a=in_a,
        with_qs=True,
        feeders=feeders,
        notes=notes,
    )


def build_mns(seed: int, *, missing_fr: bool = False, drawing_id: str | None = None, subset: str = "primary") -> DrawingRecord:
    feeders = [
        {"kind": "motor", "circuit": "WL1", "qf": "QF2", "in_a": 100, "km": "KM1", "fr": not missing_fr, "fr_tag": "FR1", "fr_a": 63, "motor": "M1", "kw": 30, "wl": "WL1", "cable": _cable(35, 80)},
        {"kind": "motor", "circuit": "WL2", "qf": "QF3", "in_a": 63, "km": "KM2", "fr": True, "fr_tag": "FR2", "fr_a": 40, "motor": "M2", "kw": 15, "wl": "WL2", "cable": _cable(16, 40)},
        {"kind": "motor", "circuit": "WL3", "qf": "QF4", "in_a": 32, "km": "KM3", "fr": True, "fr_tag": "FR3", "fr_a": 18, "motor": "M3", "kw": 7, "wl": "WL3", "cable": _cable(6, 18)},
        {"kind": "plain", "circuit": "WL4", "qf": "QF5", "in_a": 160, "wl": "WL4", "cable": _cable(70, 120)},
        {"kind": "plain", "circuit": "WL5", "qf": "QF6", "in_a": 63, "wl": "WL5", "cable": _cable(16, 45)},
    ]
    notes = ["MNS 抽出式低压柜，电动机回路按断路器 + 接触器 + 热继电器配置。"]
    if missing_fr:
        notes.append("注入缺陷：M1 回路未画热继电器。")
    return _lv_drawing(
        drawing_id=drawing_id or "EBJS-P-MNS-002",
        subset=subset,
        title="MNS 低压抽出式开关柜一次系统图",
        cabinet="MNS",
        seed=seed,
        alias=False,
        voltage="AC380V TN-S",
        in_a=630,
        with_qs=True,
        feeders=feeders,
        notes=notes,
    )


def build_gcs(seed: int) -> DrawingRecord:
    feeders = [
        {"kind": "motor", "circuit": "WL1", "qf": "QF2", "in_a": 100, "km": "KM1", "fr": True, "fr_tag": "FR1", "fr_a": 63, "motor": "M1", "kw": 22, "wl": "WL1", "cable": _cable(35, 70)},
        {
            "kind": "capacitor",
            "circuit": "WL2",
            "qf": "QF3",
            "in_a": 63,
            "reactor": "L1",
            "cap": "C1",
            "cap_model": "EB-C-30kvar",
            "cap_spec": "30kvar 400V",
            "wl": "WL2",
            "cable": _cable(16, 45),
        },
        {"kind": "plain", "circuit": "WL3", "qf": "QF4", "in_a": 160, "wl": "WL3", "cable": _cable(70, 130)},
        {"kind": "fused", "circuit": "WL4", "fu": "FU1", "in_a": 32, "wl": "WL4", "cable": _cable(6, 20)},
        {"kind": "plain", "circuit": "WL5", "qf": "QF5", "in_a": 63, "wl": "WL5", "cable": _cable(16, 40)},
    ]
    return _lv_drawing(
        drawing_id="EBJS-P-GCS-003",
        subset="primary",
        title="GCS 低压抽出式开关柜一次系统图",
        cabinet="GCS",
        seed=seed,
        alias=False,
        voltage="AC380V TN-S",
        in_a=400,
        with_qs=True,
        feeders=feeders,
        notes=["GCS 一次系统图，含电动机回路与串联电抗器的电容器回路。"],
    )


def build_kyn28(seed: int) -> DrawingRecord:
    canvas = Canvas(
        drawing_id="EBJS-P-KYN-004",
        subset="primary",
        title="KYN28 铠装移开式交流金属封闭开关柜一次系统图",
        seed=seed,
        voltage="AC10kV",
        cabinet="KYN28",
        notes=["KYN28 单母线一次图：隔离、接地、真空断路器、互感器与馈线变压器。"],
    )
    bus = canvas.add_bus(
        70,
        390,
        178,
        "WB1",
        {"src": 70, "f1": 190, "f2": 300, "tv": 370},
        circuit="BUS",
    )
    qs = canvas.place("QS", 70, 262, "QS1", {"model": "EB-QS-1250", "spec": "1250A 12kV"}, circuit="IN", label_side="left")
    qf = canvas.place("QF", 70, 226, "QF1", qf_specs(1250, icu=31, mv=True), circuit="IN", label_side="left")
    ta = canvas.place("TA", 70, 194, "TA1", {"model": "EB-TA-600/5", "spec": "600/5A 10P10", "ratio": "600/5"}, circuit="IN", label_side="left")
    canvas.connect(qs, "out", qf, "in", kind="power")
    canvas.connect(qf, "out", ta, "in", kind="power")
    canvas.connect(ta, "out", bus, "src", kind="power")
    qe = canvas.place("QE", 118, 262, "QE1", {"model": "EB-QE-12", "spec": "12kV"}, circuit="IN", label_side="right")
    pe = canvas.place("PE", 118, 220, "PE1", {}, label=False, circuit="IN")
    canvas.connect(qs, "tap", qe, "in", kind="power", bend="hv")
    canvas.connect(qe, "out", pe, "in", kind="power")

    tv = canvas.place("TV", 370, 220, "TV1", {"model": "EB-TV-10/0.1", "spec": "10/0.1kV"}, circuit="IN", label_side="left")
    canvas.connect(bus, "tv", tv, "in", kind="branch")
    pv = canvas.place("PV", 370, 258, "PV1", {"model": "EB-PV-12kV", "spec": "12kV"}, circuit="IN", label_side="left")
    canvas.connect(tv, "out", pv, "in", kind="branch")
    pa = canvas.place("PA", 160, 230, "PA1", {"model": "EB-PA-5A", "spec": "5A"}, circuit="IN", label_side="above")
    canvas.connect(ta, "sec", pa, "in", kind="branch", bend="hv")

    def outgoing(port: str, x: float, index: int, in_a: int, section: int, ib: int, with_reactor: bool, with_transformer: bool) -> None:
        circuit = f"WL{index}"
        qs_o = canvas.place("QS", x, 146, f"QS{index+1}", {"model": "EB-QS-630", "spec": "630A 12kV"}, circuit=circuit)
        qf_o = canvas.place("QF", x, 114, f"QF{index+1}", qf_specs(in_a, icu=31, mv=True), circuit=circuit)
        canvas.connect(bus, port, qs_o, "in", kind="power")
        canvas.connect(qs_o, "out", qf_o, "in", kind="power")
        previous = qf_o
        if with_reactor:
            reactor = canvas.place("L", x, 82, "L1", {"model": "EB-L-10kV", "spec": "10kV 限流"}, circuit=circuit)
            canvas.connect(previous, "out", reactor, "in", kind="power")
            previous = reactor
        else:
            ta_o = canvas.place("TA", x, 82, "TA2", {"model": "EB-TA-200/5", "spec": "200/5A 0.5", "ratio": "200/5"}, circuit=circuit)
            canvas.connect(previous, "out", ta_o, "in", kind="power")
            previous = ta_o
        if with_transformer:
            transformer = canvas.place("T", x, 50, "T1", {"model": "EB-T-800", "spec": "10/0.4kV 800kVA"}, circuit=circuit)
            canvas.connect(previous, "out", transformer, "in", kind="power")
        cable = _cable(section, ib)
        _attach_cable(canvas, qf_o, f"WL{index}", cable, circuit, x + 18, 30)

    # Incomer is 1250 A. Outgoing breakers stay below it and below Iz.
    outgoing("f1", 190, 1, 160, 70, 120, True, False)
    outgoing("f2", 300, 2, 200, 95, 150, False, True)
    return canvas.record


def build_random_primary(seed: int, count: int) -> list[DrawingRecord]:
    """Seeded LV variants. Always electrically clean under the benchmark rules."""
    rng = random.Random(seed)
    drawings = []
    ratings = [32, 63, 100, 160, 250]
    for index in range(count):
        in_a = 630
        n_feeders = rng.randint(3, 5)
        feeders = []
        for nth in range(n_feeders):
            in_feeder = rng.choice([value for value in ratings if value < in_a])
            section, _iz = select_section(in_feeder)
            ib = max(1, int(in_feeder * 0.7))
            cable = _cable(section, ib)
            if nth == 0:
                feeders.append(
                    {
                        "kind": "motor",
                        "circuit": f"WL{nth+1}",
                        "qf": f"QF{nth+2}",
                        "in_a": in_feeder,
                        "km": f"KM{nth+1}",
                        "fr": True,
                        "fr_tag": f"FR{nth+1}",
                        "fr_a": max(10, int(in_feeder * 0.6)),
                        "motor": f"M{nth+1}",
                        "kw": max(4, in_feeder // 4),
                        "wl": f"WL{nth+1}",
                        "cable": cable,
                    }
                )
            else:
                feeders.append(
                    {
                        "kind": "plain",
                        "circuit": f"WL{nth+1}",
                        "qf": f"QF{nth+2}",
                        "in_a": in_feeder,
                        "wl": f"WL{nth+1}",
                        "cable": cable,
                    }
                )
        while len(feeders) < 5:
            # Pad with a small compliant lighting feeder so the fixed slot
            # layout stays populated. Padding is deterministic given count.
            nth = len(feeders)
            feeders.append(
                {
                    "kind": "plain",
                    "circuit": f"WL{nth+1}",
                    "qf": f"QF{nth+2}",
                    "in_a": 32,
                    "wl": f"WL{nth+1}",
                    "cable": _cable(6, 16),
                }
            )
        drawings.append(
            _lv_drawing(
                drawing_id=f"EBJS-R-{index+1:03d}",
                subset="primary",
                title=f"随机低压一次系统图 {index+1}",
                cabinet=rng.choice(["GGD", "MNS", "GCS"]),
                seed=seed,
                alias=False,
                voltage="AC380V TN-S",
                in_a=in_a,
                with_qs=True,
                feeders=feeders,
                notes=["由随机种子生成的合规一次图，不进入冻结样例卷。"],
            )
        )
    return drawings
