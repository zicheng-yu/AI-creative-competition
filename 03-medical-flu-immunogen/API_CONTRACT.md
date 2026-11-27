# 赛道 03 离线证据审阅接口

本阶段交付软件原型与离线评测，不以实验有效性或临床效果作为承诺。本分支交付版本化证据导入、引文审阅及专家签批。配套演示运行于两条公开研究方法文献。

## 离线运行

在 `03-medical-flu-immunogen/` 下使用 Python 3.11+。测试环境已安装 Python 3.13、`pydantic==2.13.4`、`networkx==3.4.2`、`pyarrow==24.0.0`、`fastapi==0.115.12`、`httpx==0.28.1` 和 `pytest==9.0.3`。直接启动 HTTP 服务还需 uvicorn。隔离环境可从本地 wheel 目录通过 `pip install --no-index --find-links <wheel-dir>` 安装依赖。

```bash
python -m benchmarks.export_demo
python -m pytest -q
python -m uvicorn server:demo_app --factory --host 127.0.0.1 --port 8765
```

## YOU-274 接入

`engine.capsules.Snapshot(path, lock)` 接受单个 JSONL、单个 Parquet 文件或包含证据记录的目录。目录递归读取这两类文件。包含评测题、序列元数据或其他表的 release 应传入证据记录专用文件或目录。

证据行使用 `solution.md` §3.1 字段和补充完整性字段，均为非空字符串。

| 字段 | 约定 |
| --- | --- |
| `evidence_id`、`dataset_version` | 共同标识记录。同一 ID 可出现在不同版本。 |
| `source_type`、`primary_ref` | 保留来源类型与已核验的原始引用，例如 `PMID:26978244`。复合引用按 release 原值保留。 |
| `ingested_at` | 带时区的 ISO 8601 时间。 |
| `evidence_tier` | `T1_WET_LAB_ASSAY`、`T2_SURVEILLANCE`、`T3_PEER_REVIEWED_LIT`、`T4_COMPUTATIONAL`。 |
| `subtype_context`、`claim_summary`、`raw_snippet` | 分别保存上下文、检索摘要和原始引用片段。 |
| `sha256` | `raw_snippet` 原字符串 UTF-8 字节的 SHA256 小写十六进制值。 |

数据维护者核验来源及分级后，单独提供可信发行锁。锁为 JSON 对象，`records` 数组每项包含 `evidence_id`、`dataset_version`、`record_sha256`。后者是十个标准字段经 `json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")` 后的 SHA256。额外列由适配器忽略。发行锁应来自受信任的本地配置位置。运行时核验来源记录与发行锁是否一致，来源数据库中的 ID 真实性由发布者在发布前核验。载入时检测重复、缺失和被修改的行。

## 本地 API

| 路由 | 请求和结果 |
| --- | --- |
| `GET /api/v1/health` | 返回 `ok`、`snapshot_id`、`record_count`。 |
| `POST /api/v1/qa` | JSON 请求 `query`、可选 `limit`。从快照检索引文并建立审阅草稿。 |
| `POST /api/v1/compare` | JSON 请求 `groups`，2–6 组，每组含唯一 `label` 和 `citations` 数组。每条引用传入 `evidence_id` 与 `dataset_version`。返回分组引文及各证据等级计数。 |
| `POST /api/v1/review/signoff` | JSON 请求 `report_id`、`expected_version`、`reviewer`、`actions`、`signoff`。单条操作包括 `statement_id`、`action` 及可选 `note`。 |

返回报告包含 `snapshot_id`、`statements`、`provenance`、`agent_trace`、`scientific_boundary` 及可能的 `review_notice`。前端可用每条 `statement` 的 `evidence_id`、`dataset_version`、`primary_ref`、`evidence_tier`、`text` 渲染角标。结构和完整样例见 [静态演示](frontend_demo_data/methods_review.json)。

草稿从 `AI_DRAFT_PENDING_REVIEW`、版本 1 开始。每次提交复核操作或签批，报告版本递增。操作为 `accept`、`flag_doubt`、`reject`、`comment`。签批要求每条引文都有处置结果。签批成功后报告进入 `EXPERT_SIGNED` 并返回 Markdown、JSON 和证据附表 CSV。JSON 提供全部原始引文及完整复核轨迹。Markdown、CSV 只收录已采纳引文。未知报告返回 404，版本冲突或签批条件未满足返回 409，请求或证据引用校验失败返回 422。

`server.py` 面向单机单快照演示。复核者由调用方填写，报告与轨迹按服务进程保存在内存中，退出前应将导出文件保存至授权存储。
