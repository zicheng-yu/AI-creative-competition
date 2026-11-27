# 赛道 02 深度调研：公开数据集、开源方案与竞品分析（`AI-JIANGSU-Q36`）

> **对应赛题**：`AI-JIANGSU-Q36` 异构算力智能调度与能效优化（江苏省数据集团有限公司命题 / “三苏”赛道）  
> **关联 Linear Issue**：`YOU-260`（调研） · `YOU-268`（`JS-ComputeSim-313` 仿真环境） · `YOU-269`~`YOU-273`（算法/前端/评测）  
> **核心要求**：未提供官方数据，须构建**可量化、可仿真验证**的绿色算力优化方案，交付**算法模型权重包**、**调度策略仿真评测报告与能耗对比基线**、**可演示平台**与**部署实施方案**

---

## 一、现成公开数据集盘点（真实集群 Trace + 绿电碳强数据）

虽然赛题未下发生产日志，但学术界与云厂商已有**极其扎实的大规模真实 GPU 集群 Trace 与碳感知电网数据集**，可直接用于校准 `JS-ComputeSim-313` 仿真器的到达分布、任务时长、异构资源需求与绿电碳排波动，彻底杜绝“拍脑袋编造仿真数据”的质疑！

### 1.1 真实大规模 GPU / 智算集群工作负载 Trace

| 数据集 | 发布方与规模 | 核心特征与字段 | 获取入口 | 对本赛题的复用价值 |
| :--- | :--- | :--- | :--- | :--- |
| **Alibaba Cluster Trace GPU (`v2026` / `v2025` / `v2020`)** | 阿里巴巴 PAI / Serverless Infra：<br>• `v2026`：155,000+ GPU，6 个月<br>• `v2025`：推理 PD 分离服务<br>• `v2020`：6,500 GPU（NSDI'22） | 完整涵盖大模型训练、微调与在线推理混合负载，含提交时间、GPU 卡型/卡数需求、显存/CPU、排队与运行时长、潮汐周期与碎片特征 | GitHub: `alibaba/clusterdata` | **首选主底座**：直接提取真实 24h 推理潮汐波峰与夜间批量训练提交分布，按等比缩放注入江苏 13 地市负载生成器 |
| **SenseTime Helios (`HeliosData`)** | 商汤科技 & S-Lab（SC'21）：多租户异构 GPU 集群 | 覆盖多代异构 GPU 混部集群的深度学习作业特征、作业优先级、抢占与失败重试行为 | GitHub: `S-Lab-System-Group/HeliosData` | **极高**：用于校准异构芯片混部亲和度、排队拥塞与故障重调度参数 |
| **Microsoft Philly Traces** | 微软研究院：经典多租户 DL 训练集群 Trace | 分布式训练作业拓扑、GPU 申请规模分布与作业完成时间（JCT）基准 | GitHub: `msr-fiddle/philly-traces` | **补充基准**：常用于与 Themis/Gandiva/HiveD 类调度器对标 |
| **DIR-LAB/Gen-Parallel-Workloads** | 跨平台并行负载聚合库 | 统一封装 Alibaba、Helios、Philly 与 HPC 超算日志 | GitHub: `DIR-LAB/Gen-Parallel-Workloads` | **高**：一键对齐通算/智算/超算三类异构任务混合比例 |

### 1.2 电网碳排放强度与绿电时序数据

| 数据集 / 工具 | 内容与粒度 | 获取入口 | 江苏本土校准方式 |
| :--- | :--- | :--- | :--- |
| **Electricity Maps（开源数据与解析器）** | 小时级电网碳排放强度（`gCO2eq/kWh`）与风电/光伏发电占比曲线 | GitHub: `electricitymaps/electricitymaps-contrib` | 提取典型沿海风电（夜间大发）+ 光伏（午间尖峰）波动形态，按华东电网排放因子及江苏盐城/南通/连云港风光装机特征标定 |
| **Carbon-Aware Cloud Resource Management Dataset** | 面向多区域云数据中心的碳感知调度标准评测时序包 | Figshare 检索 `Carbon-Aware Cloud Resource Management Dataset` | 直接参考其多区域碳强/电价/PUE 联合时间序列格式 |
| **Green Software Foundation Carbon Aware SDK** | 行业标准碳感知调度 API 规范与历史碳强查询接口 | GitHub: `Green-Software-Foundation/carbon-aware-sdk` | 对齐企业级绿色算力碳足迹计量口径（支撑 `YOU-271` 账本模块） |

---

## 二、可直接复用的开源仿真器、算法库与云原生调度栈

### 2.1 算力与绿色能源协同仿真器

