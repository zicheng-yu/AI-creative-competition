"""FluEvidenceBench-v1 lock, tasks, and API compatibility. Network stays disabled."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from benchmarks.flu_bench import (
    BENCH, GOLD, RECORDS, capsule_row, materialize, release_lock, run_bench,
)
from engine.capsules import Snapshot
from engine.dossiers import Dossier, compare_dossiers
from server import FIXTURES, create_app, demo_app, flu_app


def test_methods_fixture_ids_unchanged():
    rows = [json.loads(line) for line in (FIXTURES / "methods.jsonl").read_text().splitlines()]
    assert [row["evidence_id"] for row in rows] == [
        "EV-METHODS-FAIR", "EV-METHODS-PRISMA", "EV-METHODS-PRISMA-ELAB",
        "EV-METHODS-PRISMA-P", "EV-METHODS-REPRO", "EV-METHODS-SYNTH-REGISTER",
    ]
    assert {row["source_type"] for row in rows} == {"PUBMED_LITERATURE", "SYNTHETIC_METHODS"}


def test_committed_lock_matches_materializer(tmp_path):
    fresh = materialize(tmp_path)
    committed = Snapshot(BENCH / "jsonl", BENCH / "release.lock.json")
    parquet = Snapshot(BENCH / "parquet", BENCH / "release.lock.json")
    assert fresh.snapshot_id == committed.snapshot_id == parquet.snapshot_id
    assert len(committed.records) == len(RECORDS) == 24
    card = (BENCH / "DATASET_CARD.md").read_text(encoding="utf-8")
    for spec in RECORDS:
        assert spec["primary_ref"] in card
        assert spec["evidence_id"] in card
        assert spec["ingested_at"] in card
    assert "未测" in (BENCH / "tasks.json").read_text(encoding="utf-8")


def test_every_public_anchor_matches_its_source_page():
    lock = release_lock()
    for entry in lock["records"]:
        row = next(item for item in (capsule_row(spec) for spec in RECORDS)
                   if item["evidence_id"] == entry["evidence_id"])
        assert entry["record_sha256"]
        assert row["sha256"]
        if entry["nature"] == "public_methods":
            pmid = entry["primary_ref"].split(":", 1)[1]
            assert entry["source_url"] == f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        else:
            assert entry["nature"] == "public_database"
            assert entry["source_url"].startswith("https://")


def test_bad_database_url_is_rejected(tmp_path):
    lock = release_lock()
    lock["records"][0]["nature"] = "public_database"
    lock["records"][0]["primary_ref"] = "PDB:3GBN"
    lock["records"][0]["source_url"] = "https://example.invalid/3GBN"
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="public database"):
        Snapshot(BENCH / "jsonl", path)


def test_task_gold_matches_dossier_dimensions():
    snapshot = Snapshot(BENCH / "jsonl", BENCH / "release.lock.json")
    from benchmarks.flu_bench import dossier_bodies
    matrix = compare_dossiers([Dossier.model_validate(row) for row in dossier_bodies(snapshot)], snapshot)
    assert [row["dossier_id"] for row in matrix] == list(GOLD)
    for row in matrix:
        gold = GOLD[row["dossier_id"]]
        dimensions = row["evidence_dimensions"]
        predicted = [list(pair) for pair in sorted(
            (item["left_ref"], item["right_ref"]) for item in dimensions["citation_conflicts"])]
        assert predicted == gold["conflicts"]
        assert dimensions["evidence_gaps"] == gold["gaps"]
        assert row["version_consistency"]["consistent"] is gold["consistent"]
        assert "实验" not in " ".join(dimensions["evidence_gaps"])
        assert "性能" in dimensions["note"]


def test_flu_api_keeps_methods_app_unchanged():
    with TestClient(demo_app()) as methods, TestClient(flu_app()) as flu:
        assert methods.get("/api/v1/health").json()["record_count"] == 6
        health = flu.get("/api/v1/health").json()
        assert health["record_count"] == 24
        assert health["ok"] is True
        rejected = flu.post("/api/v1/compare", json={"groups": [
            {"label": "甲", "citations": [{"evidence_id": "EV-REF-GARTEN", "dataset_version": "fluevidence-v1"}]},
            {"label": "乙", "citations": [{"evidence_id": "EV-REF-GARTEN", "dataset_version": "missing"}]},
        ]})
        assert rejected.status_code == 422
        answer = flu.post("/api/v1/qa", json={"query": "PMID:19465683", "limit": 1}).json()
        assert answer["statements"][0]["primary_ref"] == "PMID:19465683"
        assert answer["statements"][0]["dataset_version"] == "fluevidence-v1"


def test_offline_flu_metrics_are_measured():
    _bundle, metrics = run_bench()
    assert metrics["manual_sop_baseline"] == "未测"
    assert metrics["task_1"]["queries"] == 7
    assert metrics["task_1"]["recall_at_5"] == 1
    assert 0 < metrics["task_1"]["ndcg_at_5"] < 1
    assert metrics["task_1"]["per_question"][5]["hits"][2] == "EV-STEM-HEADLESS"
    assert metrics["citations"]["accepted_matching_lock"] == metrics["citations"]["accepted_total"]
    assert metrics["no_retrieval_baseline"]["accepted_statements"] == 0
    assert metrics["no_retrieval_baseline"]["rejected"]["outside_selection"] == 2
    assert metrics["compliance_gate"]["stored_snippets_matching_effect_promise"] == 0
    assert metrics["compliance_gate"]["probe_effect_promise_rejected"] == 1
    assert metrics["compliance_gate"]["probe_accepted"] == 0
    assert metrics["task_2"]["dossiers_matching_gold"] == 4
    assert metrics["task_2"]["signed_state"] == "EXPERT_SIGNED"
    tiers = {tier: 0 for tier in ("T1_WET_LAB_ASSAY", "T2_SURVEILLANCE", "T3_PEER_REVIEWED_LIT", "T4_COMPUTATIONAL")}
    for spec in RECORDS:
        tiers[spec["evidence_tier"]] += 1
    assert tiers["T4_COMPUTATIONAL"] == 0
    assert tiers["T1_WET_LAB_ASSAY"] > 0 and tiers["T2_SURVEILLANCE"] > 0
