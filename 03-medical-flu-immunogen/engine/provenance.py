"""A four-type NetworkX provenance graph, scoped to one approved snapshot."""
import json
from collections.abc import Iterable
from pathlib import Path

import networkx as nx

from .capsules import EvidenceKey, Snapshot, canonical


Node = tuple[str, ...]


class ProvenanceGraph:
    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot
        self.graph = nx.Graph()
        for key, record in sorted(snapshot.records.items()):
            entry = snapshot.metadata[key]
            document = ("document", record.primary_ref)
            evidence = ("evidence", *key)
            release = ("snapshot", record.dataset_version)
            self.graph.add_node(document, title=entry.title, source_url=entry.source_url, nature=entry.nature)
            self.graph.add_node(evidence, evidence_id=key[0], dataset_version=key[1],
                                evidence_tier=record.evidence_tier, review_status=entry.review_status)
            self.graph.add_node(release, released_at=snapshot.releases[key[1]].released_at)
            self.graph.add_edge(document, evidence, relation="contains")
            self.graph.add_edge(evidence, release, relation="published_in")
            for topic in entry.topics:
                node = ("topic", topic)
                self.graph.add_node(node, title=topic)
                self.graph.add_edge(document, node, relation="indexed_under")

    def query(self, seeds: Iterable[Node], hops: int = 2) -> dict:
        if hops not in (1, 2, 3):
            raise ValueError("hops must be 1, 2 or 3")
        anchors = sorted(set(seeds))
        if any(node not in self.graph for node in anchors):
            raise ValueError("graph seed outside snapshot")
        paths = {}
        for anchor in anchors:
            for node, path in nx.single_source_shortest_path(self.graph, anchor, cutoff=hops).items():
                previous = paths.get(node)
                if previous is None or (len(path), path) < (len(previous), previous):
                    paths[node] = path
        subgraph = self.graph.subgraph(paths)
        edges = sorted((min(u, v), max(u, v), data["relation"]) for u, v, data in subgraph.edges(data=True))
        return {
            "snapshot_id": self.snapshot.snapshot_id,
            "hops": hops,
            "nodes": [{"id": node, "kind": node[0], **self.graph.nodes[node]} for node in sorted(paths)],
            "edges": [{"source": u, "target": v, "relation": relation} for u, v, relation in edges],
            "paths": [{"evidence_id": node[1], "dataset_version": node[2], "path": paths[node]}
                      for node in sorted(paths) if node[0] == "evidence"],
        }

    def all(self) -> dict:
        seeds = [("evidence", *key) for key in self.snapshot.records]
        return self.query(seeds, 3)

    def save(self, path: Path) -> None:
        path.write_bytes(canonical(self.all()) + b"\n")

    @classmethod
    def load(cls, snapshot: Snapshot, path: Path) -> "ProvenanceGraph":
        # The published JSON is a derived artifact. The approved lock remains authoritative.
        graph = cls(snapshot)
        if canonical(json.loads(path.read_bytes())) != canonical(graph.all()):
            raise ValueError("graph JSON differs from the approved snapshot")
        return graph

    def evidence_neighbors(self, seeds: Iterable[Node], hops: int) -> dict[EvidenceKey, int]:
        return {(item["evidence_id"], item["dataset_version"]): len(item["path"]) - 1
                for item in self.query(seeds, hops)["paths"]}
