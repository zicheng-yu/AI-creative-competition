# FluEvidenceBench-v1 数据集说明

软件原型用的离线证据快照。每条记录都是已发表题名、NCBI 定义行、RCSB 题名、IEDB `epitope_summary` 或 UniProt FASTA 首行。
本数据集不提供湿实验步骤、构建体序列、逃逸或适应度预测，也不把文献题名里的结果用语当作临床或保护效果结论。

- 数据版本：`fluevidence-v1`，以及增补更正通知与两条茎部结构登录的 `fluevidence-v1.1`。
- 审核范围：`methods-and-records-governance`。租户：`demo`。
- 标识核验日期：2026-11-28。来源是当时的 NCBI esummary/efetch、RCSB Data API、IEDB query API 和 UniProt FASTA 首行。
- 证据等级映射：IEDB 与 RCSB 实验登录记为 `T1_WET_LAB_ASSAY`（公开实验记录，不是复现的实验步骤）；NCBI nuccore 元数据记为 `T2_SURVEILLANCE`；PubMed 题名记为 `T3_PEER_REVIEWED_LIT`；UniProt 已审校蛋白条目也记为 T3，表示它是蛋白质数据库中的审校记录，不是期刊论文，也不是新的计算结果。
- `T4_COMPUTATIONAL` 计数为 0。深度突变扫描、逃逸分数和适应度预测没有入库。

## 未入库

- GISAID sequences and counts
- Nextstrain clade-frequency tables
- Bloom Lab deep-mutational-scan escape or fitness scores
- nucleotide sequences and designed amino-acid constructs
- wet-lab protocols and experimental recipes
- new immunogenicity, protection, or clinical scores
- timed human SOP (left as 未测)

## 记录

| evidence_id | primary_ref | source_type | dataset_version | ingested_at | evidence_tier | published_on | review_status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EV-REF-GARTEN | PMID:19465683 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 2009-07-10 | accepted |
| EV-REF-SMITH | PMID:15218094 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 2004-07-16 | accepted |
| EV-REF-PETROVA | PMID:29081496 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 未提供精确日 | accepted |
| EV-REF-CALHA | PMID:23110350 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 2012-10-30 | accepted |
| EV-CONS-GILES | PMID:21320540 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 2011-04-05 | accepted |
| EV-CONS-CARTER | PMID:26912624 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 未提供精确日 | flagged |
| EV-CONS-CARTER-CORR | PMID:38819164 | PUBMED_LITERATURE | fluevidence-v1.1 | 2026-11-28T09:00:00+08:00 | T3_PEER_REVIEWED_LIT | 2024-07-23 | accepted |
| EV-GLY-WANG | PMID:19822741 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 2009-10-27 | accepted |
| EV-GLY-TATE | PMID:24638204 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 2014-03-14 | accepted |
| EV-GLY-ADD | PMID:23365085 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 2013-03-01 | accepted |
| EV-STEM-IMP | PMID:26303961 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 2015-09-18 | accepted |
| EV-STEM-YASSINE | PMID:26301691 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 未提供精确日 | accepted |
| EV-STEM-EKIERT | PMID:19251591 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 2009-04-10 | accepted |
| EV-STEM-HEADLESS | PMID:26947245 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 2016-03-07 | accepted |
| EV-STEM-STALK | PMID:25210189 | PUBMED_LITERATURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 未提供精确日 | accepted |
| EV-ACC-CA07 | Accession:CY121680.1 | NCBI_NUCCORE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T2_SURVEILLANCE | 未提供精确日 | accepted |
| EV-ACC-HK68 | Accession:AF348176.1 | NCBI_NUCCORE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T2_SURVEILLANCE | 未提供精确日 | accepted |
| EV-PDB-3GBN | PDB:3GBN | PDB_STRUCTURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T1_WET_LAB_ASSAY | 2009-03-10 | accepted |
| EV-PDB-3GBM | PDB:3GBM | PDB_STRUCTURE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T1_WET_LAB_ASSAY | 2009-03-10 | accepted |
| EV-PDB-5C0S | PDB:5C0S | PDB_STRUCTURE | fluevidence-v1.1 | 2026-11-28T09:00:00+08:00 | T1_WET_LAB_ASSAY | 2015-09-02 | accepted |
| EV-PDB-5C0R | PDB:5C0R | PDB_STRUCTURE | fluevidence-v1.1 | 2026-11-28T09:00:00+08:00 | T1_WET_LAB_ASSAY | 2015-09-02 | accepted |
| EV-IEDB-570 | IEDB:570 | IEDB_EPITOPE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T1_WET_LAB_ASSAY | 未提供精确日 | accepted |
| EV-IEDB-226309 | IEDB:226309 | IEDB_EPITOPE | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T1_WET_LAB_ASSAY | 未提供精确日 | accepted |
| EV-UP-P03452 | UniProt:P03452 | UNIPROT_RECORD | fluevidence-v1 | 2026-11-28T06:00:00+08:00 | T3_PEER_REVIEWED_LIT | 未提供精确日 | accepted |

## 任务

Task-1 是证据问答。每题给出必须召回的 evidence_id，问题里使用公开题名或公开 ID，答案只能引用上表原文。
Task-2 比较四份已经发表的候选方案文献档案：参考株、共识序列文献、头部糖基化文献、保守茎部文献。
比较维度是来源覆盖、版本一致性、引用交叉（档案注释里点名另一条公开 ID）、T1–T4 分布，以及证据空白。证据空白包括缺 T1/T2 记录、版本不一致和审阅未关闭。它不是实验清单，也不是新的生物学性能分数。

人工检索 SOP 没有计时，记为未测。
