"""Export the static two-task demo plus a reloadable provenance graph."""
import argparse
import json
from pathlib import Path

from benchmarks.demo_tasks import approved_snapshot, run
from benchmarks.flu_bench import attach_records, export_workbench, materialize, run_bench, workbench_document
from engine.provenance import ProvenanceGraph


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("frontend_demo_data/methods_review.json"))
    destination = parser.parse_args().output
    bundle, metrics = run()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    snapshot = approved_snapshot()
    path = destination.with_name("provenance_graph.json")
    ProvenanceGraph(snapshot).save(path)
    ProvenanceGraph.load(snapshot, path)
    flu_snapshot = materialize()
    flu_bundle, flu_metrics = run_bench(flu_snapshot)
    export_workbench(attach_records(workbench_document(flu_bundle, flu_metrics), flu_snapshot))
    print(json.dumps({"methods": metrics, "flu_recall_at_5": flu_metrics["task_1"]["recall_at_5"],
                      "manual_sop_baseline": flu_metrics["manual_sop_baseline"]}, ensure_ascii=False))
