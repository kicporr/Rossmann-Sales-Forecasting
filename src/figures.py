"""Reproducible portfolio figures that are not part of the EDA script."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.config import ensure_directories, load_config

LOGGER = logging.getLogger(__name__)

MODEL_LABELS = {
    "historical_average": "Historical\naverage",
    "linear_regression": "Linear\nregression",
    "random_forest": "Random\nforest",
    "xgboost": "XGBoost",
    "seasonal_naive": "Seasonal\nnaive",
    "ensemble_xgb_hist": "XGBoost +\nhist. avg.",
}


def model_comparison_chart(cfg: dict | None = None) -> Path:
    """Plot mean rolling-fold RMSPE (with std) against the holdout RMSPE."""
    cfg = cfg or load_config()
    ensure_directories(cfg)
    results = json.loads((Path(cfg["paths"]["metrics"]) / "validation_results.json").read_text(encoding="utf-8"))
    folds = [fold["name"] for fold in cfg["split"]["validation_folds"]]
    models = [model for model in MODEL_LABELS if model in results["folds"][folds[0]]["models"]]

    means = [float(np.mean([results["folds"][fold]["models"][model]["rmspe"] for fold in folds])) for model in models]
    stds = [float(np.std([results["folds"][fold]["models"][model]["rmspe"] for fold in folds])) for model in models]
    holdout = [results["folds"]["holdout"]["models"][model]["rmspe"] for model in models]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#e5e7eb",
        }
    )
    fig, ax = plt.subplots(figsize=(10, 5.4), dpi=150)
    x = np.arange(len(models))
    width = 0.36
    bars_folds = ax.bar(
        x - width / 2,
        means,
        width,
        yerr=stds,
        capsize=4,
        color="#1f3a5f",
        label="Mean of rolling folds 1-3 (selection)",
        error_kw={"ecolor": "#94a3b8", "lw": 1.2},
    )
    bars_holdout = ax.bar(x + width / 2, holdout, width, color="#2a9d8f", label="Holdout (reported once)")
    for bars in (bars_folds, bars_holdout):
        for bar in bars:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.006,
                f"{bar.get_height():.3f}",
                ha="center",
                fontsize=8.5,
            )
    ax.set_xticks(x, [MODEL_LABELS[model] for model in models], fontsize=9)
    ax.set_ylabel("RMSPE (lower is better)")
    ax.set_title(
        "Model comparison: rolling validation folds and untouched holdout",
        fontsize=13,
        fontweight="bold",
        color="#1f3a5f",
    )
    ax.legend(loc="upper right", frameon=False, fontsize=9)
    ax.set_ylim(0, (max(means) + max(stds)) * 1.12)
    fig.text(
        0.01,
        0.01,
        "Source: outputs/metrics/validation_results.json · RMSPE on open days with positive sales",
        fontsize=7.5,
        color="#64748b",
    )
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    path = Path(cfg["paths"]["figures"]) / "fig20_model_comparison.png"
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    LOGGER.info("Saved %s", path)
    return path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    print(model_comparison_chart())


if __name__ == "__main__":
    main()
