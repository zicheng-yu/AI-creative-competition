"""Optional stateless sidecar. Run with uvicorn server:app."""
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError, model_validator

from backend.copilot import (ASSUMPTIONS, PRESETS, BaseCopilotAdapter, Fault,
                             default_adapter, selection_reason, summarize_window)
from backend.planner import DEFAULT
from backend.replay import compact_receipt, replay
from backend.report import Meter, is_cross_region, ledger_csv, ledger_row
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


class LedgerRequest(Simulation):
    task_id: int | None = Field(default=None,ge=0)
    cross_region_only: bool = False
    limit: int | None = Field(default=None,ge=1,le=2000)


def get_adapter() -> BaseCopilotAdapter:
    return default_adapter()


_CACHE = {}


def execute(req,fault=None):
    key = (req.seed,req.scenario,req.strategy,req.hours,
           tuple(sorted((k,float(v)) for k,v in req.weights.items())),fault)
    meter = _CACHE.get(key)
    if meter is None:
        if len(_CACHE)>=4:
            _CACHE.pop(next(iter(_CACHE)))
        meter = Meter(run(Trace(req.seed,req.scenario,req.hours),req.strategy,req.weights,fault))
        _CACHE[key] = meter
    return meter


def audited(meter):
    cached = getattr(meter,"audits",None)
    if cached is None:
        cached = {job.id:meter.audit(job.id) for job in meter.sim.trace.jobs}
        meter.audits = cached
    return cached


def _checked(model,payload,message):
    try:
        return model(**payload)
    except ValidationError:
        raise HTTPException(422,message) from None


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


@app.get("/api/v1/copilot/presets")
def presets():
    return {"presets":PRESETS}


@app.post("/api/v1/copilot/command")
def command(req:Command,adapter:BaseCopilotAdapter=Depends(get_adapter)):
    action = adapter.parse_command(req.text)
    config = req.model_dump(exclude={"text","task_id"})
    if action.scenario:
        config["scenario"] = action.scenario
    narrative = ""
    if action.kind=="fault" and action.fault:
        slot = 6 if action.slot is None else action.slot
        injected = _checked(Injection,{**config,"fault":action.fault,"slot":slot},"故障参数超出本次仿真窗口。")
        result = inject(injected)
        narrative = adapter.describe_applied(action,execute(injected,(slot,action.fault.city,
                   action.fault.kind,action.fault.severity,action.fault.duration_slots)))
    elif action.kind=="weights":
        config["weights"].update(action.weights)
        sim = _checked(Simulation,config,"无法应用该权重或场景。")
        meter = execute(sim)
        result = meter.kpi(0,sim.hours)
        narrative = adapter.describe_applied(action,meter)
    elif action.kind=="explain":
        sim = _checked(Simulation,config,"无法按该场景重算。")
        meter = execute(sim)
        number = req.task_id if req.task_id is not None else action.task_id
        if number is None:
            placed = next((job.id for job in meter.sim.trace.jobs if meter.segments[job.id]),None)
            number = placed if placed is not None else (meter.sim.trace.jobs[0].id if meter.sim.trace.jobs else None)
            if number is None:
                raise HTTPException(404,"unknown task_id in this replay")
        if number not in meter.sim.trace.by_id:
            raise HTTPException(404,"unknown task_id in this replay")
        result = adapter.explain_decision({"task":meter.audit(number),"global":summarize_window(meter)})
    else:
        raise HTTPException(422,"无法识别指令，可试“优先绿电消纳”或“南京宕机”。")
    return {"action":action,"result":result,"narrative":narrative}


def _ledger_records(req:LedgerRequest):
    meter = execute(req)
    records = list(audited(meter).values())
    if req.task_id is not None and req.task_id not in meter.sim.trace.by_id:
        raise HTTPException(404,"unknown task_id in this replay")
    records.sort(key=lambda item:(not is_cross_region(item),item["task_id"]))
    return meter,records


def _public_receipt(receipt):
    view = compact_receipt(receipt)
    view["selection_reason"] = selection_reason(receipt)
    view["cross_region"] = is_cross_region(receipt)
    return view


@app.post("/api/v1/ledger")
def ledger(req:LedgerRequest):
    meter,records = _ledger_records(req)
    visible = records
    if req.cross_region_only:
        visible = [item for item in records if is_cross_region(item)]
    index = [dict(task_id=item["task_id"],source=item["source"],
                  dest=item["segments"][0]["node"] if item["segments"] else None,
                  cross_region=is_cross_region(item),sla_met=item["sla_met"],sha256=item["sha256"],
                  effective_efh=item["effective_efh"],electricity_cny=item["electricity_cny"],
                  co2_kg=item["co2_kg"],avoided_vs_grid_kg=item["avoided_vs_grid_kg"],
                  task_class=item["task_class"]) for item in visible]
    selected = visible
    if req.task_id is not None:
        selected = [item for item in records if item["task_id"]==req.task_id]
    elif req.limit is not None:
        selected = visible[:req.limit]
    return dict(assumptions=ASSUMPTIONS,global_summary=summarize_window(meter),index=index,
                receipts=[_public_receipt(item) for item in selected],
                tasks=len(records),cross_region_tasks=sum(is_cross_region(item) for item in records))


@app.post("/api/v1/ledger/csv")
def ledger_export(req:LedgerRequest):
    _,records = _ledger_records(req)
    if req.cross_region_only:
        records = [item for item in records if is_cross_region(item)]
    if req.task_id is not None:
        records = [item for item in records if item["task_id"]==req.task_id]
    body = ledger_csv([ledger_row(item,selection_reason(item)) for item in records])
    return Response(content=body,media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":"attachment; filename=sucompute-ledger.csv"})
