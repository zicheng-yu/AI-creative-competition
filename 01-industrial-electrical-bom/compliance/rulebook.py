"""Public rule registry. Each ID is independently configurable."""

from dataclasses import dataclass

SEL = "GB 50054-2011 6.1.2"
AMP = "GB 50054-2011 6.3.3"
LINE = "GB 50054-2011 3.2"
SCC = "GB 50054-2011 6.2"
SWITCH = "GB 50054-2011 3.1"
CB = "GB/T 14048.2-2020"
PANEL = "GB/T 7251.1-2023"
MOTOR = "GB 50055-2011 2.3.1"
CONTACT = "GB/T 14048.4-2020"
OVER = "GB/T 5226.1-2019 7.3"
OCP = "GB/T 5226.1-2019 7.2"
CTRL = "GB/T 5226.1-2019 9.2"
ILK = "GB/T 5226.1-2019 9.3"
WIRE = "GB/T 5226.1-2019 13"
ATS = "IEC 60947-6-1:2026"
ATS_GB = "GB/T 14048.11-2024"
CT = "GB/T 20840.2-2014"
SPD = "GB/T 18802.11-2020"
MV = "GB/T 3906-2020"
MV_ILK = "GB 50060-2008 2.0.10"
TAG = "GB/T 5094.2-2018"


@dataclass(frozen=True)
class Rule:
    id: str
    family: str
    severity: str
    title: str
    action: str
    refs: tuple


