"""Seeded 7×24 arrival generator. The class mix is a scenario prior, not a trace fit."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from js_computesim.scenarios import Scenario
from js_computesim.topology import Node


@dataclass
class Cohort:
    task: int
    origin: int
    eflops: float
    age: int
    priority: int


def _normalized_diurnal(workload_cfg: dict, task_ids: list[str]) -> np.ndarray:
    rows = []
    for task in task_ids:
        curve = np.array(workload_cfg["diurnal"][task], dtype=np.float64)
        if curve.shape != (24,):
            raise ValueError(f"diurnal.{task} must have 24 hours")
        mean = float(curve.mean())
        if mean <= 0:
            raise ValueError(f"diurnal.{task} mean must be positive")
        rows.append(curve / mean)
    return np.stack(rows, axis=0)


def origin_shares(workload_cfg: dict, nodes: list[Node], task_ids: list[str]) -> np.ndarray:
    tilts = workload_cfg["origin_region_tilt"]
    shares = np.zeros((len(task_ids), len(nodes)), dtype=np.float64)
    for task_index, task in enumerate(task_ids):
        tilt = tilts[task]
        for node_index, node in enumerate(nodes):
            if node.kind != "city" or node.gdp_100m_cny is None:
                continue
            shares[task_index, node_index] = node.gdp_100m_cny * float(tilt[node.region])
        total = float(shares[task_index].sum())
        if total <= 0:
            raise ValueError(f"origin share for {task} is empty")
        shares[task_index] /= total
    return shares


def generate_arrivals(
    workload_cfg: dict,
    scenario: Scenario,
    nodes: list[Node],
    task_ids: list[str],
    jiangsu_eflops: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``arrivals[t, k, origin]`` and ``burst[t, origin]`` in reference EFlops."""
    hours = int(workload_cfg["episode_hours"])
    task_count = len(task_ids)
    node_count = len(nodes)
    mix = np.array([float(workload_cfg["task_mix"][task]) for task in task_ids], dtype=np.float64)
    if abs(float(mix.sum()) - 1.0) > 1e-9:
        raise ValueError(f"task_mix must sum to 1, got {mix.sum()}")
    scale = np.array(
        [float(scenario.task_load_scale.get(task, 1.0)) for task in task_ids],
        dtype=np.float64,
    )
    mean = jiangsu_eflops * float(workload_cfg["offered_load_fraction"]) * scenario.load_scale * mix * scale
    diurnal = _normalized_diurnal(workload_cfg, task_ids)
    weekend = np.array([float(workload_cfg["weekend_scale"][task]) for task in task_ids], dtype=np.float64)
    shares = origin_shares(workload_cfg, nodes, task_ids)
    sigma = float(workload_cfg["lognormal_sigma"])
    arrivals = np.zeros((hours, task_count, node_count), dtype=np.float64)
    for hour_index in range(hours):
        clock = hour_index % 24
        day = hour_index // 24
        is_weekend = scenario.apply_weekend and day >= 5
        noise = rng.lognormal(mean=-0.5 * sigma * sigma, sigma=sigma, size=task_count)
        factor = diurnal[:, clock] * noise
        if is_weekend:
            factor = factor * weekend
        arrivals[hour_index] = (mean * factor)[:, None] * shares

    burst_cfg = workload_cfg["burst"]
    probability = float(burst_cfg["probability_per_hour"])
    inference_index = task_ids.index("inference")
    burst_mean = float(mean[inference_index]) * float(burst_cfg["multiplier_of_inference_mean"])
    burst = np.zeros((hours, node_count), dtype=np.float64)
    for hour_index in range(hours):
        if float(rng.random()) < probability:
            burst[hour_index] = burst_mean * shares[inference_index]
    return arrivals, burst


def spawn_cohorts(
    arrivals_t: np.ndarray,
    burst_t: np.ndarray,
    priority: np.ndarray,
    burst_priority: int,
    inference_index: int,
) -> list[Cohort]:
    cohorts: list[Cohort] = []
    task_count, node_count = arrivals_t.shape
    for task in range(task_count):
        for origin in range(node_count):
            amount = float(arrivals_t[task, origin])
            if amount > 1e-12:
                cohorts.append(Cohort(task, origin, amount, 0, int(priority[task])))
    for origin in range(node_count):
        amount = float(burst_t[origin])
        if amount > 1e-12:
            cohorts.append(Cohort(inference_index, origin, amount, 0, int(burst_priority)))
    return cohorts
