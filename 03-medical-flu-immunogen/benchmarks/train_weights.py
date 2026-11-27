"""Fit and export two CPU text classifiers using explicitly synthetic examples."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from torch import nn

from benchmarks.metrics import classification, ndcg
from benchmarks.text_corpus import DOMAINS, samples
from engine.capsules import canonical, digest
from engine.models import LABELS, WEIGHTS
from engine.text_features import FEATURES, pair_features


SEED = 2706
SPLITS = ("train", "validation", "test")
HIDDEN = 24


def model_for(class_count: int) -> nn.Module:
    return nn.Sequential(nn.Linear(len(FEATURES), HIDDEN), nn.ReLU(), nn.Linear(HIDDEN, class_count))


def encode(rows):
    return (torch.tensor([pair_features(row.left, row.right) for row in rows], dtype=torch.float32),
            torch.tensor([row.label for row in rows], dtype=torch.int64))


def score(model, data, rows, labels, *, threshold: float | None = None) -> dict:
    with torch.inference_mode():
        x, y = data
        logits = model(x)
        probabilities = logits.softmax(1)[:, 1].tolist()
        predictions = (logits.argmax(1).tolist() if threshold is None
                       else [int(p >= threshold) for p in probabilities])
        result = classification(y.tolist(), predictions, labels)
    if threshold is not None:
        result["decision_threshold"] = threshold
        groups = defaultdict(list)
        for row, probability in zip(rows, probabilities):
            groups[row.group].append((probability, row.label))
        result["ndcg_at_3"] = sum(ndcg([v for _, v in sorted(group, key=lambda x: -x[0])],
                                      sorted((v for _, v in group), reverse=True), 3)
                                  for group in groups.values()) / len(groups)
    return result


def fit(name: str, directory: Path) -> dict:
    torch.manual_seed(SEED)
    labels = LABELS[name]
    rows = {split: samples(name, split) for split in SPLITS}
    pairs = {split: {(row.left, row.right) for row in records} for split, records in rows.items()}
    if any(pairs[a] & pairs[b] for i, a in enumerate(SPLITS) for b in SPLITS[i + 1:]):
        raise ValueError("corpus overlap across splits")
    data = {split: encode(value) for split, value in rows.items()}
    model = model_for(len(labels))
    opt = torch.optim.AdamW(model.parameters(), lr=0.025)
    train_x, train_y = data["train"]
    val_x, val_y = data["validation"]
    weights = len(train_y) / (len(labels) * torch.bincount(train_y))
    loss = nn.CrossEntropyLoss(weight=weights)
    best = (float("inf"), None, 0)
    for epoch in range(1, 221):
        opt.zero_grad()
        loss(model(train_x), train_y).backward()
        opt.step()
        with torch.inference_mode():
            validation = loss(model(val_x), val_y).item()
        if validation < best[0]:
            best = (validation, {k: v.clone() for k, v in model.state_dict().items()}, epoch)
    model.load_state_dict(best[1])
    model.eval()
    threshold = None
    if name == "reranker":
        with torch.inference_mode():
            val_scores = model(val_x).softmax(1)[:, 1].tolist()
        candidates = sorted(set(val_scores) | {0.5, 1.0})
        threshold = max(candidates, key=lambda t: (
            classification(val_y.tolist(), [int(p >= t) for p in val_scores], labels)["macro_f1"],
            -abs(t - 0.5),
        ))
    paths = {suffix: directory / f"{name}.{suffix}" for suffix in ("pt", "onnx")}
    torch.save(model.state_dict(), paths["pt"])
    torch.onnx.export(
        model, train_x[:2], str(paths["onnx"]), opset_version=17, dynamo=False,
        input_names=["features"], output_names=["logits"],
        dynamic_axes={"features": {0: "batch"}, "logits": {0: "batch"}},
    )
    return {
        "labels": list(labels), "features": list(FEATURES),
        "parameters": sum(param.numel() for param in model.parameters()),
        "chosen_epoch": best[2], "validation_loss": best[0],
        "corpus": {split: {"examples": len(rows[split]), "domains": sorted(DOMAINS[split]),
                           "sha256": digest(canonical([r.__dict__ for r in rows[split]]))}
                   for split in SPLITS},
        "metrics": {split: score(model, data[split], rows[split], labels, threshold=threshold)
                    for split in ("validation", "test")},
        "files": {path.name: {"sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}
                  for path in paths.values()},
    }


def train(directory: Path) -> dict:
    import onnx

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "format_version": 1, "seed": SEED, "corpus_nature": "synthetic only; domain and template held out",
        "runtime": {"torch": torch.__version__, "numpy": np.__version__, "onnx": onnx.__version__},
        "models": {model: fit(model, directory) for model in LABELS},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=WEIGHTS)
    manifest = train(parser.parse_args().output)
    print(json.dumps({k: {"parameters": v["parameters"], "test": v["metrics"]["test"]}
                      for k, v in manifest["models"].items()}, indent=2))
