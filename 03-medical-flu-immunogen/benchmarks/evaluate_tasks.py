"""Run the methods fixture tasks and both FluEvidenceBench tasks."""
import argparse
import json
from pathlib import Path

from benchmarks.demo_tasks import run
from benchmarks.flu_bench import run_bench, write_eval


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    _, metrics = run()
    report = json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    _, flu = run_bench()
    directory = write_eval(flu)
    print(report, end="")
    print(json.dumps({"flu_evidence_bench": directory.as_posix(),
                      "recall_at_5": flu["task_1"]["recall_at_5"],
                      "ndcg_at_5": flu["task_1"]["ndcg_at_5"],
                      "citation_accuracy_among_accepted": flu["citations"]["accuracy_among_accepted"],
                      "dossiers_matching_gold": flu["task_2"]["dossiers_matching_gold"],
                      "manual_sop_baseline": flu["manual_sop_baseline"]},
                     ensure_ascii=False, indent=2))
