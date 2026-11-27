"""Calendar summaries over document, release and ingestion metadata."""
from collections import Counter, defaultdict
from datetime import date, datetime, UTC
from typing import Literal

from .capsules import Snapshot


Period = Literal["month", "quarter"]
TRACKED_FIELDS = ("published_on", "archive_note")


def bucket(value: str, period: Period) -> str:
    day = (datetime.fromisoformat(value).astimezone(UTC).date()
           if len(value) > 10 else date.fromisoformat(value))
    if period == "month":
        return day.strftime("%Y-%m")
    return f"{day.year}-Q{(day.month - 1) // 3 + 1}"


def anchor(key: tuple[str, str]) -> dict[str, str]:
    return dict(zip(("evidence_id", "dataset_version"), key))


def metadata_timeline(snapshot: Snapshot, period: Period) -> dict:
    if period not in ("month", "quarter"):
        raise ValueError("expected month or quarter")
    publications = defaultdict(dict)
    ingestion = defaultdict(list)
    updates = defaultdict(list)
    cells = defaultdict(list)
    unpublished = []
    for key, record in sorted(snapshot.records.items()):
        entry = snapshot.metadata[key]
        if entry.published_on:
            publication = bucket(entry.published_on, period)
            publications[publication].setdefault(record.primary_ref, anchor(key))
        else:
            unpublished.append(anchor(key))
        ingestion[bucket(record.ingested_at, period)].append((key, record, entry))
        cells[(bucket(record.ingested_at, "month"), record.source_type)].append((key, entry))
    for release in sorted(snapshot.releases.values(), key=lambda entry: (entry.released_at, entry.dataset_version)):
        updates[bucket(release.released_at, period)].append(release.model_dump())
    curve = []
    for window in sorted(publications.keys() | ingestion.keys() | updates.keys()):
        rows = ingestion[window]
        curve.append({
            "period": window,
            "document_count": len(publications[window]),
            "published_documents": list(publications[window].values()),
            "ingested_count": len(rows),
            "ingested_evidence": [anchor(key) for key, _, _ in rows],
            "source_counts": dict(Counter(record.source_type for _, record, _ in rows)),
            "review_counts": dict(Counter(entry.review_status for _, _, entry in rows)),
            "snapshot_updates": updates[window],
        })
    heatmap = [{
        "month": month,
        "source": source,
        "records": len(rows),
        "present": {field: sum(bool(getattr(entry, field)) for _, entry in rows)
                    for field in TRACKED_FIELDS},
        "missing": {field: sum(not getattr(entry, field) for _, entry in rows)
                    for field in TRACKED_FIELDS},
        "evidence": [anchor(key) for key, _ in rows],
    } for (month, source), rows in sorted(cells.items())]
    return {"snapshot_id": snapshot.snapshot_id, "period": period,
            "curve": curve, "heatmap": heatmap, "undated_documents": unpublished}
