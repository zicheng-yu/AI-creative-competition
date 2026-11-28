"""Dispatch copilot: deterministic Chinese parser and attribution.

Offline by default. When ``LLM_BASE_URL`` and ``LLM_API_KEY`` are both set, task
narratives can be rewritten by an OpenAI-compatible chat endpoint. Any failure,
or a reply that drops the voucher hash, falls back to the template.
"""
import os
import re
from abc import ABC, abstractmethod
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from .planner import DEFAULT
from .replay import compact_receipt
from .report import is_cross_region
from .world import CITIES, CROSS, POOLS, SLOTS


ASSUMPTIONS = (
    "电费使用 backend/world.py weather() 的演示分时电价（可配置假设），"
    "不是国网江苏省电力 2025 年 8 月 110 kV 两部制公告价的逐时复刻；"
    "公告价见 docs/DATA_CONSTRUCTION.md §1.3，供 JS-ComputeSim-313 小时环境使用。"
    "碳核算使用同一后端的演示参数 GRID=0.55 kgCO₂/kWh（world.py 注释写为 East China 2023 的近似）。"
    "生态环境部、国家统计局公告 2024 年第 33 号公布的 2022 年华东区域因子是 0.5617 kgCO₂/kWh，"
    "分省因子见该文档 §1.4。本凭证不把 0.55 写成那份公告里的数字。"
    "绿电只抵扣碳排、不抵扣电费。设施电量含 PUE 与保活，任务电费按同槽物理算力份额分摊。"
    "算力当量是按芯片亲和度 η 折算后的有效 EF·h。"
    "凭证是计量 JSON 的 SHA-256（键排序、紧凑分隔符、UTF-8，去掉 sha256 以及选中理由等展示字段）。"
)

PRESETS = (
    {"id":"peak-summer","label":"迎峰度夏保电","text":"迎峰度夏保电模式：碳排权重调至 0.6"},
    {"id":"nanjing-outage","label":"南京 30% 算力故障","text":"注入南京节点 30% 算力宕机故障"},
    {"id":"green-first","label":"优先绿电消纳","text":"优先绿电消纳"},
    {"id":"explain","label":"解释调度","text":"解释调度"},
)

WEIGHT_WORDS = (
    ("carbon",("碳排","碳排放","绿电","保电")),
    ("cost",("成本","电费")),
    ("sla",("sla","时延","延迟")),
    ("utilization",("利用率",)),
    ("network",("网络权重","带宽权重")),
)
FAULT_WORDS = ("故障","宕机","折损","飙升","离线","下线","注入")
CITY_ALIASES = (("杭州","浙江"),("芜湖","安徽芜湖"),("安徽","安徽芜湖"))


class Fault(BaseModel):
    city: str
    kind: Literal["outage","capacity","pue"] = "outage"
    severity: float = Field(default=1.,gt=0,le=1)
    duration_slots: int = Field(default=12,ge=1,le=288)


class SchedulingControlAction(BaseModel):
    kind: Literal["weights","fault","explain","unknown"]
    weights: dict[str,float] = Field(default_factory=dict)
    fault: Fault | None = None
    scenario: str | None = None
    task_id: int | None = None
    slot: int | None = None


class ExplanationResult(BaseModel):
    summary: str
    evidence: dict
    global_summary: str = ""
    generator: Literal["template","llm"] = "template"


class BaseCopilotAdapter(ABC):
    @abstractmethod
    def parse_command(self,text:str) -> SchedulingControlAction: ...

    @abstractmethod
    def explain_decision(self,attribution_payload:dict) -> ExplanationResult: ...

    def describe_applied(self,action:SchedulingControlAction,meter) -> str:
        return ""


def _number_near(text,end):
    """First number after a weight keyword. Looks forward so an earlier weight is not reused."""
    window = text[end:min(len(text),end+18)]
    match = re.search(r"(\d+(?:\.\d+)?)\s*([%％])?",window)
    if not match:
        return None
    value = float(match.group(1))
    if match.group(2):
        value /= 100.
    return value