GROUPS = {
    "selectivity": (
        ("selectivity_inversion", "error", "上下级额定电流倒挂", "复核负荷后调整上级保护电器或脱扣整定。", SEL, CB),
        ("selectivity_margin_low", "warning", "上下级电流筛查级差不足", "核查时间电流曲线与厂家选择性配合表。", SEL, CB),
        ("breaking_coordination_review", "warning", "上下级分断配合需复核", "核查各安装点短路电流及厂家级联配合。", SCC, CB),
        ("breaker_frame_overload", "error", "额定电流超过壳架等级", "按目录更换壳架或调整脱扣额定值。", CB),
        ("breaker_short_circuit_rating", "error", "安装点短路电流超过分断能力", "复核同电压条件下的分断能力和短路计算。", SCC, CB),
        ("incoming_isolation_missing", "warning", "进线缺少明确的隔离器件", "在进线验明独立隔离器或断路器隔离功能。", SWITCH, PANEL),
        ("incoming_isolation_order", "warning", "进线隔离与保护顺序待核", "核对进线隔离和保护的布置及设计顺序。", SWITCH, PANEL),
        ("isolator_current_rating", "warning", "进线隔离器额定电流偏低", "核对进线隔离器与上游保护和负荷。", SWITCH, PANEL),
    ),
    "ampacity": (
        ("ampacity_insufficient", "error", "导线与过负荷保护不匹配", "按 Ib≤In≤Iz 复核截面与整定。", AMP),
        ("ampacity_margin_low", "warning", "导线载流量余量低于 10%", "结合敷设条件评估升级截面。", AMP),
        ("cable_ampacity_table_mismatch", "warning", "标称载流量与筛查表不符", "核对材质、敷设条件与载流量来源。", AMP, LINE),
        ("cable_mechanical_minimum", "warning", "电缆截面低于机械强度下限", "按敷设方式核对最小截面。", LINE),
        ("cable_neutral_section", "warning", "中性线截面低于设计下限", "按谐波、负荷不平衡和截面条件复核中性线。", LINE),
        ("cable_pe_section", "warning", "保护导体截面低于设计下限", "核对保护导体材料及短路热稳定。", LINE),
        ("cable_unprotected", "warning", "电缆上游保护证据缺失", "核对电源路径以及上游保护电器。", AMP),
        ("cable_rating_incomplete", "warning", "导线载流量计算缺少参数", "补全计算电流、截面、材质和额定电流。", AMP),
        ("cable_conventional_trip_current", "error", "约定动作电流超过导体条件", "校核保护电器 I2 并重选电缆或保护器。", AMP),
        ("cable_short_circuit_thermal", "error", "电缆短路热稳定不足", "复核通流能量及导体绝热系数。", SCC),
    ),
    "equipment": (
        ("motor_protection_missing", "error", "电动机主回路配套缺失", "为缺失功能增加短路保护、接触器或过载保护。", MOTOR, OVER, "GB 50054-2011 6.1.1", OCP),
        ("motor_contactor_rating", "error", "接触器额定工作电流小于电机电流", "核对使用类别和电机铭牌电流。", CONTACT),
        ("motor_overload_setting", "warning", "电机过载整定偏离设计区间", "按负载和启动模式重新核对过载整定。", MOTOR, OVER),
        ("motor_pe_missing", "warning", "电机图未显示保护接地证据", "补充电机外壳  PE 接线或跨页引用。", MOTOR),
        ("ct_ratio_load", "warning", "CT 变比与回路电流匹配存疑", "核实 CT 变比、准确级、饱和特性及实际回路电流。", CT, PANEL),
        ("ct_secondary_open", "warning", "CT 二次闭合或短接证据不足", "核查仪表回路、短接端子和二次接地。", CT, PANEL),
        ("ct_meter_rating", "warning", "CT 二次额定电流与仪表输入不符", "核对仪表输入电流与 CT 二次额定值。", CT, PANEL),
        ("vt_ratio_voltage", "warning", "PT 一次额定值与回路电压不符", "核查变比和回路额定电压是否使用同一电压基准。", PANEL),
        ("vt_meter_missing", "warning", "PT 测量支路证据不足", "核对电压表、继保端口和跨页连接。", PANEL),
        ("capacitor_reactor_missing", "warning", "补偿支路缺少串联电抗器", "按谐波设计复核补偿电容器的串联电抗器。", PANEL),
        ("capacitor_switch_protection", "warning", "补偿支路投切或保护证据不足", "核对投切类别、合闸涌流及短路保护器。", PANEL),
        ("spd_backup_missing", "warning", "SPD 后备保护证据不足", "按厂家要求核查 SPD 支路专用后备保护。", SPD, PANEL),
        ("spd_pe_missing", "warning", "SPD 接地路径证据不足", "核对 SPD PE 端与接地端子的连接。", SPD, PANEL),
        ("kyn_vacuum_breaker", "warning", "KYN28 断路器真空或电压规格待核", "确认 KYN28 真空断路器和额定电压。", MV),
        ("kyn_switchgear_members", "warning", "KYN28 隔离或接地器件证据不足", "补充隔离位置和接地开关图纸证据。", MV),
        ("kyn_five_preventions", "warning", "KYN28 五防闭锁证据不全", "逐项核对断路器、隔离开关、接地开关及柜门的防误闭锁。", MV_ILK, MV),
        ("kyn_earthing_path", "warning", "KYN28 接地开关接地路径待核", "核对接地开关与 PE 主端子的接线。", MV, MV_ILK),
    ),
    "control": (
        ("interlock_missing", "error", "正反转对侧常闭互锁缺失或被旁路", "将对侧常闭辅助触点串入所有线圈励磁路径。", ILK),
        ("control_coil_unreachable", "warning", "线圈控制供电路径不完整", "核对控制电源、触点和线圈路径。", CTRL),
        ("control_return_missing", "warning", "线圈返回端未发现端子路径", "核查线圈回线和接线端子。", CTRL, WIRE),
        ("control_self_hold_missing", "warning", "启动按钮缺少对应的并联自锁", "让同位号常开触点与启动按钮并联。", CTRL),
        ("control_stop_bypass", "warning", "停止按钮缺失或可被旁路", "将停止常闭点串入线圈公共控制路径。", CTRL),
        ("control_emergency_stop_priority", "warning", "急停可被旁路或缺少常闭接点", "让急停对所有相关励磁路径具有停止优先权。", CTRL, ILK),
        ("control_overload_contact", "warning", "主回路过载常闭触点未覆盖线圈", "核对与主回路 FR 同位号的常闭触点。", OVER, CTRL),
        ("control_fuse_missing", "warning", "控制电源缺少串联熔断器", "复核每条控制电源到线圈路径的过流保护。", OCP),
        ("ats_electrical_interlock", "warning", "ATS 转换侧电气闭锁证据不足", "核查每侧合闸路径是否受对侧已分闸证据约束。", ATS_GB, ATS, ILK),
        ("ats_mechanical_interlock", "warning", "ATS 机械互锁证据不足", "核对设备内置机械联锁或现场联锁机构。", ATS_GB, ATS),
        ("ats_transfer_delay", "warning", "ATS 备用侧延时链证据不足", "核对时间继电器或控制器设定及延时触点。", ATS_GB, ATS),
        ("ats_source_count", "warning", "ATS 转换输入源数量有误", "确认两个独立电源接至不同的转换输入端。", ATS_GB, ATS),
        ("control_terminal_missing", "warning", "网表引用了不存在的端子", "对照端子标注核对边的端口名称。", WIRE),
        ("control_wire_number_mismatch", "warning", "网表两端线号不一致", "按端子与线号标注修正连接。", WIRE),
    ),
    "bom": (
        ("duplicate_bom_tag", "error", "同范围采购锚点位号重复", "修正重复位号并保留辅助触点与本体关系。", TAG),
        ("bom_breaker_poles_missing", "warning", "断路器极数缺失或无法解析", "补注极数及中性极形式。", CB),
        ("bom_rated_current_missing", "warning", "保护器缺少有效额定电流", "从型号规格或铭牌补充额定电流。", CB, SWITCH),
        ("bom_anchor_spec_missing", "warning", "采购锚点规格信息不足", "补齐元件型号或规格。", TAG),
        ("bom_anchor_tag_missing", "warning", "采购锚点缺少位号", "添加图纸范围内唯一的采购位号。", TAG),
        ("bom_detail_anchor_mismatch", "warning", "BOM 明细与采购锚点不一致", "从当前实例重新生成 BOM 明细。", TAG),
        ("bom_summary_quantity_mismatch", "warning", "BOM 汇总数量异常", "从当前采购锚点重新汇总 BOM。", TAG),
        ("symbol_class_unknown", "warning", "无法解析冻结符号类别", "根据图例确认标准符号类型。", TAG),
        ("netlist_dangling_edge", "warning", "网表边引用缺失实例", "修复网表端点 ID 引用。", WIRE),
    ),
}

RULES = {row[0]: Rule(row[0], family, row[1], row[2], row[3], row[4:])
         for family, rows in GROUPS.items() for row in rows}
