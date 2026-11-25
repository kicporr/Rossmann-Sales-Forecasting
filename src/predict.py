"""Generate the Kaggle submission and store forecast artefacts.

The script refits the selected XGBoost component on the full training history,
blends it with the historical average when the ensemble is selected, forecasts
the 48-day competition horizon from a single origin and validates the
submission file against ``sample_submission.csv`` (row count, Id order,
non-negative sales).

Run ``python -m src.predict`` after ``python -m src.train``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import ensure_directories, load_config
from src.data_preparation import load_processed
from src.features import FEATURE_COLUMNS, DirectForecaster
from src.train import ENSEMBLE_NAME, historical_average_forecast, select_best_model, train_final_model

LOGGER = logging.getLogger(__name__)


def validate_submission(submission: pd.DataFrame, sample: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    """Hard checks required before a submission can be uploaded."""
    if list(submission.columns) != ["Id", "Sales"]:
        raise ValueError(f"Unexpected submission columns: {list(submission.columns)}")
    if len(submission) != len(sample):
        raise ValueError(f"Row count mismatch: {len(submission)} != {len(sample)}")
    if not np.array_equal(submission["Id"].to_numpy(), sample["Id"].to_numpy()):
        raise ValueError("Id order does not match sample_submission.csv")
    if submission["Sales"].isna().any():
        raise ValueError("Submission contains NaN predictions")
    if (submission["Sales"] < 0).any():
        raise ValueError("Submission contains negative predictions")
    horizon_days = int(cfg["split"]["horizon_days"])
    report = {
        "rows": int(len(submission)),
        "unique_ids": int(submission["Id"].nunique()),
        "id_order_matches_sample": True,
        "min_sales": float(submission["Sales"].min()),
        "max_sales": float(submission["Sales"].max()),
        "mean_sales": float(submission["Sales"].mean()),
        "median_sales": float(submission["Sales"].median()),
        "share_zero_predictions": float((submission["Sales"] == 0).mean()),
        "horizon_days": horizon_days,
    }
    return report


def generate_submission(cfg: dict[str, Any] | None = None, model_name: str | None = None) -> dict[str, Any]:
    """Fit the final model, forecast ``test.csv`` and write submission files."""
    cfg = cfg or load_config()
    ensure_directories(cfg)
    data = load_processed(cfg)
    train, test, store = data["train"], data["test"], data["store"]

    selected_model = model_name or select_best_model(cfg)
    fit_name = "xgboost" if selected_model == ENSEMBLE_NAME else selected_model
    model, _ = train_final_model(cfg, model_name=fit_name, data=data)

    forecaster = DirectForecaster(
        model=model,
        store=store,
        history=train,
        feature_columns=FEATURE_COLUMNS,
        lags=cfg["features"]["lags"],
        windows=cfg["features"]["rolling_windows"],
        max_horizon=int(cfg["split"]["horizon_days"]),
    )
    output = forecaster.predict(test)
    prediction_frame = test[["Store", "Date"]].merge(
        output.predictions, on=["Store", "Date"], how="left", validate="one_to_one"
    )
    if selected_model == ENSEMBLE_NAME:
        weights = cfg["models"]["ensemble"]["weights"]
        historical = historical_average_forecast(train, test)
        historical_frame = test[["Store", "Date"]].copy()
        historical_frame["Historical"] = historical.to_numpy()
        prediction_frame = prediction_frame.merge(
            historical_frame, on=["Store", "Date"], how="left", validate="one_to_one"
        )
        prediction_frame["Prediction"] = (
            float(weights["xgboost"]) * prediction_frame["Prediction"]
            + float(weights["historical_average"]) * prediction_frame["Historical"]
        )
        LOGGER.info(
            "Applied ensemble weights: xgboost=%.2f, historical_average=%.2f",
            float(weights["xgboost"]),
            float(weights["historical_average"]),
        )

    submission_frame = test[["Id", "Store", "Date", "Open", "Promo", "StoreType"]].merge(
        prediction_frame[["Store", "Date", "Prediction"]], on=["Store", "Date"], how="left", validate="one_to_one"
    )
    if submission_frame["Prediction"].isna().any():
        missing = int(submission_frame["Prediction"].isna().sum())
        raise ValueError(f"{missing} test rows did not receive a prediction")
    submission_frame["Sales"] = submission_frame["Prediction"].clip(lower=0)
    submission_frame.loc[submission_frame["Open"] == 0, "Sales"] = 0.0
    submission = submission_frame.sort_values("Id")[["Id", "Sales"]].reset_index(drop=True)

    sample = pd.read_csv(Path(cfg["paths"]["raw"]) / cfg["data"]["submission_file"])
    report = validate_submission(submission, sample, cfg)
    report["model"] = selected_model

    predictions_dir = Path(cfg["paths"]["predictions"])
    submission.to_csv(predictions_dir / "submission.csv", index=False)
    submission.to_csv(Path(cfg["project_root"]) / "submission.csv", index=False)
    submission_frame.sort_values(["Store", "Date"])[
        ["Id", "Store", "Date", "Open", "Promo", "StoreType", "Sales"]
    ].to_parquet(predictions_dir / "test_predictions.parquet", index=False)
    output.feature_snapshot.to_parquet(predictions_dir / "feature_snapshot.parquet", index=False)

    metrics_dir = Path(cfg["paths"]["metrics"])
    (metrics_dir / "submission_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    LOGGER.info("Submission summary: %s", report)
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    generate_submission()


if __name__ == "__main__":
    main()
