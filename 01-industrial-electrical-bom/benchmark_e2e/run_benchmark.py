"""Reproduce the offline Track 01 benchmark and workbench exports."""

from argparse import ArgumentParser
from contextlib import contextmanager
from contextvars import ContextVar
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import platform
import sys

from .adapter import SCORING_FILES
from .baselines import LANES, asset_for, execute, originals
from .error_analysis import aggregate, drawing_errors
from .metrics import load_references, score, summarize
from .vlm_baseline import load_predictions, to_prediction

TRACK = Path(__file__).resolve().parents[1]
UPSTREAM = {
    "4": "a5e0e28bafd3d8a8b1356bbf8c510ee26194ed35",
    "5": "91b6adaaf4f249126bd66af06c3c13566989d906",
    "8": "28ace34225bf182b81753c6c70b739f0797f8963",
    "9": "fcb266c85350a65ff3e128989407cad7e7ca281c",
}
GUARD = ContextVar("benchmark_inference_guard", default=False)


def _audit(event, args):
    if not GUARD.get():
        return
    if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "subprocess.Popen"}:
        raise RuntimeError(f"offline benchmark inference attempted {event}")
    if event == "open" and isinstance(args[0], (bytes, str)):
        name = args[0].decode(errors="replace") if isinstance(args[0], bytes) else args[0]
        if Path(name).name.lower() in SCORING_FILES:
            raise RuntimeError("inference attempted to open a scoring-only file")


sys.addaudithook(_audit)


@contextmanager
def offline_inference():
    token = GUARD.set(True)
    try:
        yield
    finally:
        GUARD.reset(token)


def _row(lane_id, sample, asset, prediction, ref):
    counts, matched = score(prediction, ref)
    return {"lane": lane_id, "drawing_id": sample["id"], "subset": sample["subset"],
            "degradation": (sample.get("degradation") or {}).get("type"),
            "format": asset.suffix[1:], "channel": prediction["channel"], "counts": dict(counts),
            "compliance_run": prediction["compliance"] is not None, "timing": prediction["timing"],
            "warnings": prediction["warnings"]}, matched


def _supported(lane, sample):
    degraded = sample["subset"] == "degraded"
    return lane.scope == "all" or ((lane.scope == "degraded") == degraded)


