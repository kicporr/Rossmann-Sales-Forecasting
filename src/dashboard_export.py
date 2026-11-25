"""Export flat files for the Power BI dashboard.

Power BI Desktop is not installed in this environment, so the project ships a
complete, reproducible data export plus a documented model and DAX layer
instead of a binary PBIX.  Every CSV in ``dashboard/data`` is generated from
the processed parquet files by this script.

Run ``python -m src.dashboard_export``.
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

LOGGER = logging.getLogger(__name__)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def export(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    ensure_directories(cfg)
    data = load_processed(cfg)
    train, test, store = data["train"], data["test"], data["store"]
    out_dir = Path(cfg["project_root"]) / "dashboard" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    dim_store = store[
        [
            "Store",
            "StoreType",
            "Assortment",
            "CompetitionDistance",
            "CompetitionOpenSinceYear",
            "CompetitionOpenSinceMonth",
            "Promo2",
            "Promo2SinceYear",
            "PromoInterval",
        ]
    ].copy()
    dim_store.to_csv(out_dir / "dim_store.csv", index=False)

    dates = pd.date_range(train["Date"].min(), test["Date"].max(), freq="D")
    dim_date = pd.DataFrame({"Date": dates})
    dim_date["Year"] = dim_date["Date"].dt.year
    dim_date["Quarter"] = dim_date["Date"].dt.quarter
    dim_date["Month"] = dim_date["Date"].dt.month
    dim_date["MonthName"] = dim_date["Month"].map(lambda m: MONTHS[m - 1])
    dim_date["WeekOfYear"] = dim_date["Date"].dt.isocalendar().week.astype(int)
    dim_date["DayOfWeek"] = dim_date["Date"].dt.dayofweek + 1
    dim_date["DayName"] = dim_date["DayOfWeek"].map(lambda d: DAYS[d - 1])
    dim_date["IsWeekend"] = (dim_date["DayOfWeek"] >= 6).astype(int)
    dim_date["YearMonth"] = dim_date["Date"].dt.strftime("%Y-%m")
    dim_date.to_csv(out_dir / "dim_date.csv", index=False)

    fact = train[
        ["Store", "Date", "Sales", "Customers", "Open", "Promo", "StateHoliday", "SchoolHoliday"]
    ].copy()
    fact["Date"] = fact["Date"].dt.strftime("%Y-%m-%d")
    fact.to_csv(out_dir / "fact_sales.csv", index=False)

    open_df = train[train["Open"] == 1]
    agg_store = (
        open_df.groupby("Store", observed=True)
        .agg(
            avg_daily_sales=("Sales", "mean"),
            total_sales=("Sales", "sum"),
            avg_customers=("Customers", "mean"),
            open_days=("Sales", "size"),
            std_sales=("Sales", "std"),
        )
        .reset_index()
    )
    agg_store["cv"] = agg_store["std_sales"] / agg_store["avg_daily_sales"]
    agg_store = agg_store.merge(store[["Store", "StoreType", "Assortment"]], on="Store", how="left")
    agg_store.to_csv(out_dir / "agg_store.csv", index=False)

    agg_daily = (
        train.groupby("Date", observed=True)
        .agg(total_sales=("Sales", "sum"), total_customers=("Customers", "sum"), open_stores=("Open", "sum"))
        .reset_index()
    )
    agg_daily["Date"] = agg_daily["Date"].dt.strftime("%Y-%m-%d")
    agg_daily.to_csv(out_dir / "agg_daily.csv", index=False)

    agg_weekday = (
        open_df.groupby("DayOfWeek", observed=True)
        .agg(avg_sales=("Sales", "mean"), avg_customers=("Customers", "mean"), store_days=("Sales", "size"))
        .reset_index()
    )
    agg_weekday["DayName"] = agg_weekday["DayOfWeek"].map(lambda d: DAYS[d - 1])
    agg_weekday.to_csv(out_dir / "agg_weekday.csv", index=False)

    agg_promo = (
        open_df.groupby(["Promo", "StoreType"], observed=True)
        .agg(avg_sales=("Sales", "mean"), avg_customers=("Customers", "mean"), store_days=("Sales", "size"))
        .reset_index()
    )
    agg_promo.to_csv(out_dir / "agg_promo.csv", index=False)

    metrics_path = Path(cfg["paths"]["metrics"]) / "validation_results.json"
    if metrics_path.exists():
        results = json.loads(metrics_path.read_text(encoding="utf-8"))
        rows = []
        for fold, payload in results["folds"].items():
            for model, metrics in payload["models"].items():
                rows.append(
                    {
                        "fold": fold,
                        "model": model,
                        "rmspe": metrics["rmspe"],
                        "mae": metrics["mae"],
                        "rmse": metrics["rmse"],
                        "wape": metrics["wape"],
                        "bias_pct": metrics["bias_pct_of_mean"],
                        "n_scored": metrics["n_rows_scored"],
                    }
                )
        pd.DataFrame(rows).to_csv(out_dir / "model_metrics.csv", index=False)

    predictions_path = Path(cfg["paths"]["predictions"]) / "validation_predictions.parquet"
    if predictions_path.exists():
        predictions = pd.read_parquet(predictions_path)
        forecast_model = "ensemble_xgb_hist" if (predictions["model"] == "ensemble_xgb_hist").any() else "xgboost"
        holdout = predictions[(predictions["fold"] == "holdout") & (predictions["model"] == forecast_model)].copy()
        holdout["Date"] = pd.to_datetime(holdout["Date"]).dt.strftime("%Y-%m-%d")
        holdout[["Store", "Date", "Sales", "Prediction", "Open", "Promo", "StoreType"]].to_csv(
            out_dir / "forecast_holdout.csv", index=False
        )

    test_path = Path(cfg["paths"]["predictions"]) / "test_predictions.parquet"
    if test_path.exists():
        test_predictions = pd.read_parquet(test_path)
        test_predictions["Date"] = pd.to_datetime(test_predictions["Date"]).dt.strftime("%Y-%m-%d")
        test_predictions.to_csv(out_dir / "forecast_test.csv", index=False)

    summary = {
        "dim_store_rows": int(len(dim_store)),
        "dim_date_rows": int(len(dim_date)),
        "fact_sales_rows": int(len(fact)),
        "forecast_holdout_rows": int(len(pd.read_csv(out_dir / "forecast_holdout.csv")))
        if (out_dir / "forecast_holdout.csv").exists()
        else 0,
        "forecast_test_rows": int(len(pd.read_csv(out_dir / "forecast_test.csv")))
        if (out_dir / "forecast_test.csv").exists()
        else 0,
    }
    (out_dir / "export_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    export()


if __name__ == "__main__":
    main()