| 开源项目 | 语言 / 生态 | 核心特性 | 72h 冲刺选型建议 |
| :--- | :--- | :--- | :--- |
| **`dos-group/vessim`** | Python | 专为碳感知计算设计的算力-微电网联合仿真平台，原生挂载真实历史风光绿电数据 | **强烈推荐参考**：纯 Python，架构轻巧，绿电/储能/市电切换建模极贴合本赛题 |
| **`SustainCluster`** | Python (Gymnasium) | 面向多目标/约束强化学习的数据中心碳感知调度 Gymnasium 基准，直接对接 Electricity Maps | **强烈推荐参考**：其 Gymnasium CMDP 接口与观测/动作空间设计可直接迁移至 `JS-ComputeSim-313` |
| **`gpu2grid/openg2g`** | Python | 聚焦 AI 智算中心与电网交互、功率流与碳感知时延管理的模块化仿真库 | 用于完善 GPU 集群非线性动态功耗 $P(u, T)$ 与电网交互建模 |
| **`atlarge-research/opendc`**（含 `OpenDC-STEAM` / `opendc-m3sa`） | Kotlin / Python Notebooks | 学术界最知名的模块化数据中心离散事件仿真器，支持碳排放追踪、时间移峰与跨区迁移 | 适合在计划书/白皮书中作为国际对标仿真方法论引用 |
| **`CloudLab-NEU/CloudSimPer`** & **`simgrid/simgrid`** | Java / C++ | 经典混合风光绿电云仿真器与分布式碳足迹插件 | 重型平台（Java/C++），72h 冲刺不建议直接二开，推荐自研轻量 Python Gymnasium 环境并吸收其功耗模型 |

### 2.2 运筹优化、Safe-RL 与时序预测算法库
- **宏观小时级 MILP 求解器**：`HiGHS`（通过 `scipy.optimize.milp` 或 `highspy`）或 `Google OR-Tools`——纯 CPU 毫秒至秒级求解 16 节点 × 24 时段多目标配额问题，可直接导出对偶变量（Shadow Price）给 LLM 做决策归因。
- **微观实时约束强化学习（Safe-RL）**：**`PKU-Alignment/omnisafe`**（北大开源 Safe-RL 权威框架，开箱内置 `PPOLag` 拉格朗日约束 PPO）+ **`Safety-Gymnasium`** API，直接将 `SLA 违约率 ≤ 0.5%` 建模为安全代价约束，并导出轻量 PyTorch (`.pt`) + ONNX (`.onnx`) 权重包。
- **24h 负荷与绿电时序预测**：`LightGBM` / 轻量化 `PatchTST`（PyTorch），输入历史 7 天滑动窗口预测未来 24h 节点到达率与沿海风光出力。

### 2.3 生产级云原生异构调度生态（用于《部署实施方案》高分加分！）
在向江苏省一体化算力调度监测平台（1+13）对接的部署方案中，明确提出**非侵入式策略边车（Scheduling Advisor Sidecar）**对接主流开源云原生异构调度底座：
- **CNCF HAMi**（`Project-HAMi/HAMi`）：已原生支持 **NVIDIA GPU、华为昇腾 Ascend、寒武纪 MLU、海光 DCU、摩尔线程、天数智芯**等主流国产/进口异构算力虚拟化与切分；
- **Volcano**：大规模 AI 分布式训练 Gang Scheduling 与队列编排；
- **Koordinator**：NUMA/RDMA/GPU 拓扑感知与在线离线混部（Co-location）；
- **Kueue**：多租户跨集群配额治理。

---

## 三、国内外核心竞品对比分析

| 竞品 / 平台 | 类别定位 | 核心技术优势 | 针对江苏 `1+13` 绿色异构算网的局限 |
| :--- | :--- | :--- | :--- |
| **Run:ai（已被 NVIDIA 收购）** | 国际 AI 集群虚拟化与编排标杆 | 极致 GPU 细粒度切分（Fractional GPU）、动态配额与高集群利用率 | 深度绑定 NVIDIA 企业生态，**缺乏多品牌国产芯片统一当量抽象与省级绿电/碳排协同优化** |
| **Cast AI** | 多云 Kubernetes 自动化成本优化 | 实时工作负载分析 + Spot 竞价实例自动切换，显著降本 | 聚焦公有云 K8s 成本套利，不支持国产智算卡、城域 1ms 时延圈及 PUE/绿电时空移峰 |
| **阿里云灵骏（PAI）** | 国内超大规模智算云底座 | 磐久服务器 + 800G RDMA + 万卡超节点 + 分钟级故障自愈 | 面向自有公有云同构/准同构集群，**非厂商中立的省级跨运营商调度层** |
| **华为云昇腾（CANN + 灵衢超节点）** | 全国产全栈 AI 算力生态 | CANN 根技术 + Volcano 调度 + 液冷低 PUE + 高可靠长稳训练 | 以昇腾硬件体系为核心，难以公平统管全省 313 座数据中心内的多厂商混杂算力 |
| **无问芯穹（Infinigence）** | 国内多元异构 AI 基础设施新锐 | 软硬协同跨多品牌国产/进口芯片纳管与大模型高效推理（MaaS） | 聚焦芯片级算子编译与推理加速，**在省级电网分时电价、苏北风光绿电消纳、长三角跨主体碳足迹结算上并非核心重心** |
| **国家超算互联网** | 国家级算力网枢纽门户 | 汇聚全国超算/智算资源、支撑“东数西算”宏观供需对接 | 偏宏观交易与门户接入，底层仍亟需智能化的**细粒度多目标绿色调度算法引擎**作为大脑 |
| **我方方案（SuCompute）** | **省级一体化异构算网绿色智能调度引擎与数字孪生沙盘** | **厂商中立非侵入边车 + 异构当量与非线性 PUE/绿电联合建模 + MILP+Safe-RL 秒级自愈 + LLM 归因与长三角计量账本** | 精准嵌入中国算力平台（江苏）1+13 与沪浙皖互联架构，补齐“调度层绿色量化 + 异构最优决策”核心拼图 |
