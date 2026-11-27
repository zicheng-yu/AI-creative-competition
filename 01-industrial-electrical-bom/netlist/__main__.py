"""Command-line entry point for the topology stage."""

import argparse
import json
from pathlib import Path

from . import build_bom, export_bom, reconstruct


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a netlist and BOM from recognized symbols plus drawing wires."
    )
    parser.add_argument(
        "project",
        type=Path,
        help="Input JSON, with drawing paths relative to this file",
    )
    parser.add_argument("--out", required=True, type=Path, help="Result directory")
    args = parser.parse_args()
    project = json.loads(args.project.read_text(encoding="utf-8"))
    result = reconstruct(project, args.project.parent)
    args.out.mkdir(exist_ok=True, parents=True)
    export_bom(build_bom(project), args.out)
    (args.out / "netlist.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
