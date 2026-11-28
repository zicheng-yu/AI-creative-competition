import csv
import io

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.copilot import (PRESETS, OpenAICompatibleCopilot, RuleBasedCopilotStub,
                             default_adapter, selection_reason)
from backend.replay import expand_receipt
from backend.report import ledger_csv, ledger_row, receipt_hash
from backend.world import POOLS
from server import app


def sample_receipt():
    scores = [.32,.98,.95,.85,.92,.39]
    candidates = []
    for node in range(16):
        candidates.append(dict(node=node,scores=scores,
                               feasible=[node<2 and pool==1 for pool in range(6)],
                               latency_ms=1 if node==0 else 5 if node<13 else 10,
                               resource_shadow=.01*(node+1),carbon_shadow=.002*(16-node)))
    voucher = "ab"*32
    return dict(task_id=7,scenario="peak_shaving",seed=313,strategy="SuCompute",source=0,
                task_class="Inference",release_slot=0,deadline_slot=12,latency_limit_ms=5,
                required_efh=1.,candidate_affinity=candidates,
                segments=[dict(node=1,pool="Ascend",start_slot=0,end_slot=4,latency_ms=5,
                               green_share=.42,pue=1.21,probability=.37,resource_shadow=.02,
                               carbon_shadow=.028)],
                effective_efh=1.,physical_efh=1.02,energy_kwh=10.,electricity_cny=6.5,co2_kg=3.2,
                avoided_vs_grid_kg=2.3,sla_met=True,sha256=voucher)


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL",raising=False)
    monkeypatch.delenv("LLM_API_KEY",raising=False)


def test_parser_presets_and_free_text(offline):
    stub = RuleBasedCopilotStub()
    peak = stub.parse_command("迎峰度夏保电模式：碳排权重调至 0.6")
    assert peak.kind=="weights" and peak.weights=={"carbon":.6} and peak.scenario=="peak_shaving"
    outage = stub.parse_command("注入南京节点 30% 算力宕机故障")
    assert outage.kind=="fault" and outage.fault.city=="南京"
    assert outage.fault.kind=="capacity" and outage.fault.severity==pytest.approx(.3)
    assert stub.parse_command("碳排权重调至0.6").weights=={"carbon":.6}
    assert stub.parse_command("优先绿电").weights=={"carbon":.8}
    assert stub.parse_command("碳排权重调至0.6，电费权重调至0.2").weights=={"carbon":.6,"cost":.2}
    assert stub.parse_command("SLA权重调至60%").weights=={"sla":.6}
    pue = stub.parse_command("芜湖PUE飙升30%")
    assert pue.fault.city=="安徽芜湖" and pue.fault.kind=="pue" and pue.fault.severity==pytest.approx(.3)
    assert stub.parse_command("解释任务 12").task_id==12
    assert stub.parse_command("南京节点宕机").fault.kind=="outage"
    assert stub.parse_command("切换到绿电大发日").scenario=="high_renewable"
    assert stub.parse_command("碳排权重调至2").kind=="unknown"
    assert stub.parse_command("随便说说").kind=="unknown"
    assert stub.parse_command("优先绿电")==stub.parse_command("优先绿电")
    assert {item["text"] for item in PRESETS} >= {
        "迎峰度夏保电模式：碳排权重调至 0.6","注入南京节点 30% 算力宕机故障"}


def test_template_attributes_affinity_duals_and_voucher(offline):
    receipt = sample_receipt()
    text = selection_reason(receipt)
    assert "南京" in text and "苏州" in text
    assert "0.98" in text and "Ascend" in text
    assert "影子价格" in text and "PUE" in text and "绿电" in text
    assert "37.00%" in text and "Safe-RL" in text
    assert receipt["sha256"] in text and "1.0000 EF·h" in text
    assert "6.50 元" in text and "SLA 达成" in text
    explained = RuleBasedCopilotStub().explain_decision({"task":receipt,"global":"全局摘要"})
    assert explained.generator=="template"
    assert explained.summary==explained.evidence["template_summary"]
    assert explained.evidence["cross_region"] is False
    assert explained.evidence["probability"]==pytest.approx(.37)
    assert explained.global_summary=="全局摘要"
    row = ledger_row(receipt,text)
    table = list(csv.DictReader(io.StringIO(ledger_csv([row]).lstrip("\ufeff"))))
    assert table[0]["凭证SHA256"]==receipt["sha256"]
    assert table[0]["是否跨域"]=="否"
    assert table[0]["来源城市"]=="南京" and table[0]["目的城市"]=="苏州"
    assert float(table[0]["亲和度"])==pytest.approx(.98)
    assert POOLS.index("Ascend")==1


