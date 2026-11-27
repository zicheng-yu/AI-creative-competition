import csv
import json
from io import BytesIO, StringIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from openpyxl import load_workbook

from backend.contracts import Workspace
from backend.main import FIXTURES, create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_fixtures_and_portable_schema(client):
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "workspace.schema.json").read_text()
    )
    model = Workspace.model_json_schema()
    assert schema == {
        **model,
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:competition:workbench:workspace:1.0.0",
    }
    index = client.get("/api/v1/workspaces").json()
    assert index["mode"] == "mock"
    assert {item["id"] for item in index["workspaces"]} == {"electrical", "sucompute"}
    for item in index["workspaces"]:
        response = client.get(f"/api/v1/workspaces/{item['id']}")
        assert response.status_code == 200
        Draft202012Validator(schema).validate(response.json())


def test_real_mode_requires_config_and_never_falls_back(client, tmp_path):
    assert client.get("/api/v1/workspaces?mode=real").status_code == 503
    real = TestClient(create_app(tmp_path))
    assert real.get("/api/v1/workspaces?mode=real").json()["workspaces"] == []
    assert real.get("/api/v1/workspaces/electrical?mode=real").status_code == 404
    data = json.loads((FIXTURES / "electrical.json").read_text())
    data["version"] = "imported-fixture"
    (tmp_path / "electrical.json").write_text(json.dumps(data))
    assert (
        real.get("/api/v1/workspaces/electrical?mode=real").json()["version"]
        == "imported-fixture"
    )
    assert (
        real.get("/api/v1/workspaces/electrical?mode=mock").json()["version"]
        == "mock-v1"
    )
    data["findings"][0]["source_id"] = "unknown"
    (tmp_path / "electrical.json").write_text(json.dumps(data))
    assert real.get("/api/v1/workspaces/electrical?mode=real").status_code == 502


@pytest.mark.parametrize("format_name", ["md", "pdf", "csv", "xlsx"])
def test_report_exports_use_posted_view_data(client, format_name):
    data = client.get("/api/v1/workspaces/electrical").json()
    data["charts"] = [
        {
            "id": "custom-chart",
            "kind": "bar",
            "title": "=导入评测",
            "unit": "%",
            "axes": [{"label": "样本 1"}],
            "series": [{"name": "导入策略", "values": [97.5]}],
        }
    ]
    response = client.post(f"/api/v1/reports/{format_name}", json=data)
    assert response.status_code == 200
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="electrical-report.{format_name}"'
    )
    if format_name == "md":
        assert "导入策略 · 97.5 %" in response.text
    if format_name == "pdf":
        assert response.content.startswith(b"%PDF-")
        assert response.content.rstrip().endswith(b"%%EOF")
    if format_name == "csv":
        first_row = next(
            csv.reader(StringIO(response.content.decode("utf-8-sig").split("\n", 1)[1]))
        )
        assert first_row == ["'=导入评测", "样本 1", "导入策略", "97.5", "%"]
    if format_name == "xlsx":
        sheet = load_workbook(BytesIO(response.content))["评测数据"]
        assert sheet["A2"].data_type == "s"
        assert sheet["A2"].value == "=导入评测"
        assert sheet["D2"].value == 97.5


def test_invalid_references_and_missing_chart_values_are_rejected(client):
    data = client.get("/api/v1/workspaces/sucompute").json()
    data["charts"][0]["series"][0]["values"].pop()
    assert client.post("/api/v1/reports/md", json=data).status_code == 422
    data = client.get("/api/v1/workspaces/sucompute").json()
    data["sources"][0]["raw_snippet"] = "这句话不在来源里"
    assert client.post("/api/v1/reports/md", json=data).status_code == 422
