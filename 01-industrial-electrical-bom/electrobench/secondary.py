"""Secondary control schematics: DOL, reversing, and ATS."""

from __future__ import annotations

from .ampacity import cable_spec
from .canvas import Canvas
from .logic import build_logic
from .model import ControlBranch, DrawingRecord, Instance
from .primary import fr_specs, km_specs, motor_specs, qf_specs


def _cable_from_qf(canvas: Canvas, qf: Instance, tag: str, section: int, ib: int, circuit: str, x: float, y: float) -> None:
    spec, iz = cable_spec(section)
    wl = canvas.add_wl(x, y, tag, section_mm2=section, iz_a=iz, ib_a=ib, spec=spec, circuit=circuit)
    canvas.connect(qf, "out", wl, "in", kind="power", draw=False)


def _h(canvas: Canvas, code: str, x: float, y: float, tag: str, specs: dict | None = None, **kwargs) -> Instance:
    return canvas.place(code, x, y, tag, specs or {}, label_side="above", **kwargs)


def build_dol(seed: int) -> DrawingRecord:
    canvas = Canvas(
        drawing_id="EBJS-S-DOL-001",
        subset="secondary",
        title="电动机启停自锁控制原理图",
        seed=seed,
        voltage="主回路 AC380V / 控制 AC220V",
        circuit_kind="dol_self_hold",
        notes=["启停按钮、接触器自锁常开触点与热继电器常闭触点串联在线圈回路中。"],
    )
    qf = canvas.place("QF", 40, 250, "QF1", qf_specs(32), circuit="WL1", label_side="left")
    km = canvas.place("KM_MAIN", 40, 210, "KM1", km_specs(32), circuit="WL1", label_side="left")
    fr = canvas.place("FR", 40, 170, "FR1", fr_specs(18), circuit="WL1", label_side="left")
    motor = canvas.place("M", 40, 130, "M1", motor_specs(7), circuit="WL1", label_side="left")
    pe = canvas.place("PE", 40, 92, "PE1", {}, label=False, circuit="WL1")
    canvas.connect(qf, "out", km, "in")
    canvas.connect(km, "out", fr, "in")
    canvas.connect(fr, "out", motor, "in")
    canvas.connect(motor, "out", pe, "in", kind="pe")
    _cable_from_qf(canvas, qf, "WL1", 6, 18, "WL1", 58, 150)

    tc = canvas.place("TC", 108, 250, "TC1", {"model": "EB-TC-100", "spec": "380/220V 100VA"}, circuit="CTRL", label_side="left")
    fu = _h(canvas, "FU", 168, 214, "FU1", {"model": "EB-FU-4", "spec": "In=4A", "In_A": 4}, rotation=90, circuit="CTRL")
    stop = _h(canvas, "SB_NC", 228, 186, "SB1", {"model": "EB-SB", "spec": "停止 常闭"}, circuit="CTRL")
    start = _h(canvas, "SB_NO", 292, 186, "SB2", {"model": "EB-SB", "spec": "启动 常开"}, circuit="CTRL")
    fr_nc = _h(canvas, "FR_NC", 348, 186, "FR1", {}, circuit="CTRL")
    coil = _h(canvas, "KM_COIL", 400, 186, "KM1", {}, circuit="CTRL")
    hold = _h(canvas, "KM_NO", 292, 222, "KM1", {}, circuit="CTRL")
    run_aux = _h(canvas, "KM_NO", 228, 132, "KM1", {}, circuit="CTRL")
    ka = _h(canvas, "KA_COIL", 292, 132, "KA1", {"model": "EB-KA", "spec": "AC220V"}, circuit="CTRL")
    ka_no = _h(canvas, "KA_NO", 292, 96, "KA1", {}, circuit="CTRL")
    hl = _h(canvas, "HL", 348, 96, "HL1", {"model": "EB-HL-GN", "spec": "绿色 AC220V"}, circuit="CTRL")
    ha = _h(canvas, "HA", 400, 96, "HA1", {"model": "EB-HA", "spec": "AC220V"}, circuit="CTRL")
    xt1 = _h(canvas, "XT", 168, 250, "XT1", {"model": "EB-XT", "spec": "2.5mm2"}, circuit="CTRL")
    xt2 = _h(canvas, "XT", 168, 70, "XT2", {"model": "EB-XT", "spec": "2.5mm2"}, circuit="CTRL")

    canvas.connect(tc, "out", xt1, "left", kind="control", bend="vh")
    canvas.connect(xt1, "right", fu, "in", kind="control")
    canvas.connect(fu, "out", stop, "left", kind="control", bend="vh")
    canvas.connect(stop, "right", start, "left", kind="control")
    canvas.connect(start, "right", fr_nc, "left", kind="control")
    canvas.connect(fr_nc, "right", coil, "left", kind="control")
    canvas.connect(stop, "right", hold, "left", kind="control", bend="vh")
    canvas.connect(hold, "right", fr_nc, "left", kind="control", bend="hv")
    canvas.connect(coil, "right", xt2, "right", kind="control", bend="vh")
    canvas.connect(stop, "right", run_aux, "left", kind="control", bend="vh")
    canvas.connect(run_aux, "right", ka, "left", kind="control")
    canvas.connect(ka, "right", xt2, "left", kind="control", bend="vh")
    canvas.connect(ka, "left", ka_no, "left", kind="control", bend="vh")
    canvas.connect(ka_no, "right", hl, "left", kind="control")
    canvas.connect(hl, "right", ha, "left", kind="control")
    canvas.connect(ha, "right", xt2, "right", kind="control", bend="vh")

    for number, xy in (("1", (176, 228)), ("3", (236, 196)), ("5", (360, 196)), ("7", (300, 142)), ("9", (360, 106))):
        canvas.add_wire_no(*xy, number)

    canvas.add_branch(
        ControlBranch(
            id="run",
            coil_tag="KM1",
            pair_tag=None,
            series_ids=[fu.id, stop.id, start.id, fr_nc.id, coil.id],
        )
    )
    canvas.record.logic = build_logic("dol_self_hold")
    return canvas.record