def test_llm_rewrites_only_when_the_voucher_survives(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL","http://127.0.0.1:9/v1")
    monkeypatch.setenv("LLM_API_KEY","not-a-real-key")
    receipt = sample_receipt()
    calls = []

    def fake_post(url,headers,json,timeout):
        calls.append((url,headers["Authorization"],json["model"],timeout))
        class Response:
            def raise_for_status(self):
                return None
            def json(self):
                return {"choices":[{"message":{"content":"改写但丢掉了哈希"}}]}
        return Response()

    monkeypatch.setattr("backend.copilot.httpx.post",fake_post)
    dropped = OpenAICompatibleCopilot().explain_decision(receipt)
    assert dropped.generator=="template" and dropped.summary==dropped.evidence["template_summary"]

    def accepted(url,headers,json,timeout):
        calls.append(url)
        class Response:
            def raise_for_status(self):
                return None
            def json(self):
                return {"choices":[{"message":{"content":f"改写说明，凭证 {receipt['sha256']}"}}]}
        return Response()

    monkeypatch.setattr("backend.copilot.httpx.post",accepted)
    rewritten = OpenAICompatibleCopilot().explain_decision(receipt)
    assert rewritten.generator=="llm" and receipt["sha256"] in rewritten.summary
    assert rewritten.evidence["template_summary"]==dropped.summary
    assert calls[0][0].endswith("/chat/completions") and calls[0][1]=="Bearer not-a-real-key"

    def broken(*args,**kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr("backend.copilot.httpx.post",broken)
    assert OpenAICompatibleCopilot().explain_decision(receipt).generator=="template"
    assert isinstance(default_adapter(),OpenAICompatibleCopilot)
    monkeypatch.delenv("LLM_API_KEY")
    assert isinstance(default_adapter(),RuleBasedCopilotStub)


@pytest.fixture
def api(offline):
    with TestClient(app) as client:
        yield client


def test_command_and_ledger_api_use_live_receipts(api):
    presets = api.get("/api/v1/copilot/presets")
    assert presets.status_code==200
    assert any(item["text"]=="迎峰度夏保电模式：碳排权重调至 0.6" for item in presets.json()["presets"])
    weight = api.post("/api/v1/copilot/command",json={"hours":1,"text":"迎峰度夏保电模式：碳排权重调至 0.6"})
    assert weight.status_code==200
    body = weight.json()
    assert body["action"]["scenario"]=="peak_shaving" and body["action"]["weights"]["carbon"]==.6
    assert "peak_shaving" in body["narrative"] and "0.60" in body["narrative"]
    assert "0.55" in body["narrative"] and "0.5617" in body["narrative"]
    fault = api.post("/api/v1/copilot/command",json={"hours":1,"text":"注入南京节点 30% 算力宕机故障"})
    assert fault.status_code==200
    injected = fault.json()
    assert injected["action"]["fault"]["kind"]=="capacity"
    assert injected["result"]["fault"]["city"]=="南京" and injected["result"]["fault"]["severity"]==.3
    assert "立即重算" in injected["narrative"]
    explained = api.post("/api/v1/copilot/command",json={"hours":1,"strategy":"SuCompute","text":"解释调度"})
    assert explained.status_code==200
    report = explained.json()["result"]
    assert report["generator"]=="template"
    assert "亲和" in report["summary"] and report["evidence"]["sha256"] in report["summary"]
    assert "影子" in report["global_summary"]
    ledger = api.post("/api/v1/ledger",json={"hours":1,"strategy":"SuCompute","limit":2})
    assert ledger.status_code==200
    page = ledger.json()
    assert page["tasks"]==len(page["index"]) and 1<=len(page["receipts"])<=2
    for receipt in page["receipts"]:
        assert receipt_hash(expand_receipt(receipt))==receipt["sha256"]
        assert receipt["selection_reason"]
        assert "亲和" in receipt["selection_reason"]
    exported = api.post("/api/v1/ledger/csv",json={"hours":1,"strategy":"SuCompute"})
    assert exported.status_code==200 and exported.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff"))))
    assert len(rows)==page["tasks"]
    assert {row["凭证SHA256"] for row in rows}=={item["sha256"] for item in page["index"]}
    missing = api.post("/api/v1/ledger",json={"hours":1,"task_id":999999})
    assert missing.status_code==404
