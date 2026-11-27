"""Summarize a downloaded trace if one is present. Does not fetch data.

Looks under ``data/traces/`` for a CSV and prints a few numeric columns.
Exits 0 when nothing has been downloaded.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from js_computesim.trace_anchors import PUBLISHED_ANCHORS

TRACE_ROOT = ROOT / "data" / "traces"
CANDIDATE_COLUMNS = (
    "plan_gpu",
    "gpu_num",
    "duration",
    "start_time",
    "end_time",
    "submit_time",
)


def _find_csvs(root: Path, limit: int) -> list[Path]:
    if not root.exists():
        return []
    found: list[Path] = []
    for path in sorted(root.rglob("*.csv")):
        found.append(path)
        if len(found) >= limit:
            break
    return found


def _column_stats(path: Path, column: str, max_rows: int) -> str | None:
    values: list[float] = []
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or column not in reader.fieldnames:
            return None
        for index, row in enumerate(reader):
            if index >= max_rows:
                break
            raw = row.get(column)
            if raw is None or raw == "":
                continue
            try:
                values.append(float(raw))
            except ValueError:
                continue
    if not values:
        return None
    values.sort()
    mid = values[len(values) // 2]
    return f"{column}: n={len(values)} min={values[0]:.4g} median={mid:.4g} max={values[-1]:.4g}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-files", type=int, default=8)
    parser.add_argument("--max-rows", type=int, default=200_000)
    parser.add_argument("--show-anchors", action="store_true")
    args = parser.parse_args()
    if args.show_anchors:
        for name, payload in PUBLISHED_ANCHORS.items():
            print(f"[{name}] {payload.get('citation', '')}")
    csvs = _find_csvs(TRACE_ROOT, args.max_files)
    if not csvs:
        print("No CSV under data/traces/. The bundled simulator does not need one.")
        print("Download with: python scripts/download_traces.py --download helios")
        return
    for path in csvs:
        print(path.relative_to(ROOT))
        reported = False
        for column in CANDIDATE_COLUMNS:
            line = _column_stats(path, column, args.max_rows)
            if line:
                print(" ", line)
                reported = True
        if not reported:
            print("  no numeric plan_gpu/gpu_num/duration columns in the first rows")


if __name__ == "__main__":
    main()
