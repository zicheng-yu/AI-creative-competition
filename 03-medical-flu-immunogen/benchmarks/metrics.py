"""Small deterministic metrics used by both training and software evaluation."""
import math

import numpy as np


def ndcg(order: list[int], ideal: list[int], k: int) -> float:
    def gain(values):
        return sum((2 ** grade - 1) / math.log2(i + 2) for i, grade in enumerate(values[:k]))
    maximum = gain(ideal)
    return gain(order) / maximum if maximum else 0.0


def classification(y: list[int], predictions: list[int], labels: tuple[str, ...]) -> dict:
    gold, pred = np.asarray(y), np.asarray(predictions)
    classes = {}
    for index, name in enumerate(labels):
        support = int((gold == index).sum())
        predicted = int((pred == index).sum())
        tp = int(((gold == index) & (pred == index)).sum())
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        classes[name] = {"support": support, "precision": precision, "recall": recall,
                         "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
    return {"per_class": classes, **{f"macro_{name}": sum(row[name] for row in classes.values()) / len(classes)
                                    for name in ("precision", "recall", "f1")}}
