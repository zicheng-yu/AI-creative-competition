"""Optional loopback-only API for reviewing a local, curator-verified release."""
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from engine.capsules import Snapshot
from engine.llm_adapter import BaseLLMClient
from engine.service import EvidenceService
from engine.review import ReviewConflict


FIXTURES = Path(__file__).parent / "tests" / "fixtures"
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Question(Input):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1200)]
    limit: int = Field(default=5, ge=1, le=15)


class EvidenceRef(Input):
    evidence_id: Identifier
    dataset_version: Identifier


class CitationGroup(Input):
    label: Identifier
    citations: list[EvidenceRef] = Field(min_length=1, max_length=15)


class Comparison(Input):
    groups: list[CitationGroup] = Field(min_length=2, max_length=6)


class Action(Input):
    statement_id: Identifier
    action: Literal["accept", "flag_doubt", "reject", "comment"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""


class Review(Input):
    report_id: Identifier
    expected_version: int = Field(ge=1)
    reviewer: Identifier
    actions: list[Action] = Field(default_factory=list, max_length=90)
    signoff: bool = False

    @model_validator(mode="after")
    def require_action(self):
        if not self.actions and not self.signoff:
            raise ValueError("at least one action or signoff is required")
        return self


def create_app(snapshot: Snapshot, client: BaseLLMClient | None = None) -> FastAPI:
    app = FastAPI(title="离线证据审阅", docs_url=None, redoc_url=None, openapi_url=None)
    service = EvidenceService(snapshot, client)

    @app.get("/api/v1/health")
    def health():
        return {"ok": True, "snapshot_id": snapshot.snapshot_id, "record_count": len(snapshot.records)}

    @app.post("/api/v1/qa")
    def qa(body: Question):
        return service.qa(body.query, body.limit)

    @app.post("/api/v1/compare")
    def compare(body: Comparison):
        try:
            return service.compare(body.model_dump()["groups"])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/review/signoff")
    def signoff(body: Review):
        try:
            return service.reviews.review(
                body.report_id, body.expected_version, body.reviewer,
                [action.model_dump() for action in body.actions], signoff=body.signoff,
            )
        except ReviewConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="report not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


def demo_app():
    return create_app(Snapshot(FIXTURES / "methods.jsonl", FIXTURES / "release.lock.json"))
