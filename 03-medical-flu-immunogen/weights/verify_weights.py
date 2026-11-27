"""Verify all weight members and compare PyTorch and ONNX CPU predictions."""
import argparse
import json
import sys
from pathlib import Path
from time import perf_counter_ns

if __package__ in ("", None):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import onnx
import onnxruntime as ort
import torch

from benchmarks.text_corpus import samples
from benchmarks.train_weights import encode, model_for
from engine.capsules import digest
from engine.models import LABELS, WEIGHTS, TextModels


def median_ms(run, iterations: int = 200) -> float:
    for _ in range(10):
        run()
    durations = []
    for _ in range(iterations):
        start = perf_counter_ns()
        run()
        durations.append((perf_counter_ns() - start) / 1e6)
    return float(np.median(durations))


def verify(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_bytes())
    runtime = TextModels(directory)
    torch.set_num_threads(1)
    total = 0
    results = {}
    for name, labels in LABELS.items():
        info = manifest["models"][name]
        expected = {f"{name}.{suffix}" for suffix in ("pt", "onnx")}
        if set(info["files"]) != expected:
            raise ValueError("unexpected weight files in manifest")
        for filename in sorted(expected):
            raw = (directory / filename).read_bytes()
            member = info["files"][filename]
            if digest(raw) != member["sha256"] or len(raw) != member["bytes"]:
                raise ValueError(f"weight verification failed: {filename}")
            total += len(raw)
        onnx.checker.check_model(str(directory / f"{name}.onnx"))
        model = model_for(len(labels))
        model.load_state_dict(torch.load(directory / f"{name}.pt", map_location="cpu", weights_only=True))
        model.eval()
        if sum(p.numel() for p in model.parameters()) != info["parameters"]:
            raise ValueError(f"parameter count mismatch: {name}")
        held_out, _ = encode(samples(name, "test"))
        inputs = held_out.numpy()
        session = runtime.sessions[name]
        single = {"features": inputs[:1]}
        with torch.inference_mode():
            expected_logits = model(held_out).numpy()
            actual_logits, = session.run(None, {"features": inputs})
            np.testing.assert_allclose(actual_logits, expected_logits, atol=1e-5, rtol=1e-5)
            np.testing.assert_array_equal(actual_logits.argmax(1), expected_logits.argmax(1))
            results[name] = {
                "held_out_rows": len(inputs), "max_abs_logit_error": float(np.abs(actual_logits - expected_logits).max()),
                "pytorch_cpu_median_ms": median_ms(lambda: model(held_out[:1])),
                "onnx_cpu_median_ms": median_ms(lambda: session.run(None, single)),
            }
    if total >= 15_000_000:
        raise ValueError("combined weights exceed the size target")
    return {"weight_bytes": total, "onnxruntime": ort.__version__, "models": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=WEIGHTS)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = json.dumps(verify(args.directory), indent=2) + "\n"
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    print(report, end="")
