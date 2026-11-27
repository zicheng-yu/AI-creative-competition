"""Tariff bands, renewable shapes, and the nonlinear facility power model."""

from __future__ import annotations

import numpy as np

from js_computesim.topology import Node


def _hour_bands(energy_cfg: dict, season: str) -> list[str]:
    if season not in ("summer", "winter"):
        raise ValueError(
            f"season {season!r} has no bundled agent-purchase price table; "
            "use 'summer' (2025-08) or 'winter' (2025-12)"
        )
    hours = energy_cfg["tariff"]["season_hours"]
    bands = [""] * 24
    for band, clock in hours.items():
        for hour in clock:
            if bands[int(hour)]:
                raise ValueError(f"hour {hour} is in more than one TOU band")
            bands[int(hour)] = band
    if any(band == "" for band in bands):
        raise ValueError("TOU bands do not cover 24 hours")
    for hour in energy_cfg["tariff"]["spike_hours"][season]:
        bands[int(hour)] = "spike"
    return bands


def price_vector(energy_cfg: dict, season: str) -> np.ndarray:
    """All-in CNY/kWh for hours 0–23. Same vector for 苏南 and 苏北."""
    bands = _hour_bands(energy_cfg, season)
    table = energy_cfg["tariff"]["tables"][season]
    return np.array([float(table[band]) for band in bands], dtype=np.float64)


def wind_capacity_factor(energy_cfg: dict) -> np.ndarray:
    spec = energy_cfg["renewables"]["wind_cf"]
    hours = np.arange(24, dtype=np.float64)
    angle = 2.0 * np.pi * (hours - float(spec["phase_hour"])) / 24.0
    curve = float(spec["mean"]) + float(spec["amplitude"]) * np.cos(angle)
    return np.clip(curve, 0.0, 1.0)


def solar_capacity_factor(energy_cfg: dict) -> np.ndarray:
    spec = energy_cfg["renewables"]["solar_cf"]
    sunrise = float(spec["sunrise_hour"])
    sunset = float(spec["sunset_hour"])
    peak = float(spec["peak"])
    curve = np.zeros(24, dtype=np.float64)
    for hour in range(24):
        if sunrise <= hour < sunset:
            phase = (hour - sunrise) / (sunset - sunrise)
            curve[hour] = peak * np.sin(np.pi * phase)
    return curve


def repeat_week(hourly: np.ndarray, episode_hours: int) -> np.ndarray:
    if episode_hours % 24 != 0:
        raise ValueError("episode length must be a whole number of days")
    return np.tile(hourly, episode_hours // 24)


def green_available_mw(
    energy_cfg: dict,
    nodes: list[Node],
    episode_hours: int,
    cf_scale: float,
    contract_scale: float,
) -> np.ndarray:
    """Assumed DC green contract, MW, shape (T, N). Non-coastal nodes stay 0."""
    renewables = energy_cfg["renewables"]
    fraction = float(renewables["assumption_contract_fraction"]) * float(contract_scale)
    wind = np.clip(wind_capacity_factor(energy_cfg) * float(cf_scale), 0.0, 1.0)
    solar = np.clip(solar_capacity_factor(energy_cfg) * float(cf_scale), 0.0, 1.0)
    wind_week = repeat_week(wind, episode_hours)
    solar_week = repeat_week(solar, episode_hours)
    out = np.zeros((episode_hours, len(nodes)), dtype=np.float64)
    cities = renewables["cities"]
    for index, node in enumerate(nodes):
        city = cities.get(node.id)
        if city is None:
            continue
        # 1 万千瓦 = 10 MW.
        wind_mw = float(city["wind_wan_kw"]) * 10.0
        pv_mw = float(city["pv_wan_kw"]) * 10.0
        out[:, index] = fraction * (wind_mw * wind_week + pv_mw * solar_week)
    return out


def facility_power_mw(
    occupied_nameplate: np.ndarray,
    available_nameplate: np.ndarray,
    health: np.ndarray,
    pue_base: np.ndarray,
    pue_multiplier: np.ndarray,
    idle_fraction: np.ndarray,
    it_kw_per_eflops: float,
    alpha: float,
    pue_util_coeff: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return facility MW, node utilization, and effective PUE, one hour.

    ``occupied_nameplate`` and ``available_nameplate`` are (N, M) EFlops.
    Offline nodes (health == 0) draw no power.
    """
    available = np.maximum(available_nameplate, 0.0)
    occupied = np.clip(occupied_nameplate, 0.0, available)
    with np.errstate(divide="ignore", invalid="ignore"):
        util_pool = np.divide(occupied, available, out=np.zeros_like(occupied), where=available > 0)
    nameplate_node = available.sum(axis=1)
    occupied_node = occupied.sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        util_node = np.divide(
            occupied_node, nameplate_node, out=np.zeros_like(occupied_node), where=nameplate_node > 0
        )
    peak_mw = available * (float(it_kw_per_eflops) / 1000.0)
    idle = idle_fraction.reshape(1, -1)
    dynamic = idle + (1.0 - idle) * np.power(util_pool, float(alpha))
    it_mw = (peak_mw * dynamic).sum(axis=1)
    pue = pue_base * (1.0 + float(pue_util_coeff) * util_node) * pue_multiplier
    facility = pue * it_mw
    facility = np.where(health > 0, facility, 0.0)
    pue = np.where(health > 0, pue, 0.0)
    return facility, util_node, pue
