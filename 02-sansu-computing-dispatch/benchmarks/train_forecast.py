"""Fit on independent synthetic weeks and select by chronological validation windows."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch
from backend.models import Forecaster, SCALE, WEIGHTS, pack_history
from backend.world import SCENARIOS, Trace


def windows(seeds):
    xs, ys = [], []
    for seed in seeds:
        for scene in SCENARIOS:
            tr = Trace(seed, scene, 120)
            for h in range(0, 97, 3):
                xs.append(pack_history(tr.history_at(h)))
                y = tr.series[48+h:72+h]/SCALE
                ys.append(y.transpose(1,2,0))
    return tuple(torch.from_numpy(np.concatenate(items)) for items in (xs,ys))


def metrics(model, data):
    x, y = data
    with torch.no_grad():
        pred = model(x).numpy().reshape(-1,16,2,24)*SCALE[None,:,:,None]
    target = y.numpy().reshape(-1,16,2,24)*SCALE[None,:,:,None]
    report = {}
    for i, name in enumerate(("arrivals_jobs_per_hour","renewable_peak_fraction")):
        truth = target[:,:,i]
        err = abs(pred[:,:,i]-truth)
        positive = truth > 1e-6
        report[name] = dict(mae=float(err.mean()), mape_pct=float(
            100*(err[positive]/truth[positive]).mean()),nonzero_targets=int(positive.sum()))
    return report


if __name__ == "__main__":
    torch.set_num_threads(1)
    torch.manual_seed(268)
    train, valid = windows([41,42,43]), windows([72])
    model = Forecaster()
    opt = torch.optim.AdamW(model.parameters(), lr=.003)
    best = float("inf")
    WEIGHTS.mkdir(exist_ok=True)
    for epoch in range(18):
        for ix in torch.randperm(len(train[0])).split(256):
            loss = torch.nn.functional.smooth_l1_loss(model(train[0][ix]),train[1][ix])
            opt.zero_grad()
            loss.backward()
            opt.step()
        with torch.no_grad():
            val = (model(valid[0])-valid[1]).abs().mean().item()
        if val < best:
            best = val
            torch.save(model.state_dict(),WEIGHTS/"forecast.pt")
    model.load_state_dict(torch.load(WEIGHTS/"forecast.pt", weights_only=True))
    stats = {"train_seeds":[41,42,43],"validation_seeds":[72],"epochs":18,
             "train":metrics(model,train),"validation":metrics(model,valid)}
    (WEIGHTS/"forecast_metrics.json").write_text(json.dumps(stats,indent=2)+"\n",newline="\n")
    print(stats)
