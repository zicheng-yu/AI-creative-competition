"""Boolean truth tables for the three secondary-circuit templates.

Equations are the ElectroBench control model of the drawn contacts.
They are evaluation ground truth, not a claim that every real panel
uses the same contact arrangement.
"""

from __future__ import annotations


def _bits(n: int, width: int) -> list[int]:
    return [(n >> shift) & 1 for shift in range(width - 1, -1, -1)]


def dol_rows() -> dict:
    """Direct-on-line start/stop with a hold-in contact.

    ``stop`` is 1 when the stop button is pressed (NC contact open).
    ``fr`` is 1 when the thermal relay has tripped (NC contact open).
    """
    inputs = ["stop", "start", "fr", "km"]
    rows = []
    for i in range(16):
        stop, start, fr, km = _bits(i, 4)
        km_next = int((not stop) and (not fr) and (start or km))
        rows.append({"stop": stop, "start": start, "fr": fr, "km": km, "km_next": km_next})
    return {
        "kind": "dol_self_hold",
        "equation": "KM' = (not STOP) and (not FR) and (START or KM)",
        "inputs": inputs,
        "outputs": ["km_next"],
        "rows": rows,
    }


def reversing_rows(*, interlock: bool) -> dict:
    """Forward/reverse contactor pair.

    With interlock, each direction is blocked by the opposite command and
    by the opposite contactor state. Without interlock both coils can be
    commanded together: that row set is the ground truth of the defect.
    """
    inputs = ["stop", "sb_f", "sb_r", "fr", "sq_f", "sq_r", "km_f", "km_r"]
    rows = []
    for i in range(256):
        stop, sb_f, sb_r, fr, sq_f, sq_r, km_f, km_r = _bits(i, 8)
        base = (not stop) and (not fr)
        allow_f = not sq_f
        allow_r = not sq_r
        if interlock:
            allow_f = allow_f and (not km_r) and (not sb_r)
            allow_r = allow_r and (not km_f) and (not sb_f)
        km_f_next = int(base and allow_f and (sb_f or km_f))
        km_r_next = int(base and allow_r and (sb_r or km_r))
        rows.append(
            {
                "stop": stop,
                "sb_f": sb_f,
                "sb_r": sb_r,
                "fr": fr,
                "sq_f": sq_f,
                "sq_r": sq_r,
                "km_f": km_f,
                "km_r": km_r,
                "km_f_next": km_f_next,
                "km_r_next": km_r_next,
            }
        )
    equation = (
        "KMF' = (not STOP) and (not FR) and (not SQF) and (SBF or KMF)"
        " and (not KMR) and (not SBR);"
        " KMR' symmetric"
        if interlock
        else "KMF' = (not STOP) and (not FR) and (not SQF) and (SBF or KMF); KMR' symmetric; no electrical interlock"
    )
    return {
        "kind": "reversing",
        "interlock": interlock,
        "equation": equation,
        "inputs": inputs,
        "outputs": ["km_f_next", "km_r_next"],
        "rows": rows,
    }


def ats_rows() -> dict:
    """Dual-source automatic transfer, mutually exclusive closes.

    ``sa`` is 1 (force source I), 2 (force source II) or 0 (auto).
    ``kt`` is 1 when the transfer delay has elapsed.
    """
    inputs = ["ka1", "ka2", "sa", "kt"]
    rows = []
    for ka1 in (0, 1):
        for ka2 in (0, 1):
            for sa in (0, 1, 2):
                for kt in (0, 1):
                    if sa == 1:
                        qf1, qf2 = 1, 0
                    elif sa == 2:
                        qf1, qf2 = 0, 1
                    elif ka1:
                        qf1, qf2 = 1, 0
                    elif ka2 and kt:
                        qf1, qf2 = 0, 1
                    else:
                        qf1, qf2 = 0, 0
                    rows.append(
                        {
                            "ka1": ka1,
                            "ka2": ka2,
                            "sa": sa,
                            "kt": kt,
                            "qf1_close": qf1,
                            "qf2_close": qf2,
                        }
                    )
    return {
        "kind": "ats",
        "equation": (
            "manual SA=1 closes source I only; SA=2 closes source II only; "
            "auto prefers source I when KA1 is healthy, otherwise source II after KT"
        ),
        "inputs": inputs,
        "outputs": ["qf1_close", "qf2_close"],
        "rows": rows,
    }


def build_logic(kind: str, *, interlock: bool = True) -> dict:
    if kind == "dol_self_hold":
        return dol_rows()
    if kind == "reversing":
        return reversing_rows(interlock=interlock)
    if kind == "ats":
        return ats_rows()
    raise KeyError(kind)
