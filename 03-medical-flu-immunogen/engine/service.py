"""Four-stage, synchronous evidence review workflow over an approved local snapshot."""
from collections import Counter, defaultdict
from itertools import combinations

from .audit import INSUFFICIENT, audit
from .capsules import EvidenceCapsule, Snapshot
from .dossiers import Dossier, compare_dossiers
from .llm_adapter import BaseLLMClient, Citation, OfflineClient
from .models import TextModels
from .retrieval import EvidenceIndex
from .review import ReviewStore
from .timeline import Period, anchor, metadata_timeline


class MetadataTimelineAgent:
    def run(self, snapshot: Snapshot, period: Period) -> tuple[dict, dict]:
        timeline = metadata_timeline(snapshot, period)
        return timeline, {"step": type(self).__name__, "status": "complete",
                          "periods": len(timeline["curve"]), "heatmap_cells": len(timeline["heatmap"])}


class EvidenceRetrievalAgent:
    def __init__(self, index: EvidenceIndex, models: TextModels):
        self.index = index
        self.models = models

    def run(self, query: str, limit: int, hops: int) -> tuple[list[EvidenceCapsule], list[dict], dict]:
        result = self.index.retrieve(query, limit, hops)
        return result.records, result.hits, {"step": type(self).__name__, "status": "complete",
                                             "routes": result.route_counts, "selected": len(result.hits)}

    def method_differences(self, accepted: list[EvidenceCapsule]) -> list[dict]:
        buckets = defaultdict(list)
        for record in accepted:
            for topic in self.index.snapshot.metadata[record.key].topics:
                buckets[topic].append(record)
        rows = []
        for topic, group in sorted(buckets.items()):
            unique = {record.primary_ref: record for record in group}
            for left, right in combinations(unique.values(), 2):
                if len(rows) == 15:
                    break
                rows.append((topic, left, right))
        predictions = self.models.nli([(left.raw_snippet, right.raw_snippet) for _, left, right in rows])
        return [{"topic": topic, "left": anchor(left.key), "right": anchor(right.key),
                 "nli": probabilities, "status": "requires_expert_review"}
                for (topic, left, right), probabilities in zip(rows, predictions)]


class DossierComparisonAgent:
    def run(self, dossiers: list[Dossier] | None, snapshot: Snapshot) -> tuple[list[dict], dict]:
        matrix = compare_dossiers(dossiers, snapshot) if dossiers is not None else []
        return matrix, {"step": type(self).__name__, "status": "complete" if dossiers else "skipped",
                        "dossiers": len(matrix),
                        "open_items": sum(len(row["review_status"]["open_items"]) for row in matrix)}


class UncertaintyAuditAgent:
    def __init__(self, models: TextModels):
        self.models = models

    def run(self, citations: list[Citation], selected: list[EvidenceCapsule], snapshot: Snapshot
            ) -> tuple[list[dict], dict]:
        statements, rejected = audit(citations, selected)
        by_key = {record.key: record for record in selected}
        paired = [(by_key[key].raw_snippet, draft.text) for draft in citations
                  if (key := (draft.evidence_id, draft.dataset_version)) in by_key]
        signals = Counter(max(p, key=p.get) for p in self.models.nli(paired))
        for statement in statements:
            entry = snapshot.metadata[(statement["evidence_id"], statement["dataset_version"])]
            statement.update(source_url=entry.source_url, nature=entry.nature,
                             source_review_status=entry.review_status)
        return statements, {"step": type(self).__name__, "status": "complete",
                            "accepted": len(statements), "rejected": rejected, "nli_signals": dict(signals)}


class EvidenceService:
    def __init__(self, snapshot: Snapshot, client: BaseLLMClient | None = None,
                 models: TextModels | None = None):
        self.snapshot = snapshot
        self.models = models if models is not None else TextModels()
        self.index = EvidenceIndex(snapshot, self.models)
        self.reviews = ReviewStore()
        self.client = client if client is not None else OfflineClient()
        self.timeline = MetadataTimelineAgent()
        self.retrieval = EvidenceRetrievalAgent(self.index, self.models)
        self.comparison = DossierComparisonAgent()
        self.audit = UncertaintyAuditAgent(self.models)

    def qa(self, query: str, limit: int, *, period: Period = "month", hops: int = 2) -> dict:
        return self._run(query=query, limit=limit, period=period, hops=hops)

    def compare(self, groups: list[dict], *, period: Period = "month", hops: int = 2) -> dict:
        dossiers = [Dossier.model_validate({"dossier_id": f"group-{i}", **group})
                    for i, group in enumerate(groups, 1)]
        if len({dossier.label for dossier in dossiers}) != len(dossiers):
            raise ValueError("group labels must be unique")
        return self.compare_dossiers(dossiers, period=period, hops=hops)

    def compare_dossiers(self, dossiers: list[Dossier], *, period: Period = "month", hops: int = 2) -> dict:
        return self._run(dossiers=dossiers, period=period, hops=hops)

    def _run(self, *, query: str | None = None, limit: int = 5, dossiers: list[Dossier] | None = None,
             period: Period, hops: int) -> dict:
        timeline, time_step = self.timeline.run(self.snapshot, period)
        if query is not None:
            selected, hits, retrieve_step = self.retrieval.run(query, limit, hops)
        else:
            refs = [ref.key for dossier in (dossiers or []) for ref in dossier.citations]
            if any(key not in self.snapshot.records for key in refs):
                raise ValueError("unknown evidence ID/version pair")
            selected = [self.snapshot.records[key] for key in dict.fromkeys(refs)]
            hits = []
            retrieve_step = {"step": "EvidenceRetrievalAgent", "status": "complete",
                             "mode": "declared_anchors", "selected": len(selected)}
        matrix, compare_step = self.comparison.run(dossiers, self.snapshot)
        client = self.client if query is not None else OfflineClient()
        statements, audit_step = self.audit.run(
            client.assemble(query or "", list(selected)), selected, self.snapshot
        )
        accepted = {(s["evidence_id"], s["dataset_version"]): s for s in statements}
        groups = []
        for row in matrix:
            anchors = row["evidence_traceability"]["anchors"]
            keys = [(ref["evidence_id"], ref["dataset_version"]) for ref in anchors]
            quoted = [accepted[key] for key in keys if key in accepted]
            row["evidence_traceability"]["accepted_citations"] = len(quoted)
            if len(quoted) < len(keys):
                row["review_status"]["open_items"].append("quotation_audit_pending")
            groups.append({"label": row["label"], "statement_ids": [s["statement_id"] for s in quoted],
                           "tier_counts": dict(Counter(s["evidence_tier"] for s in quoted)),
                           "review_notice": INSUFFICIENT if len(quoted) < len(keys) else None})
        return self.reviews.draft(
            snapshot_id=self.snapshot.snapshot_id, statements=statements, inventory=groups,
            metadata_timeline=timeline, retrieval=hits, dossier_matrix=matrix,
            method_differences=self.retrieval.method_differences(
                [self.snapshot.records[key] for key in accepted]
            ) if query is not None else [],
            review_notice=INSUFFICIENT if not statements or any(audit_step["rejected"].values()) else None,
            provenance=self.index.provenance(accepted, hops),
            agent_trace=[time_step, retrieve_step, compare_step, audit_step],
        )
