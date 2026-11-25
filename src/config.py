"""Central configuration loader for the Rossmann forecasting project.

All paths in ``config/config.yaml`` are relative to the project root.  This
module resolves them to absolute paths so that every script can be executed
from any working directory (important for Windows launchers and notebooks).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

_PATH_KEYS = (
    "raw",
    "processed",
    "dashboard_data",
    "outputs",
    "figures",
    "metrics",
    "predictions",
    "models",
)


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load the YAML configuration and resolve project paths.

    Parameters
    ----------
    path:
        Optional alternative configuration file.  Defaults to
        ``config/config.yaml`` inside the project root.

    Returns
    -------
    dict
        Configuration dictionary.  ``cfg["paths"]`` contains absolute
        :class:`Path` objects, and ``cfg["project_root"]`` points at the
        repository root.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as handle:
        cfg: dict[str, Any] = yaml.safe_load(handle)

    paths = cfg.setdefault("paths", {})
    for key in _PATH_KEYS:
        if key in paths:
            raw_value = Path(paths[key])
            paths[key] = raw_value if raw_value.is_absolute() else PROJECT_ROOT / raw_value
    cfg["project_root"] = PROJECT_ROOT
    cfg["config_path"] = config_path
    return cfg


def ensure_directories(cfg: dict[str, Any]) -> None:
    """Create every directory referenced in the configuration."""
    for value in cfg["paths"].values():
        Path(value).mkdir(parents=True, exist_ok=True)
    for extra in ("reports", "docs", "sql", "dashboard"):
        (PROJECT_ROOT / extra).mkdir(parents=True, exist_ok=True)
