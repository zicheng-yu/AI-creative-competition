# 赛道 03 深度调研：公开数据集、开源方案与竞品分析（`AI-HEALTH-Q40`）

> **对应赛题**：`AI-HEALTH-Q40` 流感病毒免疫原辅助设计智能体研发和应用（宿迁市楚润数据集团有限公司命题 / 医疗健康赛道）  
> **关联 Linear Issue**：`YOU-260`（调研） · `YOU-274`（`FluEvidenceBench-v1` 数据集） · `YOU-275`~`YOU-278`（KG/算法/前端/评测）  
> **合规红线**：本阶段交付**软件原型、标准化数据集、轻量化权重包与离线评测（对比固定人工 SOP）**，**绝不承诺湿实验有效性或临床保护效果**

---

## 一、权威公开生物医药数据源盘点（全部可脚本化拉取与版本锁定）

赛题要求“跨来源文献、公开数据库和计算分析结果”接入且强制“来源与数据版本可追溯”。经核实，以下 **7 类权威公开资源均可合法、免费、脚本化抓取并固化本地版本快照**（明确避开 GISAID 禁止二次分发的协议风险）：

| 数据源 | 覆盖内容与证据等级 | 程序化获取方式（支持版本快照锁定） | 对本赛题的核心作用 |
| :--- | :--- | :--- | :--- |
| **NCBI Virus / Datasets CLI**（原 NCBI Influenza Virus Resource 升级版） | 全球公开甲型 H3N2/H1N1pdm09、乙型 B/Victoria 的 HA/NA 基因组与蛋白 FASTA、采样日期与地理元数据（`T2` 流行监测） | `datasets download virus genome taxon "Alphainfluenzavirus influenzae" --include genome,cds,protein --filename influenza_genomes.zip` 或 Entrez EDirect API | 提供合法可再分发的 GenBank Accession 序列快照与流行时序基座 |
| **Nextstrain Seasonal Flu & Nextclade Data** | 持续更新的 H3N2 / H1N1pdm / B-Vic 进化树、分支定义（如 `3C.2a1b.2a.2a.3a.1` / `J.2`）与元数据 TSV（`T2`） | `nextstrain remote download datasets remote://nextstrain/seasonal-flu/h3n2/ha/12y` 及 `nextstrain/nextclade_data` | 直接提供权威进化分支划分、时序占比演变与突变注释参考 |
| **IEDB（Immune Epitope Database）** | 经湿实验验证的流感病毒 B 细胞 / T 细胞表位、抗体中和 / HI 测定与对应 PMID（**`T1` 湿实验核心证据**） | IEDB Database Export 全量表 + `IEDB/IQ-API` REST 查询 + `pip install iedb` | 将 HA 抗原区 A–E 与保守茎部（Stem）精准锚定至带 `IEDB ID + PMID` 的真实实验记录 |
| **Bloom Lab Influenza HA Deep Mutational Scanning（DMS）** | Fred Hutch Bloom 实验室发布的深度突变扫描实验数据（覆盖 H3N2 如 *A/Massachusetts/18/2022*、*A/HongKong/45/2019* 及 H5N1）（**`T1` 高通量实验证据**） | `dms-vep.org` 公开表 + GitHub: `jbloomlab` / `dms-vep` | **极大提升学术说服力**：为每个 HA 氨基酸位点提供真实实验测得的抗体/血清逃逸分数与细胞进入适应度 |
| **BV-BRC（原 IRD / FluDB 继承者）& WHO GISRS** | NIH 资助的综合流感基因组与重配分析库 + WHO 全球流感监测与历年南北半球疫苗推荐株决议（`T2/T3`） | `bv-brc.org` API/导出 + WHO 公开疫苗株推荐报告 | 提供权威疫苗参考株对照（用于 Task-2 候选方案对比）与流行病学背景 |
| **RCSB PDB & UniProt** | 流感 HA/NA 蛋白三维晶体/冷冻电镜结构（含成熟 HA1/HA2 经典 H3 编号映射与受体结合域注释）（`T1`） | RCSB Search/Data API & UniProt REST API | 解决通用大模型最致命的**“H3 成熟编号 vs 全长信号肽编号偏移”**对齐难题 |
| **PubMed / Europe PMC** | 数万篇流感免疫原、广谱茎部疫苗、去糖基化、鸡胚适应性突变（Egg-adapted mutations）同行评议文献（`T3`） | NCBI E-utilities / Europe PMC REST API（按 PMID 精确拉取摘要与全文开放段） | 构建可回链 `PMID + 原文段落 + 抓取快照版本` 的无幻觉文献证据库 |

