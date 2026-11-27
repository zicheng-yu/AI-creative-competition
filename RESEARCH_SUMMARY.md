# 三赛道数据集、开源方案与竞品全景调研总览

> **调研日期**：2026-11-27  
> **同步看板**：Linear Project `P-YOU-22`（[2026.11-12 江苏“人工智能+”创新应用大赛 · 三赛道](https://linear.app/youonlyattendonce/project/202611-12-江苏人工智能创新应用大赛-三赛道-a4b4dd4ad4ed/overview)）  
> **关联调研任务**：`YOU-260` ｜ **分赛道详版报告**：[01 电气图纸与 BOM](./01-industrial-electrical-bom/research.md) · [02 异构算力智能调度](./02-sansu-computing-dispatch/research.md) · [03 流感免疫原科研智能体](./03-medical-flu-immunogen/research.md)

---

## 一、三赛道数据可得性结论与 72h 破局策略

| 赛道 / 赛题 | 官方数据要求 | 现成公开数据集结论 | 72h 冲刺最优数据构建策略 | 对应 Linear Issue |
| :--- | :--- | :--- | :--- | :---: |
| **01 · `AI-MFG-Q21`**<br>电气图纸智能解析与 BOM 自动生成 | 预期成果明确要求**标准化数据集**；硬指标：解析准确率 ≥93%、BOM 完整率 ≥95% | **有通用电路/符号数据集，但无现成国标成套开关柜一次/二次+合规缺陷数据集**。<br>可用基础集：`CGHD`（DFKI，3200+ 手绘电路图含 Netlist）、Roboflow `single line diagram` / `EplanSymbols`、`bshada/open-schematics`、`FloorPlanCAD`（矢量符号定位方法参考） | **公开集验证泛化 + 程序化合成国标真值集（`ElectroBench-JS`）**：用 `ezdxf` + `GB/T 4728 / IEC 60617` 标准符号块批量合成一次配电系统图与二次电机控制图（DXF + 高清渲染 PNG + 扫描退化增强），自动导出 100% 精确 COCO 框、Netlist 与 BOM 真值，并可控注入 4 类国标违规缺陷 | `YOU-262` |
| **02 · `AI-JIANGSU-Q36`**<br>异构算力智能调度与能效优化 | 官方未给真实生产日志，但要求**可量化、可仿真验证**及**能耗对比基线 + 算法权重包** | **有极高质量真实大规模 GPU 集群 Trace 与电网碳强数据！**<br>`Alibaba Cluster Trace GPU`（`v2020/v2025/v2026`，最高 15.5 万 GPU）、SenseTime `HeliosData`（异构 GPU 多租户）、Microsoft `Philly`、`Electricity Maps` / Figshare Carbon-Aware 数据集 | **真实公开 Trace 驱动 + 江苏真实底座校准（`JS-ComputeSim-313`）**：从 Alibaba/Helios 抽取训推任务到达分布与时长规律，映射到江苏 1+13（313 数据中心 / 271.8 EFlops）+ 沪浙皖长三角拓扑、1ms/5ms/10ms 时延矩阵、苏南/苏北分时电价与盐城/南通风光绿电曲线 | `YOU-268` |
| **03 · `AI-HEALTH-Q40`**<br>流感病毒免疫原辅助设计智能体 | 预期成果明确要求**标准化数据集**；强制**来源 + 数据版本 + 不确定性 + 专家复核**；两类科研任务对比人工 SOP | **全部权威公开生物医药数据源均免费开放且支持脚本化拉取锁定快照！**<br>`NCBI Virus / Datasets CLI`、`Nextstrain` 季节性流感 FASTA/TSV、`IEDB` 流感表位实验库、`Bloom Lab DMS` 逃逸实验数据、`BV-BRC`、`RCSB PDB`、`PubMed/Europe PMC`（注：规避 GISAID 再分发限制） | **多权威库本地版本快照 + 循证评测集（`FluEvidenceBench-v1`）**：脚本抓取并固化带时间戳/版本号的 Evidence Capsule（区分 `T1` 湿实验 / `T2` 流行监测 / `T3` 文献 / `T4` 计算预测），参照 `LitQA2` / `BioASQ` 口径构建 Task-1 问答集与 Task-2 4 候选对照集 + 固定人工 SOP 计时基线 | `YOU-274` |

---

## 二、三赛道推荐直接复用的开源技术栈

| 赛道 | 核心解析 / 仿真 / 检索开源底座 | 算法 / 智能体核心组件 | 工业/科研部署参考栈 |
| :--- | :--- | :--- | :--- |
| **01 工业电气 BOM** | `mozman/ezdxf`（矢量 DXF 解析与图块拆解）、`PyMuPDF`、`D4NGYY/schematic-extractor`（矢量 PDF+YOLO+BFS 拓扑）、`JKc66/CircuitVision`（YOLOv11+SAM+VLM） | `SAHI` + `YOLOv11` + `PaddleOCR` + `Qwen2.5-VL`（ROI 精修）+ `NetworkX`（Netlist 构图）+ 确定性规则引擎 + 国标 RAG | Docker/K8s 厂区内网私有化 + 浏览器 Web Speech / Whisper ASR |
| **02 异构算力调度** | `dos-group/vessim`（Python 算电协同仿真）、`SustainCluster`（Gymnasium 碳感知调度基准）、`gpu2grid/openg2g`、`atlarge-research/opendc` | `HiGHS` / `SciPy milp` / `Google OR-Tools`（宏观 MILP）+ `PKU-Alignment/omnisafe`（`PPOLag` Safe-RL）+ `LightGBM`/`PatchTST`（24h 预测） | 非侵入边车对接 **CNCF HAMi**（已支持昇腾/寒武纪/海光/NVIDIA）+ **Volcano** + **Koordinator** + **Kueue** |
| **03 流感免疫原智能体** | `Nextclade`（进化分支与突变调用）、`ncbi/MedCPT`（PubMed 专用双塔检索 + Cross-Encoder 重排）、`Future-House/paper-qa`（PaperQA2 句级引文溯源架构） | `LangGraph` 四智能体编排 + `BioChatter`/NetworkX 四维 KG + `OATML-Markslab/EVEscape`（`T4` 辅助证据）+ NLI 零幻觉审计门禁 | 全离线私有化容器 + 本地向量库（Qdrant/Chroma）+ 本地 LLM/Cross-Encoder |

---

## 三、三赛道核心竞品格局与我方差异化抓手

| 赛道 | 核心竞品代表 | 竞品核心短板（我方直接破局点） | 我方核心壁垒 |
| :--- | :--- | :--- | :--- |
| **01 工业电气 BOM** | **Werk24**（德国机械图纸 AI API）、**CADDi Drawer**、**EPLAN**、**利驰电小二/SuperWORKS**、**广联达 GQI**、**浩辰 CAD 电气** | **Werk24 主攻机械零件 GD&T/公差**而非电气回路拓扑与国标电气合规；EPLAN/利驰依赖原生正向制图库，对第三方扫描 PDF 与跨院画法泛化弱；广联达偏建筑造价而非成套开关柜二次控制逻辑 | **矢量+光栅双通道兼容非标扫描件 + 可计算电气 Netlist 拓扑重建 + 国标（GB 7251/50054）KG 双引擎自动抓错 + 语音审图 Copilot** |
| **02 异构算力调度** | **Run:ai（NVIDIA）**、**Cast AI**、**阿里云灵骏**、**华为云昇腾**、**无问芯穹**、**国家超算互联网** | Run:ai 绑定 NVIDIA 单集群生态；Cast AI 偏多云 Spot 省钱缺国产异构与省域绿电；云大厂方案生态封闭；无问芯穹重芯片级 MaaS 缺省级 1+13 电网/PUE/碳排联合优化 | **厂商中立省级 1+13 + 长三角跨主体调度大脑 + 异构当量与非线性 PUE/风光绿电联合建模 + MILP+Safe-RL 秒级故障自愈 + LLM 影子价格归因与碳足迹账本** |
| **03 流感免疫原智能体** | **FutureHouse（PaperQA/Kosmos）**、**Elicit / Consensus / Scite.ai**、**Cradle Bio / Absci / Generate**、**深势科技 Bohrium / 百图生科 / 晶泰科技** | 通用科研搜索（Elicit/Consensus）不懂流感 HA 成熟编号与信号肽偏移、无多源版本锁与 HITL 签批；生成式蛋白平台（Cradle/Absci/百图）属黑盒预测或重湿实验闭环，不符合本赛题“可溯源、不承诺疗效”的合规导向 | **多权威库严格版本快照锁 + 四级证据分级（严禁 T4 伪装 T1）+ HA 编号对齐四维 KG + 文献冲突/证据空白显式披露 + 专家 HITL 签批留痕** |

---

## 四、并行开发分工与 Linear Issue 索引

为实现团队多线并行冲刺，Linear 项目 `P-YOU-22` 已新增 `M0`（数据基准与竞品锁定）与 `M1.5`（离线定量评测闭环）2 个同步门禁，并拆解 23 个子任务：

| 并行条线 | M0 数据/仿真基准 | M1 核心算法/前端/底座 | M1.5 离线定量评测 | M2 交付物冲刺（11/29） |
| :--- | :--- | :--- | :--- | :--- |
| **共享底座** | `YOU-260` 调研（本 PR） | `YOU-261` 前后端契约与 4 共用组件 | — | `YOU-282` 终审与网盘打包（11/30） |
| **01 电气 BOM** | `YOU-262` `ElectroBench-JS` | `YOU-263` 双通道解析 · `YOU-264` 拓扑/BOM · `YOU-265` 国标 KG 校验 · `YOU-266` 审图工作台 | `YOU-267` ≥93%/≥95% 三基线评测 | `YOU-279` 计划书/PPT/录屏/佐证 |
| **02 算力调度** | `YOU-268` `JS-ComputeSim-313` | `YOU-269` 时序+MILP · `YOU-270` Safe-RL+权重 · `YOU-271` LLM Copilot+账本 · `YOU-272` 1+13 地图沙盘 | `YOU-273` 四基线六维仿真评测 | `YOU-280` 计划书/白皮书/PPT/录屏 |
| **03 流感智能体** | `YOU-274` `FluEvidenceBench-v1` | `YOU-275` 四维 KG+时序 · `YOU-276` 混合 RAG/权重/四智能体 · `YOU-277` 科研工作台+HITL | `YOU-278` 两类任务对比人工 SOP | `YOU-281` 计划书/部署/PPT/录屏 |
