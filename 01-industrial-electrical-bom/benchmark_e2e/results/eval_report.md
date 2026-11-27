# ElectroBench-JS v1.0.0 端到端离线评测

完整系统在 11 张主验收图上的综合解析为 **97.88%**，严格采购明细完整率为 **96.92%**，图纸可见字段汇总完整率为 **96.65%**，平均耗时为 **0.088 秒/张**。

- 93% 综合门槛通过，95.5% 主集综合目标通过，95% 严格明细门槛通过，95% 可见字段汇总门槛通过，15 秒耗时目标通过。
- 明细 Precision 96.92%，汇总 Precision 96.65%。含采购目录号的扩展诊断完整率为 13.88%。原图缺少的目录号需由 ERP 或选型目录补充。
- 四类合规红灯 Precision **100.00%**，Recall **100.00%**，5 TP、0 FP、0 FN。7 张标准图全部规则的红灯误报 **0**。
- Full 14 张全集综合 **93.13%**，93% 全集目标通过。

## 主验收集与通道对比

| 组别 | 图数 | 综合 | 符号 F1 | 规格原始精确 | 规格语义 | 无向边 F1 | 有向边 F1 | BOM 严格明细 | BOM 可见字段汇总 | 均值秒 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full 完整系统 | 11 | 97.88% | 100.00% | 96.92% | 96.92% | 95.83% | 90.66% | 96.92% | 96.65% | 0.088 |
| 纯 DXF | 11 | 97.88% | 100.00% | 96.92% | 96.92% | 95.83% | 90.66% | 96.92% | 96.65% | 0.088 |
| A1 全光栅 | 11 | 78.45% | 88.68% | 68.28% | 79.30% | 60.89% | 54.95% | 90.31% | 90.91% | 5.716 |
| 纯 PDF | 11 | 77.32% | 86.25% | 66.52% | 77.97% | 62.14% | 56.31% | 92.95% | 92.34% | 6.315 |
| B1 OCR 正则 | 11 | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 60.35% | 57.89% | 3.556 |
| B2 纯光栅 | 11 | 75.23% | 88.68% | 68.28% | 79.30% | 48.02% | 43.77% | 90.31% | 90.43% | 5.219 |
| B3 纯 VLM | 0 | — | — | — | — | — | — | — | — | — |
| A2 朴素连线 | 11 | 89.95% | 100.00% | 96.92% | 96.92% | 64.13% | 60.33% | 96.92% | 96.65% | 0.048 |
| A3 去 KG | 11 | 97.88% | 100.00% | 96.92% | 96.92% | 95.83% | 90.66% | 96.92% | 96.65% | 0.073 |

主验收集包含 4 张一次、3 张二次、4 张缺陷图。Full 在主集自动选 DXF，全集还含光栅退化输入。纯 PDF 先走 PDF 页的文字和原语解析，再从同一页的渲染图追踪导线。
B1 仅从原始 PNG 做 OCR 和文本规格抽取。其文字框无法替代器件定位，明细仍逐条核对真值规格。

## 分层与退化对照

| 组别 | 图数 | 综合 | 符号 F1 | 规格语义 | 输出规格精确 | 拓扑 F1 | BOM 严格明细 | BOM 可见字段汇总 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full/primary | 4 | 98.48% | 100.00% | 95.65% | 95.65% | 100.00% | 95.65% | 95.35% |
| full/secondary | 3 | 97.31% | 100.00% | 100.00% | 100.00% | 89.23% | 100.00% | 100.00% |
| full/defect | 4 | 97.88% | 100.00% | 96.59% | 96.59% | 96.30% | 96.59% | 96.30% |
| full/degraded | 3 | 73.29% | 90.51% | 61.67% | 58.33% | 62.00% | 63.33% | 63.16% |
| full/all | 14 | 93.13% | 98.09% | 89.55% | 88.85% | 90.22% | 89.90% | 89.47% |
| png/main | 11 | 78.45% | 88.68% | 79.30% | 68.72% | 60.89% | 90.31% | 90.91% |
| png/degraded | 3 | 56.25% | 82.35% | 41.67% | 38.33% | 34.88% | 51.67% | 50.88% |
| degraded_no_kg/degraded | 3 | 56.25% | 82.35% | 41.67% | 23.33% | 34.88% | 43.33% | 50.88% |

