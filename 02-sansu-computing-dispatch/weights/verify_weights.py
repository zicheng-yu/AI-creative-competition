"""Check the release manifest, forecast shape and Torch/ONNX CPU logit parity."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np
import onnx
import onnxruntime as ort
import torch
from backend.models import ActorCritic, FEATURES, Forecaster, WEIGHTS, forecast, load_model

ARTIFACTS = {"policy.pt":"PPO actor and critic state_dict",
             "forecast.pt":"seasonal residual TCN state_dict",
             "policy.onnx":"portable actor logits, opset 17",
             "forecast_metrics.json":"independent train/validation MAE and positive-target MAPE",
             "ppo_training.csv":"on-policy sample reward, violation rate and projected multiplier"}


def metadata():
    return dict(version=2,format="state_dict (CPU) / ONNX opset 17",
                forecast=dict(input="[16,4,24] scaled counts and renewable fractions at lag 48/24",
                              output="[16,2,24]",parameters=sum(p.numel() for p in Forecaster().parameters())),
                policy=dict(input="[batch,96,15] node-major, pool-minor",features=FEATURES,
                            output="raw actor logits; add backend.models.dispatch_bias, then apply feasibility mask",
                            parameters=sum(p.numel() for p in ActorCritic().parameters())),
                files=[dict(path=name,description=desc,size=(WEIGHTS/name).stat().st_size,
                            sha256=hashlib.sha256((WEIGHTS/name).read_bytes()).hexdigest())
                       for name,desc in ARTIFACTS.items()])


def verify():
    manifest = json.loads((WEIGHTS/"manifest.json").read_text())
    if json.loads(json.dumps(metadata()))!=manifest:
        raise ValueError("mismatched release manifest")
    size = sum(p.stat().st_size for p in WEIGHTS.iterdir() if p.is_file())
    if size>=15_000_000:
        raise ValueError("weight package exceeds 15 MB")
    onnx.checker.check_model(str(WEIGHTS/"policy.onnx"))
    rng = np.random.default_rng(313)
    x = rng.normal(size=(3,96,len(FEATURES))).astype("float32")
    with torch.inference_mode():
        pyt = load_model("policy")(torch.from_numpy(x)).numpy()
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    rt = ort.InferenceSession(str(WEIGHTS/"policy.onnx"),options,providers=["CPUExecutionProvider"])
    pred = rt.run(None,{"candidates":x})[0]
    np.testing.assert_allclose(pred,pyt,rtol=2e-5,atol=4e-6)
    future = forecast(load_model("forecast"),rng.random((48,16,2),dtype="float32"))
    if future.shape!=(24,16,2) or not np.isfinite(future).all() or future.min()<0:
        raise ValueError("invalid forecast")
    print(f"Verified {len(manifest['files'])} hashes, {size} bytes; max logit error "
          f"{abs(pred-pyt).max():.3g}; forecast {future.shape}")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--release",action="store_true",help="regenerate manifest after retraining")
    if p.parse_args().release:
        (WEIGHTS/"manifest.json").write_text(json.dumps(metadata(),indent=2)+"\n",newline="\n")
    verify()
