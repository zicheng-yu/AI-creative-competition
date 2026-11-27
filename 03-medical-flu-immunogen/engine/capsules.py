"""Read curated records and verify their identity against an independent release lock."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class EvidenceCapsule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore", strict=True, str_min_length=1)
    evidence_id: str
    source_type: str
    primary_ref: str
    dataset_version: str
    ingested_at: str
    evidence_tier: Literal["T1_WET_LAB_ASSAY", "T2_SURVEILLANCE",
                           "T3_PEER_REVIEWED_LIT", "T4_COMPUTATIONAL"]
    subtype_context: str
    claim_summary: str
    raw_snippet: str
    sha256: str

    @field_validator("ingested_at")
    @classmethod
    def timestamp_with_zone(cls, value):
        if datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is None:
            raise ValueError("ingested_at requires a timezone")
        return value

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
    def key(self):
        return (self.evidence_id, self.dataset_version)


def read_rows(path):
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq
        yield from pq.read_table(path).to_pylist()
    elif path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as lines:
            for line in lines:
                if line.strip():
                    yield json.loads(line)
    else:
        raise ValueError("expected JSONL or Parquet")


class Snapshot:
    """A trusted, curator-supplied lock is required separately from incoming records."""

    def __init__(self, path: Path, lock: Path):
        manifest = json.loads(lock.read_text(encoding="utf-8"))
        expected = {(r["evidence_id"], r["dataset_version"]): r["record_sha256"]
                    for r in manifest["records"]}
        if len(expected) != len(manifest["records"]) or not expected:
            raise ValueError("empty or duplicate release key")
        files = sorted([*path.rglob("*.jsonl"), *path.rglob("*.parquet")]) if path.is_dir() else [path]
        records = {}
        for file in files:
            for row in read_rows(file):
                record = EvidenceCapsule.model_validate(row)
                if record.key in records or expected.get(record.key) != digest(canonical(record.model_dump())):
                    raise ValueError("duplicate, unknown or altered capsule")
                records[record.key] = record
        if records.keys() != expected.keys():
            raise ValueError("incomplete snapshot")
        self.records = MappingProxyType(records)
        self.snapshot_id = digest(canonical(sorted([*key, value] for key, value in expected.items())))