| 退化图 | 模式 | 综合 | 规格原始精确 | 输出规格精确 | 规格语义 | BOM 明细 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| EBJS-G-ALIAS-003（alias） | png | 56.79% | 4.35% | 43.48% | 43.48% | 65.22% |
| EBJS-G-ALIAS-003（alias） | degraded_no_kg | 56.79% | 4.35% | 4.35% | 43.48% | 43.48% |
| EBJS-G-BLUR-001（blur） | png | 33.04% | 8.70% | 8.70% | 8.70% | 8.70% |
| EBJS-G-BLUR-001（blur） | degraded_no_kg | 33.04% | 8.70% | 8.70% | 8.70% | 8.70% |
| EBJS-G-SKEW-002（skew） | png | 82.95% | 78.57% | 78.57% | 92.86% | 100.00% |
| EBJS-G-SKEW-002（skew） | degraded_no_kg | 82.95% | 78.57% | 78.57% | 92.86% | 100.00% |

### 低清 PNG 前后对照

主验收 PNG 中 0/11 张触发增强。两路解析共用增强后的同尺寸像素网格。

| 图纸 | 模式 | 符号 F1 | 规格语义 | BOM 严格明细 | 无向边 F1 | 综合 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| EBJS-G-BLUR-001 | 原始输入 | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| EBJS-G-BLUR-001 | 增强输入 | 75.00% | 8.70% | 8.70% | 0.00% | 33.04% |

## 消融贡献

各列为完整模式减对应消融组。退化去 KG 行使用同一组 3 张原始 PNG，简写行仅比较 alias 图。YOU-263 自身会解析常见别名，关闭 KG 时保留其内置解析能力，并以可获取的 OCR 原文输出位号与规格。
端到端红灯 Recall 衡量管线实际发出的告警。A3 关闭合规模块，因此没有发出告警，模块自身 Precision/Recall 仍留空。

| 消融 | 图数 | 综合 pp | 拓扑 F1 pp | BOM 明细 pp | BOM 汇总 pp | 输出规格精确 pp | 红灯 Recall pp | 均值秒差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| png | 11 | +19.43 | +34.93 | +6.61 | +5.74 | +28.19 | +40.00 | -5.628 |
| no_topology | 11 | +7.92 | +31.69 | +0.00 | +0.00 | +0.00 | +20.00 | +0.039 |
| no_kg | 11 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +100.00 | +0.014 |
| degraded_no_kg | 3 | +0.00 | +0.00 | +8.33 | +0.00 | +15.00 | — | -0.037 |
| alias_no_kg | 1 | +0.00 | +0.00 | +21.74 | +0.00 | +39.13 | — | -0.113 |

## 合规与耗时

| Full 主集红灯 | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| ampacity_insufficient | 1 | 0 | 0 | 100.00% | 100.00% |
| interlock_missing | 2 | 0 | 0 | 100.00% | 100.00% |
| motor_protection_missing | 1 | 0 | 0 | 100.00% | 100.00% |
| selectivity_inversion | 1 | 0 | 0 | 100.00% | 100.00% |

| 主集通道 | 阶段 | 均值秒 | P50 秒 | P95 秒 |
| --- | --- | ---: | ---: | ---: |
| full | parse_s | 0.053 | 0.049 | 0.086 |
| full | topology_s | 0.030 | 0.031 | 0.037 |
| full | compliance_s | 0.004 | 0.005 | 0.006 |
| full | total_s | 0.088 | 0.082 | 0.121 |
| dxf | parse_s | 0.053 | 0.049 | 0.086 |
| dxf | topology_s | 0.030 | 0.031 | 0.037 |
| dxf | compliance_s | 0.004 | 0.005 | 0.006 |
| dxf | total_s | 0.088 | 0.082 | 0.121 |
| png | parse_s | 5.396 | 5.171 | 6.822 |
| png | topology_s | 0.317 | 0.300 | 0.427 |
| png | compliance_s | 0.003 | 0.003 | 0.004 |
| png | total_s | 5.716 | 5.474 | 7.165 |
| pdf | parse_s | 5.922 | 5.408 | 8.205 |
| pdf | topology_s | 0.389 | 0.400 | 0.451 |
| pdf | compliance_s | 0.004 | 0.003 | 0.007 |
| pdf | total_s | 6.315 | 5.831 | 8.636 |

## 误差归因

