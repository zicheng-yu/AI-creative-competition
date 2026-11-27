"""Validate and compare previously approved document archives."""
import csv
import io
import json
from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .capsules import Identifier, SHA256, EvidenceKey, Snapshot, canonical, digest
from .timeline import anchor


class EvidenceRef(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    evidence_id: Identifier
    dataset_version: Identifier

    @property
    def key(self) -> EvidenceKey:
        return (self.evidence_id, self.dataset_version)


class Dossier(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    dossier_id: Identifier
    label: str = Field(min_length=1, max_length=160)
    version: Identifier | None = None
    source_ref: str | None = Field(default=None, min_length=1, max_length=160)
    archive_sha256: SHA256 | None = None
    document_text: str | None = Field(default=None, min_length=1, max_length=20000)
    annotation: str | None = Field(default=None, min_length=1, max_length=1000)
    review_status: Literal["pending", "accepted", "flagged", "rejected"] | None = None
    citations: list[EvidenceRef] = Field(min_length=1, max_length=15)

    @field_validator("label", "annotation")
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("blank dossier label or annotation")
        return value


COLUMNS = tuple(Dossier.model_fields)
CHECKED = ("version", "source_ref", "archive_sha256", "annotation", "review_status")


def parse_csv(text: str) -> list[Dossier]:
    table = csv.DictReader(io.StringIO(text.removeprefix("\ufeff"), newline=""), strict=True)
    fields = table.fieldnames or []
    if len(fields) != len(set(fields)) or not set(fields) <= set(COLUMNS):
        raise ValueError("unknown or duplicate dossier CSV header")
    dossiers = []
    for row in table:
        if len(dossiers) == 6 or None in row or None in row.values():
            raise ValueError("too many or malformed dossier CSV rows")
        supplied = {key: value for key, value in row.items() if value != ""}
        if "citations" in supplied:
            supplied["citations"] = json.loads(supplied["citations"])
        dossiers.append(Dossier.model_validate(supplied))
    if len(dossiers) < 2:
        raise ValueError("expected 2–6 dossier rows")
    return dossiers


def archive_digest(dossier: Dossier) -> str:
    if dossier.document_text is not None:
        return digest(dossier.document_text.encode())
    return digest(canonical(dossier.model_dump(exclude={"archive_sha256", "document_text"})))


def compare_dossiers(dossiers: list[Dossier], snapshot: Snapshot) -> list[dict]:
    if not 2 <= len(dossiers) <= 6 or len({d.dossier_id for d in dossiers}) != len(dossiers):
        raise ValueError("expected 2–6 unique dossier IDs")
    matrix = []
    for dossier in dossiers:
        keys = [ref.key for ref in dossier.citations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate dossier references")
        if any(key not in snapshot.records for key in keys):
            raise ValueError("unknown evidence ID/version pair")
        records = [snapshot.records[key] for key in keys]
        sources = sorted({entry.primary_ref for entry in records})
        if dossier.source_ref and dossier.source_ref not in sources:
            raise ValueError("dossier source is absent from its approved references")
        if dossier.document_text is not None and not any(
            record.primary_ref == dossier.source_ref and record.raw_snippet == dossier.document_text
            for record in records
        ):
            raise ValueError("document text is outside its approved source excerpt")
        if dossier.archive_sha256 and dossier.archive_sha256 != archive_digest(dossier):
            raise ValueError("dossier SHA256 mismatch")

        missing = [name for name in CHECKED if getattr(dossier, name) is None]
        versions = sorted({entry.dataset_version for entry in records})
        same_version = None if not dossier.version else versions == [dossier.version]
        review_counts = dict(Counter(snapshot.metadata[key].review_status for key in keys))
        open_items = [f"missing:{name}" for name in missing]
        if same_version is False:
            open_items.append("version_mismatch")
        if dossier.review_status != "accepted":
            open_items.append("dossier_review_open")
        if any(status != "accepted" for status in review_counts):
            open_items.append("source_review_open")
        matrix.append({
            "dossier_id": dossier.dossier_id,
            "label": dossier.label,
            "source_coverage": {"count": len(sources), "primary_refs": sources},
            "field_completeness": {"present": len(CHECKED) - len(missing), "total": len(CHECKED),
                                   "missing": missing},
            "version_consistency": {"declared": dossier.version, "referenced": versions,
                                    "consistent": same_version},
            "evidence_traceability": {"anchors": [anchor(key) for key in keys],
                                      "hash_verified": dossier.archive_sha256 is not None},
            "review_status": {"declared": dossier.review_status, "source_counts": review_counts,
                              "open_items": open_items, "operator_annotation": dossier.annotation},
        })
    return matrix