def build_reversing(seed: int, *, interlock: bool = True, drawing_id: str | None = None, subset: str = "secondary") -> DrawingRecord:
    canvas = Canvas(
        drawing_id=drawing_id or "EBJS-S-FREV-002",
        subset=subset,
        title="电动机正反转互锁控制原理图",
        seed=seed,
        voltage="主回路 AC380V / 控制 AC220V",
        circuit_kind="reversing",
        interlock=interlock,
        notes=[
            "正反转接触器换相，控制回路串入对方常闭触点。"
            if interlock
            else "注入缺陷：正反转线圈回路未串入对方常闭互锁触点。"
        ],
    )
    qf = canvas.place("QF", 48, 258, "QF1", qf_specs(32), circuit="WL1", label_side="left")
    kmf = canvas.place("KM_MAIN", 28, 214, "KMF", km_specs(32), circuit="WL1", label_side="left")
    kmr = canvas.place("KM_MAIN", 72, 214, "KMR", km_specs(32), circuit="WL1", label_side="right")
    fr = canvas.place("FR", 48, 168, "FR1", fr_specs(18), circuit="WL1", label_side="left")
    motor = canvas.place("M", 48, 128, "M1", motor_specs(7), circuit="WL1", label_side="left")
    canvas.connect(qf, "out", kmf, "in", bend="vh")
    canvas.connect(qf, "out", kmr, "in", bend="vh")
    canvas.connect(kmf, "out", fr, "in", bend="vh")
    canvas.connect(kmr, "out", fr, "in", bend="vh")
    canvas.connect(fr, "out", motor, "in")
    _cable_from_qf(canvas, qf, "WL1", 6, 18, "WL1", 90, 140)

    fu = _h(canvas, "FU", 150, 230, "FU1", {"model": "EB-FU-4", "spec": "In=4A", "In_A": 4}, rotation=90, circuit="CTRL")
    stop = _h(canvas, "SB_NC", 150, 196, "SB1", {"model": "EB-SB", "spec": "停止 常闭"}, circuit="CTRL")
    sb_f = _h(canvas, "SB_NO", 214, 230, "SB2", {"model": "EB-SB", "spec": "正转 常开"}, circuit="CTRL")
    sb_r = _h(canvas, "SB_NO", 214, 160, "SB3", {"model": "EB-SB", "spec": "反转 常开"}, circuit="CTRL")
    sq_f = _h(canvas, "SQ", 278, 230, "SQ1", {"model": "EB-SQ", "spec": "正转限位 常闭"}, circuit="CTRL")
    sq_r = _h(canvas, "SQ", 278, 160, "SQ2", {"model": "EB-SQ", "spec": "反转限位 常闭"}, circuit="CTRL")
    hold_f = _h(canvas, "KM_NO", 214, 258, "KMF", {}, circuit="CTRL")
    hold_r = _h(canvas, "KM_NO", 214, 128, "KMR", {}, circuit="CTRL")
    coil_x = 360 if interlock else 320
    if interlock:
        nc_f = _h(canvas, "KM_NC", 336, 230, "KMR", {}, circuit="CTRL", extra={"interlocks": "KMR"})
        nc_r = _h(canvas, "KM_NC", 336, 160, "KMF", {}, circuit="CTRL", extra={"interlocks": "KMF"})
    else:
        nc_f = nc_r = None
    coil_f = _h(canvas, "KM_COIL", coil_x, 230, "KMF", {}, circuit="CTRL")
    coil_r = _h(canvas, "KM_COIL", coil_x, 160, "KMR", {}, circuit="CTRL")
    xt = _h(canvas, "XT", 150, 78, "XT1", {"model": "EB-XT", "spec": "2.5mm2"}, circuit="CTRL")
    hl_f = _h(canvas, "HL", 400, 230, "HL1", {"model": "EB-HL-GN", "spec": "正转 绿色"}, circuit="CTRL")
    hl_r = _h(canvas, "HL", 400, 160, "HL2", {"model": "EB-HL-YE", "spec": "反转 黄色"}, circuit="CTRL")

    canvas.connect(fu, "out", stop, "left", kind="control", bend="vh")
    canvas.connect(stop, "right", sb_f, "left", kind="control", bend="vh")
    canvas.connect(stop, "right", sb_r, "left", kind="control", bend="vh")
    canvas.connect(sb_f, "right", sq_f, "left", kind="control")
    canvas.connect(sb_r, "right", sq_r, "left", kind="control")
    canvas.connect(stop, "right", hold_f, "left", kind="control", bend="vh")
    canvas.connect(hold_f, "right", sq_f, "left", kind="control", bend="hv")
    canvas.connect(stop, "right", hold_r, "left", kind="control", bend="vh")
    canvas.connect(hold_r, "right", sq_r, "left", kind="control", bend="hv")
    if interlock:
        assert nc_f is not None and nc_r is not None
        canvas.connect(sq_f, "right", nc_f, "left", kind="control")
        canvas.connect(nc_f, "right", coil_f, "left", kind="control")
        canvas.connect(sq_r, "right", nc_r, "left", kind="control")
        canvas.connect(nc_r, "right", coil_r, "left", kind="control")
        forward_ids = [fu.id, stop.id, sb_f.id, sq_f.id, nc_f.id, coil_f.id]
        reverse_ids = [fu.id, stop.id, sb_r.id, sq_r.id, nc_r.id, coil_r.id]
    else:
        canvas.connect(sq_f, "right", coil_f, "left", kind="control")
        canvas.connect(sq_r, "right", coil_r, "left", kind="control")
        forward_ids = [fu.id, stop.id, sb_f.id, sq_f.id, coil_f.id]
        reverse_ids = [fu.id, stop.id, sb_r.id, sq_r.id, coil_r.id]
    canvas.connect(coil_f, "right", hl_f, "left", kind="control")
    canvas.connect(coil_r, "right", hl_r, "left", kind="control")
    canvas.connect(hl_f, "right", xt, "right", kind="control", bend="vh")
    canvas.connect(hl_r, "right", xt, "left", kind="control", bend="vh")
    for number, xy in (("1", (158, 210)), ("3", (222, 240)), ("5", (286, 240)), ("11", (222, 148)), ("13", (286, 148))):
        canvas.add_wire_no(*xy, number)

    canvas.add_branch(ControlBranch("forward", "KMF", "KMR", forward_ids))
    canvas.add_branch(ControlBranch("reverse", "KMR", "KMF", reverse_ids))
    canvas.record.logic = build_logic("reversing", interlock=interlock)
    return canvas.record