定位先核对符号命中，再核对规格和端口边。疑似 OCR 混淆、串位或断线的分类是自动归因线索，需回到原图框和连线复核。差错计数允许同一器件在不同阶段出现。

| 阶段与归因 | 数量 |
| --- | ---: |
| compliance/false_positive/topology | 1 |
| spec/absent_spec_text | 17 |
| spec/possible_ocr_confusion | 3 |
| symbol/false_detection | 2 |
| symbol/missed | 11 |
| topology/extra_connection | 13 |
| topology/logical_branch_or_port_missing | 9 |
| topology/missing_endpoint | 17 |
| topology/possible_raster_break | 19 |
| topology/unmatched_endpoint | 1 |

- 符号漏检 Top-K 为 WL 5、PA 1、PE 1、PJ 1、PV 1、TV 1、WB 1。

- 符号误检 Top-K 为 T 1、WL 1。

### 可复核案例

1. EBJS-G-BLUR-001 / i016 / false_positive/topology。真值 `null`，预测 `"motor_protection_missing"`，像素框 `[[680.0, 932.0, 48.0, 64.0]]`。对照匹配框、规格与路径证据，补齐可观测字段后再运行确定性规则。
2. EBJS-D-AMP-002 / i001 / absent_spec_text。真值 `"TMY"`，预测 `""`，像素框 `[[160.0, 496.8, 1472.0, 6.4]]`。核对原图字形与位号周围规格框，联合检查文字行分割和规格绑定。
3. EBJS-G-ALIAS-003 / i001 / absent_spec_text。真值 `"TMY"`，预测 `""`，像素框 `[[160.0, 496.8, 1472.0, 6.4]]`。核对原图字形与位号周围规格框，联合检查文字行分割和规格绑定。
4. EBJS-G-BLUR-001 / i001 / missed。真值 `"WB WB1"`，预测 `null`，像素框 `[[160.0, 496.8, 1472.0, 6.4]]`。检查训练或模板中该符号的尺寸、方向及遮挡条件。
5. EBJS-D-ILK-004 / i008 / logical_branch_or_port_missing。真值 `{"connection":["i008","i009"],"kind":"control"}`，预测 `null`，像素框 `[[568.0, 376.0, 64.0, 40.8], [824.0, 240.0, 64.0, 40.8]]`。检查端口挂接、母线分支、线段连续性或电缆标注的逻辑连接。
6. EBJS-G-BLUR-001 / i001 / missing_endpoint。真值 `{"connection":["i001","i004"],"kind":"power"}`，预测 `null`，像素框 `[[160.0, 496.8, 1472.0, 6.4], [172.0, 372.0, 46.0, 64.0]]`。检查端口挂接、母线分支、线段连续性或电缆标注的逻辑连接。
7. EBJS-D-MOT-003 / i001 / absent_spec_text。真值 `"TMY"`，预测 `""`，像素框 `[[160.0, 496.8, 1472.0, 6.4]]`。核对原图字形与位号周围规格框，联合检查文字行分割和规格绑定。
8. EBJS-G-BLUR-001 / i002 / absent_spec_text。真值 `"630A 3P"`，预测 `""`，像素框 `[[182.0, 100.0, 32.0, 64.0]]`。核对原图字形与位号周围规格框，联合检查文字行分割和规格绑定。
9. EBJS-G-SKEW-002 / i005 / missed。真值 `"PE PE1"`，预测 `null`，像素框 `[[189.13, 894.9, 42.37, 42.37]]`。检查训练或模板中该符号的尺寸、方向及遮挡条件。
10. EBJS-S-ATS-003 / i015 / logical_branch_or_port_missing。真值 `{"connection":["i015","i021"],"kind":"control"}`，预测 `null`，像素框 `[[1528.0, 168.0, 64.0, 40.0], [456.0, 866.4, 48.0, 19.2]]`。检查端口挂接、母线分支、线段连续性或电缆标注的逻辑连接。
11. EBJS-G-SKEW-002 / i001 / missing_endpoint。真值 `{"connection":["i001","i006"],"kind":"power"}`，预测 `null`，像素框 `[[152.76, 248.3, 37.44, 65.93], [266.25, 648.03, 56.25, 28.1]]`。检查端口挂接、母线分支、线段连续性或电缆标注的逻辑连接。
12. EBJS-D-SEL-001 / i001 / absent_spec_text。真值 `"TMY"`，预测 `""`，像素框 `[[160.0, 496.8, 1472.0, 6.4]]`。核对原图字形与位号周围规格框，联合检查文字行分割和规格绑定。
13. EBJS-G-BLUR-001 / i003 / absent_spec_text。真值 `"In=630A 3P Icu=50kA"`，预测 `""`，像素框 `[[175.2, 236.0, 33.6, 64.0]]`。核对原图字形与位号周围规格框，联合检查文字行分割和规格绑定。
14. EBJS-G-BLUR-001 / i005 / missed。真值 `"PA PA1"`，预测 `null`，像素框 `[[322.0, 212.0, 44.0, 64.0]]`。检查训练或模板中该符号的尺寸、方向及遮挡条件。
15. EBJS-S-DOL-001 / i012 / logical_branch_or_port_missing。真值 `{"connection":["i012","i020"],"kind":"control"}`，预测 `null`，像素框 `[[1568.0, 424.0, 64.0, 40.0], [648.0, 898.4, 48.0, 19.2]]`。检查端口挂接、母线分支、线段连续性或电缆标注的逻辑连接。

