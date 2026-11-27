import json
import socket

import numpy as np
import pytest
from fastapi.testclient import TestClient

from benchmarks.demo_tasks import approved_snapshot, csv_text, demo_dossiers
from benchmarks.text_corpus import DOMAINS, samples
from engine.capsules import Snapshot, digest
from engine.dossiers import Dossier, archive_digest, compare_dossiers, parse_csv
from engine.models import TextModels
from engine.provenance import ProvenanceGraph
from engine.service import EvidenceService
from engine.timeline import metadata_timeline
from server import FIXTURES, create_app


@pytest.fixture
def snapshot():
    return approved_snapshot()


def test_wrong_tenant_rejected_and_reports_isolated(snapshot, tmp_path):
    with pytest.raises(ValueError, match="another tenant"):
        Snapshot(FIXTURES / "methods.jsonl", FIXTURES / "release.lock.json", tenant_id="other")
    manifest = json.loads((FIXTURES / "release.lock.json").read_bytes())
    other_lock = tmp_path / "other.lock"
    manifest["tenant_id"] = "other"
    other_lock.write_text(json.dumps(manifest), encoding="utf-8")
    other = Snapshot(FIXTURES / "methods.jsonl", other_lock, tenant_id="other")
    assert snapshot.snapshot_id != other.snapshot_id
    with TestClient(create_app(snapshot)) as a, TestClient(create_app(other)) as b:
        draft = a.post("/api/v1/qa", json={"query": "PMID:26978244", "limit": 1}).json()
        resp = b.post("/api/v1/review/signoff", json={
            "report_id": draft["report_id"], "expected_version": 1,
            "reviewer": "other-tenant", "signoff": True,
        })
        assert resp.status_code == 404


@pytest.mark.parametrize("change", ["not_approved", "bad_source", "bad_lineage", "row_tenant"])
def test_unknown_release_scope_or_source_rejected(tmp_path, change):
    manifest = json.loads((FIXTURES / "release.lock.json").read_bytes())
    rows = [json.loads(line) for line in (FIXTURES / "methods.jsonl").read_bytes().splitlines()]
    if change == "not_approved":
        manifest["records"][0]["approval"] = "pending"
    elif change == "bad_source":
        manifest["records"][0]["source_url"] = manifest["records"][1]["source_url"]
    elif change == "bad_lineage":
        manifest["releases"][1]["previous_version"] = "unavailable"
    else:
        rows[0]["tenant_id"] = "other"
    lock, records = tmp_path / "lock.json", tmp_path / "rows.jsonl"
    lock.write_text(json.dumps(manifest), encoding="utf-8")
    records.write_text("\n".join(map(json.dumps, rows)), encoding="utf-8")
    with pytest.raises(ValueError):
        Snapshot(records, lock)


def test_graph_hops_paths_and_persistence(snapshot, tmp_path):
    graph = ProvenanceGraph(snapshot)
    seed = [("document", "PMID:33782057")]
    expected = ("EV-METHODS-PRISMA-ELAB", "methods-fixture-v2")
    assert expected not in graph.evidence_neighbors(seed, 1)
    assert expected not in graph.evidence_neighbors(seed, 2)
    assert graph.evidence_neighbors(seed, 3)[expected] == 3
    exported = graph.query(seed, 3)
    route = next(row["path"] for row in exported["paths"] if row["evidence_id"] == expected[0])
    assert len(route) == 4 and route[0] == seed[0]
    assert {node["kind"] for node in exported["nodes"]} == {"document", "topic", "evidence", "snapshot"}
    path = tmp_path / "graph.json"
    graph.save(path)
    assert ProvenanceGraph.load(snapshot, path).query(seed, 3) == exported
    data = json.loads(path.read_bytes())
    data["edges"].pop()
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        ProvenanceGraph.load(snapshot, path)
    with pytest.raises(ValueError, match="hops"):
        graph.query(seed, 4)


def test_timeline_traceability(snapshot):
    monthly = metadata_timeline(snapshot, "month")
    quarterly = metadata_timeline(snapshot, "quarter")
    assert sum(row["document_count"] for row in monthly["curve"]) == 5
    assert sum(row["ingested_count"] for row in quarterly["curve"]) == 6
    assert sum(len(row["snapshot_updates"]) for row in monthly["curve"]) == 2
    assert sum(sum(row["review_counts"].values()) for row in monthly["curve"]) == 6
    assert sum(row["missing"]["published_on"] for row in monthly["heatmap"]) == 1
    assert sum(row["missing"]["archive_note"] for row in monthly["heatmap"]) == 2
    for row in monthly["heatmap"]:
        assert row["records"] == len(row["evidence"])
        for key in row["evidence"]:
            assert (key["evidence_id"], key["dataset_version"]) in snapshot.records
    assert monthly["undated_documents"][0]["evidence_id"] == "EV-METHODS-SYNTH-REGISTER"


