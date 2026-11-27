import json
import socket
from concurrent.futures import ThreadPoolExecutor

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from benchmarks.export_demo import run
from engine.audit import BOUNDARY, INSUFFICIENT, audit
from engine.capsules import EvidenceCapsule, Snapshot, digest
from engine.llm_adapter import BaseLLMClient, Citation
from engine.review import ReviewConflict, csv_cell, markdown_text
from engine.service import EvidenceService
from server import FIXTURES, demo_app


FAIR = ("EV-METHODS-FAIR", "methods-fixture-v1")


@pytest.fixture
def snapshot():
    return Snapshot(FIXTURES / "methods.jsonl", FIXTURES / "release.lock.json")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def disabled(*args, **kwargs):
        raise AssertionError("external network I/O in offline tests")

    def loopback_only(connect):
        def checked(sock, address):
            # On Windows the asyncio wakeup socket pair uses loopback TCP.
            if not isinstance(address, tuple) or address[0] not in ("127.0.0.1", "::1"):
                disabled()
            return connect(sock, address)
        return checked

    monkeypatch.setattr(socket.socket, "connect", loopback_only(original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", loopback_only(original_connect_ex))
    monkeypatch.setattr(socket, "getaddrinfo", disabled)


def test_parquet_and_directory_match(snapshot, tmp_path):
    rows = [record.model_dump() for record in snapshot.records.values()]
    path = tmp_path / "evidence.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    lock = FIXTURES / "release.lock.json"
    assert Snapshot(path, lock).snapshot_id == Snapshot(tmp_path, lock).snapshot_id
    assert Snapshot(tmp_path, lock).snapshot_id == snapshot.snapshot_id


@pytest.mark.parametrize("change", ["source_ref", "summary", "snippet", "missing", "duplicate"])
def test_lock_rejects_mutations(snapshot, tmp_path, change):
    rows = [record.model_dump() for record in snapshot.records.values()]
    if change == "source_ref":
        rows[0]["primary_ref"] = rows[1]["primary_ref"]
    elif change == "summary":
        rows[0]["claim_summary"] = "Unverified replacement."
    elif change == "snippet":
        rows[0]["raw_snippet"] = "Unverified replacement."
        rows[0]["sha256"] = digest(rows[0]["raw_snippet"].encode())
    elif change == "missing":
        rows.pop()
    else:
        rows.append(rows[0])
    path = tmp_path / "modified.jsonl"
    path.write_text("\n".join(map(json.dumps, rows)), encoding="utf-8")
    with pytest.raises(ValueError):
        Snapshot(path, FIXTURES / "release.lock.json")


def test_computation_must_use_t4(snapshot):
    row = snapshot.records[FAIR].model_dump()
    row["source_type"] = "LOCAL_COMPUTATIONAL"
    with pytest.raises(ValueError, match="require T4"):
        EvidenceCapsule.model_validate(row)
    row["evidence_tier"] = "T4_COMPUTATIONAL"
    assert EvidenceCapsule.model_validate(row).evidence_tier == "T4_COMPUTATIONAL"


@pytest.mark.parametrize("effect", ["临床保护率", "湿实验有效", "最优疫苗", "Guaranteed protection"])
def test_science_gate_on_literal_snippet(snapshot, effect):
    record = snapshot.records[FAIR].model_copy(
        update={"raw_snippet": effect, "sha256": digest(effect.encode())}
    )
    statements, rejected = audit([Citation(*record.key, effect)], [record])
    assert statements == []
    assert rejected["effect_promise"] == 1


def test_generated_identifiers_and_sentence_variants_fail_closed(snapshot):
    original = snapshot.records[FAIR]
    unregistered = "EV-" + digest(b"not in the release")[:12]

    class UntrustedDraft(BaseLLMClient):
        def assemble(self, query, records):
            return [
                Citation(*FAIR, original.raw_snippet + " PMID:" + "0"),
                Citation(unregistered, FAIR[1], original.raw_snippet),
                Citation(FAIR[0], "other-version", original.raw_snippet),
            ]

    report = EvidenceService(snapshot, UntrustedDraft()).qa("PMID:26978244", 1)
    assert report["statements"] == []
    assert report["review_notice"] == INSUFFICIENT
    assert "PMID:" not in json.dumps(report)
    assert report["agent_trace"][-1]["rejected"] == {
        "outside_selection": 2, "nonverbatim": 1, "effect_promise": 0,
    }


def test_verified_citation_deduplicates_and_preserves_metadata(snapshot):
    original = snapshot.records[FAIR]
    rows, counts = audit([Citation(*FAIR, original.raw_snippet)] * 2, [original])
    assert len(rows) == 1
    assert rows[0]["primary_ref"] == original.primary_ref
    assert rows[0]["dataset_version"] == original.dataset_version
    assert rows[0]["evidence_tier"] == original.evidence_tier
    assert sum(counts.values()) == 0


def test_provenance_contains_source_and_release(snapshot):
    report = EvidenceService(snapshot).qa("PMID:26978244", 1)
    nodes = report["provenance"]["nodes"]
    assert ["evidence", *FAIR] in nodes
    assert ["source", "PMID:26978244"] in nodes
    assert ["release", FAIR[1]] in nodes
    assert len(report["provenance"]["edges"]) == 2


def test_review_error_leaves_version_and_dispositions_unchanged(snapshot):
    service = EvidenceService(snapshot)
    draft = service.qa("PMID:26978244", 1)
    report_id = draft["report_id"]
    invalid = [
        {"statement_id": "S1", "action": "accept"},
        {"statement_id": "unknown", "action": "reject"},
    ]
    with pytest.raises(ValueError):
        service.reviews.review(report_id, 1, "expert", invalid, signoff=True)
    with pytest.raises(ReviewConflict):
        service.reviews.review(report_id, 1, "expert", [], signoff=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        def submit():
            try:
                return service.reviews.review(report_id, 1, "expert", invalid[:1], signoff=True)
            except ReviewConflict:
                return None
        outcomes = list(pool.map(lambda _: submit(), range(2)))
    exports, = [result["exports"] for result in outcomes if result is not None]
    assert BOUNDARY in exports["markdown"]
    assert "PMID:26978244" in exports["evidence_csv"]


def test_api_schema_errors_and_unmatched_query():
    with TestClient(demo_app()) as client:
        assert client.get("/api/v1/health").json()["record_count"] == 2
        qa = client.post("/api/v1/qa", json={"query": "unknownx123"})
        assert qa.json()["review_notice"] == INSUFFICIENT
        assert client.post("/api/v1/qa", json={"query": "  "}).status_code == 422
        assert client.post("/api/v1/compare", json={"groups": [], "fasta": "invalid"}).status_code == 422
        response = client.post("/api/v1/review/signoff", json={
            "report_id": "missing", "expected_version": 1, "reviewer": "expert", "signoff": True,
        })
        assert response.status_code == 404


def test_api_rejects_reference_outside_snapshot():
    groups = [
        {"label": label, "citations": [{"evidence_id": FAIR[0], "dataset_version": version}]}
        for label, version in [("valid", FAIR[1]), ("invalid", "different-version")]
    ]
    with TestClient(demo_app()) as client:
        assert client.post("/api/v1/compare", json={"groups": groups}).status_code == 422


def test_exports_escape_markup_and_spreadsheet_formulas():
    assert markdown_text("<b>[x](y)") == r"&lt;b&gt;\[x\]\(y\)"
    assert csv_cell("  =SUM(1,2)") == "'  =SUM(1,2)"


def test_offline_demo():
    bundle, metrics = run()
    assert metrics["qa_expected_reference_at_1"] == "1/1"
    assert metrics["comparison_groups_verified"] == "2/2"
    assert metrics["signed_accepted_citations"] == "1/1"
    assert bundle["signoff"]["report"]["version"] == 2
    assert len(bundle["signoff"]["report"]["timeline"]) == 3
