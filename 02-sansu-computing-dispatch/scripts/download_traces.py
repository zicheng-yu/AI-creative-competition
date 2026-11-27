"""Print or optionally clone the public trace repos used as references.

The simulator does not need these files. They are large and must not be
committed. Downloaded trees go under ``data/traces/``, which is gitignored.

Examples:
    python scripts/download_traces.py
    python scripts/download_traces.py --download helios
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST_ROOT = ROOT / "data" / "traces"

REPOS = {
    "alibaba": {
        "url": "https://github.com/alibaba/clusterdata.git",
        "note": "PAI GPU trace v2020 lives in cluster-trace-gpu-v2020/. The repo also carries other, larger traces.",
    },
    "helios": {
        "url": "https://github.com/S-Lab-System-Group/HeliosData.git",
        "note": "SenseTime Helios. The upstream README has said that only Venus is public; do not assume Earth/Saturn/Uranus are in the clone.",
    },
    "philly": {
        "url": "https://github.com/msr-fiddle/philly-traces.git",
        "note": "Microsoft Philly DNN training trace.",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download",
        nargs="*",
        choices=sorted(REPOS),
        help="Clone these repos with --depth 1. Omit to print URLs only.",
    )
    args = parser.parse_args()
    for name, spec in REPOS.items():
        print(f"{name}: {spec['url']}")
        print(f"  {spec['note']}")
    print("Electricity Maps hourly intensity is not bundled. The sim uses the 2022 annual factors in configs/energy.yaml.")
    print("Optional upstream: https://github.com/electricitymaps/electricitymaps-contrib")
    if not args.download:
        return
    DEST_ROOT.mkdir(parents=True, exist_ok=True)
    for name in args.download:
        dest = DEST_ROOT / name
        if dest.exists():
            print(f"skip {name}: {dest} already exists", file=sys.stderr)
            continue
        subprocess.run(
            ["git", "clone", "--depth", "1", REPOS[name]["url"], str(dest)],
            check=True,
        )


if __name__ == "__main__":
    main()
