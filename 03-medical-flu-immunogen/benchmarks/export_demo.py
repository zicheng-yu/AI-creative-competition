"""Run the methods-only demo through the same local HTTP entry points as the UI."""
import argparse
import json
from pathlib import Path
from time import perf_counter_ns

from fastapi.testclient import TestClient

from server import demo_app


def post(client, route, body):
    response = client.post(f"/api/v1/{route}", json=body)
    response.raise_for_status()
    return response.json()


def run() -> tuple[dict, dict]:
    start = perf_counter_ns()
    with TestClient(demo_app()) as client:
        manifest = client.get("/api/v1/health").json()
        question = "PMID:26978244 FAIR data stewardship"
        qa = post(client, "qa", {"query": question, "limit": 1})
        groups = []
        for label, evidence_id in [("数据管理规范", "EV-METHODS-FAIR"),
                                   ("系统综述报告规范", "EV-METHODS-PRISMA")]:
            groups.append({"label": label, "citations": [
                {"evidence_id": evidence_id, "dataset_version": "methods-fixture-v1"}
            ]})
        compare = post(client, "compare", {"groups": groups})
        review = post(client, "review/signoff", {
            "report_id": compare["report_id"], "expected_version": 1,
            "reviewer": "demo-reviewer", "actions": [
                {"statement_id": "S1", "action": "accept"},
                {"statement_id": "S2", "action": "flag_doubt", "note": "核对适用范围。"},
            ], "signoff": True,
        })
    elapsed_ms = (perf_counter_ns() - start) / 1e6
    assert [s["evidence_id"] for s in qa["statements"]] == ["EV-METHODS-FAIR"]
    assert [r["statement_ids"] for r in compare["inventory"]] == [["S1"], ["S2"]]
    assert review["report"]["state"] == "EXPERT_SIGNED"
    assert "EV-METHODS-FAIR" in review["exports"]["evidence_csv"]
    assert "EV-METHODS-PRISMA" not in review["exports"]["evidence_csv"]
    bundle = {
        "scope": "公开研究方法文献的离线证据审阅示例",
        "snapshot": manifest,
        "qa": {"query": question, "report": qa},
        "compare": {"groups": groups, "report": compare},
        "signoff": review,
    }
    metrics = {
        "qa_expected_reference_at_1": f"{len(qa['statements'])}/1",
        "comparison_groups_verified": f"{len(compare['inventory'])}/2",
        "signed_accepted_citations": f"{review['exports']['evidence_csv'].count('EV-METHODS-FAIR')}/1",
        "local_demo_elapsed_ms": round(elapsed_ms, 2),
    }
    return bundle, metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("frontend_demo_data/methods_review.json"))
    destination = parser.parse_args().output
    bundle, metrics = run()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics))
