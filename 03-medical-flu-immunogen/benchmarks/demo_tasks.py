"""Two offline software tasks against verified methods titles and labeled synthetic archives."""
import csv
import io
import json
from statistics import mean, median
from time import perf_counter_ns

from fastapi.testclient import TestClient

from benchmarks.metrics import ndcg
from benchmarks.offline import offline_runtime
from engine.capsules import Snapshot
from engine.dossiers import COLUMNS, Dossier, archive_digest
from engine.llm_adapter import BaseLLMClient, Citation
from engine.models import TextModels
from engine.timeline import anchor
from server import FIXTURES, create_app


QUESTIONS = (
    ("Find PMID:26978244", {"EV-METHODS-FAIR"}),
    ("Where are the PRISMA reporting guidelines for systematic review protocols?", {"EV-METHODS-PRISMA-P"}),
    ("Which records provide the PRISMA 2020 reporting statement and explanation?",
     {"EV-METHODS-PRISMA", "EV-METHODS-PRISMA-ELAB"}),
    ("Find the simple rules for reproducible computational research.", {"EV-METHODS-REPRO"}),
)


def approved_snapshot() -> Snapshot:
    return Snapshot(FIXTURES / "methods.jsonl", FIXTURES / "release.lock.json")


def _post(client, route: str, body: dict) -> tuple[dict, float]:
    start = perf_counter_ns()
    response = client.post(f"/api/v1/{route}", json=body)
    elapsed = (perf_counter_ns() - start) / 1e6
    response.raise_for_status()
    return response.json(), elapsed


def demo_dossiers(snapshot: Snapshot) -> list[dict]:
    selected = ("FAIR", "PRISMA", "PRISMA-ELAB", "SYNTH-REGISTER")
    key_by_name = {key[0]: key for key in snapshot.records}
    dossiers = []
    for i, name in enumerate(selected):
        key = key_by_name[f"EV-METHODS-{name}"]
        record = snapshot.records[key]
        body = {"dossier_id": f"synthetic-dossier-{i + 1}", "label": f"演示档案 {name}",
                "citations": [anchor(key)]}
        if i != 1:
            body.update(version="methods-fixture-v1" if i == 2 else record.dataset_version,
                        source_ref=record.primary_ref, annotation="合成档案元数据，用于演示。",
                        review_status=snapshot.metadata[key].review_status)
            if i == 0:
                body["document_text"] = record.raw_snippet
            body["archive_sha256"] = archive_digest(Dossier.model_validate(body))
        dossiers.append(body)
    return dossiers


def csv_text(dossiers: list[dict]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
    writer.writeheader()
    for dossier in dossiers:
        writer.writerow({**dossier, "citations": json.dumps(dossier["citations"], ensure_ascii=False)})
    return stream.getvalue()


def run() -> tuple[dict, dict]:
    with offline_runtime():
        snapshot = approved_snapshot()
        models = TextModels()
        with TestClient(create_app(snapshot, models=models)) as client:
            manifest = client.get("/api/v1/health").json()
            qa_runs = [{"query": query, "expected": sorted(expected), "report": result, "elapsed_ms": elapsed}
                       for query, expected in QUESTIONS
                       for result, elapsed in [_post(client, "qa", {"query": query, "limit": 3, "hops": 3})]]
            dossiers = demo_dossiers(snapshot)
            source_csv = csv_text(dossiers)
            compare, compare_ms = _post(client, "compare", {
                "dossier_csv": source_csv, "period": "quarter", "hops": 3,
            })
            actions = [{"statement_id": statement["statement_id"], "action": disposition,
                        "note": "合成签批演示操作。"}
                       for statement, disposition in zip(compare["statements"],
                                                         ("accept", "flag_doubt", "reject", "accept"))]
            review, review_ms = _post(client, "review/signoff", {
                "report_id": compare["report_id"], "expected_version": 1,
                "reviewer": "demo-reviewer", "actions": actions, "signoff": True,
            })

        class BadDraft(BaseLLMClient):
            def assemble(self, query, records):
                original = records[0]
                return [Citation("EV-SYNTHETIC-UNREGISTERED", original.dataset_version, original.raw_snippet),
                        Citation(original.evidence_id, "wrong-version", original.raw_snippet),
                        Citation(*original.key, "A synthetic assertion that is absent from the cited title.")]

        with TestClient(create_app(snapshot, client=BadDraft(), models=models)) as guarded:
            rejected, _ = _post(guarded, "qa", {"query": QUESTIONS[0][0], "limit": 1})

        all_statements = [statement for report in [*(row["report"] for row in qa_runs), compare]
                          for statement in report["statements"]]
        valid_citations = sum(
            (record := snapshot.records.get((row["evidence_id"], row["dataset_version"]))) is not None
            and record.raw_snippet == row["text"] and record.primary_ref == row["primary_ref"]
            for row in all_statements
        )
        recalls, rankings = [], []
        for row in qa_runs:
            relevant = set(row["expected"])
            hits = [item["evidence_id"] for item in row["report"]["retrieval"]]
            recalls.append(len(relevant & set(hits)) / len(relevant))
            rankings.append(ndcg([int(hit in relevant) for hit in hits], [1] * len(relevant), 3))
        matrix = compare["dossier_matrix"]
        assert len(matrix) == 4 and matrix[0]["evidence_traceability"]["hash_verified"]
        assert len(matrix[1]["field_completeness"]["missing"]) == 5
        assert matrix[2]["version_consistency"]["consistent"] is False
        assert "source_review_open" in matrix[3]["review_status"]["open_items"]
        assert review["report"]["state"] == "EXPERT_SIGNED" and review["report"]["version"] == 2
        assert len(review["exports"]["evidence_csv"].splitlines()) == 3
        assert valid_citations == len(all_statements) > 0
        assert not rejected["statements"] and sum(rejected["agent_trace"][-1]["rejected"].values()) == 3
        metrics = {
            "scope": "methods-only software tasks",
            "task_1": {"queries": len(qa_runs), "recall_at_3": mean(recalls), "ndcg_at_3": mean(rankings),
                       "median_ms": median(row["elapsed_ms"] for row in qa_runs)},
            "task_2": {"dossiers": len(matrix), "dossiers_checked": 4, "signed_accepted_citations": 2,
                       "compare_ms": compare_ms, "signoff_ms": review_ms},
            "citations": {"valid": valid_citations, "total": len(all_statements),
                          "invalid_drafts_blocked": 3, "invalid_drafts_total": 3},
            "manual_sop_baseline": "未测",
        }
        bundle = {"scope": "公开研究方法文献与明确标注的合成档案", "snapshot": manifest,
                  "timeline": compare["metadata_timeline"], "heatmap": compare["metadata_timeline"]["heatmap"],
                  "qa": qa_runs, "compare": {"dossiers": dossiers, "dossier_csv": source_csv, "report": compare},
                  "signoff": review, "audit_example": rejected, "software_metrics": metrics}
        return bundle, metrics
