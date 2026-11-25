"""Forecast evaluation: competition RMSPE plus absolute and relative errors.

The official Rossmann metric is RMSPE:

.. math:: \\sqrt{\\frac{1}{n}\\sum_i \\left(\\frac{y_i - \\hat y_i}{y_i}\\right)^2}

It is only defined for positive actual sales, so closed days and the 54
anomalous open-but-zero rows are excluded from the metric (they are still
scored as zero in the submission by the closed-day rule).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

TARGET = "Sales"
PREDICTION = "Prediction"


def _positive_mask(y_true: np.ndarray) -> np.ndarray:
    return np.isfinite(y_true) & (y_true > 0)


def rmspe(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    """Root Mean Squared Percentage Error on positive actuals."""
    y_true_arr = np.asarray(y_true, dtype="float64")
    y_pred_arr = np.asarray(y_pred, dtype="float64")
    mask = _positive_mask(y_true_arr) & np.isfinite(y_pred_arr)
    if mask.sum() == 0:
        return float("nan")
    error = (y_true_arr[mask] - y_pred_arr[mask]) / y_true_arr[mask]
    return float(np.sqrt(np.mean(np.square(error))))


def mae(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    y_true_arr = np.asarray(y_true, dtype="float64")
    y_pred_arr = np.asarray(y_pred, dtype="float64")
    mask = _positive_mask(y_true_arr) & np.isfinite(y_pred_arr)
    return float(np.mean(np.abs(y_true_arr[mask] - y_pred_arr[mask]))) if mask.any() else float("nan")


def rmse(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    y_true_arr = np.asarray(y_true, dtype="float64")
    y_pred_arr = np.asarray(y_pred, dtype="float64")
    mask = _positive_mask(y_true_arr) & np.isfinite(y_pred_arr)
    if not mask.any():
        return float("nan")
    return float(np.sqrt(np.mean(np.square(y_true_arr[mask] - y_pred_arr[mask]))))


def wape(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    """Weighted absolute percentage error: sum|e| / sum(y)."""
    y_true_arr = np.asarray(y_true, dtype="float64")
    y_pred_arr = np.asarray(y_pred, dtype="float64")
    mask = _positive_mask(y_true_arr) & np.isfinite(y_pred_arr)
    denominator = np.sum(y_true_arr[mask])
    if denominator <= 0:
        return float("nan")
    return float(np.sum(np.abs(y_true_arr[mask] - y_pred_arr[mask])) / denominator)


def evaluate_predictions(
    frame: pd.DataFrame,
    target_col: str = TARGET,
    prediction_col: str = PREDICTION,
    open_col: str = "Open",
    label: str | None = None,
) -> dict[str, Any]:
    """Compute the full metric set on a prediction frame.

    Rows must contain actual sales.  Only open days with positive sales enter
    the percentage metrics; this matches the competition definition and is
    reported explicitly.
    """
    data = frame
    if open_col in data.columns:
        data = data[data[open_col] == 1]
    mask = (data[target_col] > 0) & data[prediction_col].notna()
    scored = data.loc[mask]
    result: dict[str, Any] = {
        "model": label or str(frame.attrs.get("model", "unknown")),
        "n_rows_total": int(len(frame)),
        "n_rows_scored": int(len(scored)),
        "rmspe": rmspe(scored[target_col], scored[prediction_col]),
        "mae": mae(scored[target_col], scored[prediction_col]),
        "rmse": rmse(scored[target_col], scored[prediction_col]),
        "wape": wape(scored[target_col], scored[prediction_col]),
        "bias_mean": float(np.mean(scored[prediction_col] - scored[target_col])),
        "bias_pct_of_mean": float(
            np.mean(scored[prediction_col] - scored[target_col]) / np.mean(scored[target_col])
        ),
    }
    return result


def error_breakdown(
    frame: pd.DataFrame,
    by: str | list[str],
    target_col: str = TARGET,
    prediction_col: str = PREDICTION,
    min_rows: int = 30,
) -> pd.DataFrame:
    """RMSPE/MAE/WAPE by segment (store, weekday, promo, sales decile, ...)."""
    data = frame[frame[target_col] > 0].copy()
    if isinstance(by, str):
        by = [by]
    rows = []
    for key, group in data.groupby(by, observed=True, dropna=False):
        if len(group) < min_rows:
            continue
        key_values = key if isinstance(key, tuple) else (key,)
        record = dict(zip(by, key_values, strict=True))
        record.update(
            {
                "n": int(len(group)),
                "rmspe": rmspe(group[target_col], group[prediction_col]),
                "mae": mae(group[target_col], group[prediction_col]),
                "wape": wape(group[target_col], group[prediction_col]),
                "mean_actual": float(group[target_col].mean()),
                "mean_prediction": float(group[prediction_col].mean()),
            }
        )
        rows.append(record)
    return pd.DataFrame(rows).sort_values("rmspe", ascending=False).reset_index(drop=True)


def compare_models(results: Iterable[dict[str, Any]]) -> pd.DataFrame:
    """Turn a list of metric dictionaries into a sorted comparison table."""
    frame = pd.DataFrame(list(results))
    order = ["model", "rmspe", "mae", "rmse", "wape", "n_rows_scored"]
    columns = [c for c in order if c in frame.columns]
    return frame[columns].sort_values("rmspe").reset_index(drop=True)


def save_metrics(payload: dict[str, Any], path: str | Path) -> None:
    """Write metrics as JSON with native Python types."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def convert(value: Any) -> Any:
        if isinstance(value, (np.floating, np.integer)):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        return value

    path.write_text(json.dumps(payload, indent=2, default=convert), encoding="utf-8")
