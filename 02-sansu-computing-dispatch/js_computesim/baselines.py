"""Random and least-loaded greedy policies on the hourly preference action."""

from __future__ import annotations

import numpy as np

from js_computesim.env import JSComputeSimEnv, summarize_episode

POLICIES = ("random", "greedy")


def random_preference(env: JSComputeSimEnv, rng: np.random.Generator) -> np.ndarray:
    return rng.random((env.n_tasks, env.n_nodes, env.n_pools), dtype=np.float64)


def greedy_least_loaded(env: JSComputeSimEnv) -> np.ndarray:
    """Spread each task toward high effective throughput and low previous-hour load.

    The score ignores price on purpose: this is a load-balancing greedy, not
    the cost-first baseline. Feasibility is applied inside the env.
    """
    effective = env.eta * env.operator_gain
    health_hour = min(env.t, env.episode_hours - 1)
    health = env.health[health_hour]
    score = np.zeros((env.n_tasks, env.n_nodes, env.n_pools), dtype=np.float64)
    for task in range(env.n_tasks):
        raw = health[:, None] * effective[task][None, :] / (env.pool_util + 0.05)
        peak = float(raw.max())
        score[task] = raw / peak if peak > 0.0 else raw
    return score


def run_episode(scenario: str, policy: str, seed: int, carbon_factor_mode: str | None = None) -> dict[str, float]:
    if policy not in POLICIES:
        raise KeyError(f"unknown policy {policy!r}")
    env = JSComputeSimEnv(scenario=scenario, carbon_factor_mode=carbon_factor_mode)
    env.reset(seed=seed)
    rng = np.random.default_rng(seed)
    totals = {key: 0.0 for key in (
        "served_eflops",
        "arrived_eflops",
        "violated_eflops",
        "unfinished_eflops",
        "energy_kwh",
        "carbon_kg",
        "cost_cny",
        "green_kwh",
        "green_available_kwh",
        "pue_energy_kwh",
        "available_nameplate_eflops",
        "occupied_nameplate_eflops",
        "cross_domain_eflops",
        "reward",
    )}
    steps = 0
    truncated = False
    while not truncated:
        action = random_preference(env, rng) if policy == "random" else greedy_least_loaded(env)
        _obs, reward, _terminated, truncated, info = env.step(action)
        for key, value in info["metrics"].items():
            totals[key] += value
        totals["reward"] += float(reward)
        steps += 1
        if steps > env.episode_hours:
            raise RuntimeError("episode did not finish")
    summary = summarize_episode(totals)
    summary["steps"] = float(steps)
    summary["scenario"] = scenario
    summary["policy"] = policy
    summary["seed"] = float(seed)
    env.close()
    return summary
