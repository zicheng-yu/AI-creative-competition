# ElectroBench-JS v1.0.0 合规实测

- 4 类红灯 Precision **100%**，Recall **100%**。
- 匹配 5 条，额外红灯 0 条，漏检 0 条。
- 7 张 primary + secondary 标准图红灯误报 **0**。
- 匹配键为 rule_id 与排序后的 instance_ids。每条误报均计入 Precision。
- 退化对比使用冻结标注及同构网表。非标简写对比另走 OCR 标签归一化路径。
- 黄灯包括图纸证据不足和项目筛查阈值。各红灯预测独立于标注 defects。

| 图纸 | 子集 | 真值 | TP | FP | FN | 黄灯 | 绿灯 | 预测红灯 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| EBJS-D-AMP-002 | defect | 1 | 1 | 0 | 0 | 7 | 157 | ampacity_insufficient (i011/i012) |
| EBJS-D-ILK-004 | defect | 2 | 2 | 0 | 0 | 1 | 95 | interlock_missing (i015), interlock_missing (i016) |
| EBJS-D-MOT-003 | defect | 1 | 1 | 0 | 0 | 8 | 182 | motor_protection_missing (i013) |
| EBJS-D-SEL-001 | defect | 1 | 1 | 0 | 0 | 9 | 157 | selectivity_inversion (i003/i011) |
| EBJS-G-ALIAS-003 | degraded | 0 | 0 | 0 | 0 | 8 | 158 | — |
| EBJS-G-BLUR-001 | degraded | 0 | 0 | 0 | 0 | 8 | 158 | — |
| EBJS-G-SKEW-002 | degraded | 0 | 0 | 0 | 0 | 0 | 93 | — |
| EBJS-P-GCS-003 | primary | 0 | 0 | 0 | 0 | 6 | 166 | — |
| EBJS-P-GGD-001 | primary | 0 | 0 | 0 | 0 | 8 | 158 | — |
| EBJS-P-KYN-004 | primary | 0 | 0 | 0 | 0 | 5 | 106 | — |
| EBJS-P-MNS-002 | primary | 0 | 0 | 0 | 0 | 8 | 187 | — |
| EBJS-S-ATS-003 | secondary | 0 | 0 | 0 | 0 | 4 | 105 | — |
| EBJS-S-DOL-001 | secondary | 0 | 0 | 0 | 0 | 0 | 93 | — |
| EBJS-S-FREV-002 | secondary | 0 | 0 | 0 | 0 | 1 | 99 | — |

## 规则注册和触发统计