def find_city(text):
    hits = []
    occupied = [False]*len(text)
    for name in sorted(CITIES,key=len,reverse=True):
        start = 0
        while True:
            index = text.find(name,start)
            if index<0:
                break
            if not any(occupied[index:index+len(name)]):
                hits.append((index,name))
                occupied[index:index+len(name)] = [True]*len(name)
            start = index+len(name)
    for alias,name in CITY_ALIASES:
        index = text.find(alias)
        if index>=0 and not any(occupied[index:index+len(alias)]):
            hits.append((index,name))
            occupied[index:index+len(alias)] = [True]*len(alias)
    if not hits:
        return None
    anchors = [m.start() for m in re.finditer("|".join(FAULT_WORDS),text)]
    if anchors:
        return min(hits,key=lambda hit:min(abs(hit[0]-anchor) for anchor in anchors))[1]
    return min(hits)[1]


def _duration(text):
    match = re.search(r"(?:持续|时长)\s*(\d+(?:\.\d+)?)\s*(小时|分钟|个槽|槽)",text)
    if not match:
        return 12
    amount = float(match.group(1))
    unit = match.group(2)
    if unit=="小时":
        slots = round(amount*SLOTS)
    elif unit=="分钟":
        slots = round(amount/5)
    else:
        slots = round(amount)
    return min(288,max(1,slots))


def _slot(text):
    match = re.search(r"第\s*(\d+)\s*小时",text)
    if not match:
        return None
    return int(match.group(1))*SLOTS


def _fault(text):
    if not any(word in text for word in FAULT_WORDS):
        return None
    city = find_city(text)
    if not city:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*([%％])",text)
    amount = float(match.group(1))/100 if match else 1.
    if not 0<amount<=1:
        return "invalid"
    if "pue" in text.lower():
        kind = "pue"
    elif amount<1:
        kind = "capacity"
    else:
        kind = "outage"
    return Fault(city=city,kind=kind,severity=amount,duration_slots=_duration(text))


def _weights(text):
    if not any(cue in text for cue in ("权重","调至","调到","设为","优先")):
        return {}
    found = {}
    invalid = False
    for key,words in WEIGHT_WORDS:
        for word in words:
            haystack = text.lower() if word.isascii() else text
            needle = word.lower() if word.isascii() else word
            index = haystack.find(needle)
            if index<0:
                continue
            value = _number_near(text,index+len(word))
            if value is None:
                found.setdefault(key,None)
            elif not 0<=value<=1:
                invalid = True
            else:
                found[key] = value
    if invalid:
        return None
    if not found:
        return {}
    if all(value is None for value in found.values()):
        return {key:.8 for key in found}
    return {key:value for key,value in found.items() if value is not None}


def _scenario(text):
    if any(word in text for word in ("迎峰度夏","尖峰保电","保电模式")):
        return "peak_shaving"
    if any(word in text for word in ("绿电大发","高比例绿电")):
        return "high_renewable"
    if "故障压测" in text:
        return "fault_stress"
    if any(word in text for word in ("常规工作日","恢复常规")):
        return "normal_weekday"
    return None


def _task_id(text):
    match = re.search(r"(?:任务|task)\s*#?\s*(\d+)",text,re.I)
    if match:
        return int(match.group(1))
    match = re.search(r"#(\d+)",text)
    return int(match.group(1)) if match else None


