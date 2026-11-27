"""Refresh the default template catalog from the ElectroBench glyph definitions."""

import json
import sys
from argparse import ArgumentParser
from pathlib import Path


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("electrobench_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.electrobench_root.resolve()))
    from electrobench.catalog import ALIASES, CLASSES
    from electrobench.glyphs import GLYPHS

    classes = {}
    for item in CLASSES:
        glyph = GLYPHS.get(item.code)
        classes[item.code] = {
            "name_zh": item.name_zh,
            "prefix": item.bom_letter or item.code,
            "unit": item.unit or "",
            "bom_anchor": item.default_bom_anchor,
            "in_netlist": item.default_in_netlist,
            "bbox": glyph.bbox if glyph else None,
            "ports": glyph.ports if glyph else {},
            "strokes": glyph.entities if glyph else [],
        }
    catalog = {
        "origin": "ElectroBench-JS procedural glyphs, YOU-262",
        "aliases": ALIASES,
        "classes": classes,
    }
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
