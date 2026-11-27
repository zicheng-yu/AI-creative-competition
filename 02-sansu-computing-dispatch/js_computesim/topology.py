"""Nodes, GDP-proportional capacity, and the three-tier latency matrix."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from js_computesim.config import load_configs


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    kind: str
    region: str
    province: str
    gdp_100m_cny: float | None
    eflops: float
    dc_count: int
    pue_base: float
    carbon_kg_per_kwh: float
    price_is_proxy: bool


def largest_remainder(weights: np.ndarray, total: int) -> np.ndarray:
    """Integer allocation that sums to ``total`` and follows ``weights``."""
    if total < 0:
        raise ValueError("total must be non-negative")
    weights = np.asarray(weights, dtype=np.float64)
    if weights.ndim != 1 or weights.shape[0] == 0:
        raise ValueError("weights must be a non-empty vector")
    if np.any(weights < 0) or float(weights.sum()) <= 0:
        raise ValueError("weights must be non-negative and not all zero")
    raw = weights / weights.sum() * total
    floors = np.floor(raw).astype(np.int64)
    shortfall = int(total - int(floors.sum()))
    fractional = raw - floors
    order = np.argsort(-fractional, kind="mergesort")
    floors[order[:shortfall]] += 1
    return floors


def _latency_matrix(nodes: list[Node], latency_ms: dict[str, float]) -> np.ndarray:
    count = len(nodes)
    matrix = np.empty((count, count), dtype=np.float64)
    metro = float(latency_ms["metro"])
    intra = float(latency_ms["intra_province"])
    yangtze = float(latency_ms["yangtze"])
    for src in range(count):
        for dst in range(count):
            if src == dst:
                matrix[src, dst] = metro
            elif nodes[src].kind == "city" and nodes[dst].kind == "city":
                matrix[src, dst] = intra
            else:
                matrix[src, dst] = yangtze
    return matrix


def build_topology(configs: dict | None = None) -> dict:
    configs = configs if configs is not None else load_configs()
    topo = configs["topology"]
    energy = configs["energy"]
    meta = topo["meta"]
    total_eflops = float(meta["jiangsu_total_eflops"])
    total_dcs = int(meta["jiangsu_dc_count"])
    carbon = energy["carbon"]["provincial_kg_per_kwh"]
    pue_lo, pue_hi = 1.16, 1.48

    rows = topo["nodes"]
    cities = [row for row in rows if row["kind"] == "city"]
    if len(cities) != 13:
        raise ValueError(f"expected 13 Jiangsu city nodes, found {len(cities)}")
    gdp = np.array([float(row["gdp_100m_cny"]) for row in cities], dtype=np.float64)
    documented_sum = float(meta["gdp_city_sum_100m_cny"])
    if abs(float(gdp.sum()) - documented_sum) > 0.02:
        raise ValueError(
            f"city GDP sum {gdp.sum():.2f} does not match documented {documented_sum:.2f}"
        )
    shares = gdp / gdp.sum()
    dc_counts = largest_remainder(shares, total_dcs)
    eflops = shares * total_eflops
    eflops[-1] = total_eflops - float(eflops[:-1].sum())
    if abs(float(eflops.sum()) - total_eflops) > 1e-6:
        raise ValueError("Jiangsu EFlops do not sum to the official total")

    city_eflops = {row["id"]: float(eflops[index]) for index, row in enumerate(cities)}
    city_dcs = {row["id"]: int(dc_counts[index]) for index, row in enumerate(cities)}

    nodes: list[Node] = []
    for row in rows:
        pue = float(row["pue_base"])
        if not pue_lo <= pue <= pue_hi:
            raise ValueError(f"{row['id']} pue_base {pue} is outside {pue_lo}–{pue_hi}")
        province = row["province"]
        if province not in carbon:
            raise ValueError(f"no provincial carbon factor for {province}")
        if row["kind"] == "city":
            node_eflops = city_eflops[row["id"]]
            dc_count = city_dcs[row["id"]]
            proxy = False
        elif row["kind"] == "hub":
            node_eflops = float(row["assumed_eflops"])
            dc_count = 0
            proxy = True
        else:
            raise ValueError(f"unknown node kind {row['kind']}")
        nodes.append(
            Node(
                id=row["id"],
                name=row["name"],
                kind=row["kind"],
                region=row["region"],
                province=province,
                gdp_100m_cny=None if row["gdp_100m_cny"] is None else float(row["gdp_100m_cny"]),
                eflops=node_eflops,
                dc_count=dc_count,
                pue_base=pue,
                carbon_kg_per_kwh=float(carbon[province]),
                price_is_proxy=proxy,
            )
        )

    pools_cfg = configs["pools"]
    pool_ids = list(pools_cfg["pools"])
    task_ids = list(pools_cfg["tasks"])
    share = np.array([float(pools_cfg["pool_share"][pool]) for pool in pool_ids], dtype=np.float64)
    if abs(float(share.sum()) - 1.0) > 1e-9:
        raise ValueError(f"pool_share must sum to 1, got {share.sum()}")
    nameplate = np.array([node.eflops for node in nodes], dtype=np.float64)[:, None] * share[None, :]

    def matrix(section: str) -> np.ndarray:
        out = np.zeros((len(task_ids), len(pool_ids)), dtype=np.float64)
        table = pools_cfg[section]
        for task_index, task in enumerate(task_ids):
            for pool_index, pool in enumerate(pool_ids):
                if pool not in table[task]:
                    raise ValueError(f"{section} missing {task}.{pool}")
                out[task_index, pool_index] = float(table[task][pool])
        if np.any(out <= 0):
            raise ValueError(f"{section} must be positive")
        return out

    return {
        "nodes": nodes,
        "node_ids": [node.id for node in nodes],
        "pool_ids": pool_ids,
        "task_ids": task_ids,
        "latency_ms": _latency_matrix(nodes, meta["latency_ms"]),
        "latency_spec_ms": {key: float(value) for key, value in meta["latency_ms"].items()},
        "nameplate_eflops": nameplate,
        "pool_share": share,
        "eta": matrix("eta"),
        "operator_gain": matrix("operator_gain"),
        "jiangsu_total_eflops": total_eflops,
        "jiangsu_dc_count": total_dcs,
        "gdp_city_sum_100m_cny": float(gdp.sum()),
        "east_china_kg_per_kwh": float(energy["carbon"]["east_china_kg_per_kwh"]),
        "carbon_default_mode": energy["carbon"]["default_mode"],
    }
