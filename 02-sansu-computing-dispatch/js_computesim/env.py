"""Gymnasium environment for hourly allocation on JS-ComputeSim-313.

Action
    Preference, shape ``(task, dest, pool)``, values >= 0. For each origin the
    environment keeps destinations whose design latency is within the task SLA
    and renormalizes. An explicit MILP plan, shape
    ``(task, origin, dest, pool)``, is accepted by ``step`` as well.

Observation
    A clipped float32 vector. Layout is ``observation_layout``. Raw queue,
    forecast and coefficients are on the env and in ``planning_snapshot``.

Constraint cost
    ``info["cost"]`` is reference EFlops that missed their deadline this hour
    (plus unfinished work when the episode ends). Safe-RL can treat it as the
    Lagrangian cost. Currency and carbon stay in ``info["metrics"]``.
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from js_computesim.config import load_configs
from js_computesim.energy import facility_power_mw, green_available_mw, price_vector
from js_computesim.scenarios import Scenario, get_scenario, reward_weights
from js_computesim.scheduling import serve
from js_computesim.topology import build_topology
from js_computesim.workload import Cohort, generate_arrivals, spawn_cohorts

OBS_CLIP = 5.0


class JSComputeSimEnv(gym.Env):
    """7-day hourly scheduling gym. One episode is 168 steps."""

    metadata = {"render_modes": ["ansi"], "name": "JSComputeSim-313"}

    def __init__(
        self,
        scenario: str = "weekday",
        config_dir: str | None = None,
        carbon_factor_mode: str | None = None,
        render_mode: str | None = None,
    ):
        super().__init__()
        self.render_mode = render_mode
        self.configs = load_configs(config_dir)
        self.world = build_topology(self.configs)
        self.scenario: Scenario = get_scenario(self.configs["scenarios"], scenario)
        self.reward_w = reward_weights(self.configs["scenarios"])
        mode = carbon_factor_mode or self.world["carbon_default_mode"]
        if mode not in ("provincial", "east_china"):
            raise ValueError("carbon_factor_mode must be 'provincial' or 'east_china'")
        self.carbon_factor_mode = mode

        self.nodes = self.world["nodes"]
        self.node_ids: list[str] = self.world["node_ids"]
        self.pool_ids: list[str] = self.world["pool_ids"]
        self.task_ids: list[str] = self.world["task_ids"]
        self.node_index = {node_id: index for index, node_id in enumerate(self.node_ids)}
        self.task_index = {task_id: index for index, task_id in enumerate(self.task_ids)}
        self.n_nodes = len(self.node_ids)
        self.n_pools = len(self.pool_ids)
        self.n_tasks = len(self.task_ids)
        self.episode_hours = int(self.configs["workload"]["episode_hours"])

        workload = self.configs["workload"]
        self.sla_latency_ms = np.array(
            [float(workload["sla_latency_ms"][task]) for task in self.task_ids], dtype=np.float64
        )
        self.deadline_h = np.array(
            [int(workload["deadline_hours"][task]) for task in self.task_ids], dtype=np.int64
        )
        self.priority = np.array(
            [int(workload["priority"][task]) for task in self.task_ids], dtype=np.int64
        )
        self.burst_priority = int(workload["burst"]["priority"])
        self.inference_index = self.task_index["inference"]

        energy = self.configs["energy"]
        power = energy["power"]
        self.it_kw_per_eflops = float(power["assumption_it_kw_per_eflops"])
        self.alpha = float(power["assumption_alpha"])
        self.pue_util_coeff = float(power["assumption_pue_util_coeff"])
        self.idle_fraction = np.array(
            [float(power["assumption_idle_fraction"][pool]) for pool in self.pool_ids],
            dtype=np.float64,
        )
        self.pue_base = np.array([node.pue_base for node in self.nodes], dtype=np.float64)
        self._carbon_provincial = np.array(
            [node.carbon_kg_per_kwh for node in self.nodes], dtype=np.float64
        )
        self.east_china_kg_per_kwh = float(self.world["east_china_kg_per_kwh"])
        if self.carbon_factor_mode == "east_china":
            self.carbon_kg_per_kwh = np.full(self.n_nodes, self.east_china_kg_per_kwh)
        else:
            self.carbon_kg_per_kwh = self._carbon_provincial.copy()

        self.nameplate_eflops = np.array(self.world["nameplate_eflops"], dtype=np.float64)
        self.eta = np.array(self.world["eta"], dtype=np.float64)
        self.operator_gain = np.array(self.world["operator_gain"], dtype=np.float64)
        self.latency_ms = np.array(self.world["latency_ms"], dtype=np.float64)
        self.jiangsu_mask = np.array([node.kind == "city" for node in self.nodes], dtype=bool)
        self.spike_price = float(energy["tariff"]["tables"]["summer"]["spike"])

        self.action_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(self.n_tasks, self.n_nodes, self.n_pools),
            dtype=np.float32,
        )
        self.observation_layout = self._build_layout()
        self.observation_space = spaces.Box(
            low=0.0,
            high=OBS_CLIP,
            shape=(self.observation_layout["dim"],),
            dtype=np.float32,
        )

        self._seed: int | None = None
        self.rng: np.random.Generator | None = None
        self.t = 0
        self.cohorts: list[Cohort] = []
        self.arrivals = np.zeros((self.episode_hours, self.n_tasks, self.n_nodes))
        self.burst = np.zeros((self.episode_hours, self.n_nodes))
        self.health = np.ones((self.episode_hours, self.n_nodes))
        self.pue_multiplier = np.ones((self.episode_hours, self.n_nodes))
        self.capacity_derate = np.ones((self.episode_hours, self.n_nodes))
        self.price_cny_per_kwh = np.zeros((self.episode_hours, self.n_nodes))
        self.green_mw = np.zeros((self.episode_hours, self.n_nodes))
        self.hour_bands: list[str] = []
        self.pool_util = np.zeros((self.n_nodes, self.n_pools))
        self.node_util = np.zeros(self.n_nodes)
        self.last_served = np.zeros((self.n_tasks, self.n_nodes, self.n_nodes, self.n_pools))
        self._hour_arrived = 0.0

    def _build_layout(self) -> dict[str, Any]:
        cursor = 0
        slices: dict[str, slice] = {}

        def take(name: str, width: int) -> None:
            nonlocal cursor
            slices[name] = slice(cursor, cursor + width)
            cursor += width

        take("time", 3)
        take("queue", self.n_tasks * self.n_nodes)
        take("health", self.n_nodes)
        take("util", self.n_nodes)
        take("price", self.n_nodes)
        take("green", self.n_nodes)
        take("pue", self.n_nodes)
        take("arrival", self.n_tasks * self.n_nodes)
        return {"dim": cursor, "slices": slices}

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        del options  # accepted so check_env can pass options={}
        if seed is None:
            self._seed = int(self.np_random.integers(0, 2**31 - 1))
        else:
            self._seed = int(seed)
        self.rng = np.random.default_rng(self._seed)
        self._materialize_episode()
        self.t = 0
        self.pool_util[:] = 0.0
        self.node_util[:] = 0.0
        self.last_served[:] = 0.0
        self.cohorts = self._spawn(0)
        self._hour_arrived = self._arrived_amount(0)
        return self._obs(), self._info(0.0, 0.0, 0.0, 0.0, empty_metrics=True)

    def step(self, action):
        if self.t >= self.episode_hours:
            raise RuntimeError("episode is finished; call reset()")
        hour = self.t
        health = self.health[hour]
        derate = self.capacity_derate[hour]
        available = self.nameplate_eflops * health[:, None] * derate[:, None]
        cohorts, served, occupied = serve(
            self.cohorts,
            action,
            latency_ms=self.latency_ms,
            sla_latency_ms=self.sla_latency_ms,
            health=health,
            remaining_nameplate=available,
            eta=self.eta,
            gain=self.operator_gain,
        )
        self.cohorts = cohorts
        self.last_served = served
        with np.errstate(divide="ignore", invalid="ignore"):
            self.pool_util = np.divide(
                occupied, available, out=np.zeros_like(occupied), where=available > 0
            )
        facility_mw, util_node, pue = facility_power_mw(
            occupied,
            available,
            health,
            self.pue_base,
            self.pue_multiplier[hour],
            self.idle_fraction,
            self.it_kw_per_eflops,
            self.alpha,
            self.pue_util_coeff,
        )
        self.node_util = util_node
        energy_kwh = facility_mw * 1000.0
        green_available_kwh = self.green_mw[hour] * 1000.0
        green_kwh = np.minimum(energy_kwh, green_available_kwh)
        grid_kwh = energy_kwh - green_kwh
        price = self.price_cny_per_kwh[hour]
        cost_cny = float(np.sum(energy_kwh * price))
        carbon_kg = float(np.sum(grid_kwh * self.carbon_kg_per_kwh))
        served_eflops = float(served.sum())
        cross = served[:, :, ~self.jiangsu_mask, :].sum()
        arrived = self._hour_arrived

        self.cohorts, violated = self._age_and_expire(self.cohorts)
        self.t += 1
        unfinished = 0.0
        truncated = self.t >= self.episode_hours
        if truncated:
            unfinished = float(sum(cohort.eflops for cohort in self.cohorts))
            violated += unfinished
            self.cohorts = []
        else:
            self.cohorts.extend(self._spawn(self.t))
            self._hour_arrived = self._arrived_amount(self.t)

        violated_total = violated
        reward = self._reward(served_eflops, violated_total, cost_cny, carbon_kg, arrived)
        metrics = {
            "served_eflops": served_eflops,
            "arrived_eflops": float(arrived),
            "violated_eflops": float(violated_total),
            "unfinished_eflops": float(unfinished),
            "energy_kwh": float(energy_kwh.sum()),
            "carbon_kg": carbon_kg,
            "cost_cny": cost_cny,
            "green_kwh": float(green_kwh.sum()),
            "green_available_kwh": float(green_available_kwh.sum()),
            "pue_energy_kwh": float(np.sum(pue * energy_kwh)),
            "available_nameplate_eflops": float(available.sum()),
            "occupied_nameplate_eflops": float(occupied.sum()),
            "cross_domain_eflops": float(cross),
        }
        return self._obs(), float(reward), False, bool(truncated), self._info(
            reward, served_eflops, violated_total, cost_cny, metrics=metrics
        )

    def planning_snapshot(self) -> dict[str, Any]:
        """Arrays a MILP can read. The forecast is the generator's own future."""
        if self.rng is None:
            raise RuntimeError("call reset() before planning_snapshot()")
        remaining = self.episode_hours - self.t
        future = slice(self.t, self.episode_hours)
        queue = self._queue_matrix()
        return {
            "t": int(self.t),
            "horizon": int(remaining),
            "scenario": self.scenario.name,
            "seed": self._seed,
            "node_ids": list(self.node_ids),
            "pool_ids": list(self.pool_ids),
            "task_ids": list(self.task_ids),
            "latency_ms": self.latency_ms.copy(),
            "sla_latency_ms": self.sla_latency_ms.copy(),
            "deadline_hours": self.deadline_h.copy(),
            "eta": self.eta.copy(),
            "operator_gain": self.operator_gain.copy(),
            "nameplate_eflops": self.nameplate_eflops.copy(),
            "queue_eflops": queue,
            "arrivals_eflops": self.arrivals[future].copy(),
            "burst_inference_eflops": self.burst[future].copy(),
            "health": self.health[future].copy(),
            "capacity_derate": self.capacity_derate[future].copy(),
            "pue_multiplier": self.pue_multiplier[future].copy(),
            "pue_base": self.pue_base.copy(),
            "price_cny_per_kwh": self.price_cny_per_kwh[future].copy(),
            "green_available_mw": self.green_mw[future].copy(),
            "carbon_kg_per_kwh": self.carbon_kg_per_kwh.copy(),
            "east_china_kg_per_kwh": self.east_china_kg_per_kwh,
            "carbon_factor_mode": self.carbon_factor_mode,
            "it_kw_per_eflops": self.it_kw_per_eflops,
            "alpha": self.alpha,
            "idle_fraction": self.idle_fraction.copy(),
            "pue_util_coeff": self.pue_util_coeff,
            "price_sunan_cny_per_kwh": self._region_price_today("sunan"),
            "price_subei_cny_per_kwh": self._region_price_today("subei"),
            "price_suzhong_cny_per_kwh": self._region_price_today("suzhong"),
        }

    def action_mask(self) -> np.ndarray:
        """Latency-and-health mask broadcast to preference shape (task, dest, pool).

        The mask uses a logical AND across origins that still have a queue, so a
        destination must be feasible for every queued origin of that task. Prefer
        ``planning_snapshot`` when origins differ. Health is the current hour.
        """
        hour = min(self.t, self.episode_hours - 1)
        health = self.health[hour] > 0
        queue = self._queue_matrix()
        mask = np.zeros((self.n_tasks, self.n_nodes, self.n_pools), dtype=bool)
        for task in range(self.n_tasks):
            origins = np.flatnonzero(queue[task] > 1e-12)
            if origins.size == 0:
                feasible = np.ones(self.n_nodes, dtype=bool)
            else:
                feasible = np.ones(self.n_nodes, dtype=bool)
                for origin in origins:
                    feasible &= self.latency_ms[origin] <= self.sla_latency_ms[task]
            feasible &= health
            mask[task, feasible, :] = True
        return mask

    def render(self):
        if self.render_mode != "ansi":
            return None
        queued = float(sum(cohort.eflops for cohort in self.cohorts))
        return f"t={self.t}/{self.episode_hours} scenario={self.scenario.name} queue_eflops={queued:.4f}"

    def _materialize_episode(self) -> None:
        assert self.rng is not None
        arrivals, burst = generate_arrivals(
            self.configs["workload"],
            self.scenario,
            self.nodes,
            self.task_ids,
            float(self.world["jiangsu_total_eflops"]),
            self.rng,
        )
        self.arrivals = arrivals
        self.burst = burst
        energy = self.configs["energy"]
        hourly_price = price_vector(energy, self.scenario.season)
        self.hour_bands = _bands_for_season(energy, self.scenario.season)
        day_price = np.repeat(hourly_price[:, None], self.n_nodes, axis=1)
        self.price_cny_per_kwh = np.tile(day_price, (self.episode_hours // 24, 1))
        self.green_mw = green_available_mw(
            energy,
            self.nodes,
            self.episode_hours,
            self.scenario.green_cf_scale,
            self.scenario.green_contract_scale,
        )
        self.health = np.ones((self.episode_hours, self.n_nodes), dtype=np.float64)
        self.pue_multiplier = np.ones((self.episode_hours, self.n_nodes), dtype=np.float64)
        self.capacity_derate = np.ones((self.episode_hours, self.n_nodes), dtype=np.float64)
        peak_or_spike = {index for index, band in enumerate(self.hour_bands) if band in ("peak", "spike")}
        derate = float(self.scenario.peak_capacity_derate)
        for hour in range(self.episode_hours):
            if hour % 24 in peak_or_spike:
                self.capacity_derate[hour, self.jiangsu_mask] = derate
        if self.scenario.fault_day_1based is not None:
            day = self.scenario.fault_day_1based - 1
            start = day * 24
            stop = start + 24
            for node_id in self.scenario.offline_nodes:
                self.health[start:stop, self.node_index[node_id]] = 0.0
            for node_id, multiplier in self.scenario.pue_multiplier.items():
                self.pue_multiplier[start:stop, self.node_index[node_id]] = multiplier

    def _spawn(self, hour: int) -> list[Cohort]:
        return spawn_cohorts(
            self.arrivals[hour],
            self.burst[hour],
            self.priority,
            self.burst_priority,
            self.inference_index,
        )

    def _arrived_amount(self, hour: int) -> float:
        return float(self.arrivals[hour].sum() + self.burst[hour].sum())

    def _age_and_expire(self, cohorts: list[Cohort]) -> tuple[list[Cohort], float]:
        kept: list[Cohort] = []
        violated = 0.0
        for cohort in cohorts:
            if cohort.eflops <= 1e-12:
                continue
            cohort.age += 1
            if cohort.age >= int(self.deadline_h[cohort.task]):
                violated += cohort.eflops
            else:
                kept.append(cohort)
        return kept, violated

    def _queue_matrix(self) -> np.ndarray:
        queue = np.zeros((self.n_tasks, self.n_nodes), dtype=np.float64)
        for cohort in self.cohorts:
            queue[cohort.task, cohort.origin] += cohort.eflops
        return queue

    def _obs(self) -> np.ndarray:
        hour = min(self.t, self.episode_hours - 1)
        queue = self._queue_matrix()
        if self.t < self.episode_hours:
            arrival = self.arrivals[self.t] + self.burst[self.t] * _inference_column(self)
        else:
            arrival = np.zeros((self.n_tasks, self.n_nodes))
        total = float(self.world["jiangsu_total_eflops"])
        green_ref = max(float(self.green_mw.max()), 1.0)
        parts = [
            np.array(
                [
                    self.t / max(self.episode_hours - 1, 1),
                    (hour % 24) / 23.0,
                    (hour // 24) / 6.0,
                ]
            ),
            (queue / total).reshape(-1),
            self.health[hour],
            self.node_util,
            self.price_cny_per_kwh[hour] / self.spike_price,
            self.green_mw[hour] / green_ref,
            np.minimum(self.pue_base * self.pue_multiplier[hour] / 2.0, OBS_CLIP),
            (arrival / total).reshape(-1),
        ]
        obs = np.concatenate(parts).astype(np.float32, copy=False)
        return np.clip(obs, 0.0, OBS_CLIP).copy()

    def _reward(
        self,
        served: float,
        violated: float,
        cost_cny: float,
        carbon_kg: float,
        arrived: float,
    ) -> float:
        scale = max(arrived, 1e-6)
        weights = self.reward_w
        return (
            weights["w_served"] * served
            - weights["w_sla"] * violated
            - weights["w_cost"] * cost_cny
            - weights["w_carbon"] * carbon_kg
        ) / scale

    def _info(
        self,
        reward: float,
        served: float,
        violated: float,
        cost_cny: float,
        metrics: dict[str, float] | None = None,
        empty_metrics: bool = False,
    ) -> dict[str, Any]:
        if empty_metrics:
            metrics = {key: 0.0 for key in _METRIC_KEYS}
        assert metrics is not None
        return {
            "t": int(self.t),
            "scenario": self.scenario.name,
            "seed": int(self._seed or 0),
            "cost": float(violated),
            "served_eflops": float(served),
            "cost_cny": float(cost_cny),
            "reward": float(reward),
            "metrics": {key: float(metrics[key]) for key in _METRIC_KEYS},
        }

    def _region_price_today(self, region: str) -> np.ndarray:
        hour = min(self.t, self.episode_hours - 1)
        for node in self.nodes:
            if node.region == region:
                start = (hour // 24) * 24
                return self.price_cny_per_kwh[start : start + 24, self.node_index[node.id]].copy()
        raise KeyError(region)


_METRIC_KEYS = (
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
)


def _inference_column(env: JSComputeSimEnv) -> np.ndarray:
    column = np.zeros((env.n_tasks, env.n_nodes), dtype=np.float64)
    column[env.inference_index] = 1.0
    return column


def _bands_for_season(energy_cfg: dict, season: str) -> list[str]:
    hours = energy_cfg["tariff"]["season_hours"]
    bands = [""] * 24
    for band, clock in hours.items():
        for hour in clock:
            bands[int(hour)] = band
    for hour in energy_cfg["tariff"]["spike_hours"][season]:
        bands[int(hour)] = "spike"
    return bands


def summarize_episode(totals: dict[str, float]) -> dict[str, float]:
    """Turn summed hourly metrics into the ratios reported by the baselines."""
    arrived = totals["arrived_eflops"]
    energy = totals["energy_kwh"]
    available = totals["available_nameplate_eflops"]
    green_available = totals["green_available_kwh"]
    return {
        "served_ratio": totals["served_eflops"] / arrived if arrived else 0.0,
        "sla_violation_ratio": totals["violated_eflops"] / arrived if arrived else 0.0,
        "mean_utilization": totals["occupied_nameplate_eflops"] / available if available else 0.0,
        "energy_mwh": energy / 1000.0,
        "weighted_pue": totals["pue_energy_kwh"] / energy if energy else 0.0,
        "carbon_t": totals["carbon_kg"] / 1000.0,
        "cost_10k_cny": totals["cost_cny"] / 10000.0,
        "green_energy_share": totals["green_kwh"] / energy if energy else 0.0,
        "green_absorption": totals["green_kwh"] / green_available if green_available else 0.0,
        "cross_domain_eflops": totals["cross_domain_eflops"],
        "reward": totals.get("reward", 0.0),
    }
