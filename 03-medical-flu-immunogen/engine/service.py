"""Local evidence review service with a shared audit gate."""
from collections import Counter

from .audit import INSUFFICIENT, audit
from .llm_adapter import OfflineClient
from .retrieval import EvidenceIndex
from .review import ReviewStore


class EvidenceService:
    def __init__(self, snapshot, client=None):
        self.snapshot = snapshot
        self.index = EvidenceIndex(snapshot)
        self.reviews = ReviewStore()
        self.client = client if client is not None else OfflineClient()

    def qa(self, query, limit):
        selected = self.index.search(query, limit)
        return self._draft(self.client.assemble(query, list(selected)), selected)

    def compare(self, groups):
        keys_by_group = {
            group["label"]: list(dict.fromkeys(
                (ref["evidence_id"], ref["dataset_version"]) for ref in group["citations"]
            ))
            for group in groups
        }
        if len(keys_by_group) != len(groups):
            raise ValueError("group labels must be unique")
        keys = dict.fromkeys(key for refs in keys_by_group.values() for key in refs)
        if any(key not in self.snapshot.records for key in keys):
            raise ValueError("unknown evidence ID/version pair")
        selected = [self.snapshot.records[key] for key in keys]
        citations = OfflineClient().assemble("", selected)
        return self._draft(citations, selected, groups=keys_by_group)

    def _draft(self, citations, selected, groups=None):
        statements, rejected = audit(citations, selected)
        keys = {(s["evidence_id"], s["dataset_version"]): s for s in statements}
        inventory = []
        for label, refs in (groups or {}).items():
            rows = [keys[key] for key in refs if key in keys]
            inventory.append({"label": label, "statement_ids": [s["statement_id"] for s in rows],
                              "tier_counts": dict(Counter(s["evidence_tier"] for s in rows)),
                              "review_notice": INSUFFICIENT if len(rows) < len(refs) else None})
        return self.reviews.draft(
            snapshot_id=self.snapshot.snapshot_id,
            statements=statements,
            inventory=inventory,
            review_notice=INSUFFICIENT if not statements or any(rejected.values()) else None,
            provenance=self.index.provenance(keys),
            agent_trace=[
                {"step": "evidence_selection", "selected": len(selected)},
                {"step": "quotation_audit", "accepted": len(statements), "rejected": rejected},
            ],
        )
