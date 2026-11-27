"""Run random and least-loaded greedy on the four built-in scenarios.

Example:
    python scripts/run_baselines.py --seed 313
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from js_computesim import SCENARIO_NAMES, run_episode
from js_computesim.baselines import POLICIES

COLUMNS = (
    "served_ratio",
    "sla_violation_ratio",
    "mean_utilization",
    "weighted_pue",
    "energy_mwh",
    "carbon_t",
    "green_energy_share",
    "cost_10k_cny",
    "cross_domain_eflops",
    "reward",
)


def render_table(rows: list[dict]) -> str:
    header = ("scenario", "policy", *COLUMNS)
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows:
        cells = [str(row["scenario"]), str(row["policy"])]
        for key in COLUMNS:
            cells.append(f"{float(row[key]):.4f}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "results" / "baseline_seed313.md",
    )
    args = parser.parse_args()
    rows = []
    for scenario in SCENARIO_NAMES:
        for policy in POLICIES:
            rows.append(run_episode(scenario, policy, seed=args.seed))
    table = render_table(rows)
    text = (
        f"# JS-ComputeSim-313 baseline episode, seed {args.seed}\n\n"
        "One episode is 168 hourly steps. Absolute MWh, tonnes and CNY use the\n"
        "sandbox coefficient `assumption_it_kw_per_eflops: 1000` in `configs/energy.yaml`.\n"
        "They are not a provincial energy balance.\n"
        "Random and least-loaded greedy ignore price and green power, so "
        "`green_surplus` matches `weekday` on placement and differs on carbon "
        "and green share. A price- or carbon-aware policy is what should move "
        "flexible load. Regenerate with:\n\n"
        "```bash\n"
        "python scripts/run_baselines.py --seed 313\n"
        "```\n\n"
        + table
        + "\n"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
