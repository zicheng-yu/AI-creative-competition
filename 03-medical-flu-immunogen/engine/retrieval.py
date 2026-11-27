"""Three local recall routes, reciprocal-rank fusion and text-model reranking."""
import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .capsules import EvidenceCapsule, EvidenceKey, Snapshot
from .models import TextModels
from .provenance import ProvenanceGraph
from .text_features import dense_vector, words


@dataclass
class Retrieval:
    records: list[EvidenceCapsule]
    hits: list[dict]
    route_counts: dict[str, int]


class EvidenceIndex:
    def __init__(self, snapshot: Snapshot, models: TextModels):
        self.snapshot = snapshot
        self.model = models
        self.graph = ProvenanceGraph(snapshot)
        self.keys = sorted(snapshot.records)
        self.documents = {}
        self.texts = {}
        self.frequency = Counter()
        for key in self.keys:
            record, metadata = snapshot.records[key], snapshot.metadata[key]
            self.texts[key] = f"{metadata.title} {record.claim_summary} {record.raw_snippet}"
            self.documents[key] = Counter(words(" ".join(
                (self.texts[key], record.primary_ref, key[1], *metadata.topics)
            )))
            self.frequency.update(set(self.documents[key]))
        self.vectors = np.stack([dense_vector(self.texts[key]) for key in self.keys])
        self.average_length = sum(c.total() for c in self.documents.values()) / len(self.keys) or 1.0

    def _bm25(self, query: str, depth: int) -> list[EvidenceKey]:
        query_terms = set(words(query))
        scores = []
        for key, counts in self.documents.items():
            denominator = 1.2 * (0.25 + 0.75 * counts.total() / self.average_length)
            score = math.fsum(
                math.log1p((len(self.keys) - self.frequency[term] + 0.5) /
                           (self.frequency[term] + 0.5))
                * counts[term] * 2.2 / (counts[term] + denominator)
                for term in sorted(query_terms & counts.keys())
            )
            if score > 0:
                scores.append((-score, key))
        return [key for _, key in sorted(scores)[:depth]]

    def retrieve(self, query: str, limit: int, hops: int = 2) -> Retrieval:
        depth = max(12, 3 * limit)
        lexical = self._bm25(query, depth)
        dense_score = self.vectors @ dense_vector(query)
        dense = [key for score, key in sorted(zip(-dense_score, self.keys))[:depth] if score < -0.12]
        query_terms = set(words(query))
        nodes = []
        for kind, name, *rest in self.graph.graph:
            if kind == "document" and name.casefold() in query_terms:
                nodes.append((kind, name))
            elif kind == "topic" and set(words(name)) <= query_terms:
                nodes.append((kind, name))
            elif kind == "snapshot" and name.casefold() in query_terms:
                nodes.append((kind, name))
        nodes.extend(("evidence", *key) for key in lexical[:2])
        hops_by_key = self.graph.evidence_neighbors(nodes, hops)
        graph = sorted(hops_by_key, key=lambda key: (hops_by_key[key], lexical.index(key)
                       if key in lexical else len(lexical), key))[:depth]
        routes = {"bm25": lexical, "dense": dense, "graph": graph}
        ranks: dict[EvidenceKey, dict[str, int]] = {}
        for route, keys in routes.items():
            for rank, key in enumerate(keys, 1):
                ranks.setdefault(key, {})[route] = rank
        rrf = {key: sum(1 / (60 + rank) for rank in by_route.values())
               for key, by_route in ranks.items()}
        candidates = sorted(rrf, key=lambda key: (-rrf[key], key))[:depth]
        probabilities = self.model.relevance(query, [self.texts[key] for key in candidates])
        scores = dict(zip(candidates, probabilities))
        exact = {key for key in candidates if self.snapshot.records[key].primary_ref.casefold() in query_terms}
        peak = max(rrf.values(), default=1)
        ranked = sorted(candidates, key=lambda key: (
            key not in exact, -(0.75 * rrf[key] / peak + 0.25 * scores[key]), key
        ))[:limit]
        return Retrieval([self.snapshot.records[key] for key in ranked], [{
            "evidence_id": key[0], "dataset_version": key[1], "ranks": ranks[key],
            "rrf": rrf[key], "text_relevance": scores[key], "graph_hops": hops_by_key.get(key),
        } for key in ranked], {route: len(keys) for route, keys in routes.items()})

    def search(self, query: str, limit: int) -> list[EvidenceCapsule]:
        return self.retrieve(query, limit).records

    def provenance(self, keys: Iterable[EvidenceKey], hops: int = 1) -> dict:
        return self.graph.query((("evidence", *key) for key in keys), hops)
