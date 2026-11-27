"""Export the static two-task demo plus a reloadable provenance graph."""
import argparse
import json
from pathlib import Path

from benchmarks.demo_tasks import approved_snapshot, run
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
    print(json.dumps(metrics, ensure_ascii=False))
