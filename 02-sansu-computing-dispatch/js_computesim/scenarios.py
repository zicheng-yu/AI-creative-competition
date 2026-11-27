"""The four built-in stress scenarios."""

from __future__ import annotations

from dataclasses import dataclass

SCENARIO_NAMES = ("weekday", "green_surplus", "peak_conservation", "node_failure")


@dataclass(frozen=True)
class Scenario:
    name: str
    label: str
    season: str
    load_scale: float
    task_load_scale: dict[str, float]
    green_cf_scale: float
    green_contract_scale: float
    peak_capacity_derate: float
    apply_weekend: bool
    fault_day_1based: int | None
    offline_nodes: tuple[str, ...]
    pue_multiplier: dict[str, float]


def reward_weights(scenarios_cfg: dict) -> dict[str, float]:
    reward = scenarios_cfg["reward"]
    return {key: float(reward[key]) for key in ("w_served", "w_sla", "w_cost", "w_carbon")}


def get_scenario(scenarios_cfg: dict, name: str) -> Scenario:
    if name not in scenarios_cfg["scenarios"]:
        known = ", ".join(scenarios_cfg["scenarios"])
        raise KeyError(f"unknown scenario {name!r}; expected one of: {known}")
    raw = scenarios_cfg["scenarios"][name]
    fault = raw.get("fault") or None
    if fault is None:
        day = None
        offline: tuple[str, ...] = ()
        pue_mult: dict[str, float] = {}
    else:
        day = int(fault["day_1based"])
        offline = tuple(fault.get("offline") or [])
        pue_mult = {str(key): float(value) for key, value in (fault.get("pue_multiplier") or {}).items()}
    scales = {str(key): float(value) for key, value in (raw.get("task_load_scale") or {}).items()}
    return Scenario(
        name=name,
        label=str(raw["label"]),
        season=str(raw["season"]),
        load_scale=float(raw["load_scale"]),
        task_load_scale=scales,
        green_cf_scale=float(raw.get("green_cf_scale", 1.0)),
        green_contract_scale=float(raw.get("green_contract_scale", 1.0)),
        peak_capacity_derate=float(raw["peak_capacity_derate"]),
        apply_weekend=bool(raw["apply_weekend"]),
        fault_day_1based=day,
        offline_nodes=offline,
        pue_multiplier=pue_mult,
    )
