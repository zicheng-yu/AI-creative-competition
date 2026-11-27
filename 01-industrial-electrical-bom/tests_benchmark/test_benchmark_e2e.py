import csv
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image
import pytest

from benchmark_e2e.adapter import _bind_bus_specs, predict, prepare_raster, preview_fix, source_only
from benchmark_e2e.baselines import LANES, execute, originals
from benchmark_e2e.charts import METRICS, metric
from benchmark_e2e.metrics import _bom_detail, _summarized, composite_accuracy, load_references, score, spec_semantic, summarize
from benchmark_e2e.reporting import METRIC_NAMES, WORKBENCH_FIELDS
from benchmark_e2e.run_benchmark import canonical_metrics_bytes, offline_inference
from benchmark_e2e.vlm_baseline import OpenAICompatibleVision, PENDING, load_predictions, to_prediction
from compliance.engine import evaluate

TRACK = Path(__file__).resolve().parents[1]
SAMPLES = TRACK / "samples"
OUT = TRACK / "benchmark_e2e" / "results"
FRONTEND = TRACK / "frontend_demo_data"


@pytest.fixture(scope="module")
def refs():
    return load_references(SAMPLES)


def asset(reference, format="dxf"):
    d = reference.sample
    return originals(SAMPLES / d["subset"] / d["id"])[format]


def test_formula_and_zero_denominators():
    assert composite_accuracy(.95, .9, .8) == pytest.approx(.895)
    assert composite_accuracy(None, .9, .8) is None
    assert summarize([]) is None
    summary = summarize([{"counts": {"symbol_fn": 2, "edge_fn": 1, "spec_expected": 2},
                          "timing": None, "compliance_run": False}])
    assert summary["symbol"]["f1"] == summary["edge"]["f1"] == summary["composite"] == 0
    assert summary["symbol"]["precision"] is None
    assert summary["compliance"] is None
    assert summary["pipeline_core_defect_recall"] is None
    no_rules = summarize([{"counts": {"core_defects_expected": 5},
                           "timing": None, "compliance_run": False}])
    assert no_rules["pipeline_core_defect_recall"] == 0
    assert no_rules["compliance"] is None


def test_bom_two_metrics_are_independent_of_hidden_part_number():
    visible = {"class_code":"QF","tag":"QF1","spec":"In=80A 3P","qty":1,"unit":"台",
               "anchors":[{"instance_id":"prediction"}],"model":""}
    reference = visible | {"bom_letter":"QF","qty":"1","model":"catalog-no","instance_id":"true-id"}
    assert _bom_detail([visible,visible],[reference],{"prediction":"true-id"}) == 1
    assert _summarized([visible],by_model=True) != _summarized([reference],by_model=True)
    assert _summarized([visible],by_model=False) == _summarized([reference],by_model=False)
    assert _summarized([visible,visible],by_model=False) != _summarized([reference],by_model=False)
    mismatch = visible | {"spec": "In=63A 3P"}
    absent = visible | {"spec": ""}
    assert _bom_detail([mismatch,absent],[reference],{"prediction":"true-id"}) == 0
    assert _bom_detail([visible | {"tag":"?"}],[reference],{"prediction":"true-id"}) == 1
    assert _bom_detail([visible | {"tag":"?"}],[reference],{}) == 0
    assert _bom_detail([visible | {"qty":2}],[reference],{"prediction":"true-id"}) == 0
    equivalent = visible | {"spec":"80A 3极"}
    assert _summarized([equivalent],by_model=False) == _summarized([reference],by_model=False)


def test_spec_equivalence_preserves_required_ratings():
    assert spec_semantic("QF","塑壳断路器 100A/80A 3极","",{"In_A":80,"frame_A":100,"poles":"3P"})
    assert spec_semantic("QF","In=80A 3极 Icu=36kA","In=80A 3P Icu=36kA")
    assert not spec_semantic("QF","In=80A 3P Icu=36kA","In=80A 3P Icu=25kA")
    assert not spec_semantic("QF","In=80A 3P Icu=36kA","In=80A 3P")
    assert not spec_semantic("M","7kW 380V 4P","",{"kW":7})


def test_no_truth_files_or_network_inside_inference(refs, tmp_path):
    path = asset(next(r for r in refs if r.sample["subset"] == "primary"))
    unlabeled = tmp_path / "neutral.dxf"
    unlabeled.write_bytes(path.read_bytes())
    forbidden = tmp_path/"annotations.json"
    forbidden.write_text('{"unused": true}',encoding="utf-8")
    seen = []

    def parser(staged):
        from symbol_parser.engine import parse_drawing
        assert staged.name == "drawing.dxf"
        assert set(p.name for p in staged.parent.iterdir()) == {"drawing.dxf"}
        assert staged.read_bytes() == unlabeled.read_bytes()
        seen.append(staged.name)
        with pytest.raises(RuntimeError,match="scoring-only"):
            forbidden.read_bytes()
        with pytest.raises(RuntimeError,match="offline"):
            import socket
            socket.getaddrinfo("example.invalid",443)
        return parse_drawing(staged)

    with offline_inference():
        r = predict(unlabeled, parser=parser)
    assert seen and r["symbols"]
    assert forbidden.is_file()
    for candidate in (forbidden, tmp_path/"bom.csv"):
        with pytest.raises(ValueError,match="original"):
            predict(candidate)
    fake = tmp_path/"fake.dxf"
    fake.write_text('{"instances":[]}',encoding="utf-8")
    with pytest.raises(ValueError,match="format"):
        with source_only(fake):
            pass