def test_dense_and_graph_routes_are_active(snapshot):
    index = EvidenceService(snapshot).index
    retrieval = index.retrieve("curation and repeatable research", 5, hops=3)
    assert retrieval.route_counts["dense"] > 0
    assert retrieval.route_counts["bm25"] > 0
    assert retrieval.route_counts["graph"] > 0
    assert {route for hit in retrieval.hits for route in hit["ranks"]} == {"dense", "bm25", "graph"}
    assert any(hit["graph_hops"] is not None and hit["graph_hops"] > 0 for hit in retrieval.hits)
    assert all(0 <= hit["text_relevance"] <= 1 for hit in retrieval.hits)
    assert index.retrieve("PMID:33781993", 1).records[0].primary_ref == "PMID:33781993"


def test_dossier_csv_and_inline_yield_same_matrix(snapshot):
    raw = demo_dossiers(snapshot)
    dossiers = [Dossier.model_validate(row) for row in raw]
    matrix = compare_dossiers(dossiers, snapshot)
    assert matrix == compare_dossiers(parse_csv(csv_text(raw)), snapshot)
    assert matrix[0]["evidence_traceability"]["hash_verified"]
    assert matrix[1]["field_completeness"]["missing"] == [
        "version", "source_ref", "archive_sha256", "annotation", "review_status",
    ]
    assert matrix[2]["version_consistency"]["consistent"] is False
    assert "source_review_open" in matrix[3]["review_status"]["open_items"]


def test_document_checksum_preserves_original_whitespace(snapshot):
    raw = demo_dossiers(snapshot)[0]
    raw["document_text"] = "  approved content with original spacing\n"
    dossier = Dossier.model_validate(raw)
    assert archive_digest(dossier) == digest(raw["document_text"].encode())


@pytest.mark.parametrize("change", ["hash", "unapproved_text", "wrong_source", "malformed_csv"])
def test_api_rejects_invalid_dossiers(snapshot, change):
    raw = demo_dossiers(snapshot)
    if change == "hash":
        raw[0]["archive_sha256"] = "0" * 64
    elif change == "unapproved_text":
        raw[0]["document_text"] = "Synthetic test text outside the release."
        raw[0]["archive_sha256"] = archive_digest(Dossier.model_validate(raw[0]))
    elif change == "wrong_source":
        raw[0]["source_ref"] = "SYNTHETIC:not-approved"
    body = {"dossier_csv": 'dossier_id,label\n"unterminated'} if change == "malformed_csv" else {"dossiers": raw}
    with TestClient(create_app(snapshot)) as client:
        assert client.post("/api/v1/compare", json=body).status_code == 422


def test_nli_returns_three_normalized_probabilities():
    model = TextModels()
    examples = [
        ("The greenhouse contains 7 notes.", "The greenhouse holds 7 notes."),
        ("The greenhouse contains 7 notes.", "The greenhouse contains 8 notes."),
        ("The greenhouse contains 7 notes.", "The planter holds 7 notes."),
    ]
    predictions = model.nli(examples)
    assert [max(row, key=row.get) for row in predictions] == ["ENTAIL", "CONTRADICT", "UNSUPPORTED"]
    assert np.allclose([sum(row.values()) for row in predictions], 1)


def test_review_comment_preserved_through_signoff(snapshot):
    service = EvidenceService(snapshot)
    draft = service.qa("PMID:26978244", 1)
    commented = service.reviews.review(draft["report_id"], 1, "local-expert", [
        {"statement_id": "S1", "action": "comment", "note": "Check publication scope."},
    ])
    assert commented["report"]["review"] == {}
    assert commented["report"]["state"] == "AI_DRAFT_PENDING_REVIEW"
    signed = service.reviews.review(draft["report_id"], 2, "local-expert", [
        {"statement_id": "S1", "action": "accept"},
    ], signoff=True)
    assert signed["report"]["version"] == 3
    assert [event["action"] for event in signed["report"]["timeline"]] == ["comment", "accept", "signoff"]
    assert signed["report"]["timeline"][0]["timestamp"]


@pytest.mark.parametrize("model", ["reranker", "nli_auditor"])
def test_synthetic_splits_have_distinct_domains_and_pairs(model):
    assert len(set().union(*DOMAINS.values())) == sum(map(len, DOMAINS.values()))
    pairs = [{(row.left, row.right) for row in samples(model, split)} for split in DOMAINS]
    assert len(set.union(*pairs)) == sum(map(len, pairs))


def test_offline_guard_trips_before_external_connect():
    with socket.socket() as sock, pytest.raises(AssertionError, match="external network"):
        sock.connect(("192.0.2.1", 443))
    with pytest.raises(AssertionError, match="external network"):
        socket.getaddrinfo("example.invalid", 443)
