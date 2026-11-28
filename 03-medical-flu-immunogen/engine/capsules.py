"""Read curated records and verify their identity against an independent release lock."""
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Iterator, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


EvidenceKey = tuple[str, str]
Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]
SHA256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
SCOPE = "methods-and-records-governance"
# Public-database anchors added for FluEvidenceBench. Existing PubMed and synthetic rules stay intact.
DATABASE_ANCHORS = (
    ("PDB_STRUCTURE", re.compile(r"PDB:([0-9][A-Z0-9]{3})"), "https://www.rcsb.org/structure/{}/"),
    ("IEDB_EPITOPE", re.compile(r"IEDB:([1-9][0-9]{1,11})"), "https://www.iedb.org/epitope/{}/"),
    ("NCBI_NUCCORE", re.compile(r"Accession:([A-Z]{1,2}[0-9]{5,8}(?:\.[0-9]+)?)"),
     "https://www.ncbi.nlm.nih.gov/nuccore/{}/"),
    ("UNIPROT_RECORD", re.compile(r"UniProt:([OPQ][0-9][A-Z0-9]{3}[0-9])"),
     "https://www.uniprot.org/uniprotkb/{}/"),
)


def database_source_type(primary_ref: str) -> str | None:
    for source_type, pattern, _template in DATABASE_ANCHORS:
        if pattern.fullmatch(primary_ref):
            return source_type
    return None


def database_source_url(primary_ref: str) -> str | None:
    for _source_type, pattern, template in DATABASE_ANCHORS:
        match = pattern.fullmatch(primary_ref)
        if match:
            return template.format(match.group(1))
    return None


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_zoned_timestamp(value: str) -> str:
    if datetime.fromisoformat(value).utcoffset() is None:
        raise ValueError("ingested_at requires a timezone")
    return value


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class EvidenceCapsule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore", strict=True, str_min_length=1)
    evidence_id: Identifier
    source_type: str
    primary_ref: str
    dataset_version: Identifier
    ingested_at: str
    evidence_tier: Literal["T1_WET_LAB_ASSAY", "T2_SURVEILLANCE",
                           "T3_PEER_REVIEWED_LIT", "T4_COMPUTATIONAL"]
    subtype_context: str
    claim_summary: str
    raw_snippet: str
    sha256: SHA256

    @field_validator("ingested_at")
    @classmethod
    def timestamp_with_zone(cls, value: str) -> str:
        return require_zoned_timestamp(value)

    @model_validator(mode="after")
    def check_record(self):
        if any(not value.strip() for value in self.model_dump().values()):
            raise ValueError("empty capsule field")
        if digest(self.raw_snippet.encode()) != self.sha256:
            raise ValueError("raw_snippet SHA256 mismatch")
        if re.search(r"COMPUT|PREDICT|SIMULAT|IN_SILICO", self.source_type, re.I):
            if self.evidence_tier != "T4_COMPUTATIONAL":
                raise ValueError("computational sources require T4")
        return self

    @property
    def key(self) -> EvidenceKey:
        return (self.evidence_id, self.dataset_version)


class ApprovedEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)
    evidence_id: Identifier
    dataset_version: Identifier
    record_sha256: SHA256
    title: str = Field(min_length=1)
    primary_ref: str
    source_url: str | None = None
    nature: Literal["public_methods", "synthetic", "public_database"]
    approval: Literal["approved"]
    review_status: Literal["pending", "accepted", "flagged", "rejected"]
    topics: tuple[str, ...] = Field(min_length=1)
    published_on: str | None = None
    archive_note: str | None = None

    @model_validator(mode="after")
    def validate_anchor(self) -> "ApprovedEntry":
        if self.published_on is not None:
            date.fromisoformat(self.published_on)
        if any(not topic.strip() for topic in self.topics):
            raise ValueError("empty approved topic")
        if self.nature == "public_methods":
            match = re.fullmatch(r"PMID:([1-9][0-9]{0,11})", self.primary_ref)
            if not match or self.source_url != f"https://pubmed.ncbi.nlm.nih.gov/{match[1]}/":
                raise ValueError("invalid curated PubMed anchor")
        elif self.nature == "synthetic":
            if not re.fullmatch(r"SYNTHETIC:[a-z0-9][a-z0-9-]*", self.primary_ref) or self.source_url:
                raise ValueError("synthetic entries require a synthetic anchor and no source URL")
        else:
            source_type = database_source_type(self.primary_ref)
            if source_type is None or self.source_url != database_source_url(self.primary_ref):
                raise ValueError("invalid public database anchor")
        return self


