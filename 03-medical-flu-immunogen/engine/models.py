"""Load frozen ONNX classifiers on local CPU, with manifest integrity checks."""
import json
from pathlib import Path

import numpy as np

from .capsules import digest
from .text_features import FEATURES, pair_features


WEIGHTS = Path(__file__).resolve().parent.parent / "weights"
LABELS = {"reranker": ("IRRELEVANT", "RELEVANT"),
          "nli_auditor": ("ENTAIL", "CONTRADICT", "UNSUPPORTED")}


class TextModels:
    def __init__(self, directory: Path = WEIGHTS):
        import onnxruntime as ort

        manifest = json.loads((directory / "manifest.json").read_bytes())
        self.sessions = {}
        options = ort.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1
        for model, labels in LABELS.items():
            info = manifest["models"][model]
            if info["features"] != list(FEATURES) or info["labels"] != list(labels):
                raise ValueError("model feature or class order mismatch")
            payload = (directory / f"{model}.onnx").read_bytes()
            if digest(payload) != info["files"][f"{model}.onnx"]["sha256"]:
                raise ValueError("ONNX digest mismatch")
            self.sessions[model] = ort.InferenceSession(payload, sess_options=options,
                                                        providers=["CPUExecutionProvider"])

    def probabilities(self, model: str, pairs: list[tuple[str, str]]) -> np.ndarray:
        if not pairs:
            return np.empty((0, len(LABELS[model])), dtype=np.float32)
        array = np.asarray([pair_features(*pair) for pair in pairs], dtype=np.float32)
        logits, = self.sessions[model].run(None, {"features": array})
        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        return exp / exp.sum(axis=1, keepdims=True)

    def relevance(self, query: str, texts: list[str]) -> list[float]:
        return self.probabilities("reranker", [(query, text) for text in texts])[:, 1].tolist()

    def nli(self, pairs: list[tuple[str, str]]) -> list[dict[str, float]]:
        return [dict(zip(LABELS["nli_auditor"], map(float, row)))
                for row in self.probabilities("nli_auditor", pairs)]
