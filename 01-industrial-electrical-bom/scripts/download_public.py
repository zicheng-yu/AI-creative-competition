#!/usr/bin/env python3
"""List or fetch the public datasets named in public/catalog.json.

Large archives are not vendored. A fetch runs only when an entry has a
direct_url. Landing-page entries print the URL and stop, so a multi-gigabyte
Zenodo zip is never pulled by accident.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "public" / "catalog.json"
sys.path.insert(0, str(ROOT))

from electrobench.catalog import CLASSES  # noqa: E402


def load() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def cmd_list(catalog: dict) -> int:
    print(f"retrieved_on={catalog['retrieved_on']} entries={len(catalog['datasets'])}")
    for item in catalog["datasets"]:
        direct = "direct" if item.get("direct_url") else "landing-page-only"
        print(f"- {item['id']}: {item['name']} [{direct}]")
        print(f"    url: {item['landing_url']}")
        print(f"    license: {item['license']}")
    return 0


def cmd_targets() -> int:
    print("ElectroBench-JS target classes (map external labels onto these codes; do not invent matches)")
    for item in CLASSES:
        iec = item.iec81346 or "-"
        print(f"{item.class_id:2d}  {item.code:10s}  {item.name_zh}  iec81346={iec}")
    return 0


def cmd_fetch(catalog: dict, dataset_id: str, out: Path) -> int:
    match = next((item for item in catalog["datasets"] if item["id"] == dataset_id), None)
    if match is None:
        print(f"unknown id {dataset_id}", file=sys.stderr)
        return 2
    if not match.get("direct_url"):
        print(f"{dataset_id} has no direct_url.")
        print(f"Open the landing page and follow its license: {match['landing_url']}")
        print(match["license"])
        return 2
    out.mkdir(parents=True, exist_ok=True)
    dest = out / Path(match["direct_url"]).name
    print(f"downloading {match['direct_url']} -> {dest}")
    urllib.request.urlretrieve(match["direct_url"], dest)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ElectroBench-JS 公开数据集目录")
    parser.add_argument("--list", action="store_true", help="打印目录（默认）")
    parser.add_argument("--targets", action="store_true", help="打印本数据集的目标符号代号")
    parser.add_argument("--fetch", metavar="ID", help="仅当条目含 direct_url 时下载")
    parser.add_argument("--out", type=Path, default=ROOT / "public_cache")
    args = parser.parse_args(argv)
    catalog = load()
    if args.targets:
        return cmd_targets()
    if args.fetch:
        return cmd_fetch(catalog, args.fetch, args.out)
    return cmd_list(catalog)


if __name__ == "__main__":
    raise SystemExit(main())
