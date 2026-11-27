"""Symbol catalog for ElectroBench-JS.

Letter codes printed on Chinese switchgear drawings (QF, QS, KM, FR, FU,
TA, TV, …) follow workshop practice. ``iec81346`` stores the IEC 81346-2:2019
Table 1 entry class where one applies. Letters D, J, L, V, Y and Z are
reserved in that edition and are not used here as class codes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolClass:
    class_id: int
    code: str
    name_zh: str
    name_en: str
    # Purchasing letter used to roll a glyph up into a BOM line.
    # Contacts share the letter of the device and are not anchors by default.
    bom_letter: str | None
    bom_name_zh: str | None
    iec81346: str | None
    unit: str | None
    supercategory: str
    default_bom_anchor: bool
    default_in_netlist: bool


def _s(
    class_id: int,
    code: str,
    name_zh: str,
    name_en: str,
    bom_letter: str | None,
    bom_name_zh: str | None,
    iec81346: str | None,
    unit: str | None,
    supercategory: str,
    *,
    anchor: bool = True,
    netlist: bool = True,
) -> SymbolClass:
    return SymbolClass(
        class_id=class_id,
        code=code,
        name_zh=name_zh,
        name_en=name_en,
        bom_letter=bom_letter,
        bom_name_zh=bom_name_zh,
        iec81346=iec81346,
        unit=unit,
        supercategory=supercategory,
        default_bom_anchor=anchor,
        default_in_netlist=netlist,
    )


# IEC 81346-2:2019 Table 1 entry classes used below:
# Q controlling, K information processing, F protecting, B sensing,
# T transforming, M driving, P presenting, C storing, S human interaction,
# W guiding, X interfacing.
# Contactors are Q in the 2019 edition (they control energy flow). The
# drawing still prints the workshop code KM.
CLASSES: tuple[SymbolClass, ...] = (
    _s(0, "QF", "断路器", "circuit breaker", "QF", "断路器", "Q", "台", "primary"),
    _s(1, "QS", "隔离开关", "disconnector", "QS", "隔离开关", "Q", "台", "primary"),
    _s(2, "QE", "接地开关", "earthing switch", "QE", "接地开关", "Q", "台", "primary"),
    _s(3, "KM_MAIN", "接触器主触头", "contactor main poles", "KM", "交流接触器", "Q", "台", "primary"),
    _s(4, "KM_COIL", "接触器线圈", "contactor coil", "KM", "交流接触器", "Q", "台", "secondary", anchor=False),
    _s(5, "KM_NO", "接触器常开触点", "contactor NO contact", "KM", "交流接触器", "Q", "台", "secondary", anchor=False),
    _s(6, "KM_NC", "接触器常闭触点", "contactor NC contact", "KM", "交流接触器", "Q", "台", "secondary", anchor=False),
    _s(7, "KA_COIL", "中间继电器线圈", "auxiliary relay coil", "KA", "中间继电器", "K", "只", "secondary"),
    _s(8, "KA_NO", "中间继电器常开触点", "auxiliary relay NO", "KA", "中间继电器", "K", "只", "secondary", anchor=False),
    _s(9, "KA_NC", "中间继电器常闭触点", "auxiliary relay NC", "KA", "中间继电器", "K", "只", "secondary", anchor=False),
    _s(10, "KT_COIL", "时间继电器线圈", "time relay coil", "KT", "时间继电器", "K", "只", "secondary"),
    _s(11, "KT_NO", "时间继电器延时常开触点", "time relay NO", "KT", "时间继电器", "K", "只", "secondary", anchor=False),
    _s(12, "FR", "热继电器", "thermal overload relay", "FR", "热继电器", "F", "只", "primary"),
    _s(13, "FR_NC", "热继电器常闭触点", "thermal relay NC", "FR", "热继电器", "F", "只", "secondary", anchor=False),
    _s(14, "FU", "熔断器", "fuse", "FU", "熔断器", "F", "只", "both"),
    _s(15, "TA", "电流互感器", "current transformer", "TA", "电流互感器", "B", "只", "primary"),
    _s(16, "TV", "电压互感器", "voltage transformer", "TV", "电压互感器", "B", "只", "primary"),
    _s(17, "SPD", "电涌保护器", "surge protective device", "SPD", "电涌保护器", "F", "只", "primary"),
    _s(18, "T", "电力变压器", "power transformer", "T", "电力变压器", "T", "台", "primary"),
    _s(19, "TC", "控制变压器", "control transformer", "TC", "控制变压器", "T", "台", "secondary"),
    _s(20, "M", "电动机", "motor", "M", "电动机", "M", "台", "primary"),
    _s(21, "PA", "电流表", "ammeter", "PA", "电流表", "P", "只", "primary"),
    _s(22, "PV", "电压表", "voltmeter", "PV", "电压表", "P", "只", "primary"),
    _s(23, "PJ", "电能表", "energy meter", "PJ", "电能表", "P", "只", "primary"),
    _s(24, "C", "电容器", "capacitor", "C", "电容器", "C", "只", "primary"),
    # Industry drawings letter reactors as L. IEC 81346-2:2019 reserves L.
    _s(25, "L", "电抗器", "reactor", "L", "电抗器", None, "只", "primary"),
    _s(26, "HL", "指示灯", "indicator lamp", "HL", "指示灯", "P", "只", "secondary"),
    _s(27, "HA", "电铃", "bell", "HA", "电铃", "P", "只", "secondary"),
    _s(28, "SB_NO", "常开按钮", "NO pushbutton", "SB", "按钮", "S", "只", "secondary"),
    _s(29, "SB_NC", "常闭按钮", "NC pushbutton", "SB", "按钮", "S", "只", "secondary"),
    _s(30, "SA", "选择开关", "selector switch", "SA", "选择开关", "S", "只", "secondary"),
    _s(31, "SQ", "行程开关", "limit switch", "SQ", "行程开关", "B", "只", "secondary"),
    _s(32, "XT", "端子", "terminal", "XT", "端子", "X", "只", "secondary"),
    _s(33, "WB", "母线", "busbar", "WB", "母线", "W", "套", "primary"),
    # Y is reserved in IEC 81346-2:2019. Close/trip coils are recorded as Q
    # (operating part of the switching device) while the drawing prints YC/YO.
    _s(34, "YC", "合闸线圈", "closing coil", "YC", "合闸线圈", "Q", "只", "secondary"),
    _s(35, "YO", "分闸线圈", "opening coil", "YO", "分闸线圈", "Q", "只", "secondary"),
    _s(36, "ATS", "双电源转换开关", "transfer switch", "ATS", "双电源转换开关", "Q", "台", "primary"),
    _s(37, "PE", "保护接地", "protective earth", None, None, None, None, "annotation", anchor=False),
    _s(38, "WL", "导线回路", "cable circuit", "WL", "电力电缆", "W", "回路", "primary"),
    _s(39, "WIRE_NO", "线号", "wire number", None, None, None, None, "annotation", anchor=False, netlist=False),
)

BY_CODE: dict[str, SymbolClass] = {item.code: item for item in CLASSES}
BY_ID: dict[int, SymbolClass] = {item.class_id: item for item in CLASSES}

# Non-standard abbreviations injected on the alias subset. Ground-truth
# ``class_code`` / specs stay canonical; only the ink on the sheet changes.
ALIASES: dict[str, str] = {
    "QF": "空开",
    "QS": "闸刀",
    "QE": "地刀",
    "KM": "交流接触",
    "KA": "中间继",
    "KT": "时间继",
    "FR": "热偶",
    "FU": "保险",
    "TA": "CT",
    "TV": "PT",
    "SPD": "浪涌",
    "T": "变电器",
    "TC": "控制变",
    "M": "马达",
    "PA": "安表",
    "PV": "伏表",
    "PJ": "电度表",
    "C": "电容",
    "L": "电抗",
    "HL": "指示",
    "HA": "铃",
    "SB": "钮",
    "SA": "转换",
    "SQ": "限位",
    "XT": "端子排",
    "WB": "铜排",
    "YC": "合闸",
    "YO": "分闸",
    "ATS": "双电源",
    "WL": "电缆",
}


def alias_tag(class_code: str, tag: str) -> str:
    """Replace a workshop letter prefix with a non-standard short name."""
    symbol = BY_CODE[class_code]
    letter = symbol.bom_letter or class_code
    prefixes = sorted(ALIASES, key=len, reverse=True)
    for prefix in prefixes:
        if tag.startswith(prefix) and prefix in ALIASES:
            return ALIASES[prefix] + tag[len(prefix) :]
    return ALIASES.get(letter, tag)


def alias_spec(spec: str) -> str:
    """Colloquial specification ink. Canonical ``spec`` is unchanged.

    Only a trailing ampere unit after a number is rewritten, so tokens such
    as ``AC220V`` and ``Icu`` stay readable.
    """
    import re

    text = spec
    text = text.replace("3P+N", "三极带零").replace("3P", "三极")
    text = text.replace("In=", "额定")
    text = text.replace("kVA", "千伏安").replace("kW", "千瓦").replace("kA", "千安")
    text = re.sub(r"(\d)A\b", r"\1安", text)
    text = text.replace("YJV-", "交联电缆")
    text = text.replace("+", "加").replace("x", "乘")
    return text