def test_bus_spec_uses_near_edge_and_visible_unclaimed_text():
    def bus(node, y):
        return {"id": node, "class_code": "WB", "specs": {}, "bbox_top_left": [0,y,100,2]}

    first, second, absent = bus("one",25), bus("two",80), bus("three",150)
    taken = {"text":"LMY", "bbox_top_left":[4,75,12,2]}
    distant = {"text":"TMY","bbox_top_left":[3,177,12,2]}
    nearby = {"text":"TMY 80×8","bbox_top_left":[4,23,12,2]}
    other = {"id":"p","class_code":"QF","specs":{},"evidence":{"spec":taken}}
    sheet = {"symbols":[first,second,absent,other], "source_text":[nearby,taken,distant],
             "coordinate_space":{}}
    _bind_bus_specs(sheet)
    assert first["specs"]["spec"] == "TMY 80×8"
    assert first["evidence"]["spec"]["bbox_top_left"] == nearby["bbox_top_left"]
    assert second["specs"] == absent["specs"] == {}


def test_raster_enhancement_is_path_independent_and_shared(refs, tmp_path):
    blur = next(r for r in refs if (r.sample.get("degradation") or {}).get("type") == "blur")
    original = asset(blur, "png")
    signature = sha256(original.read_bytes()).hexdigest()
    renamed = tmp_path / "neutral.png"
    renamed.write_bytes(original.read_bytes())
    with Image.open(original) as image:
        size = image.size

    paths = []
    def parser(staged):
        paths.append(staged)
        with Image.open(staged) as image:
            assert image.size == size
        return {"sheets": [{"id":"raster","symbols":[],"source_text":[],"channel":"raster",
                            "coordinate_space":{"width":size[0],"height":size[1],"stencil_pixels_per_mm":4}}]}

    def topology(staged, sheet):
        assert staged == paths[-1]
        return {"nodes":[],"edges":[]}

    with offline_inference():
        result = predict(renamed, parser=parser, topology=topology, kg=False)
    assert result["raster_preprocessing"]["applied"]
    assert sha256(original.read_bytes()).hexdigest() == sha256(renamed.read_bytes()).hexdigest() == signature
    for ref in refs:
        if ref.sample["subset"] == "degraded":
            continue
        with source_only(asset(ref, "png")) as staged:
            selected, evidence = prepare_raster(staged)
            assert selected == staged and not evidence["applied"]


@pytest.mark.parametrize("subset",["primary","secondary"])
def test_real_native_adapter_path_and_determinism(refs, subset):
    ref = next(r for r in refs if r.sample["subset"] == subset)
    source = asset(ref)
    with offline_inference():
        first = execute(source,LANES[0])
        second = execute(source,LANES[0])
    a, _ = score(first,ref)
    b, _ = score(second,ref)
    assert a == b and a["symbol_tp"] > 0 and a["edge_tp"] > 0 and a["bom_detail_tp"] > 0
    assert set(first["annotation"]) >= {"sheet","instances","netlist","bom","bom_summary"}
    assert first["compliance"]["counts"]["error"] == 0
    ids = {item["id"] for item in first["annotation"]["instances"]}
    assert all({edge["source"],edge["target"]} <= ids for edge in first["graph"]["edges"])
    assert first["annotation"]["sheet"]["height_mm"] > 0
    assert all(item["bbox_px"] and item["bbox_mm"] for item in first["annotation"]["instances"])


def test_semantic_repair_from_real_inference(refs):
    ref = next(r for r in refs if any(f["rule_id"] == "interlock_missing" for f in r.sample["defects"]))
    with offline_inference():
        prediction = execute(asset(ref),LANES[0])
    errors = [f for f in prediction["compliance"]["findings"] if f["severity"] == "error"]
    assert len(errors) == 2 and all(f["bbox_px"] for f in errors)
    repaired = preview_fix(prediction,errors[0])
    assert repaired["counts"]["error"] == 1


def test_partial_ampacity_evidence(refs):
    ref = next(r for r in refs if any(f["rule_id"] == "ampacity_insufficient" for f in r.sample["defects"]))
    with offline_inference():
        prediction = execute(asset(ref),LANES[0])
    counts, _ = score(prediction,ref)
    assert counts["ampacity_insufficient_tp"] == 1
    errors = [f for f in prediction["compliance"]["findings"] if f["rule_id"] == "ampacity_insufficient"]
    assert len(errors) == 1
    finding = errors[0]
    assert finding["evidence"]["Ib_A"] is None
    assert finding["evidence"]["In_A"] > finding["evidence"]["Iz_A"]
    assert not finding["fix_suggestion"]["operations"]
    cable = next(i for i in prediction["annotation"]["instances"] if i["id"] == finding["instance_ids"][1])
    cable["specs"]["Iz_A"] = finding["evidence"]["In_A"]+1
    assert not any(f["rule_id"] == "ampacity_insufficient" for f in evaluate(prediction["annotation"])["findings"])


