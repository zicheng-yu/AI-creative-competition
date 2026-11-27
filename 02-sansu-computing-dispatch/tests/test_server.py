import pytest
from fastapi.testclient import TestClient
from server import app
from backend.copilot import RuleBasedCopilotStub

@pytest.fixture
def api():
    with TestClient(app) as c:
        yield c


def test_health_and_contract(api):
    assert api.get("/api/v1/health").json()["status"]=="ok"
    paths=api.get("/openapi.json").json()["paths"]
    assert len(paths)==4
    assert api.options("/api/v1/simulate",headers={"Origin":"http://localhost:3000",
               "Access-Control-Request-Method":"POST"}).headers["access-control-allow-origin"]=="*"


def test_simulate_and_replay(api):
    cfg={"hours":2,"scenario":"high_renewable","weights":{"carbon":.8}}
    result=api.post("/api/v1/simulate",json=cfg).json()
    assert result==api.post("/api/v1/simulate",json=cfg).json()
    assert len(result["hourly"])==2 and len(result["nodes"]["pue"][0])==16
    assert result["kpis"]["tasks"]>0


def test_inject_and_command(api):
    args={"city":"南京","kind":"outage","severity":1,"duration_slots":6}
    r=api.post("/api/v1/fault/inject",json={"hours":2,"slot":8,"fault":args})
    assert r.status_code==200 and r.json()["fault"]["elapsed_s"]<3
    for text,kind in [("碳排权重调至0.6","weights"),("注入南京节点30%算力故障","fault"),
                      ("解释这次调度","explain")]:
        result=api.post("/api/v1/copilot/command",json={"text":text,"hours":2})
        assert result.status_code==200 and result.json()["action"]["kind"]==kind
    result=api.post("/api/v1/copilot/command",json={"text":"解释","hours":1,"task_id":20000})
    assert result.status_code==404


@pytest.mark.parametrize("path,body",[("simulate",{"scenario":"unknown"}),("simulate",{"weights":{"carbon":2}}),
    ("fault/inject",{"fault":{"city":"其他"}}),("copilot/command",{"text":"随便说说"})])
def test_invalid(api,path,body):
    assert api.post("/api/v1/"+path,json=body).status_code==422

def test_local_stub_deterministic():
    stub=RuleBasedCopilotStub()
    assert stub.parse_command("优先绿电")==stub.parse_command("优先绿电")
    assert stub.parse_command("芜湖PUE飙升30%").fault.kind=="pue"
