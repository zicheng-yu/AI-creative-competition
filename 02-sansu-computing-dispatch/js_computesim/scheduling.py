"""Map a preference or an explicit plan onto feasible node/pool capacity."""

from __future__ import annotations

import numpy as np

from js_computesim.workload import Cohort


def serve(
    cohorts: list[Cohort],
    action: np.ndarray,
    *,
    latency_ms: np.ndarray,
    sla_latency_ms: np.ndarray,
    health: np.ndarray,
    remaining_nameplate: np.ndarray,
    eta: np.ndarray,
    gain: np.ndarray,
) -> tuple[list[Cohort], np.ndarray, np.ndarray]:
    """Serve queued cohorts in priority order.

    Preference actions have shape ``(task, dest, pool)``. The same weights are
    masked per origin by the latency SLA, then renormalized. Explicit actions
    have shape ``(task, origin, dest, pool)`` and are masked the same way, but
    each origin keeps its own weights. Unserved work stays on the cohort.
    Capacity that a share cannot use is not given to another destination.
    """
    action = np.nan_to_num(np.asarray(action, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    action = np.maximum(action, 0.0)
    task_count, pool_count = eta.shape
    node_count = remaining_nameplate.shape[0]
    explicit = action.ndim == 4
    if explicit:
        expected = (task_count, node_count, node_count, pool_count)
        if action.shape != expected:
            raise ValueError(f"explicit action shape {action.shape} != {expected}")
    elif action.shape != (task_count, node_count, pool_count):
        raise ValueError(
            f"action shape {action.shape} is neither preference {(task_count, node_count, pool_count)} "
            f"nor explicit {(task_count, node_count, node_count, pool_count)}"
        )

    remaining = np.array(remaining_nameplate, dtype=np.float64, copy=True)
    served = np.zeros((task_count, node_count, node_count, pool_count), dtype=np.float64)
    order = sorted(range(len(cohorts)), key=lambda index: (
        -cohorts[index].priority,
        -cohorts[index].age,
        cohorts[index].task,
        cohorts[index].origin,
    ))
    effective = eta * gain
    for index in order:
        cohort = cohorts[index]
        original = cohort.eflops
        if original <= 1e-12:
            continue
        task = cohort.task
        origin = cohort.origin
        feasible = (latency_ms[origin] <= sla_latency_ms[task]) & (health > 0)
        if explicit:
            score = action[task, origin] * feasible[:, None]
        else:
            score = action[task] * feasible[:, None]
        score = score * (effective[task] > 0)[None, :]
        total_score = float(score.sum())
        if total_score <= 0.0:
            continue
        # Each destination is an independent cap, so a vectorized clip matches
        # walking shares from largest to smallest.
        cap_ref = remaining * effective[task][None, :]
        take = np.minimum(original * (score / total_score), cap_ref)
        taken = float(take.sum())
        if taken > original and taken > 0.0:
            take *= original / taken
            taken = original
        consumed = np.divide(
            take,
            effective[task][None, :],
            out=np.zeros_like(take),
            where=effective[task][None, :] > 0,
        )
        remaining = np.maximum(0.0, remaining - consumed)
        served[task, origin] += take
        cohort.eflops = max(0.0, original - taken)
    occupied = remaining_nameplate - remaining
    alive = [cohort for cohort in cohorts if cohort.eflops > 1e-12]
    return alive, served, occupied