class Release(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dataset_version: Identifier
    released_at: str
    previous_version: Identifier | None = None

    @field_validator("released_at")
    @classmethod
    def timestamp_with_zone(cls, value: str) -> str:
        return require_zoned_timestamp(value)


class ReleaseLock(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    tenant_id: Identifier
    scope: Literal["methods-and-records-governance"]
    releases: tuple[Release, ...] = Field(min_length=1)
    records: tuple[ApprovedEntry, ...] = Field(min_length=1)


def read_rows(path: Path) -> Iterator[dict]:
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches():
            yield from batch.to_pylist()
    elif path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as lines:
            for line in lines:
                if line.strip():
                    yield json.loads(line)
    else:
        raise ValueError("expected JSONL or Parquet")


class Snapshot:
    """A trusted, curator-supplied lock is required separately from incoming records."""

    def __init__(self, path: Path, lock: Path, *, tenant_id: str = "demo"):
        manifest = ReleaseLock.model_validate_json(lock.read_bytes())
        if manifest.tenant_id != tenant_id:
            raise ValueError("release lock belongs to another tenant")
        releases = {r.dataset_version: r for r in manifest.releases}
        expected = {(r.evidence_id, r.dataset_version): r for r in manifest.records}
        if len(expected) != len(manifest.records) or len(releases) != len(manifest.releases):
            raise ValueError("duplicate release key")
        for release in releases.values():
            if release.previous_version:
                parent = releases.get(release.previous_version)
                if not parent or datetime.fromisoformat(parent.released_at) >= datetime.fromisoformat(release.released_at):
                    raise ValueError("invalid release lineage")
        if any(version not in releases for _, version in expected):
            raise ValueError("evidence version outside release lock")
        files = sorted([*path.rglob("*.jsonl"), *path.rglob("*.parquet")]) if path.is_dir() else [path]
        records: dict[EvidenceKey, EvidenceCapsule] = {}
        for file in files:
            for row in read_rows(file):
                if not isinstance(row, dict):
                    raise ValueError(f"expected an evidence object in {file.name}")
                if "tenant_id" in row and row["tenant_id"] != tenant_id:
                    raise ValueError("evidence row belongs to another tenant")
                record = EvidenceCapsule.model_validate(row)
                entry = expected.get(record.key)
                if (record.key in records or not entry or record.primary_ref != entry.primary_ref
                        or entry.record_sha256 != digest(canonical(record.model_dump()))):
                    raise ValueError("duplicate, unknown or altered capsule")
                if entry.nature == "synthetic" and record.source_type != "SYNTHETIC_METHODS":
                    raise ValueError("synthetic source type mismatch")
                if entry.nature == "public_methods" and record.source_type != "PUBMED_LITERATURE":
                    raise ValueError("approved PubMed source type mismatch")
                if entry.nature == "public_database" and record.source_type != database_source_type(record.primary_ref):
                    raise ValueError("public database source type mismatch")
                records[record.key] = record
        if records.keys() != expected.keys():
            raise ValueError("incomplete snapshot")
        self.records = MappingProxyType(records)
        self.metadata = MappingProxyType(expected)
        self.releases = MappingProxyType(releases)
        self.tenant_id = tenant_id
        self.snapshot_id = digest(canonical({
            "tenant_id": tenant_id, "scope": manifest.scope,
            "records": [expected[key].model_dump() for key in sorted(expected)],
            "releases": [releases[key].model_dump() for key in sorted(releases)],
        }))

    def summary(self) -> dict:
        return {"snapshot_id": self.snapshot_id, "tenant_id": self.tenant_id,
                "scope": SCOPE, "record_count": len(self.records),
                "releases": [self.releases[key].model_dump() for key in sorted(self.releases)]}
