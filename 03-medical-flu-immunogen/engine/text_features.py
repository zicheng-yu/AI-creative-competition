"""Shared deterministic text features for training, ranking and NLI."""
import hashlib
import re
import unicodedata
from collections import Counter

import numpy as np


TOKEN = re.compile(r"[a-z0-9]+(?:[.:_-][a-z0-9]+)*|[\u3400-\u9fff]", re.I)
DIM = 384
FEATURES = (
    "query_word_coverage", "document_word_coverage", "word_jaccard", "dense_cosine",
    "character_trigram_jaccard", "length_ratio", "exact_normalized_text", "negation_mismatch",
    "shared_numbers", "different_numbers", "same_first_word", "word_order_bigram_overlap",
)
NEGATION = {"no", "not", "never", "without", "neither", "none", "禁止", "没有", "不"}
CONCEPTS = {
    "archiving": "archive", "repository": "archive", "repositories": "archive",
    "curation": "stewardship", "governance": "stewardship",
    "repeatable": "reproducible", "reproducibility": "reproducible",
    "protocols": "protocol", "registration": "protocol",
    "reviewing": "review", "reviewed": "review", "reviews": "review",
    "documentation": "reporting", "report": "reporting", "reports": "reporting",
    "verification": "audit", "auditing": "audit",
    "guidance": "guidelines", "principles": "guidelines",
}


def words(text: str) -> list[str]:
    return TOKEN.findall(unicodedata.normalize("NFKC", text).casefold())


def grams(parts: list[str], size: int) -> set[str]:
    text = " ".join(parts)
    return {text[i:i + size] for i in range(len(text) - size + 1)}


def dense_vector(text: str) -> np.ndarray:
    terms = words(text)
    concepts = [CONCEPTS.get(term, term) for term in terms]
    vector = np.zeros(DIM, dtype=np.float32)
    for term, count in Counter(concepts).items():
        index = int.from_bytes(hashlib.blake2s(term.encode(), digest_size=4).digest(), "little")
        vector[index % DIM] += np.log1p(count) * (1 if index & 512 else -1)
    for gram in sorted(grams(concepts, 3)):
        index = int.from_bytes(hashlib.blake2s(gram.encode(), digest_size=4).digest(), "little")
        vector[index % DIM] += 0.12 * (1 if index & 512 else -1)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def pair_features(left: str, right: str) -> list[float]:
    a, b = words(left), words(right)
    sa, sb = set(a), set(b)
    common = len(sa & sb)
    ga, gb = grams(a, 3), grams(b, 3)
    na, nb = set(re.findall(r"\d+", left)), set(re.findall(r"\d+", right))
    ba, bb = set(zip(a, a[1:])), set(zip(b, b[1:]))
    return [
        common / max(len(sa), 1), common / max(len(sb), 1),
        common / max(len(sa | sb), 1), float(dense_vector(left) @ dense_vector(right)),
        len(ga & gb) / max(len(ga | gb), 1), min(len(a), len(b)) / max(len(a), len(b), 1),
        float(bool(a) and a == b), float(bool(sa & NEGATION) != bool(sb & NEGATION)),
        float(bool(na & nb)), float(bool(na and nb and na != nb)),
        float(bool(a and b and a[0] == b[0])), len(ba & bb) / max(len(ba | bb), 1),
    ]
