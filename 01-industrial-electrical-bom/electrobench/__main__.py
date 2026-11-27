"""Command line: generate or validate an ElectroBench-JS volume."""

from __future__ import annotations

import argparse
from pathlib import Path

from .generate import PUBLISHED_SEED, generate
from .validate import validate_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="electrobench", description="ElectroBench-JS 数据集生成与校验")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="生成 DXF/PDF/PNG 与真值")
    gen.add_argument("--preset", choices=("sample", "random"), default="sample")
    gen.add_argument("--out", type=Path, required=True)
    gen.add_argument("--seed", type=int, default=PUBLISHED_SEED)
    gen.add_argument("--count", type=int, default=2, help="preset=random 时的图纸数")

    val = sub.add_parser("validate", help="校验符号、Netlist 与 BOM 口径")
    val.add_argument("dataset", type=Path)

    args = parser.parse_args(argv)
    if args.command == "generate":
        manifest = generate(args.out, preset=args.preset, seed=args.seed, count=args.count)
        print(f"wrote {len(manifest['drawings'])} drawings to {args.out} (seed={args.seed}, preset={args.preset})")
        return 0
    errors, report = validate_dataset(args.dataset)
    print(report)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
