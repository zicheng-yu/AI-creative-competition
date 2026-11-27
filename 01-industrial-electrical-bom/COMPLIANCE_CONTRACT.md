# YOU-265 合规接口 v1.0.0

适配 PR #4 冻结的 ElectroBench-JS v1.0.0。输入字段以 [SCHEMA.md](docs/SCHEMA.md) 为准。评测入口、规则实现和公开数据分别在 [compliance/](compliance/)、[tests_compliance/](tests_compliance/) 和 [frontend_demo_data/](frontend_demo_data/)。

## 运行与复现

在 `01-industrial-electrical-bom/` 下运行。Python 3.10+，环境中需有 NetworkX 和 pytest。隔离环境可使用预备的本地 wheel 安装依赖。

```bash
python -m pip install --no-index --find-links /path/to/wheels -r compliance/requirements.txt
python -m compliance.run_eval
python -m pytest tests_compliance -q
```

已安装依赖的环境从第二条命令开始。运行时只读取本地样例与知识库，不加载外部模型。命令检查冻结 manifest 与样例标注哈希，生成 `compliance/eval_report.md`、`compliance/eval_summary.json`、`frontend_demo_data/compliance_reports.json` 和 `frontend_demo_data/electrical_kg.json`。它逐条匹配红灯的 `(rule_id, sorted(instance_ids))`，并核对 14 张纯网表输入、3 张退化图和 4 张缺陷图的修复复检。3 张退化图对比的是标注或归一化后的结构输入。

## 输入

`evaluate(annotation)` 和 `DeterministicRAGExplainer.answer(question, drawing=annotation)` 接受字典。完整冻结标注可直接传入。YOU-263 / YOU-264 最小集为：

```json
{
  "id": "client-drawing",
  "sheet": {"height_mm": 297, "width_mm": 420, "px_per_mm": 4},
  "instances": [
    {"id": "b1", "class_code": "QF", "tag": "QF1", "bbox_px": [100, 90, 24, 36],
     "specs": {"In_A": 80, "poles": "3P", "model": "breaker"}},
    {"id": "w1", "class_code": "WL", "tag": "WL1", "bbox_px": [101, 160, 40, 18],
     "specs": {"section_mm2": 16, "Ib_A": 60, "Iz_A": 66, "spec": "YJV-4x16"}}
  ],
  "netlist": {"edges": [{"source": "b1", "target": "w1", "kind": "power"}]}
}
```

- 实例 `id` 为图内唯一字符串。类型优先使用 `class_code`，兼容 `class_id`、行业简写和 OCR 的 `label_tag`、`label_spec`。同一设备可有共用位号的主触头、线圈和辅助触点。只有采购锚点参与位号重复与 BOM 汇总检查。
- 网表边连接实例 ID，包含 `source`、`target` 和 `kind`。`power` 为上游到下游，`control` 为励磁方向，`branch` 与 `pe` 表示测量和接地。保留端口与线号可启用接线一致性检查。几何交叉点需在上游解析时消歧。若解析器输出端口或接线网 ID，先映射为实例间有向边。
- 有控制边时从网表计算供电可达性、对侧常闭接点是否覆盖全路径，以及并联自锁。可选 `netlist.control_sources` 指定供电实例。正反转配对由注解、公共电机前的主触头、位号或按钮语义识别。`control_branches` 提供配对线索，并可在控制边缺失时验证已有串联信息。
- 坐标均为 `[x,y,w,h]`。像素从左上角向下，毫米从左下角向上。优先使用实例已有坐标，从一套坐标推算另一套时需提供 `sheet.px_per_mm` 和 `sheet.height_mm`。倾斜图优先使用实际画布下的 `bbox_px` 和原始 `bbox_mm`。无法推算的坐标返回 `null`。
- 可选 `cabinet`、`voltage`、`circuit_kind`、`assembly.five_preventions`、`bom`、`bom_summary` 用于专项检查。`defects` 和 `logic` 由评测器或上游使用。
- 额定及计算电流使用 A，分断和预期短路电流使用 kA，`voltage_V`、`primary_V`、`circuit_V` 使用 V，截面使用 mm²。其他显式输入包括 `mechanical_min_mm2`、`neutral_min_mm2`、`pe_min_mm2`、`let_through_A2s`、`adiabatic_k`、`I2_A`；`extra.secondary_closed`、`extra.secondary_shorted`、`extra.integral_backup`、`extra.mechanical_interlock` 为布尔证据。