def test_vlm_pending_and_offline_input_contract(monkeypatch, refs, tmp_path):
    for var in ("TRACK01_VLM_ENDPOINT","TRACK01_VLM_MODEL","TRACK01_VLM_TOKEN"):
        monkeypatch.delenv(var,raising=False)
    assert OpenAICompatibleVision.from_environment() is None
    assert load_predictions(None) == {"status":PENDING,"predictions":{}}
    with pytest.raises(ValueError,match="reference files"):
        load_predictions(tmp_path/"annotations.json")
    ref = refs[0]
    image = asset(ref,"png")
    with Image.open(image) as png:
        width,height = png.size
    external = {"drawing_id":ref.sample["id"],"image_width":width,"image_height":height,
                "symbols":[],"edges":[],"bom_items":[],"findings":[]}
    path = tmp_path/"external.json"
    path.write_text(json.dumps({"schema_version":"1.0.0","predictions":[external]}),encoding="utf-8")
    imported = load_predictions(path)
    assert imported["status"] == "scored_predictions"
    observed = to_prediction(imported["predictions"][ref.sample["id"]],image)
    c, _ = score(observed,ref)
    assert c["symbol_tp"] == 0 and c["symbol_fn"] > 0
    assert observed["timing"] is None


def test_workbench_csv_schema_alignment():
    with (FRONTEND/"eval_charts_workbench.csv").open(encoding="utf-8-sig",newline="") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames) == WORKBENCH_FIELDS
        points = list(reader)
    assert points
    for chart in {r["chart_id"] for r in points}:
        rows = [r for r in points if r["chart_id"] == chart]
        labels = {r["category"] for r in rows}
        ceilings = {}
        for series in {r["series"] for r in rows}:
            subset = [r for r in rows if r["series"] == series]
            assert len(subset) == len(labels) and {r["category"] for r in subset} == labels
            for r in subset:
                assert all(r[k] for k in WORKBENCH_FIELDS)
                assert 0 <= float(r["value"]) <= float(r["maximum"])
                maximum = ceilings.setdefault(r["category"],float(r["maximum"]))
                assert float(r["maximum"]) == maximum
        if rows[0]["kind"] == "radar":
            assert len(labels) >= 3 and set(ceilings.values()) == {100.0}
            assert labels == set(METRIC_NAMES)


@pytest.mark.parametrize("filename",["fig1_baseline_comparison.png","fig2_ablation_contribution.png",
                                    "fig3_subset_heatmap_latency.png","fig4_error_attribution.png"])
def test_result_figure_is_high_resolution(filename):
    path = OUT/"figures"/filename
    assert path.stat().st_size > 10_000 and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    with Image.open(path) as image:
        assert min(image.size) > 900 and image.info["dpi"][0] == pytest.approx(300,abs=.05)
        image.verify()


def test_checked_in_report_preserves_scopes_and_vlm_state():
    result = json.loads((OUT/"eval_summary.json").read_bytes())
    assert result["lanes"]["full"]["all"]["drawings"] == 14
    assert result["lanes"]["full"]["degraded"]["drawings"] == 3
    for lane in ("full","dxf","png","pdf","b1","b2","no_topology","no_kg"):
        assert result["lanes"][lane]["main"]["drawings"] == 11
    assert len(result["error_analysis"]["cases"]) >= 5
    for case in result["error_analysis"]["compliance_cases_by_lane"]:
        assert case["lane"] and case["drawing_id"] and case["cause"]
        assert case["predicted"] is not None or case["expected"] is not None
    assert result["vlm_baseline"]["status"] == PENDING
    assert result["lanes"]["b3"]["main"] is None
    assert not [r for r in result["per_drawing"] if r["lane"] == "b3"]
    if "repeatability" in result:
        repeat = result["repeatability"]
        assert repeat["non_timing_metrics_identical"] and repeat["runs"] == 2
        assert repeat["canonical_metrics_sha256"] == sha256(canonical_metrics_bytes(result)).hexdigest()
    assert all(result["acceptance"].values())
    for key in METRICS:
        b1, b2, full = (metric(result["lanes"][lane]["main"], key) for lane in ("b1","b2","full"))
        assert b1 < b2 < full, key
    assert next(r for r in result["ablation_comparison"] if r["lane"]=="no_kg")["delta_pipeline_core_defect_recall"] == 1
    blur = next(r for r in result["raster_recovery"] if r["degradation"] == "blur")
    for key in ("symbol_tp","spec_semantic_correct","bom_detail_tp"):
        assert blur["enhanced_counts"][key] > blur["raw_counts"].get(key, 0)
