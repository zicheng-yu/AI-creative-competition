"""Local adapter boundary. TODO(zicheng): plug in LLM provider."""
import re
from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field

from .world import CITIES


class Fault(BaseModel):
    city: str
    kind: Literal["outage","capacity","pue"] = "outage"
    severity: float = Field(default=1.,gt=0,le=1)
    duration_slots: int = Field(default=12,ge=1,le=288)


class SchedulingControlAction(BaseModel):
    kind: Literal["weights","fault","explain","unknown"]
    weights: dict[str,float] = Field(default_factory=dict)
    fault: Fault | None = None


class ExplanationResult(BaseModel):
    summary: str
    evidence: dict


class BaseCopilotAdapter(ABC):
    @abstractmethod
    def parse_command(self,text:str) -> SchedulingControlAction: ...

    @abstractmethod
    def explain_decision(self,attribution_payload:dict) -> ExplanationResult: ...


class RuleBasedCopilotStub(BaseCopilotAdapter):
    def parse_command(self,text):
        if any(x in text for x in ("故障","宕机","折损","飙升")):
            city = next((c for c in CITIES if c in text or c=="安徽芜湖" and "芜湖" in text),None)
            match = re.search(r"(\d+(?:\.\d+)?)\s*[%％]",text)
            amount = float(match[1])/100 if match else 1.
            if not city or not 0<amount<=1:
                return SchedulingControlAction(kind="unknown")
            kind = "pue" if "pue" in text.lower() else "capacity" if amount<1 else "outage"
            return SchedulingControlAction(kind="fault",fault=Fault(city=city,kind=kind,severity=amount))
        for words,key in [(("绿电","碳排","保电"),"carbon"),(("成本","电费"),"cost"),
                          (("sla","时延"),"sla"),(("利用率",),"utilization")]:
            if any(w in text.lower() for w in words):
                match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d)",text)
                weight = float(match[1]) if match else .8
                if 0<=weight<=1:
                    return SchedulingControlAction(kind="weights",weights={key:weight})
                break
        return SchedulingControlAction(kind="explain" if "解释" in text or "归因" in text else "unknown")

    def explain_decision(self,attribution_payload):
        a = attribution_payload
        return ExplanationResult(summary=f"任务 {a['task_id']} 使用 {a['effective_efh']:.3f} EF·h，"
                                 f"电费 {a['electricity_cny']:.2f} 元，碳排 {a['co2_kg']:.2f} kg。",
                                 evidence={k:a[k] for k in ("sha256","segments","sla_met","avoided_vs_grid_kg")})