def build_ats(seed: int) -> DrawingRecord:
    canvas = Canvas(
        drawing_id="EBJS-S-ATS-003",
        subset="secondary",
        title="双电源切换控制原理图",
        seed=seed,
        voltage="主回路 AC380V / 控制 AC220V",
        circuit_kind="ats",
        notes=["常用/备用电源经转换开关互斥合闸，备用侧经时间继电器延时。"],
    )
    qf1 = canvas.place("QF", 36, 250, "QF1", qf_specs(160), circuit="IN1", label_side="left")
    qf2 = canvas.place("QF", 36, 196, "QF2", qf_specs(160), circuit="IN2", label_side="left")
    ats = canvas.place("ATS", 96, 223, "ATS1", {"model": "EB-ATS-160", "spec": "160A 3P 自投"}, circuit="BUS", label_side="above")
    canvas.connect(qf1, "out", ats, "in1", bend="vh")
    canvas.connect(qf2, "out", ats, "in2", bend="vh")
    spec, iz = cable_spec(70)
    wl = canvas.add_wl(120, 150, "WL1", section_mm2=70, iz_a=iz, ib_a=100, spec=spec, circuit="WL1")
    canvas.connect(ats, "out", wl, "in", kind="power", bend="vh")

    tc = canvas.place("TC", 40, 120, "TC1", {"model": "EB-TC-150", "spec": "380/220V 150VA"}, circuit="CTRL", label_side="left")
    fu = _h(canvas, "FU", 40, 78, "FU1", {"model": "EB-FU-4", "spec": "In=4A", "In_A": 4}, rotation=90, circuit="CTRL")
    sa = _h(canvas, "SA", 120, 230, "SA1", {"model": "EB-SA", "spec": "自动/I/II"}, circuit="CTRL")
    ka1 = _h(canvas, "KA_COIL", 190, 250, "KA1", {"model": "EB-KA", "spec": "I段电压"}, circuit="CTRL")
    ka2 = _h(canvas, "KA_COIL", 190, 196, "KA2", {"model": "EB-KA", "spec": "II段电压"}, circuit="CTRL")
    ka1_no = _h(canvas, "KA_NO", 250, 250, "KA1", {}, circuit="CTRL")
    ka1_nc = _h(canvas, "KA_NC", 250, 160, "KA1", {}, circuit="CTRL", extra={"interlocks": "QF1"})
    kt = _h(canvas, "KT_COIL", 190, 150, "KT1", {"model": "EB-KT", "spec": "延时 1-10s"}, circuit="CTRL")
    kt_no = _h(canvas, "KT_NO", 250, 124, "KT1", {}, circuit="CTRL")
    yc1 = _h(canvas, "YC", 330, 250, "YC1", {"model": "EB-YC", "spec": "合闸 AC220V"}, circuit="IN1")
    yo1 = _h(canvas, "YO", 390, 250, "YO1", {"model": "EB-YO", "spec": "分闸 AC220V"}, circuit="IN1")
    yc2 = _h(canvas, "YC", 330, 124, "YC2", {"model": "EB-YC", "spec": "合闸 AC220V"}, circuit="IN2")
    yo2 = _h(canvas, "YO", 390, 124, "YO2", {"model": "EB-YO", "spec": "分闸 AC220V"}, circuit="IN2")
    hl1 = _h(canvas, "HL", 330, 196, "HL1", {"model": "EB-HL-GN", "spec": "I段合位"}, circuit="CTRL")
    hl2 = _h(canvas, "HL", 390, 196, "HL2", {"model": "EB-HL-YE", "spec": "II段合位"}, circuit="CTRL")
    ha = _h(canvas, "HA", 330, 78, "HA1", {"model": "EB-HA", "spec": "故障音响"}, circuit="CTRL")
    xt = _h(canvas, "XT", 120, 78, "XT1", {"model": "EB-XT", "spec": "2.5mm2"}, circuit="CTRL")

    canvas.connect(tc, "out", fu, "in", kind="control")
    canvas.connect(fu, "out", sa, "left", kind="control", bend="vh")
    canvas.connect(sa, "right", ka1, "left", kind="control", bend="vh")
    canvas.connect(sa, "right", ka2, "left", kind="control", bend="vh")
    canvas.connect(ka1, "right", ka1_no, "left", kind="control")
    canvas.connect(ka1_no, "right", yc1, "left", kind="control")
    canvas.connect(yc1, "right", yo1, "left", kind="control")
    canvas.connect(ka2, "right", kt, "left", kind="control", bend="vh")
    canvas.connect(kt, "right", kt_no, "left", kind="control", bend="vh")
    canvas.connect(kt_no, "right", ka1_nc, "left", kind="control", bend="hv")
    canvas.connect(ka1_nc, "right", yc2, "left", kind="control", bend="hv")
    canvas.connect(yc2, "right", yo2, "left", kind="control")
    canvas.connect(ka1_no, "right", hl1, "left", kind="control", bend="vh")
    canvas.connect(hl1, "right", hl2, "left", kind="control")
    canvas.connect(yo1, "right", xt, "right", kind="control", bend="vh")
    canvas.connect(yo2, "right", ha, "left", kind="control", bend="vh")
    canvas.connect(ha, "right", xt, "left", kind="control")
    for number, xy in (("1", (48, 90)), ("3", (128, 210)), ("5", (258, 236)), ("7", (338, 140))):
        canvas.add_wire_no(*xy, number)

    canvas.add_branch(ControlBranch("close_1", "YC1", "QF2", [fu.id, sa.id, ka1.id, ka1_no.id, yc1.id]))
    canvas.add_branch(ControlBranch("close_2", "YC2", "QF1", [fu.id, kt.id, kt_no.id, ka1_nc.id, yc2.id]))
    canvas.record.logic = build_logic("ats")
    return canvas.record
