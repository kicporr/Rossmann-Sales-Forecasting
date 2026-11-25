"""Model training, rolling-origin validation and final model selection.

Validation protocol
-------------------
* The Kaggle ``test.csv`` has no public labels, so all evaluation uses a
  chronological holdout carved out of ``train.csv``.
* Three rolling-origin folds (48-day horizon each) plus one final holdout
  (2015-06-15 .. 2015-07-31) mirror the real 48-day forecasting task.
* Models are trained only on data up to each fold's ``train_end``; features for
  the forecast window are rebuilt recursively from the forecast origin, so
  actual future sales never enter the model.
* Random shuffling is never used.

Run ``python -m src.train`` to reproduce validation, then
``python -m src.predict`` to create ``outputs/predictions/submission.csv``.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from src.config import ensure_directories, load_config
from src.data_preparation import load_processed
from src.evaluation import compare_models, evaluate_predictions, save_metrics
from src.features import FEATURE_COLUMNS, DirectForecaster, build_training_matrix

LOGGER = logging.getLogger(__name__)
BASELINE_MODELS = ("historical_average", "seasonal_naive")
ML_MODELS = ("linear_regression", "random_forest", "xgboost")
ALL_MODELS = BASELINE_MODELS + ML_MODELS
# A lightweight, fold-optimised ensemble: 65% XGBoost + 35% store-weekday
# historical average.  The weight was chosen on the rolling folds only; the
# holdout remained untouched.  The ensemble is much better calibrated than
# XGBoost alone (bias -7.9% vs -10.8%) and materially lowers RMSPE.
ENSEMBLE_NAME = "ensemble_xgb_hist"
SELECTABLE_MODELS = ALL_MODELS + (ENSEMBLE_NAME,)


def make_model(name: str, cfg: dict[str, Any]) -> Any:
    """Instantiate a model from configuration (deterministic random states)."""
    params = cfg["models"]
    seed = int(cfg["project"]["random_state"])
    if name == "linear_regression":
        return Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("regressor", LinearRegression(**params["linear_regression"])),
            ]
        )
    if name == "random_forest":
        return RandomForestRegressor(**params["random_forest"], random_state=seed)
    if name == "xgboost":
        return XGBRegressor(**params["xgboost"], random_state=seed)
    raise ValueError(f"Unknown model: {name}")


def fit_model(name: str, X: pd.DataFrame, y: pd.Series, cfg: dict[str, Any]) -> Any:
    model = make_model(name, cfg)
    started = time.time()
    model.fit(X, y)
    LOGGER.info("Fitted %s on %d rows in %.1fs", name, len(X), time.time() - started)
    return model


def _fallback_series(future: pd.DataFrame, store_stats: pd.DataFrame, global_mean: float) -> pd.Series:
    values = future["Store"].map(store_stats.set_index("Store")["store_mean"]).astype("float64")
    return values.fillna(global_mean)


def historical_average_forecast(history: pd.DataFrame, future: pd.DataFrame) -> pd.Series:
    """Mean sales by store x weekday over the training history."""
    positive = history[(history["Open"] == 1) & (history["Sales"] > 0)]
    store_dow = positive.groupby(["Store", "DayOfWeek"], observed=True)["Sales"].mean().rename("dow_mean")
    store_stats = positive.groupby("Store", observed=True)["Sales"].mean().reset_index(name="store_mean")
    global_mean = float(positive["Sales"].mean())

    frame = future.merge(store_dow.reset_index(), on=["Store", "DayOfWeek"], how="left", validate="many_to_one")
    prediction = frame["dow_mean"].astype("float64")
    fallback = _fallback_series(future, store_stats, global_mean)
    prediction = prediction.fillna(fallback.reset_index(drop=True))
    prediction = np.where(future["Open"].to_numpy() == 1, prediction, 0.0)
    return pd.Series(prediction, index=future.index, name="Prediction")


def seasonal_naive_forecast(history: pd.DataFrame, future: pd.DataFrame) -> pd.Series:
    """Repeat the last observed week (same weekday) for every future date.

    If a store has no observation in the last week, fall back to its 4-week
    weekday average, then to its overall mean.
    """
    origin = history["Date"].max()
    last_week = history[(history["Date"] > origin - pd.Timedelta(days=7)) & (history["Open"] == 1)]
    last_week_stats = last_week.groupby(["Store", "DayOfWeek"], observed=True)["Sales"].mean().rename("last_week")
    four_week = history[
        (history["Date"] > origin - pd.Timedelta(days=28)) & (history["Open"] == 1) & (history["Sales"] > 0)
    ]
    four_week_stats = four_week.groupby(["Store", "DayOfWeek"], observed=True)["Sales"].mean().rename("four_week")
    store_stats = history[(history["Open"] == 1) & (history["Sales"] > 0)].groupby("Store", observed=True)[
        "Sales"
    ].mean().reset_index(name="store_mean")
    global_mean = float(history.loc[history["Open"] == 1, "Sales"].mean())

    frame = future.merge(last_week_stats.reset_index(), on=["Store", "DayOfWeek"], how="left", validate="many_to_one")
    frame = frame.merge(four_week_stats.reset_index(), on=["Store", "DayOfWeek"], how="left", validate="many_to_one")
    prediction = frame["last_week"].fillna(frame["four_week"])
    fallback = _fallback_series(future, store_stats, global_mean)
    prediction = prediction.fillna(fallback.reset_index(drop=True))
    prediction = np.where(future["Open"].to_numpy() == 1, prediction, 0.0)
    return pd.Series(prediction, index=future.index, name="Prediction")


def forecast_fold(
    name: str,
    history: pd.DataFrame,
    future: pd.DataFrame,
    store: pd.DataFrame,
    train_matrix: tuple[pd.DataFrame, pd.Series, pd.DataFrame],
    cfg: dict[str, Any],
) -> pd.Series:
    """Generate predictions for one validation window and one model."""
    if name == "historical_average":
        return historical_average_forecast(history, future)
    if name == "seasonal_naive":
        return seasonal_naive_forecast(history, future)

    X_all, y_all, meta_all = train_matrix
    train_rows = meta_all["Date"] <= history["Date"].max()
    X_train = X_all.loc[train_rows.to_numpy()]
    y_train = y_all.loc[train_rows.to_numpy()]
    model = fit_model(name, X_train, y_train, cfg)
    forecaster = DirectForecaster(
        model=model,
        store=store,
        history=history,
        feature_columns=FEATURE_COLUMNS,
        lags=cfg["features"]["lags"],
        windows=cfg["features"]["rolling_windows"],
        max_horizon=int(cfg["split"]["horizon_days"]),
    )
    output = forecaster.predict(future)
    predictions = output.predictions.set_index(["Store", "Date"])["Prediction"]
    aligned = future.set_index(["Store", "Date"]).index.map(predictions)
    return pd.Series(np.asarray(aligned, dtype="float64"), index=future.index, name="Prediction")


def _fold_windows(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    folds = list(cfg["split"]["validation_folds"])
    folds.append(cfg["split"]["holdout"])
    return folds


def run_validation(cfg: dict[str, Any] | None = None, models: tuple[str, ...] = ALL_MODELS) -> pd.DataFrame:
    """Train every model on every rolling fold and persist predictions/metrics."""
    cfg = cfg or load_config()
    ensure_directories(cfg)
    data = load_processed(cfg)
    train, store = data["train"], data["store"]

    LOGGER.info("Building the full training matrix once (features are causal, so fold subsets are safe)")
    started = time.time()
    matrix = build_training_matrix(train, store, history_offset=int(cfg["split"]["horizon_days"]))
    LOGGER.info("Training matrix ready in %.1fs", time.time() - started)

    all_results: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    fold_reports: dict[str, Any] = {}

    for fold in _fold_windows(cfg):
        train_end = pd.Timestamp(fold["train_end"])
        val_start = pd.Timestamp(fold["val_start"])
        val_end = pd.Timestamp(fold["val_end"])
        history = train[train["Date"] <= train_end]
        future = train[(train["Date"] >= val_start) & (train["Date"] <= val_end)].copy()
        if future.empty:
            raise ValueError(f"Empty validation window for {fold['name']}")
        LOGGER.info(
            "Fold %s: train <= %s (%d rows), validate %s..%s (%d rows)",
            fold["name"],
            train_end.date(),
            len(history),
            val_start.date(),
            val_end.date(),
            len(future),
        )
        fold_predictions: dict[str, pd.Series] = {}
        fold_reports[fold["name"]] = {
            "train_end": str(train_end.date()),
            "val_start": str(val_start.date()),
            "val_end": str(val_end.date()),
            "train_rows": int(len(history)),
            "validation_rows": int(len(future)),
            "models": {},
        }

        for model_name in models:
            started = time.time()
            future["Prediction"] = forecast_fold(model_name, history, future, store, matrix, cfg)
            fold_predictions[model_name] = future["Prediction"].copy()
            metrics = evaluate_predictions(future, label=model_name)
            metrics["fold"] = fold["name"]
            metrics["fit_seconds"] = round(time.time() - started, 1)
            all_results.append(metrics)
            fold_reports[fold["name"]]["models"][model_name] = metrics
            LOGGER.info(
                "  %-20s RMSPE=%.4f  MAE=%.1f  (%.1fs)",
                model_name,
                metrics["rmspe"],
                metrics["mae"],
                metrics["fit_seconds"],
            )
            prediction_frames.append(
                future[["Store", "Date", "Open", "Promo", "StoreType", "Sales", "Prediction"]].assign(
                    model=model_name, fold=fold["name"]
                )
            )

        ensemble_weights = cfg["models"].get("ensemble", {}).get("weights", {})
        if ensemble_weights and all(member in fold_predictions for member in ensemble_weights):
            started = time.time()
            future["Prediction"] = sum(
                float(weight) * fold_predictions[member] for member, weight in ensemble_weights.items()
            )
            metrics = evaluate_predictions(future, label=ENSEMBLE_NAME)
            metrics["fold"] = fold["name"]
            metrics["fit_seconds"] = round(time.time() - started, 1)
            all_results.append(metrics)
            fold_reports[fold["name"]]["models"][ENSEMBLE_NAME] = metrics
            LOGGER.info(
                "  %-20s RMSPE=%.4f  MAE=%.1f  (weighted ensemble)",
                ENSEMBLE_NAME,
                metrics["rmspe"],
                metrics["mae"],
            )
            prediction_frames.append(
                future[["Store", "Date", "Open", "Promo", "StoreType", "Sales", "Prediction"]].assign(
                    model=ENSEMBLE_NAME, fold=fold["name"]
                )
            )

    results = pd.DataFrame(all_results)
    comparison = compare_models(results.to_dict("records"))
    summary = (
        results.groupby("model", observed=True)
        .agg(
            mean_rmspe=("rmspe", "mean"),
            std_rmspe=("rmspe", "std"),
            mean_mae=("mae", "mean"),
            mean_wape=("wape", "mean"),
        )
        .reset_index()
        .sort_values("mean_rmspe")
    )

    metrics_dir = Path(cfg["paths"]["metrics"])
    predictions_dir = Path(cfg["paths"]["predictions"])
    comparison.to_csv(metrics_dir / "model_comparison.csv", index=False)
    summary.to_csv(metrics_dir / "model_comparison_summary.csv", index=False)
    pd.concat(prediction_frames, ignore_index=True).to_parquet(
        predictions_dir / "validation_predictions.parquet", index=False
    )
    save_metrics(
        {
            "protocol": {
                "horizon_days": cfg["split"]["horizon_days"],
                "fold_type": "rolling origin / expanding window",
                "metric": "RMSPE on open days with positive sales",
            },
            "folds": fold_reports,
            "summary": summary.to_dict("records"),
        },
        metrics_dir / "validation_results.json",
    )
    print(summary.to_string(index=False))
    return summary


def select_best_model(cfg: dict[str, Any] | None = None) -> str:
    """Choose the model with the lowest mean RMSPE across rolling folds only.

    The final holdout is deliberately excluded from selection so it remains a
    genuinely untouched test set.
    """
    cfg = cfg or load_config()
    path = Path(cfg["paths"]["metrics"]) / "validation_results.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    fold_names = [fold["name"] for fold in cfg["split"]["validation_folds"]]
    scores: dict[str, list[float]] = {}
    for fold_name in fold_names:
        for model_name, metrics in payload["folds"][fold_name]["models"].items():
            if model_name in SELECTABLE_MODELS:
                scores.setdefault(model_name, []).append(metrics["rmspe"])
    ranking = sorted(((name, float(np.mean(values))) for name, values in scores.items()), key=lambda item: item[1])
    LOGGER.info("Selection ranking (validation folds only): %s", ranking)
    return ranking[0][0]


def train_final_model(
    cfg: dict[str, Any] | None = None,
    model_name: str | None = None,
    data: dict[str, pd.DataFrame] | None = None,
) -> tuple[Any, pd.DataFrame]:
    """Refit the selected model on all training rows and return it with the matrix."""
    cfg = cfg or load_config()
    ensure_directories(cfg)
    data = data or load_processed(cfg)
    train, store = data["train"], data["store"]
    model_name = model_name or select_best_model(cfg)
    X, y, _ = build_training_matrix(train, store, history_offset=int(cfg["split"]["horizon_days"]))
    model = fit_model(model_name, X, y, cfg)
    model_path = Path(cfg["paths"]["models"]) / f"final_{model_name}.joblib"
    joblib.dump({"model": model, "model_name": model_name, "features": FEATURE_COLUMNS}, model_path)
    LOGGER.info("Saved final model to %s", model_path)
    return model, train


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    cfg = load_config()
    run_validation(cfg)
    best = select_best_model(cfg)
    print(f"Selected model (validation folds only): {best}")


if __name__ == "__main__":
    main()
