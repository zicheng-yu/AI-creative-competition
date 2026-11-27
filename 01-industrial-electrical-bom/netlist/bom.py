"""Generate a traceable bill of materials and export it without formulas."""

from __future__ import annotations

import csv
import json
from pathlib import Path

_NON_BOM = {
    "PE",
    "WIRE_NO",
    "KM_COIL",
    "KM_NO",
    "KM_NC",
    "KA_NO",
    "KA_NC",
    "KT_NO",
    "FR_NC",
}
_FIELDS = (
    "cabinet",
    "circuit",
    "class_code",
    "name",
    "tag",
    "model",
    "spec",
    "ratings",
    "qty",
    "unit",
    "anchors",
)


def build_bom(project: dict) -> dict:
    items = {}
    warnings = []
    for sheet in project["sheets"]:
        for symbol in sheet["symbols"]:
            klass = symbol["class_code"]
            if not symbol.get("bom_anchor", klass not in _NON_BOM):
                continue
            cabinet = symbol.get("cabinet", sheet.get("cabinet", ""))
            circuit = symbol.get("circuit", "")
            anchor = {
                "sheet_id": sheet["id"],
                "instance_id": symbol["id"],
                "bbox": symbol.get("bbox"),
            }
            tag = symbol.get("tag", "").strip()
            specs = symbol.get("specs", {})
            ratings = {
                key: val
                for key, val in specs.items()
                if key not in {"model", "spec", "circuit"}
            }
            row = {
                "cabinet": cabinet,
                "circuit": circuit,
                "class_code": klass,
                "name": symbol.get("name_zh", klass),
                "tag": tag,
                "model": specs.get("model", ""),
                "spec": specs.get("spec", ""),
                "ratings": ratings,
                "qty": 1,
                "unit": symbol.get("unit", ""),
                "anchors": [anchor],
            }
            # Without a cabinet or tag, there is no trustworthy cross-sheet identity.
            identity = tag.casefold() if tag else symbol["id"]
            key = (
                cabinet,
                circuit,
                klass,
                identity,
                "" if cabinet and tag else sheet["id"],
            )
            existing = items.get(key)
            if existing is None:
                items[key] = row
                continue
            for field in ("model", "spec", "unit"):
                if not existing[field]:
                    existing[field] = row[field]
                elif row[field] and existing[field] != row[field]:
                    warnings.append(
                        {
                            "type": "bom_conflict",
                            "tag": tag,
                            "field": field,
                            "anchor": anchor,
                        }
                    )
            for field, value in ratings.items():
                if field not in existing["ratings"]:
                    existing["ratings"][field] = value
                elif value != existing["ratings"][field]:
                    warnings.append(
                        {
                            "type": "bom_conflict",
                            "tag": tag,
                            "field": field,
                            "anchor": anchor,
                        }
                    )
            existing["anchors"].append(anchor)
    rows = list(items.values())
    totals = {}
    for row in rows:
        key = tuple(
            row[field]
            for field in (
                "cabinet",
                "circuit",
                "class_code",
                "model",
                "spec",
                "unit",
            )
        ) + (json.dumps(row["ratings"], sort_keys=True, ensure_ascii=False),)
        if key not in totals:
            totals[key] = {**row, "tag": [], "qty": 0, "anchors": []}
        group = totals[key]
        group["qty"] += row["qty"]
        group["tag"].append(row["tag"])
        group["anchors"].extend(row["anchors"])
    return {"items": rows, "summary": list(totals.values()), "warnings": warnings}


def _cell(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def export_bom(bom: dict, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    fields = list(_FIELDS)
    for filename, rows in (
        ("bom.csv", bom["items"]),
        ("bom_summary.csv", bom["summary"]),
    ):
        with (target / filename).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(fields)
            for row in rows:
                values = [_cell(row[field]) for field in fields]
                writer.writerow(
                    [
                        "'" + value
                        if isinstance(value, str)
                        and (
                            value.startswith(("\t", "\r", "\n"))
                            or value.lstrip().startswith(("=", "+", "-", "@"))
                        )
                        else value
                        for value in values
                    ]
                )

    from openpyxl import Workbook

    workbook = Workbook()
    detail = workbook.active
    detail.title = "明细"
    for sheet, rows in (
        (detail, bom["items"]),
        (workbook.create_sheet("按回路汇总"), bom["summary"]),
    ):
        sheet.append(fields)
        for row in rows:
            sheet.append([_cell(row[field]) for field in fields])
            for cell in sheet[sheet.max_row]:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column, width in zip(
            "ABCDEFGHIJK", (14, 16, 14, 18, 22, 20, 28, 36, 9, 9, 55)
        ):
            sheet.column_dimensions[column].width = width
    workbook.save(target / "bom.xlsx")
    (target / "bom.erp.json").write_text(
        json.dumps(bom, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
