"""Versioned payload shared by the demo and track adapters."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)]

Mode = Literal["mock", "real"]
Severity = Literal["critical", "warning", "pass"]
Format = Literal["md", "pdf", "csv", "xlsx"]
ChartKind = Literal["line", "radar", "bar"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class WorkspaceInfo(Contract):
    id: Identifier
    title: str = Field(min_length=1, max_length=100)
    subtitle: str = Field(max_length=120)


class Source(Contract):
    source_id: Identifier
    title: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    confidence: float | None = Field(ge=0, le=1)
    raw_snippet: str = Field(min_length=1, max_length=1000)
    source_text: str = Field(max_length=60_000)
    source_url: HttpUrl | None = None

    @model_validator(mode="after")
    def check_snippet(self):
        if self.raw_snippet not in self.source_text:
            raise ValueError("raw_snippet must occur in source_text")
        return self


class Finding(Contract):
    id: Identifier
    severity: Severity
    title: str = Field(min_length=1, max_length=120)
    detail: str = Field(max_length=1000)
    recommendation: str = Field(max_length=1000)
    source_id: Identifier | None = None


class Axis(Contract):
    label: str = Field(min_length=1, max_length=80)
    maximum: float | None = Field(default=None, gt=0)


class Series(Contract):
    name: str = Field(min_length=1, max_length=80)
    values: list[float] = Field(min_length=1, max_length=100)


class Chart(Contract):
    id: Identifier
    kind: ChartKind
    title: str = Field(min_length=1, max_length=120)
    unit: str = Field(max_length=32)
    axes: list[Axis] = Field(min_length=1, max_length=100)
    series: list[Series] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def check_axes(self):
        if any(len(series.values) != len(self.axes) for series in self.series):
            raise ValueError("each series must have one value per axis")
        if len({axis.label for axis in self.axes}) != len(self.axes):
            raise ValueError("axis labels must be unique")
        if len({series.name for series in self.series}) != len(self.series):
            raise ValueError("series names must be unique")
        if self.kind == "radar":
            if len(self.axes) < 3 or any(axis.maximum is None for axis in self.axes):
                raise ValueError("radar charts require 3 or more axes with maxima")
            if any(
                value < 0 or value > axis.maximum
                for series in self.series
                for value, axis in zip(series.values, self.axes, strict=True)
            ):
                raise ValueError("radar values must be within their axis bounds")
        return self


class Workspace(WorkspaceInfo):
    schema_version: Literal["1.0.0"]
    version: str = Field(min_length=1, max_length=80)
    summary: str = Field(max_length=1000)
    sources: list[Source] = Field(max_length=100)
    findings: list[Finding] = Field(max_length=100)
    charts: list[Chart] = Field(max_length=30)

    @model_validator(mode="after")
    def check_references(self):
        source_ids = {source.source_id for source in self.sources}
        if len(source_ids) != len(self.sources):
            raise ValueError("source ids must be unique")
        if len({finding.id for finding in self.findings}) != len(self.findings):
            raise ValueError("finding ids must be unique")
        if len({chart.id for chart in self.charts}) != len(self.charts):
            raise ValueError("chart ids must be unique")
        if any(
            finding.source_id not in source_ids
            for finding in self.findings
            if finding.source_id
        ):
            raise ValueError("unknown finding source_id")
        return self


class WorkspaceList(Contract):
    mode: Mode
    workspaces: list[WorkspaceInfo]
