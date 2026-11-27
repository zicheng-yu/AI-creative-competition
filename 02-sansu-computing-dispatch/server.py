"""Optional stateless sidecar. Run with uvicorn server:app."""
from typing import Literal
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from backend.copilot import BaseCopilotAdapter, Fault, RuleBasedCopilotStub
from backend.planner import DEFAULT
from backend.replay import replay
from backend.report import Meter
from backend.simulation import run
from backend.world import CITIES, SCENARIOS, SLOTS, STRATEGIES, Trace

app = FastAPI(title="SuCompute",version="1")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["GET","POST"],
                   allow_headers=["Content-Type"])


class Simulation(BaseModel):
    seed: int = Field(default=313,ge=0,le=2**32-1)
    scenario: str = "normal_weekday"
    strategy: str = "SuCompute"
    hours: int = Field(default=6,ge=1,le=168)
    weights: dict[str,float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_settings(self):
        if self.scenario not in SCENARIOS or self.strategy not in STRATEGIES:
            raise ValueError("unknown scenario or strategy")
        if any(k not in DEFAULT or not 0<=v<=1 for k,v in self.weights.items()):
            raise ValueError("unknown weight or value outside [0,1]")
        return self


class Injection(Simulation):
    fault: Fault
    slot: int = Field(default=6,ge=0)

    @model_validator(mode="after")
    def validate_fault(self):
        if self.slot>=self.hours*SLOTS or self.fault.city not in CITIES:
            raise ValueError("unknown city or slot outside simulation")
        return self


class Command(Simulation):
    text: str = Field(min_length=1,max_length=500)
    task_id: int | None = Field(default=None,ge=0)


def get_adapter() -> BaseCopilotAdapter:
    return RuleBasedCopilotStub()


def execute(req,fault=None):
    trace = Trace(req.seed,req.scenario,req.hours)
    return Meter(run(trace,req.strategy,req.weights,fault))


@app.get("/api/v1/health")
def health():
    return {"status":"ok","simulator":"JS-ComputeSim-313"}


@app.post("/api/v1/simulate")
def simulate(req:Simulation):
    return replay(execute(req))


@app.post("/api/v1/fault/inject")
def inject(req:Injection):
    f = req.fault
    meter = execute(req,(req.slot,f.city,f.kind,f.severity,f.duration_slots))
    event = next(e for e in meter.sim.faults if e["slot"]==req.slot)
    return {"fault":event,"kpis":meter.kpi(0,req.hours)}


@app.post("/api/v1/copilot/command")
def command(req:Command,adapter:BaseCopilotAdapter=Depends(get_adapter)):
    action = adapter.parse_command(req.text)
    config = req.model_dump(exclude={"text","task_id"})
    if action.kind=="fault" and action.fault:
        result = inject(Injection(**config,fault=action.fault))
    elif action.kind=="weights":
        config["weights"].update(action.weights)
        result = execute(Simulation(**config)).kpi(0,req.hours)
    elif action.kind=="explain":
        meter = execute(req)
        number = req.task_id if req.task_id is not None else meter.sim.trace.jobs[0].id
        if number not in meter.sim.trace.by_id:
            raise HTTPException(404,"unknown task_id in this replay")
        result = adapter.explain_decision(meter.audit(number))
    else:
        raise HTTPException(422,"无法识别指令，可试“优先绿电消纳”或“南京宕机”。")
    return {"action":action,"result":result}
