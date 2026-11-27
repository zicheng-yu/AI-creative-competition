"""Static topology and exogenous inputs. One slot is five simulated minutes."""
from dataclasses import dataclass
from functools import cached_property

import numpy as np

CITIES = ("南京", "苏州", "无锡", "常州", "镇江", "南通", "扬州", "泰州", "盐城",
          "淮安", "徐州", "连云港", "宿迁", "上海", "浙江", "安徽芜湖")
CENTRES = np.array([39, 47, 32, 25, 16, 28, 19, 17, 24, 15, 21, 16, 14, 0, 0, 0])
EF = np.r_[CENTRES[:13] * (271.8 / 313), [26., 20., 18.]]
BASE_PUE = np.array([1.44,1.48,1.42,1.38,1.36,1.23,1.35,1.31,
                     1.16,1.25,1.28,1.20,1.22,1.43,1.32,1.18])
POOLS = ("CPU", "Ascend", "MLU", "DCU", "NVIDIA", "Supercomputer")
KINDS = ("Pretrain", "Finetune", "Inference", "HPC", "General")
ETA = np.array([[.09,.96,.62,.68,.99,.51], [.23,.97,.92,.83,.94,.47],
                [.32,.98,.95,.85,.92,.39], [.53,.45,.38,.90,.84,.99],
                [.98,.39,.31,.54,.46,.73]])
SHARE = np.tile([.18,.24,.14,.13,.22,.09], (16, 1))
SHARE[0, 1:3] += [-.07,.07]
SHARE[13, 1:5] += [-.05,-.02,-.02,.09]
CAP = EF[:, None] * SHARE
LAT = np.full((16, 16), 10)
LAT[:13, :13] = 5
np.fill_diagonal(LAT, 1)
CROSS = LAT == 10
DOM = np.array([False, True, True, True, False, False])
SLOTS = 12
# After a bank becomes idle, keep it powered for another 15 minutes.
KEEPALIVE = 3
PEAK_HOURS = (9, 10, 11, 17, 18, 19)
GRID = .55  # kgCO2/kWh, East China 2023
KW_PER_EF = 10_000.
BW = 120.  # shared cross-domain link GB per 5-min slot
GB_PER_EF = 4.  # transfer GB/slot per scheduled effective EF/s
SCENARIOS = ("normal_weekday", "high_renewable", "peak_shaving", "fault_stress")
STRATEGIES = ("RR-Local", "Least-Loaded", "Cost-First", "SuCompute", "MILP-only", "Safe-RL-only")
ORIGIN = np.array([18,21,12,8,4,7,4,4,4,3,4,3,2,3,2,1], dtype=float)
ORIGIN /= ORIGIN.sum()


def weather(hours, scenario):
    """Time-of-use tariff (CNY/kWh), available renewable power (kW), temperature."""
    h = np.asarray(hours)[:, None] % 24
    phase = np.arange(16)[None, :] * .17
    coast = np.isin(np.arange(16), [5,8,11,15])
    sun = np.maximum(0, np.sin(np.pi * (h-6)/13))
    wind = .48 + .27*np.cos((h+phase)*np.pi/12) + .1*np.sin(phase+h*.77)
    green = (.025 + (.09 + .32*coast)*wind + (.09 + .17*coast)*sun)
    green *= 1.55 if scenario == "high_renewable" else 1
    peak = (h >= 16) & (h < 22)
    price = (.37 + .31*((h >= 7) & (h < 23)) + .32*peak +
             .09*np.isin(np.arange(16), [0,1,2,3,4,13,14]))
    if scenario == "peak_shaving":
        price = price + .55*peak
    return price, green*EF*KW_PER_EF, 24 + 5*np.sin((h-9)*np.pi/12) + phase


@dataclass(frozen=True)
class Job:
    id: int
    slot: int
    src: int
    kind: int
    rate: float  # effective EF/s for duration slots
    duration: int
    deadline: int  # exclusive end
    latency: int
    priority: bool


class Trace:
    def __init__(self, seed, scenario, hours):
        if scenario not in SCENARIOS or not 1 <= hours <= 168:
            raise ValueError("invalid scenario or horizon")
        self.seed, self.scenario, self.hours = seed, scenario, hours
        rng = np.random.default_rng(seed)
        self.jobs = []
        self.history = 48
        self.series = []
        for h in range(-self.history, hours):
            day = 8 <= h % 24 < 21
            burst = rng.random() < .08
            peak = h % 24 in PEAK_HOURS
            mean = 45 + 90*day + 85*peak + 26*burst + 20*(scenario == "peak_shaving" and day)
            origin = ORIGIN.copy()
            if peak:
                origin[:3] *= 1.7
                origin /= origin.sum()
            counts = rng.poisson(mean*origin)
            green = weather([h], scenario)[1][0] * rng.uniform(.82, 1.18, 16)
            self.series.append(np.stack([counts, green/(EF*KW_PER_EF)], axis=-1))
            if h < 0:
                continue
            for src, count in enumerate(counts):
                for _ in range(count):
                    kind = int(rng.choice(5, p=([.08,.15,.52,.10,.15] if day else
                                                 [.33,.28,.15,.12,.12])))
                    slot = h*SLOTS + int(rng.integers(SLOTS))
                    dur = min(hours*SLOTS-slot, max(1, round(rng.lognormal(
                        np.log([23,12,4,10,5][kind]), .48))))
                    urgent = bool(burst or rng.random() < .035)
                    slack = 0 if kind >= 2 or urgent else SLOTS*int(rng.integers(2,7))
                    rate = np.clip(rng.lognormal(.02, .48), .25, 3.8)
                    latency = int(rng.choice([1,5,10], p=[.55,.35,.10])) if kind == 2 else 10
                    self.jobs.append(Job(len(self.jobs), slot, src, kind, float(rate), dur,
                                         min(hours*SLOTS, slot+dur+slack), latency, urgent))
        self.jobs.sort(key=lambda j: (j.slot, not j.priority, j.id))
        self.series = np.asarray(self.series, dtype=np.float32)

    @cached_property
    def by_id(self):
        return {j.id:j for j in self.jobs}

    @cached_property
    def tariffs(self):
        return weather(np.arange(self.hours), self.scenario)

    def history_at(self, h):
        end = self.history+h
        return self.series[end-48:end]