### 评测基准方法论参考（用于设计 `FluEvidenceBench-v1`）
- **LitQA2**（FutureHouse 科学文献深度检索与推理基准）与 **BioASQ**（国际生物医学语义问答与信息检索权威评测）：借鉴其“精确证据片段召回（Recall@K）+ 事实忠实度 + 不可回答/证据冲突拒答机制”指标设计，形成贴合赛题的 `FluEvidenceBench-v1`（含 Task-1 跨库循证问答 + Task-2 四候选方案横向对比 + 固定人工 SOP 基线计时）。

---

## 二、可直接复用的开源方案与生物医学智能体技术栈

| 模块 | 推荐开源项目 / 模型 | 核心优势与本方案集成点 |
| :--- | :--- | :--- |
| **生物医学专用检索与重排权重底座** | **`ncbi/MedCPT`**（NIH/NLM 官方开源：`MedCPT-Query-Encoder`、`MedCPT-Article-Encoder`、`MedCPT-Cross-Encoder`） | 基于数百万真实 PubMed 检索点击日志对比预训练，生物医学零样本检索 SOTA；**直接作为我方轻量化重排/NLI 权重包（预期成果“算法模型权重包”）的基座模型**，辅以流感位点/冲突判别 LoRA 适配 |
| **高可信科学文献 RAG 智能体范式** | **`Future-House/paper-qa`（PaperQA2）** | 业内公认科学文献引文溯源标杆：采用 RCS（排序与上下文摘要）+ 句级显式引用绑定 + 撤稿/文献冲突检查，直接借鉴其证据胶囊与逐句引用核验流程 |
| **生物医学知识图谱对话后端** | **`biocypher/biochatter`** + `NetworkX` / Neo4j | 专注将 LLM 与结构化生物医学知识图谱（BioCypher）深度融合，提升多跳关系查询的事实确定性 |
| **多步生物科研智能体参考** | **`snap-stanford/biomni`** | Stanford SNAP 开源通用生物医学智能体，展示“检索规划 + 生物信息学工具调用（序列比对/突变扫描）+ 证据汇总”的多工具编排范式 |
| **序列分支调用与 `T4` 计算证据工具** | **`nextstrain/nextclade`** + **`OATML-Markslab/EVEscape`** + `Biopython` | Nextclade 快速完成上传 FASTA 序列比对、分支归属与位点突变提取；EVEscape 提供开源免疫逃逸预测分（**严格标注为 `T4` 计算预测证据，绝不替代 `T1` 湿实验结论**） |

---

## 三、国内外核心竞品对比分析

当前 AI + 生物医药/疫苗研发市场可分为**三大阵营**，而本赛题（`AI-HEALTH-Q40`）精准卡位在两大阵营之间的**“可审计循证决策中台”空白地带**：

| 竞品阵营与代表 | 核心产品能力 | 针对 `AI-HEALTH-Q40` 赛题的核心短板 |
| :--- | :--- | :--- |
| **1. 通用 AI 科研文献搜索**<br>（**Elicit**、**Consensus**、**Scite.ai**、**OpenEvidence**、**Perplexity Academic**） | 快速检索论文、抽取表格、统计支持/反驳引用次数 | **不接入病毒序列库与表位实验库**（无法解析用户本地 FASTA 候选免疫原、不懂 H3/H1 氨基酸编号系统与糖基化扫描）；**无数据快照版本锁**；缺乏面向生物医药研发团队的 **HITL 专家复核签批工作流** |
| **2. 自主科研智能体先驱**<br>（**FutureHouse / Edison / Kosmos**、**OpenScholar (AI2)**、**Phylo**） | 自主阅读海量论文、编写生信分析代码、生成科学假说 | 偏海外通用云端自主探索，**国内院所/药企内部未发表候选序列无法安全本地离线接入**；缺少针对流感疫苗研发定制的四级证据分级（`T1–T4`）与五维候选免疫原对照矩阵 |
| **3. 生成式蛋白/疫苗设计与 AI 制药平台**<br>（海外：**Cradle Bio**、**Absci**、**Generate:Biomedicines**、**EvolutionaryScale ESM-3**、**Chai Discovery**；国内：**百图生科 BioMap**、**晶泰科技 XtalPi**、**深势科技 Bohrium/Hermite**） | 从头生成蛋白/抗体/抗原序列、三维结构预测、结合自动化湿实验闭环筛选 | 聚焦“**分子生成与单点黑盒打分**”或重资产湿实验代工，**而非解决“跨库异构证据整理、版本治理、冲突披露与专家复核”的研发信息服务痛点**；单一模型预测分无法替代专业免疫学综合研判 |
| **我方方案（`03-medical-flu-immunogen`）** | **面向流感免疫原研发的全链条可溯源循证科研智能体** | **权威公开库版本快照 + 本地授权 FASTA/CSV 隔离接入 + HA 编号对齐四维 KG + `T1–T4` 分级与零幻觉审计门禁 + 冲突与待湿实验清单自动生成 + HITL 专家签批留痕 + 100% 院所离线私有化部署** |
