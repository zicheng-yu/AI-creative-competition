"""ElectroBench-JS generation, rules and validator."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image

from electrobench.ampacity import AMPACITY_TABLE, select_section, undersized_section
from electrobench.catalog import ALIASES, BY_ID, CLASSES, alias_spec, alias_tag
from electrobench.degrade import SKEW_DEG, skew_image, transform_box
from electrobench.generate import generate
from electrobench.logic import build_logic
from electrobench.primary import build_ggd, build_mns
from electrobench.rules import evaluate
from electrobench.secondary import build_reversing
from electrobench.validate import validate_dataset, validate_drawing

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def test_catalog_has_at_least_25_stable_ids():
    assert len(CLASSES) >= 25
    assert len({item.class_id for item in CLASSES}) == len(CLASSES)
    assert len({item.code for item in CLASSES}) == len(CLASSES)
    assert [BY_ID[i].code for i in range(len(CLASSES))] == [item.code for item in CLASSES]
    assert ALIASES["QF"] == "空开"
    assert alias_tag("QF", "QF1") == "空开1"
    assert alias_spec("In=630A 3P Icu=50kA AC220V") == "额定630安 三极 Icu=50千安 AC220V"


def test_ampacity_table_is_monotone_and_selects_a_covering_size():
    currents = [iz for _, iz in AMPACITY_TABLE]
    assert currents == sorted(currents)
    section, iz = select_section(100)
    assert iz >= 100
    small, small_iz = undersized_section(250)
    cover, cover_iz = select_section(250)
    assert small_iz < 250 <= cover_iz
    assert small < cover


def test_clean_and_defect_rules_without_rendering():
    assert evaluate(build_ggd(262)) == []
    assert evaluate(build_mns(262)) == []
    assert evaluate(build_reversing(262)) == []
    selectivity = evaluate(build_ggd(262, inverted=True, drawing_id="X", subset="defect"))
    assert {item["rule_id"] for item in selectivity} == {"selectivity_inversion"}
    ampacity = evaluate(build_ggd(262, thin_cable=True, drawing_id="X", subset="defect"))
    assert {item["rule_id"] for item in ampacity} == {"ampacity_insufficient"}
    motor = evaluate(build_mns(262, missing_fr=True, drawing_id="X", subset="defect"))
    assert {item["rule_id"] for item in motor} == {"motor_protection_missing"}
    interlock = evaluate(build_reversing(262, interlock=False, drawing_id="X", subset="defect"))
    assert [item["rule_id"] for item in interlock] == ["interlock_missing", "interlock_missing"]


def test_logic_tables_cover_the_input_space():
    assert len(build_logic("dol_self_hold")["rows"]) == 16
    rev = build_logic("reversing", interlock=True)
    assert len(rev["rows"]) == 256
    assert not any(row["km_f_next"] and row["km_r_next"] for row in rev["rows"])
    broken = build_logic("reversing", interlock=False)
    assert any(row["km_f_next"] and row["km_r_next"] for row in broken["rows"])
    ats = build_logic("ats")
    assert len(ats["rows"]) == 24
    assert not any(row["qf1_close"] and row["qf2_close"] for row in ats["rows"])


def test_skew_box_follows_pillow_pixels(tmp_path: Path):
    image = Image.new("RGB", (120, 80), (255, 255, 255))
    for y in range(30, 50):
        for x in range(20, 45):
            image.putpixel((x, y), (0, 0, 0))
    src = tmp_path / "src.png"
    dst = tmp_path / "rot.png"
    image.save(src)
    skew_image(src, dst, SKEW_DEG)
    rotated = Image.open(dst).convert("RGB")
    dark = []
    for y in range(rotated.height):
        for x in range(rotated.width):
            if rotated.getpixel((x, y))[0] < 128:
                dark.append((x, y))
    assert dark
    minx = min(p[0] for p in dark)
    miny = min(p[1] for p in dark)
    maxx = max(p[0] for p in dark)
    maxy = max(p[1] for p in dark)
    predicted, new_w, new_h = transform_box([20, 30, 25, 20], SKEW_DEG, 120, 80)
    assert (new_w, new_h) == rotated.size
    # Bilinear edges spill by about a pixel; the predicted box must cover the ink
    # and stay within a few pixels of the dark extent.
    assert predicted[0] <= minx + 1.5
    assert predicted[1] <= miny + 1.5
    assert predicted[0] + predicted[2] >= maxx - 1.5
    assert predicted[1] + predicted[3] >= maxy - 1.5


def test_published_sample_validates_and_regenerates(tmp_path: Path):
    generate(tmp_path / "once", preset="sample", seed=262)
    errors, report = validate_dataset(tmp_path / "once")
    assert not errors, report
    generate(tmp_path / "twice", preset="sample", seed=262)
    first = json.loads((tmp_path / "once" / "manifest.json").read_text(encoding="utf-8"))
    second = json.loads((tmp_path / "twice" / "manifest.json").read_text(encoding="utf-8"))
    assert [item["annotations_sha256"] for item in first["drawings"]] == [
        item["annotations_sha256"] for item in second["drawings"]
    ]
    published = json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))
    assert [item["annotations_sha256"] for item in published["drawings"]] == [
        item["annotations_sha256"] for item in first["drawings"]
    ]
    alias = json.loads((SAMPLES / "degraded" / "EBJS-G-ALIAS-003" / "annotations.json").read_text(encoding="utf-8"))
    breaker = next(item for item in alias["instances"] if item["tag"] == "QF1")
    assert breaker["label_tag"] == "空开1"
    assert breaker["specs"]["spec"].startswith("In=")
    assert "空开" not in breaker["specs"]["spec"]


def test_random_preset_is_reproducible_and_clean(tmp_path: Path):
    generate(tmp_path / "a", preset="random", seed=262, count=2)
    generate(tmp_path / "b", preset="random", seed=262, count=2)
    generate(tmp_path / "c", preset="random", seed=263, count=2)
    errors, report = validate_dataset(tmp_path / "a")
    assert not errors, report
    digest = lambda root: json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert [item["annotations_sha256"] for item in digest(tmp_path / "a")["drawings"]] == [
        item["annotations_sha256"] for item in digest(tmp_path / "b")["drawings"]
    ]
    assert [item["annotations_sha256"] for item in digest(tmp_path / "a")["drawings"]] != [
        item["annotations_sha256"] for item in digest(tmp_path / "c")["drawings"]
    ]


def test_validator_rejects_bom_and_netlist_edits(tmp_path: Path):
    source = SAMPLES / "primary" / "EBJS-P-GGD-001"
    bom_dir = tmp_path / "bom"
    shutil.copytree(source, bom_dir)
    data = json.loads((bom_dir / "annotations.json").read_text(encoding="utf-8"))
    data["bom"][0]["qty"] = 2
    (bom_dir / "annotations.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    bom_errors = validate_drawing(bom_dir, data)
    assert any("数量不是 1" in item for item in bom_errors)

    net_dir = tmp_path / "net"
    shutil.copytree(source, net_dir)
    data = json.loads((net_dir / "annotations.json").read_text(encoding="utf-8"))
    data["netlist"]["nodes"].pop()
    net_errors = validate_drawing(net_dir, data)
    assert any("Netlist" in item for item in net_errors)
