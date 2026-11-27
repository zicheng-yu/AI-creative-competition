"""Seed, topology, tariff and one-episode checks for JS-ComputeSim-313."""

from __future__ import annotations

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from js_computesim import JSComputeSimEnv, SCENARIO_NAMES, run_episode
from js_computesim.energy import price_vector, solar_capacity_factor, wind_capacity_factor
from js_computesim.config import load_configs

DC_COUNTS = {
    "nanjing": 42,
    "wuxi": 37,
    "xuzhou": 22,
    "changzhou": 25,
    "suzhou": 61,
    "nantong": 28,
    "lianyungang": 11,
    "huaian": 12,
    "yancheng": 18,
    "yangzhou": 18,
    "zhenjiang": 12,
    "taizhou": 16,
    "suqian": 11,
}


@pytest.fixture(scope="module")
def configs():
    return load_configs()


def test_jiangsu_totals_and_latency():
    env = JSComputeSimEnv("weekday")
    cities = [node for node in env.nodes if node.kind == "city"]
    hubs = [node for node in env.nodes if node.kind == "hub"]
    assert len(cities) == 13
    assert len(hubs) == 3
    assert sum(node.dc_count for node in cities) == 313
    assert sum(node.dc_count for node in hubs) == 0
    assert sum(node.eflops for node in cities) == pytest.approx(271.8, abs=1e-6)
    assert {node.id: node.dc_count for node in cities} == DC_COUNTS
    nanjing = env.node_index["nanjing"]
    suzhou = env.node_index["suzhou"]
    shanghai = env.node_index["shanghai"]
    assert env.latency_ms[nanjing, nanjing] == 1.0
    assert env.latency_ms[nanjing, suzhou] == 5.0
    assert env.latency_ms[nanjing, shanghai] == 10.0
    assert env.latency_ms[shanghai, env.node_index["wuhu"]] == 10.0
    assert cities[0].eflops == pytest.approx(36.626606, abs=1e-4)
    for node in env.nodes:
        assert 1.16 <= node.pue_base <= 1.48


def test_published_carbon_and_uniform_jiangsu_tariff(configs):
    env = JSComputeSimEnv("weekday")
    assert env.east_china_kg_per_kwh == pytest.approx(0.5617)
    assert env.nodes[env.node_index["suzhou"]].carbon_kg_per_kwh == pytest.approx(0.5978)
    assert env.nodes[env.node_index["shanghai"]].carbon_kg_per_kwh == pytest.approx(0.5849)
    assert env.nodes[env.node_index["zhejiang"]].carbon_kg_per_kwh == pytest.approx(0.5153)
    assert env.nodes[env.node_index["wuhu"]].carbon_kg_per_kwh == pytest.approx(0.6782)
    east = JSComputeSimEnv("weekday", carbon_factor_mode="east_china")
    assert np.all(east.carbon_kg_per_kwh == pytest.approx(0.5617))

    summer = price_vector(configs["energy"], "summer")
    winter = price_vector(configs["energy"], "winter")
    assert summer[3] == pytest.approx(0.3485)  # valley
    assert summer[8] == pytest.approx(0.6263)  # flat
    assert summer[16] == pytest.approx(0.9682)  # peak
    assert summer[14] == pytest.approx(1.1221)  # spike
    assert summer[20] == pytest.approx(1.1221)
    assert winter[18] == pytest.approx(1.1505)
    assert winter[19] == pytest.approx(1.1505)
    env.reset(seed=1)
    snapshot = env.planning_snapshot()
    sunan = snapshot["price_sunan_cny_per_kwh"]
    assert np.array_equal(sunan, snapshot["price_subei_cny_per_kwh"])
    assert np.array_equal(sunan, snapshot["price_suzhong_cny_per_kwh"])
    assert np.array_equal(sunan, summer)


def test_green_curves_only_on_coastal_nodes(configs):
    wind = wind_capacity_factor(configs["energy"])
    solar = solar_capacity_factor(configs["energy"])
    assert wind.mean() == pytest.approx(0.36, abs=0.02)
    assert solar[0] == 0.0
    assert solar[12] == pytest.approx(0.72)
    env = JSComputeSimEnv("weekday")
    env.reset(seed=0)
    yancheng = env.green_mw[:, env.node_index["yancheng"]]
    suzhou = env.green_mw[:, env.node_index["suzhou"]]
    assert yancheng.sum() > 0
    assert suzhou.sum() == 0
    assert np.array_equal(env.green_mw[:24], env.green_mw[24:48])
    surplus = JSComputeSimEnv("green_surplus")
    surplus.reset(seed=0)
    assert surplus.green_mw.sum() > env.green_mw.sum()


