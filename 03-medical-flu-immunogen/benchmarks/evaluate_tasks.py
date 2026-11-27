"""Run both offline software tasks and persist their measured results."""
import argparse
import json
from pathlib import Path

from benchmarks.demo_tasks import run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    _, metrics = run()
    report = json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    print(report, end="")