## 输出

### 图纸体检

`evaluate` 返回 `schema_version`、`drawing_id`、`status`、`counts`、`not_evaluated_rule_ids` 和 `findings`。`enabled_rules` 指定 ID 白名单，`disabled_rules` 可排除 ID。通过的适用检查返回 `pass`。缺输入的某些专项规则不执行，ID 进入 `not_evaluated_rule_ids`。有明确证据缺口的检查可发黄灯。

| 字段 | 内容 |
| --- | --- |
| `severity`, `rule_id`, `family`, `message` | 三色分级、稳定规则 ID、规则分类和名称 |
| `bbox_px`, `bbox_mm` | 该告警所涉实例框的并集。多点闪烁使用 `locations[]` 内各实例的原始精确框 |
| `instance_ids`, `tags`, `locations[]` | 实例 ID、规范化位号及每个实例的两套坐标 |
| `evidence`, `standard_refs` | 量化值、阈值或路径及条文 ID |
| `fix_suggestion.action`, `fix_suggestion.operations[]` | 整改指导和可选语义补丁。操作为空时需补充资料或工程确认 |

前端静态数据根键为 `schema_version`、`reports`、`clauses`。`reports[drawing_id]` 包含 `title`、`sheet`、相对 Track 01 根目录的 `drawing_asset` 和体检结果。红黄灯的 `rag.clause_ids` 至少包含直接依据，可在同一 JSON 的 `clauses[clause_id]` 查到来源 URL、摘要和可引用片段。绘制整体状态用 `status`，筛选项目用 `severity`。

`apply_fix(annotation, finding["fix_suggestion"])` 返回新字典，重新生成 BOM 和派生的网表索引。支持 `update_specs`、`insert_series`、`rebuild_bom`。补丁包含期望旧值或入边，旧值变化时会拒绝应用。拓扑插入点带 `layout_pending`，在 CAD 中完成实际布点和走线，复检使用更新后的图结构。冻结样例使用合成型号的补丁属于语义预览。

### KG 与国标问答

```python
from compliance.kg import build_kg, export_kg, select_cable
from compliance.explainer import DeterministicRAGExplainer

subgraph = export_kg(build_kg(), ["symbol:QF"], hops=2)
cable = select_cable(60, 70, "Cu")
answer = DeterministicRAGExplainer().answer("查一下 QF2 为什么报级差错误？", drawing=annotation)
```

图 JSON 有 `nodes[]` 和 `edges[]`。节点按 `id` 引用，`layer` 为 1（符号）、2（选型）、3（条文与规则），边含 `source`、`target`、`key`、`relation`。可直接使用全图静态 JSON，也可按多个种子取子图。

问答接受 UTF-8 文本或已转写的语音文本。返回 `intent`、`answer`、`clause_ids`、`clauses[]`、可选 `findings`、`fix_suggestion` 和 `recheck`。品牌替换在选中唯一器件并取得所需额定值时返回 `candidates` 和补丁复检预览。Icu、Icn 和中压短路开断电流按各自指标比较。厂商目录为代表性型号，依据见条目的 `source_url`。

### 条文与工程筛查边界

- `text_kind: short_excerpt` 记录可追溯短引文。仅能核到标准题录或章节范围的条目保存 `text_kind: summary` 和空 `excerpt`。获得授权全文后可在 `compliance/kb_data/clauses.json` 补片段，保持现有条文 ID。
- 1.6 倍断路器筛查、10% 载流量余量、Cu 电缆查表和 PE 截面近似沿用项目口径。Al 表为演示用 Cu 表的 0.75 向下取整。工程选型须带敷设条件、温度、聚束、短路、协调表及设计资料。
- KYN28 五防、ATS 机械联锁及 CT 二次闭合依赖显式证据。色灯是已执行规则的图纸级证据。冻结集结果可用于赛题数据链路验收。

## zicheng 接入 LLM

[compliance/explainer.py](compliance/explainer.py) 中的 `BaseComplianceLLM` 有 `TODO(zicheng): plug in LLM provider`。实现 `explain_finding(finding)` 与 `answer(question, drawing=...)`，由应用层注入实例。可复用 `DeterministicRAGExplainer` 的结构化检索结果来增强措辞，沿用此契约的引用、证据、操作语义和复检字段。规则结果来自 `evaluate`，集成方继续使用该结果作为红黄绿灯的来源。