| 类别 | 规则 ID | 规则 | 红 | 黄 | 绿 |
| --- | --- | --- | ---: | ---: | ---: |
| selectivity | selectivity_inversion | 上下级额定电流倒挂 | 1 | 0 | 35 |
| selectivity | selectivity_margin_low | 上下级电流筛查级差不足 | 0 | 2 | 33 |
| selectivity | breaking_coordination_review | 上下级分断配合需复核 | 0 | 0 | 36 |
| selectivity | breaker_frame_overload | 额定电流超过壳架等级 | 0 | 0 | 51 |
| selectivity | breaker_short_circuit_rating | 安装点短路电流超过分断能力 | 0 | 0 | 0 |
| selectivity | incoming_isolation_missing | 进线缺少明确的隔离器件 | 0 | 0 | 9 |
| selectivity | incoming_isolation_order | 进线隔离与保护顺序待核 | 0 | 0 | 9 |
| selectivity | isolator_current_rating | 进线隔离器额定电流偏低 | 0 | 0 | 9 |
| ampacity | ampacity_insufficient | 导线与过负荷保护不匹配 | 1 | 0 | 47 |
| ampacity | ampacity_margin_low | 导线载流量余量低于 10% | 0 | 31 | 16 |
| ampacity | cable_ampacity_table_mismatch | 标称载流量与筛查表不符 | 0 | 0 | 47 |
| ampacity | cable_mechanical_minimum | 电缆截面低于机械强度下限 | 0 | 0 | 0 |
| ampacity | cable_neutral_section | 中性线截面低于设计下限 | 0 | 0 | 25 |
| ampacity | cable_pe_section | 保护导体截面低于设计下限 | 0 | 0 | 47 |
| ampacity | cable_unprotected | 电缆上游保护证据缺失 | 0 | 0 | 47 |
| ampacity | cable_rating_incomplete | 导线载流量计算缺少参数 | 0 | 0 | 47 |
| ampacity | cable_conventional_trip_current | 约定动作电流超过导体条件 | 0 | 0 | 0 |
| ampacity | cable_short_circuit_thermal | 电缆短路热稳定不足 | 0 | 0 | 0 |
| equipment | motor_protection_missing | 电动机主回路配套缺失 | 1 | 0 | 15 |
| equipment | motor_contactor_rating | 接触器额定工作电流小于电机电流 | 0 | 0 | 0 |
| equipment | motor_overload_setting | 电机过载整定偏离设计区间 | 0 | 0 | 0 |
| equipment | motor_pe_missing | 电机图未显示保护接地证据 | 0 | 14 | 2 |
| equipment | ct_ratio_load | CT 变比与回路电流匹配存疑 | 0 | 0 | 0 |
| equipment | ct_secondary_open | CT 二次闭合或短接证据不足 | 0 | 15 | 0 |
| equipment | ct_meter_rating | CT 二次额定电流与仪表输入不符 | 0 | 0 | 9 |
| equipment | vt_ratio_voltage | PT 一次额定值与回路电压不符 | 0 | 0 | 0 |
| equipment | vt_meter_missing | PT 测量支路证据不足 | 0 | 0 | 9 |
| equipment | capacitor_reactor_missing | 补偿支路缺少串联电抗器 | 0 | 0 | 1 |
| equipment | capacitor_switch_protection | 补偿支路投切或保护证据不足 | 0 | 0 | 1 |
| equipment | spd_backup_missing | SPD 后备保护证据不足 | 0 | 8 | 0 |
| equipment | spd_pe_missing | SPD 接地路径证据不足 | 0 | 0 | 8 |
| equipment | kyn_vacuum_breaker | KYN28 断路器真空或电压规格待核 | 0 | 0 | 3 |
| equipment | kyn_switchgear_members | KYN28 隔离或接地器件证据不足 | 0 | 0 | 1 |
| equipment | kyn_five_preventions | KYN28 五防闭锁证据不全 | 0 | 1 | 0 |
| equipment | kyn_earthing_path | KYN28 接地开关接地路径待核 | 0 | 0 | 1 |
| control | interlock_missing | 正反转对侧常闭互锁缺失或被旁路 | 2 | 0 | 2 |
| control | control_coil_unreachable | 线圈控制供电路径不完整 | 0 | 0 | 8 |
| control | control_return_missing | 线圈返回端未发现端子路径 | 0 | 0 | 8 |
| control | control_self_hold_missing | 启动按钮缺少对应的并联自锁 | 0 | 0 | 6 |
| control | control_stop_bypass | 停止按钮缺失或可被旁路 | 0 | 0 | 6 |
| control | control_emergency_stop_priority | 急停可被旁路或缺少常闭接点 | 0 | 0 | 0 |
| control | control_overload_contact | 主回路过载常闭触点未覆盖线圈 | 0 | 0 | 2 |
| control | control_fuse_missing | 控制电源缺少串联熔断器 | 0 | 0 | 8 |
| control | ats_electrical_interlock | ATS 转换侧电气闭锁证据不足 | 0 | 1 | 1 |
| control | ats_mechanical_interlock | ATS 机械互锁证据不足 | 0 | 1 | 0 |
| control | ats_transfer_delay | ATS 备用侧延时链证据不足 | 0 | 0 | 1 |
| control | ats_source_count | ATS 转换输入源数量有误 | 0 | 0 | 1 |
| control | control_terminal_missing | 网表引用了不存在的端子 | 0 | 0 | 16 |
| control | control_wire_number_mismatch | 网表两端线号不一致 | 0 | 0 | 0 |
| bom | duplicate_bom_tag | 同范围采购锚点位号重复 | 0 | 0 | 287 |
| bom | bom_breaker_poles_missing | 断路器极数缺失或无法解析 | 0 | 0 | 51 |
| bom | bom_rated_current_missing | 保护器缺少有效额定电流 | 0 | 0 | 62 |
| bom | bom_anchor_spec_missing | 采购锚点规格信息不足 | 0 | 0 | 287 |
| bom | bom_anchor_tag_missing | 采购锚点缺少位号 | 0 | 0 | 287 |
| bom | bom_detail_anchor_mismatch | BOM 明细与采购锚点不一致 | 0 | 0 | 14 |
| bom | bom_summary_quantity_mismatch | BOM 汇总数量异常 | 0 | 0 | 14 |
| bom | symbol_class_unknown | 无法解析冻结符号类别 | 0 | 0 | 345 |
| bom | netlist_dangling_edge | 网表边引用缺失实例 | 0 | 0 | 0 |

## 退化、纯网表和修复复检

- EBJS-G-ALIAS-003 对比 EBJS-P-GGD-001，规则、分级及位号一致。
- EBJS-G-BLUR-001 对比 EBJS-P-GGD-001，规则、分级及位号一致。
- EBJS-G-SKEW-002 对比 EBJS-S-DOL-001，规则、分级及位号一致。
- 全部 14 张纯 instances + netlist 输入的红灯结果一致。
- 四张缺陷图分别应用全部红灯语义补丁后复检，红灯均清零。
