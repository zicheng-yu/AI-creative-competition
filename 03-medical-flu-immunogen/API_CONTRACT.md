# 流盾智研离线资料审阅接口

对应 AI-HEALTH-Q40 流感病毒免疫原辅助设计智能体研发和应用。YOU-275 与 YOU-276 的当前范围是经审核的非操作性科研方法学文献和资料治理档案，涵盖检索、版本溯源、资料统计和专家复核。本阶段交付软件原型与离线评测，不以实验有效性或临床效果作为承诺。

## 运行与联调

在 `03-medical-flu-immunogen/` 使用 Python 3.11 或更新版本。实测依赖及完整复现命令见 [MODEL.md](MODEL.md)。

```bash
python -m uvicorn server:demo_app --factory --host 127.0.0.1 --port 8765
```

单个服务实例绑定一个由部署方配置的可信快照及租户。请求体无法切换租户或设置文件路径。不同授权租户应运行在独立服务配置中。此演示将报告和操作历史存于进程内存，复核者字符串由本地调用方填写，部署时需要独立的访问身份与持久化机制。

## YOU-274 兼容格式

`Snapshot(path, lock, tenant_id="demo")` 读取 JSONL、Parquet 或仅包含这些证据表的目录。输入保持 `solution.md` §3.1 的十个字段，均为非空字符串。规范记录哈希覆盖下表十个字段，表的附加列通常被忽略。若含 `tenant_id`，该列必须匹配当前租户。

| 字段 | 约定 |
| --- | --- |
| `evidence_id`、`dataset_version` | 联合标识和查验键。同一 ID 可出现在不同版本。 |
| `source_type`、`primary_ref` | 当前适配批准的 `PUBMED_LITERATURE`／`PMID:<已核验编号>` 和 `SYNTHETIC_METHODS`／`SYNTHETIC:<条目名>`。 |
| `ingested_at` | 带时区的 ISO 8601 接入时间。 |
| `evidence_tier` | `T1_WET_LAB_ASSAY`、`T2_SURVEILLANCE`、`T3_PEER_REVIEWED_LIT` 或 `T4_COMPUTATIONAL`。计算记录保持 T4。 |
| `subtype_context`、`claim_summary`、`raw_snippet` | 原字段保持兼容。当前样本的上下文与检索摘要均限定为资料治理，`raw_snippet` 是可引用原文。 |
| `sha256` | `raw_snippet` 原字符串 UTF-8 字节的 SHA256 小写十六进制值。 |

可信发行锁置于只允许资料审核方写入的独立配置位置。锁中 `tenant_id` 是租户标识，`scope` 固定 `methods-and-records-governance`。 `releases` 每项含 `dataset_version`、`released_at`，可含已声明且时间更早的 `previous_version`。 `records` 每项含证据键、`record_sha256`、`primary_ref`、`title`、`topics`、`nature`、`approval`、`review_status`，可含 `source_url`、`published_on`、`archive_note`。真实 PubMed 条目必须为 `public_methods` 并带对应的 NLM 链接，演示合成条目为 `synthetic`。准入要求 `approval=approved`；`review_status` 是资料已有的记录状态，可为 `pending`、`accepted`、`flagged`、`rejected`。

`record_sha256` 是标准字段对象以 `json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")` 序列化后的 SHA256。发行锁由审核方维护，ID 真实性与资料范围由审核方在入锁前确认。运行时校验租户、锁范围、原始引用与链接对应关系、版本链、记录和片段哈希，拒绝缺失或重复条目。`snapshot_id` 指纹包含版本、租户、批准元数据和各记录哈希。参考 [发行锁样例](tests/fixtures/release.lock.json)。YOU-274 新产物应先筛选为独立的已审核资料包再联调。

## HTTP 请求

| 路由 | 主要入参和结果 |
| --- | --- |
| `GET /api/v1/health` | `ok`、`snapshot_id`、`tenant_id`、`scope`、`record_count`、`releases`。 |
| `POST /api/v1/qa` | `query` 及可选 `limit`（1–15，默认 5）、`period`（month／quarter）、`hops`（1–3）。返回检索轨迹、已审计原文和待复核的方法学对照。 |
| `POST /api/v1/compare` | 输入 `dossiers`、`dossier_csv` 或兼容的 `groups` 三者之一。可选 `period` 与 `hops` 同上。返回新报告及五维矩阵。 |
| `POST /api/v1/review/signoff` | `report_id`、`expected_version`、`reviewer`、`actions` 和 `signoff`。每条操作含 `statement_id`、`action` 和可选 `note`。 |

`dossiers` 有 2–6 份，必填唯一 `dossier_id`、`label`、非空 `citations`，每条引文用 `evidence_id` 与 `dataset_version`。可填 `version`、`source_ref`、`archive_sha256`、`annotation`、`review_status`、`document_text`。资料治理字段缺失时进入报告。若提供来源，必须存在于档案引用中。若提供文档文本，它必须与该来源的已审核片段完全一致，`archive_sha256` 按文档原字节计算。结构化档案的 `archive_sha256` 计算规范见 `engine.dossiers.archive_digest`，其输入是经 `Dossier` 校验的字段对象，包含可选字段的 null，排除 `archive_sha256` 与 `document_text`。CSV 表头为相同字段，`citations` 单元格内嵌 JSON 数组。人工注释标为 `operator_annotation`，保留在档案报告中。兼容的 `groups` 只传 `label` 和 `citations`，因此其资料属性会被标记为待补齐。API 不接受新的未审核文档上传。

引用角标使用 `statements` 中的 `evidence_id`、`dataset_version`、`primary_ref`、`source_url`、`evidence_tier`、`nature` 和 `text`。 `provenance` 返回带类型的节点、带关系名的边和引用路径。 `metadata_timeline.curve` 包含分期首次出版、资料接入、分来源及审阅状态计数和快照发布事件。出版量按来源文档去重，接入量按证据版本计数。 `metadata_timeline.heatmap` 按接入月 × 来源类型，报告出版日期和档案注释的覆盖与缺失，单元格附原始证据键。 `dossier_matrix` 提供来源覆盖、字段完整度、版本一致性、可追溯性、审阅状态与未决事项五维。 `agent_trace` 按阶段顺序返回，问答跳过档案对照，档案比较使用声明引用直接解析。

草稿为 `AI_DRAFT_PENDING_REVIEW`、版本 1。专家可 `accept`、`flag_doubt`、`reject` 或 `comment`。签批前每条引文需要实质性处置。签后状态为 `EXPERT_SIGNED`，并返回 Markdown、JSON、证据 CSV。完整 JSON 保留处置与时间戳，Markdown 与 CSV 引文只包含已采纳项。未知报告返回 404，重复签批或旧版本操作返回 409，输入、来源或哈希错误返回 422。

[静态演示数据](frontend_demo_data/methods_review.json) 包含两类任务、发布清单、时间线与热图、图谱子图和签批样例。[全量图谱 JSON](frontend_demo_data/provenance_graph.json) 可由 `ProvenanceGraph.load(snapshot, path)` 核对并载入。