def selection_reason(receipt):
    """Chinese per-task attribution from a Meter.audit receipt. No new numbers."""
    source = receipt["source"]
    source_name = CITIES[source]
    kind = receipt["task_class"]
    strategy = receipt["strategy"]
    segments = receipt["segments"]
    if not segments:
        return "\n".join((
            f"任务 {receipt['task_id']}（{kind}，策略 {strategy}）从{source_name}提交，没有可执行分段。",
            f"SLA {'达成' if receipt['sla_met'] else '未达成'}。",
            f"碳减排凭证 SHA-256 为 {receipt['sha256']}。",
        ))
    segment = segments[0]
    dest = CITIES[segment["node"]]
    pool = segment["pool"]
    chosen = receipt["candidate_affinity"][segment["node"]]
    scores = chosen["scores"]
    pool_index = POOLS.index(pool)
    score = scores[pool_index]
    ranked = max(range(len(scores)),key=lambda i:(chosen["feasible"][i],scores[i]))
    listed = "、".join(f"{name} {value:.2f}" for name,value in zip(POOLS,scores))
    affinity = (
        f"芯片亲和度 η 只随任务类型变化。{kind} 在六池上的分数为 {listed}。"
        f"选中的 {pool} 亲和度是 {score:.2f}。"
    )
    if chosen["feasible"][pool_index]:
        affinity += f"该池在{dest}的首次决策掩码里可行。"
        if ranked==pool_index:
            affinity += "在这个节点的可行池中，该亲和度最高。"
        else:
            affinity += (
                f"这个节点可行池里亲和度最高的是 {POOLS[ranked]}（{scores[ranked]:.2f}）。"
                "选中池不是最高亲和度，说明时延、负载或策略打分盖过了单纯的芯片分数。"
            )
    else:
        affinity += "账本里的首次可行掩码没有标出该池，执行段可能来自后续迁移。"
    latency = segment["latency_ms"]
    limit = receipt["latency_limit_ms"]
    delay = (
        f"落到{dest}的网络时延是 {latency} ms，任务预算 {limit} ms，"
        f"{'没有超过预算' if latency<=limit else '超过预算'}。"
    )
    resource = segment.get("resource_shadow")
    carbon = segment.get("carbon_shadow")
    if resource is None or carbon is None:
        shadow = "该策略没有写入 MILP 影子价格。"
    else:
        ranked_nodes = [item for item in receipt["candidate_affinity"]
                        if any(item["feasible"]) and item["resource_shadow"] is not None]
        ranked_nodes.sort(key=lambda item:item["resource_shadow"])
        place = next((i+1 for i,item in enumerate(ranked_nodes) if item["node"]==segment["node"]),None)
        shadow = f"选中分段的资源影子价格是 {resource:.4f}，碳影子价格是 {carbon:.4f}。"
        if place:
            shadow += f"在至少有一个可行池的节点里，按资源影子价格从低到高排第 {place}/{len(ranked_nodes)}。"
        origin = receipt["candidate_affinity"][source]
        if origin["resource_shadow"] is not None and source!=segment["node"]:
            shadow += (
                f"来源{source_name}的资源影子价格是 {origin['resource_shadow']:.4f}，"
                f"碳影子价格是 {origin['carbon_shadow']:.4f}。"
            )
        shadow += "影子价格是该次线性松弛的对偶值，用来说明容量或碳预算有多紧，不是电价。"
    site = (
        f"这段按物理算力份额分摊后的实时 PUE 是 {segment['pue']:.3f}，"
        f"绿电占比是 {segment['green_share']:.2%}。"
    )
    probability = segment.get("probability")
    if strategy in ("SuCompute","Safe-RL-only") and probability is not None:
        policy = (
            f"Safe-RL 在首次决策的可行集合上对打分做 softmax，选中动作的概率是 {probability:.2%}。"
            "这个概率描述的是相对打分，不是历史频率。"
        )
    elif strategy=="MILP-only":
        policy = "MILP-only 按配额、亲和度和负载打分选址，不输出 Safe-RL 动作概率。"
    elif strategy=="RR-Local":
        policy = "就近轮询在时延最小的可行节点之间轮转，不使用影子价格或 Safe-RL 概率。"
    elif strategy=="Least-Loaded":
        policy = "最低负载策略按池占用选址，不使用影子价格或 Safe-RL 概率。"
    elif strategy=="Cost-First":
        policy = "成本优先按边际电价选址，不使用影子价格或 Safe-RL 概率。"
    else:
        policy = "这次没有 Safe-RL 动作概率。"
    cross = "这是长三角跨域任务（执行时延 10 ms）。" if is_cross_region(receipt) else "这是省内或同城任务（时延低于 10 ms）。"
    if len(segments)>1:
        cross += f"执行分成 {len(segments)} 段，计量按各段分摊后相加。"
    account = (
        f"算力当量 {receipt['effective_efh']:.4f} EF·h，电费结算 {receipt['electricity_cny']:.2f} 元，"
        f"碳排 {receipt['co2_kg']:.2f} kg，相对同电量全网购电少排 {receipt['avoided_vs_grid_kg']:.2f} kg。"
        f"SLA {'达成' if receipt['sla_met'] else '未达成'}。"
        f"碳减排凭证 SHA-256 为 {receipt['sha256']}。"
    )
    return "\n".join((
        f"任务 {receipt['task_id']}（{kind}，策略 {strategy}）从{source_name}派到{dest}的 {pool} 池。",
        affinity,delay,shadow,site,policy,cross,account,
    ))