### 各通道合规误判追踪

| 通道 | 图纸 | 规则 | 自动归因 |
| --- | --- | --- | --- |
| png | EBJS-D-AMP-002 | ampacity_insufficient | false_negative/topology |
| pdf | EBJS-D-AMP-002 | ampacity_insufficient | false_negative/symbol |
| no_topology | EBJS-D-AMP-002 | ampacity_insufficient | false_negative/topology |
| pdf | EBJS-D-ILK-004 | motor_protection_missing | false_positive/insufficient_rule_evidence |
| no_topology | EBJS-D-ILK-004 | motor_protection_missing | false_positive/insufficient_rule_evidence |
| png | EBJS-D-SEL-001 | selectivity_inversion | false_negative/topology |
| pdf | EBJS-D-SEL-001 | selectivity_inversion | false_negative/topology |
| full | EBJS-G-BLUR-001 | motor_protection_missing | false_positive/topology |
| png | EBJS-G-BLUR-001 | motor_protection_missing | false_positive/topology |
| pdf | EBJS-S-FREV-002 | motor_protection_missing | false_positive/insufficient_rule_evidence |
| no_topology | EBJS-S-FREV-002 | motor_protection_missing | false_positive/insufficient_rule_evidence |

## 评分与复现边界

- 推理暂存目录只有原始图纸，评分器验证 manifest 记录的标注 SHA-256 后读取标签。综合指标分母包含漏检器件，所有通道共用同一评分器。
- 明细项要求类别与数量一致，且位号或定位匹配。真值有规格时，语义规格也必须一致。主汇总按采购类别、规格语义、单位及总数量匹配。目录号诊断另存为 bom_model_summary。
- 母排规格只从邻近的可见文本补绑。主集 7 张带母排的 DXF 正文没有 TMY 或 LMY 标注，对应规格保留空值并计入遗漏。
- B1 的框是 OCR 文字框，B2 和 A2 的边使用邻近端口，A3 关闭合规引擎。四类缺陷用规则 ID 和映射后的实例 ID 匹配，额外规则红灯单列。
- Cu/Al 查表按 YOU-265 的项目筛查配置。载流量条件可由已观察到的 In > Iz 单独证伪。无 Ib 的图纸不发完整载流量绿灯。
- 耗时包含解析、连接/BOM 及合规，采用本机单进程顺序测量。复现比较数值指标，耗时单独记录。

- B3 状态为 pending_vlm_api_key。配置环境后先运行以下第一条命令生成预测，再运行第二条重评。

~~~bash
python -m benchmark_e2e.vlm_baseline --out vlm_preds.json
python -m benchmark_e2e.run_benchmark --vlm-predictions vlm_preds.json
~~~

两次完整运行的非耗时评测载荷规范化为 UTF-8 JSON 后逐字节一致。SHA-256 为 937543260dcd0665e5b4ecf5fd08c8023b17d82c28e48a2fb52457bf2a7fbfe6。

## 上游代码

- PR #4 · a5e0e28bafd3d8a8b1356bbf8c510ee26194ed35
- PR #5 · 91b6adaaf4f249126bd66af06c3c13566989d906
- PR #8 · 28ace34225bf182b81753c6c70b739f0797f8963
- PR #9 · fcb266c85350a65ff3e128989407cad7e7ca281c