def _runtime():
    dependencies = {}
    for package in ("numpy","scipy","ezdxf","matplotlib","rapidocr","onnxruntime","PyMuPDF","networkx","pillow"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = None
    return {"python": platform.python_version(), "platform": platform.platform(),
            "architecture": platform.machine(), "packages": dependencies}


def _working_groups(values):
    return {"main": summarize([r for r in values if r["subset"] != "degraded"]),
            "all": summarize(values),
            "degraded": summarize([r for r in values if r["subset"] == "degraded"]),
            **{subset: summarize([r for r in values if r["subset"] == subset])
               for subset in ("primary","secondary","defect")}}


def collect_compliance_error(target, row, prediction, reference, matches):
    """Preserve cause evidence from the same inputs scored for each lane."""
    if not row["compliance_run"] or not any(
        row["counts"].get(key) for key in ("compliance_fp","compliance_fn","extra_red")
    ):
        return
    analysis = drawing_errors(prediction, reference, matches)
    target.extend(case | {"lane": row["lane"]} for case in analysis["cases"] if case["stage"] == "compliance")


def benchmark(samples, *, predictions_path=None, progress=None):
    references = load_references(samples)
    vlm = load_predictions(predictions_path)
    vlm_rows = vlm["predictions"]
    unknown_vlm = vlm_rows.keys() - {ref.sample["id"] for ref in references}
    if unknown_vlm:
        raise ValueError(f"unexpected VLM drawing ids: {sorted(unknown_vlm)}")
    rows, errors, compliance_errors = [], [], []
    for reference in references:
        data = reference.sample
        assets = originals(samples / data["subset"] / data["id"])
        required = {"png"} if data["subset"] == "degraded" else {"dxf","png","pdf"}
        if not required <= assets.keys():
            raise ValueError(f"missing original files: {data['id']}: {sorted(required-assets.keys())}")
        cache = {}
        for lane in LANES:
            if not _supported(lane, data):
                continue
            asset = asset_for(lane, assets)
            if asset is None:
                raise ValueError(f"missing input for {lane.id}")
            # Full and an identical forced-format lane share the same measured
            # inference trace. Different ablations still execute independently.
            config = (asset.suffix, lane.topology, lane.kg)
            if config not in cache:
                with offline_inference():
                    cache[config] = execute(asset, lane)
            prediction = cache[config]
            if any(w.startswith("ocr_unavailable:") for w in prediction["warnings"]):
                raise RuntimeError(f"local OCR failed for {data['id']} in {lane.id}")
            row, matches = _row(lane.id, data, asset, prediction, reference)
            rows.append(row)
            if lane.id == "full":
                errors.append(drawing_errors(prediction, reference, matches))
            collect_compliance_error(compliance_errors, row, prediction, reference, matches)
        if data["id"] in vlm_rows:
            asset = assets["png"]
            prediction = to_prediction(vlm_rows[data["id"]], asset)
            row, matches = _row("b3", data, asset, prediction, reference)
            rows.append(row)
            collect_compliance_error(compliance_errors, row, prediction, reference, matches)
        if progress:
            progress(f"scored {data['id']}")
    if not all(len([r for r in rows if r["lane"] == lane]) == 11 for lane in ("dxf","pdf","no_topology","no_kg")):
        raise AssertionError("forced main-set results must each cover 11 drawings")
    lanes = {lane.id: _working_groups([r for r in rows if r["lane"] == lane.id]) |
             {"title": lane.title, "inference": {"format": lane.format, "topology": lane.topology, "kg": lane.kg}}
             for lane in LANES}
    lanes["b3"] = _working_groups([r for r in rows if r["lane"] == "b3"]) | {"title": "B3 纯 VLM"}
    primary = lanes["full"]["main"]
    thresholds = {"composite": .93, "bom_detail": .95, "bom_summary": .95, "latency_mean_s": 15.0}
    gate = {"composite_pass": primary["composite"] >= thresholds["composite"],
            "bom_detail_pass": primary["bom_detail"]["recall"] >= thresholds["bom_detail"],
            "bom_summary_pass": primary["bom_summary"]["recall"] >= thresholds["bom_summary"],
            "latency_pass": primary["timing"]["total_s"]["mean"] <= thresholds["latency_mean_s"]}
    return {"schema_version": "1.0.0", "dataset": "ElectroBench-JS v1.0.0", "upstream_commits": UPSTREAM,
            "reference_chart_contract": {"pr": 7, "sha": "a89597614d6aefae3ce4b53b2ec90187ee2f1db5"},
            "environment": _runtime(), "thresholds": thresholds, "acceptance": gate,
            "lanes": lanes, "per_drawing": rows,
            "error_analysis": aggregate(errors) | {"compliance_cases_by_lane": compliance_errors},
            "vlm_baseline": {"status": vlm["status"], "drawings": len(vlm_rows),
                             "run": "python -m benchmark_e2e.vlm_baseline --out vlm_preds.json",
                             "rescore": "python -m benchmark_e2e.run_benchmark --vlm-predictions vlm_preds.json"}}


def stable_metrics(result):
    """For repeatability ignore wall time and its derived acceptance flag."""
    from copy import deepcopy

    snapshot = deepcopy(result)
    snapshot.pop("environment", None)
    snapshot["acceptance"].pop("latency_pass", None)
    for row in snapshot["per_drawing"]:
        row.pop("timing")
    for lane in snapshot["lanes"].values():
        for group in lane.values():
            if isinstance(group, dict):
                group.pop("timing", None)
    return snapshot


def main():
    cli = ArgumentParser(description=__doc__)
    cli.add_argument("--samples", type=Path, default=TRACK / "samples")
    cli.add_argument("--output", type=Path, default=TRACK / "benchmark_e2e" / "results")
    cli.add_argument("--frontend", type=Path, default=TRACK / "frontend_demo_data")
    cli.add_argument("--vlm-predictions", type=Path)
    cli.add_argument("--verify-repeat", action="store_true", help="Run the full matrix twice and compare non-timing metrics.")
    options = cli.parse_args()
    first = benchmark(options.samples, predictions_path=options.vlm_predictions, progress=lambda s: print(s, flush=True))
    if options.verify_repeat:
        second = benchmark(options.samples, predictions_path=options.vlm_predictions)
        if stable_metrics(first) != stable_metrics(second):
            raise AssertionError("benchmark core metrics drifted across repeated runs")
        first["repeatability"] = {"non_timing_metrics_identical": True, "runs": 2}
    from .reporting import export_results

    export_results(first, options.output, options.frontend)
    overall = first["lanes"]["full"]["main"]
    print(f"Full main ({overall['drawings']} drawings): composite={overall['composite']:.2%}, "
          f"BOM detail={overall['bom_detail']['recall']:.2%}, "
          f"BOM model/spec summary={overall['bom_summary']['recall']:.2%}")


if __name__ == "__main__":
    main()
