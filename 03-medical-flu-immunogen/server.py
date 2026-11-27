"""Optional loopback-only API for reviewing a local, curator-verified release."""
import csv
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from engine.capsules import Snapshot
from engine.dossiers import Dossier, EvidenceRef, parse_csv
from engine.llm_adapter import BaseLLMClient
from engine.models import TextModels
from engine.service import EvidenceService
from engine.review import ReviewConflict
from engine.timeline import Period


FIXTURES = Path(__file__).parent / "tests" / "fixtures"
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class WorkflowInput(Input):
    period: Period = "month"
    hops: int = Field(default=2, ge=1, le=3)


class Question(WorkflowInput):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1200)]
    limit: int = Field(default=5, ge=1, le=15)


class CitationGroup(Input):
    label: Identifier
    citations: list[EvidenceRef] = Field(min_length=1, max_length=15)


class Comparison(WorkflowInput):
    groups: list[CitationGroup] | None = Field(default=None, min_length=2, max_length=6)
    dossiers: list[Dossier] | None = Field(default=None, min_length=2, max_length=6)
    dossier_csv: str | None = Field(default=None, min_length=1, max_length=100000)

    @model_validator(mode="after")
    def one_input(self):
        if sum(value is not None for value in (self.groups, self.dossiers, self.dossier_csv)) != 1:
            raise ValueError("provide one dossier representation")
        return self


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


def create_app(snapshot: Snapshot, client: BaseLLMClient | None = None,
               models: TextModels | None = None) -> FastAPI:
    app = FastAPI(title="离线证据审阅", docs_url=None, redoc_url=None, openapi_url=None)
    service = EvidenceService(snapshot, client, models)

    @app.get("/api/v1/health")
    def health():
        return {"ok": True, **snapshot.summary()}

    @app.post("/api/v1/qa")
    def qa(body: Question):
        return service.qa(body.query, body.limit, period=body.period, hops=body.hops)

    @app.post("/api/v1/compare")
    def compare(body: Comparison):
        try:
            if body.groups is not None:
                return service.compare([group.model_dump() for group in body.groups],
                                       period=body.period, hops=body.hops)
            dossiers = body.dossiers if body.dossiers is not None else parse_csv(body.dossier_csv)
            return service.compare_dossiers(dossiers, period=body.period, hops=body.hops)
        except (ValueError, csv.Error) as exc:
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