def test_seed_reproducible_and_changes_arrivals():
    first = JSComputeSimEnv("weekday")
    second = JSComputeSimEnv("weekday")
    first.reset(seed=7)
    second.reset(seed=7)
    assert np.array_equal(first.arrivals, second.arrivals)
    assert np.array_equal(first.burst, second.burst)
    other = JSComputeSimEnv("weekday")
    other.reset(seed=8)
    assert not np.array_equal(first.arrivals, other.arrivals)

    random_a = run_episode("weekday", "random", seed=11)
    random_b = run_episode("weekday", "random", seed=11)
    assert random_a == random_b


def test_inference_cannot_cross_to_shanghai():
    env = JSComputeSimEnv("weekday")
    env.reset(seed=3)
    action = np.zeros((env.n_tasks, env.n_nodes, env.n_nodes, env.n_pools))
    task = env.task_index["inference"]
    origin = env.node_index["nanjing"]
    dest = env.node_index["shanghai"]
    pool = env.pool_ids.index("nvidia")
    action[task, origin, dest, pool] = 1.0
    env.step(action)
    assert env.last_served[task, :, dest, :].sum() == 0.0

    env.reset(seed=3)
    local = np.zeros_like(action)
    local[task, origin, origin, pool] = 1.0
    env.step(local)
    assert env.last_served[task, origin, origin, pool] > 0.0


def test_day4_fault_and_peak_derate():
    failed = JSComputeSimEnv("node_failure")
    failed.reset(seed=1)
    nanjing = failed.node_index["nanjing"]
    suzhou = failed.node_index["suzhou"]
    assert np.all(failed.health[72:96, nanjing] == 0.0)
    assert np.all(failed.health[:72, nanjing] == 1.0)
    assert np.all(failed.pue_multiplier[72:96, suzhou] == pytest.approx(1.35))
    action = np.ones(failed.action_space.shape)
    served_while_down = 0.0
    while failed.t < 96:
        hour = failed.t
        failed.step(action)
        if 72 <= hour < 96:
            served_while_down += float(failed.last_served[:, :, nanjing, :].sum())
    assert served_while_down == 0.0

    peak = JSComputeSimEnv("peak_conservation")
    peak.reset(seed=1)
    assert peak.capacity_derate[14, nanjing] == pytest.approx(0.8)
    assert peak.capacity_derate[14, peak.node_index["shanghai"]] == pytest.approx(1.0)
    assert peak.capacity_derate[3, nanjing] == pytest.approx(1.0)
    weekday = JSComputeSimEnv("weekday")
    weekday.reset(seed=1)
    assert np.all(weekday.capacity_derate == 1.0)


@pytest.mark.parametrize("scenario", SCENARIO_NAMES)
@pytest.mark.parametrize("policy", ["random", "greedy"])
def test_scenario_finishes_one_episode(scenario, policy):
    summary = run_episode(scenario, policy, seed=313)
    assert summary["steps"] == 168
    assert summary["served_ratio"] > 0
    assert np.isfinite(summary["energy_mwh"])
    assert np.isfinite(summary["carbon_t"])
    assert np.isfinite(summary["weighted_pue"])
    assert summary["sla_violation_ratio"] >= 0


def test_gymnasium_checker():
    env = JSComputeSimEnv("weekday")
    check_env(env, skip_render_check=True)


def test_planning_snapshot_shapes():
    env = JSComputeSimEnv("weekday")
    env.reset(seed=0)
    snap = env.planning_snapshot()
    assert snap["horizon"] == 168
    assert snap["eta"].shape == (5, 6)
    assert snap["arrivals_eflops"].shape == (168, 5, 16)
    assert snap["latency_ms"].shape == (16, 16)
    assert set(snap["task_ids"]) == {"pretrain", "finetune", "inference", "hpc", "general"}
    assert env.world["pool_share"].sum() == pytest.approx(1.0)