def summarize_window(meter):
    """Global attribution from the live calendar, plan duals and segment probabilities."""
    trace = meter.sim.trace
    kpi = meter.kpi(0,trace.hours)
    cross_tasks = set()
    probabilities = []
    for segment in meter.sim.segments:
        job = trace.by_id[segment.task]
        if CROSS[job.src,segment.node]:
            cross_tasks.add(segment.task)
        if segment.probability is not None:
            probabilities.append(segment.probability)
    plan = meter.sim.plan
    if plan is not None and len(plan.resource):
        resource_index = max(range(len(plan.resource)),key=lambda i:float(plan.resource[i]))
        carbon_index = max(range(len(plan.carbon)),key=lambda i:float(plan.carbon[i]))
        shadow = (
            f"最近一次 MILP 规划里，资源影子价格最高的节点是{CITIES[resource_index]}"
            f"（{float(plan.resource[resource_index]):.4f}），"
            f"碳影子价格最高的节点是{CITIES[carbon_index]}"
            f"（{float(plan.carbon[carbon_index]):.4f}）。"
        )
    else:
        shadow = "当前策略没有 MILP 规划，所以没有节点影子价格。"
    if probabilities:
        policy = (
            f"Safe-RL 记下了 {len(probabilities)} 段动作概率，"
            f"选中动作的平均概率是 {sum(probabilities)/len(probabilities):.2%}。"
        )
    else:
        policy = "当前策略不输出 Safe-RL 动作概率。"
    weights = "，".join(f"{key}={value:.2f}" for key,value in meter.sim.weights.items())
    defaults = "，".join(f"{key}={value:.2f}" for key,value in DEFAULT.items())
    return "\n".join((
        f"全局调度：策略 {meter.sim.strategy}，场景 {trace.scenario}，种子 {trace.seed}，窗口 {trace.hours} 小时。",
        f"生效权重 {weights}。规划器缺省值是 {defaults}，指令只覆盖写明的项。",
        f"任务 {kpi['tasks']} 个，SLA 履约率 {kpi['sla']:.2%}，绿电消纳占比 {kpi['green_share']:.2%}，"
        f"平均 PUE {kpi['pue']:.3f}，单位碳强度 {kpi['kgco2_per_efh']:.2f} kgCO₂/EF·h。",
        f"长三角跨域任务 {len(cross_tasks)} 个（至少有一段 10 ms 跨省链路）。",
        shadow,policy,
        "单任务电费只包含按物理算力份额分到该任务的设施电量；空载和保活留在全网指标里。",
        ASSUMPTIONS,
    ))


def _llm_complete(template,voucher):
    base = os.environ.get("LLM_BASE_URL","").strip().rstrip("/")
    key = os.environ.get("LLM_API_KEY","").strip()
    model = os.environ.get("LLM_MODEL","").strip() or "gpt-4o-mini"
    if not base or not key:
        return None
    url = base if base.endswith("/chat/completions") else base+"/chat/completions"
    system = (
        "你是苏算绿枢的调度归因助手。只根据给定模板改写中文，"
        "不得新增、修改或删除任何数字、城市、单位和哈希，不得补充模板里没有的文献。"
        "必须原样保留碳减排凭证 SHA-256。做不到时原样输出模板。"
    )
    try:
        response = httpx.post(url,headers={"Authorization":f"Bearer {key}"},
                              json={"model":model,"temperature":0,"messages":[
                                  {"role":"system","content":system},
                                  {"role":"user","content":template}]},timeout=8.0)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except Exception:
        return None
    text = content.strip() if isinstance(content,str) else ""
    if not text or voucher not in text:
        return None
    return text


