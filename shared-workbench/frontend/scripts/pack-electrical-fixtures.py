"""Extract four frozen review examples from the peer dataset and rule reports."""

import argparse
import json
import shutil
from pathlib import Path

CASES = [
    ("primary", "EBJS-P-GGD-001", "低压配电柜 GGD"),
    ("primary", "EBJS-P-KYN-004", "10 kV 开关柜 KYN28"),
    ("secondary", "EBJS-S-DOL-001", "电机启停控制"),
    ("defect", "EBJS-D-SEL-001", "级差问题样图"),
]


def pack(root: Path, output: Path):
    reports = root / "frontend_demo_data"
    reference = json.loads(
        (reports / "compliance_reports.json").read_text(encoding="utf-8")
    )
    output.mkdir(parents=True, exist_ok=True)
    index = []
    for subset, id_, label in CASES:
        source = root / "samples" / subset / id_
        annotation = json.loads(
            (source / "annotations.json").read_text(encoding="utf-8")
        )
        prefab = {
            "id": id_,
            "title": label,
            "kind": "fixture",
            "preview": id_ + ".png",
            "width": annotation["sheet"]["image_width"],
            "height": annotation["sheet"]["image_height"],
            "annotation": annotation,
            "checks": reference["reports"][id_],
        }
        json_file, png_file = output / (id_ + ".json"), output / (id_ + ".png")
        json_file.write_text(
            json.dumps(prefab, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        shutil.copyfile(source / "drawing.png", png_file)
        index.append({"id": id_, "title": label, "filename": json_file.name})
    (output / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "clauses.json").write_text(
        json.dumps(reference["clauses"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(
        reports / "eval_charts_workbench.csv", output / "eval_charts_workbench.csv"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pipeline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    pack(args.pipeline, args.output)
