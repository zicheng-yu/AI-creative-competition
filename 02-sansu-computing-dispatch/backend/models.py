from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .world import ORIGIN

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "weights"
FEATURES = ("eta", "tariff", "green_fraction", "pue_excess", "pool_fill",
            "node_fill", "latency_ratio", "cross", "domestic", "quota", "sla_risk",
            "wait_hours", "energy_per_work", "available", "urgent")
SCALE = np.stack([np.maximum(1., 80*ORIGIN), np.ones(16)], axis=-1).astype('float32')


class Forecaster(nn.Module):
    """Shared seasonal residual temporal convolution; periods aligned at lag 24/48."""
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Conv1d(4, 24, 5, padding=2), nn.GELU(),
                                 nn.Conv1d(24, 16, 3, padding=2, dilation=2), nn.GELU(),
                                 nn.Conv1d(16, 2, 1))

    def forward(self, x):
        return torch.clamp_min(.5*(x[:, :2]+x[:, 2:]) + self.net(x), 0.)


def pack_history(history):
    x = (history / SCALE).transpose(1, 2, 0)
    return np.concatenate((x[..., :24], x[..., 24:]), axis=1)


@torch.inference_mode()
def forecast(model, history):
    y = model(torch.from_numpy(pack_history(history))).numpy()
    return y.transpose(2,0,1)*SCALE


class ActorCritic(nn.Module):
    """Permutation-equivariant candidate scorer and state-value baseline."""
    def __init__(self):
        super().__init__()
        self.actor = nn.Sequential(nn.Linear(len(FEATURES), 32), nn.Tanh(),
                                   nn.Linear(32, 16), nn.Tanh(), nn.Linear(16, 1))
        self.value = nn.Sequential(nn.Linear(len(FEATURES), 24), nn.Tanh(), nn.Linear(24, 1))

    def forward(self, candidates):
        return self.actor(candidates).squeeze(-1)

    def critic(self, candidates):
        return self.value(candidates.mean(dim=-2)).squeeze(-1)


@lru_cache(maxsize=2)
def load_model(name):
    model = {"forecast": Forecaster, "policy": ActorCritic}[name]()
    model.load_state_dict(torch.load(WEIGHTS / (name+".pt"), map_location="cpu", weights_only=True))
    return model.eval()
