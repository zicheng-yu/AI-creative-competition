"""Lexical evidence lookup and provenance links for a curated snapshot."""
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable

import networkx as nx

from .capsules import Snapshot


TOKEN = re.compile(r"[a-z0-9]+(?:[.:_-][a-z0-9]+)*|[\u3400-\u9fff]", re.I)


def terms(text: str) -> set[str]:
    return set(TOKEN.findall(unicodedata.normalize("NFKC", text).casefold()))


class EvidenceIndex:
    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot
        self.graph = nx.Graph()
        self.documents = {}
        self.frequency = Counter()
        for key, record in sorted(snapshot.records.items()):
            words = TOKEN.findall(unicodedata.normalize(
                "NFKC", f"{record.primary_ref} {record.claim_summary} {record.raw_snippet}"
            ).casefold())
            self.documents[key] = Counter(words)
            self.frequency.update(set(words))
            for node in (("source", record.primary_ref), ("release", record.dataset_version)):
                self.graph.add_edge(("evidence", *key), node)
        self.average_length = (
            sum(c.total() for c in self.documents.values()) / len(self.documents) or 1.0
        )

    def search(self, query: str, limit: int):
        query_terms = terms(query)
        n = len(self.documents)
        scores = []
        for key, counts in self.documents.items():
            denominator = 1.2 * (0.25 + 0.75 * counts.total() / self.average_length)
            score = math.fsum(
                math.log1p((n - self.frequency[term] + 0.5) / (self.frequency[term] + 0.5))
                * counts[term] * 2.2 / (counts[term] + denominator)
                for term in sorted(query_terms & counts.keys())
            )
            if score:
                scores.append((-score, key))
        return [self.snapshot.records[key] for _, key in sorted(scores)[:limit]]

    def provenance(self, keys: Iterable[tuple[str, str]]):
        anchors = {("evidence", *key) for key in keys}
        nodes = anchors | {neighbor for node in anchors for neighbor in self.graph[node]}
        return {
            "nodes": [list(node) for node in sorted(nodes)],
            "edges": [list(map(list, edge)) for edge in sorted(
                tuple(sorted(edge)) for edge in self.graph.subgraph(nodes).edges
            )],
        }
