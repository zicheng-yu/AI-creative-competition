# YOU-267 · Track 01 端到端离线评测

评测从原始 DXF、PNG 或 PDF 开始，依次运行 YOU-263、YOU-264 和 YOU-265。所有基线共用评分器。PR #4、#5、#8、#9 的集成版本与 PR #7 工作台契约版本写在 `results/eval_summary.json`。

## 离线复现

在 `01-industrial-electrical-bom/` 执行。环境需要 Python 3.10+、本地 RapidOCR ONNX 模型和 `requirements.txt` 中的依赖。可提前准备 wheel 和模型，评测时完全离线。评测的进程保护会拒绝推理期间的网络调用、子进程启动和真值文件读取。原始图纸以中性文件名暂存在 `benchmark_e2e/` 内，运行后自动清理。

~~~bash
python -m pip install -r benchmark_e2e/requirements.txt
python -m benchmark_e2e.run_benchmark
python -m benchmark_e2e.run_benchmark --verify-repeat
python -m pytest -q tests_benchmark
python -m pytest -q tests/test_symbol_parser.py tests/test_netlist.py tests_compliance/test_compliance.py
~~~

在隔离无网环境，可把第一条替换成 `python -m pip install --no-index --find-links <本地wheel目录> -r benchmark_e2e/requirements.txt`。图表从已安装的 Microsoft YaHei、SimHei、Noto Sans CJK SC 或其他受支持中文字体中选择。系统无中文字体时图表用英文标签。Windows 实测本机使用 Microsoft YaHei。运行中写入的耗时反映当前机器，`--verify-repeat` 逐字段对比两轮非耗时指标。

## 样本与执行矩阵

| 组别 | 主集 11 张 | 退化 3 张 | 推理路径 |
| --- | ---: | ---: | --- |
| Full | 11 | 3 | 有原始 DXF 时走 DXF，光栅件走 PNG |
| DXF / PDF | 各 11 | — | DXF 分层几何或同一原始 PDF 页 |
| A1 PNG | 11 | 3 | PNG 模板与 OCR、骨架线追踪、KG 和合规 |
| B1 OCR | 11 | 3 | PNG 通用 OCR 和正则，输出文字框及文本 BOM |
| B2 Raster | 11 | 3 | PNG 模板与 OCR、端口邻近连线 |
| A2 去拓扑消歧 | 11 | — | DXF、端口邻近连线、合规 |
| A3 去 KG | 11 | — | DXF、精细拓扑，规则停用 |
| PNG 退化去 KG | — | 3 | PNG、精细拓扑，规则停用 |
| B3 VLM | 取决于外部预测覆盖 | 同左 | 原始 PNG，端到端结构化预测 |

Full 自动选中与强制通道配置一致的行会复用同一条实测轨迹。其余不同配置独立执行。纯 PDF 的符号与文字解析采用 PDF 原语和文字通道，导线重建采用原始 PDF 页的同分辨率渲染位图。三张退化图分别列出 blur、skew 和 alias 的纯 PNG 配对结果。常见别名还受 YOU-263 内置模板与 OCR 能力影响，去 KG 组保留该上游功能。

所有推理分支仅能看到一个原始图纸文件及公开符号、规范资料。样本名称与分组仅供驱动器挑选原始文件和汇总评分。真值读取集中在 `metrics.py`，验证冻结 manifest 的标注哈希后供评分使用。

## 指标

- 综合解析加权为符号检测 F1 × 0.40、规格语义准确率 × 0.35、无向器件连接对 F1 × 0.25。
- 符号在类别一致、IoU ≥ 0.5 时做最大基数一对一匹配，微平均。规格分母包含所有带规格的真值器件。分别报告原始 OCR/矢量文本精确值、输出规范化文本精确值和电气语义等效。拓扑同时给出无向及有向结果。预测边有未匹配端点时计入误报。
- BOM 明细要求类别与数量正确，并且位号正确或已匹配实例的可见规格语义等效。严格汇总同时检查采购型号、规格、单位与合计数量，另列规格与数量诊断口径。原图缺失的采购型号留空。两种主口径各自报告 Recall/完整率与 Precision。
- 核心红灯以规则 ID 和映射后的实例集合匹配。标准图同时统计全部规则的红灯。空分母使用 JSON null，停用规则的消融结果留空。适配层的 `preview_fix(prediction, finding)` 支持语义补丁后复检。
- 阶段耗时从已隔离好原始文件后开始，记录解析、拓扑/BOM、合规及总计。总耗时报告均值、P50 和 P95。

## B3 真实 VLM

`BaseVLMBaseline` 的接入点在 `vlm_baseline.py`。由 zicheng 在进程环境设置 `TRACK01_VLM_ENDPOINT`（完整的 chat/completions 地址）、`TRACK01_VLM_MODEL`、`TRACK01_VLM_TOKEN`。仅第一条显式采集命令访问提供方，后续重评仅加载 JSON。

~~~bash
python -m benchmark_e2e.vlm_baseline --out vlm_preds.json
python -m benchmark_e2e.run_benchmark --vlm-predictions vlm_preds.json
~~~

预测 JSON 的根字段为 `schema_version: "1.0.0"`、`predictions[]`。每行包含 `drawing_id`、`image_width`、`image_height`、`symbols[]`、`edges[]`、`bom_items[]`、`findings[]` 和可选 `seconds`。符号框采用原始 PNG 的左上像素 `[x,y,w,h]`。器件 ID 仅用于同图关联，评分使用类别和框映射。导出时只保留结构化预测。凭据从环境读取。无预测时，报告状态为 `pending_vlm_api_key`，对比表与图表保持无 B3 分数。部分覆盖汇总仍以实际覆盖图数显示，主定量对比图需要 B3 覆盖全套 11 张主集。

## 产物

- [报告](results/eval_report.md)、[详细 JSON](results/eval_summary.json)、[逐图 CSV](results/per_drawing_metrics.csv)、[消融 CSV](results/ablation_comparison.csv)
- [300 DPI 图表](results/figures/)
- [前端看板 JSON](../frontend_demo_data/eval_dashboard.json) 与 [工作台 CSV](../frontend_demo_data/eval_charts_workbench.csv)。工作台 CSV 可从「导入评测数据」直接导入，包含基线雷达图和分通道耗时柱状图。

适配主要在 `adapter.py`，包含端口坐标、图纸标注边、BOM 形状和合规输入。唯一上游修复在 `compliance/power_checks.py`。当电缆负荷电流未标注而 `In > Iz` 已由可见电流与截面证实，可以报超载红灯，并保留缺失的 Ib 和待复核状态。
