"""Load the YAML parameter files shipped with the simulator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "configs"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def load_configs(config_dir: Path | None = None) -> dict[str, Any]:
    directory = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR
    names = ("topology", "pools", "energy", "workload", "scenarios")
    return {name: load_yaml(directory / f"{name}.yaml") for name in names}