class RuleBasedCopilotStub(BaseCopilotAdapter):
    """Deterministic grammar plus template explanations. This is the default adapter."""

    def parse_command(self,text):
        fault = _fault(text)
        if fault=="invalid":
            return SchedulingControlAction(kind="unknown")
        if isinstance(fault,Fault):
            return SchedulingControlAction(kind="fault",fault=fault,slot=_slot(text))
        weights = _weights(text)
        if weights is None:
            return SchedulingControlAction(kind="unknown")
        scenario = _scenario(text)
        if weights or scenario:
            return SchedulingControlAction(kind="weights",weights=weights,scenario=scenario)
        if any(word in text for word in ("解释","归因","为什么")):
            return SchedulingControlAction(kind="explain",task_id=_task_id(text))
        return SchedulingControlAction(kind="unknown")

    def explain_decision(self,attribution_payload):
        if isinstance(attribution_payload.get("task"),dict):
            task = attribution_payload["task"]
            globe = attribution_payload.get("global") or ""
        else:
            task = attribution_payload
            globe = ""
        reason = selection_reason(task)
        segment = task["segments"][0] if task["segments"] else {}
        evidence = dict(sha256=task["sha256"],segments=task["segments"],sla_met=task["sla_met"],
                        avoided_vs_grid_kg=task["avoided_vs_grid_kg"],selection_reason=reason,
                        effective_efh=task["effective_efh"],electricity_cny=task["electricity_cny"],
                        co2_kg=task["co2_kg"],cross_region=is_cross_region(task),
                        pue=segment.get("pue"),green_share=segment.get("green_share"),
                        probability=segment.get("probability"),
                        resource_shadow=segment.get("resource_shadow"),
                        carbon_shadow=segment.get("carbon_shadow"),
                        assumptions=ASSUMPTIONS,template_summary=reason,
                        receipt=compact_receipt(dict(task)))
        return ExplanationResult(summary=reason,evidence=evidence,global_summary=globe)

    def describe_applied(self,action,meter):
        if action.kind=="fault" and action.fault:
            fault = action.fault
            if fault.kind=="pue":
                scale = f"PUE 增量 {fault.severity:.2f}"
            elif fault.kind=="outage":
                scale = "节点容量全部离线"
            else:
                scale = f"容量损失比例 {fault.severity:.0%}"
            lead = (
                f"已在{fault.city}注入{ {'outage':'离线','capacity':'算力容量下降','pue':'PUE 上浮'}[fault.kind] }，"
                f"{scale}，持续 {fault.duration_slots} 个 5 分钟槽，并已立即重算。"
            )
        elif action.kind=="weights":
            lead = "已按指令更新调度目标并立即重算。"
            if action.scenario:
                lead = f"已切换场景为 {action.scenario}，并立即重算。"
            if action.weights:
                written = "，".join(f"{key}={value:.2f}" for key,value in action.weights.items())
                lead += f"本次写入的权重：{written}。"
        else:
            return ""
        return lead+"\n"+summarize_window(meter)


class OpenAICompatibleCopilot(RuleBasedCopilotStub):
    """Same parser and ledger facts. Optionally rewrites the task narrative."""

    def explain_decision(self,attribution_payload):
        base = super().explain_decision(attribution_payload)
        task = attribution_payload["task"] if isinstance(attribution_payload.get("task"),dict) else attribution_payload
        rewritten = _llm_complete(base.summary,task.get("sha256",""))
        if not rewritten:
            return base
        evidence = dict(base.evidence)
        evidence["generator"] = "llm"
        return base.model_copy(update={"summary":rewritten,"generator":"llm","evidence":evidence})


def default_adapter():
    if os.environ.get("LLM_BASE_URL","").strip() and os.environ.get("LLM_API_KEY","").strip():
        return OpenAICompatibleCopilot()
    return RuleBasedCopilotStub()
