"""Tests for leakage safety and feature correctness."""

import numpy as np
import pandas as pd
import pytest

from src.features import (
    FEATURE_COLUMNS,
    DirectForecaster,
    build_training_matrix,
)


def _previous_day_sales(history: pd.DataFrame, store: int, date: pd.Timestamp) -> float:
    row = history[(history["Store"] == store) & (history["Date"] == date - pd.Timedelta(days=1))]
    return float(row["Sales"].iloc[0]) if not row.empty else np.nan


def test_matrix_has_expected_columns(small_history):
    history, store = small_history
    X, y, meta = build_training_matrix(history, store, history_offset=1)
    assert list(X.columns) == FEATURE_COLUMNS
    assert len(X) == len(y) == len(meta)
    assert (y > 0).all(), "training target is log1p(Sales) and must be positive"


def test_lag_one_is_previous_calendar_day(small_history):
    history, store = small_history
    X, y, meta = build_training_matrix(history, store, history_offset=1)
    sample = meta[(meta["Store"] == 1) & (meta["Date"] == pd.Timestamp("2014-06-16"))]
    assert len(sample) == 1
    position = sample.index[0]
    expected = np.log1p(_previous_day_sales(history, 1, pd.Timestamp("2014-06-16")))
    assert X.iloc[position]["sales_lag_1"] == pytest.approx(expected, rel=1e-6)


def test_rolling_mean_uses_only_past_days(small_history):
    history, store = small_history
    X, y, meta = build_training_matrix(history, store, history_offset=1)
    target_date = pd.Timestamp("2014-06-16")
    sample = meta[(meta["Store"] == 1) & (meta["Date"] == target_date)]
    position = sample.index[0]
    window = history[
        (history["Store"] == 1)
        & (history["Date"] < target_date)
        & (history["Date"] >= target_date - pd.Timedelta(days=7))
    ]
    expected = np.log1p(window["Sales"]).mean()
    assert X.iloc[position]["sales_roll_mean_7"] == pytest.approx(expected, rel=1e-6)


def test_perturbing_future_sales_does_not_change_past_features(small_history):
    history, store = small_history
    cutoff = pd.Timestamp("2014-09-01")
    base = history[history["Date"] <= pd.Timestamp("2014-12-31")].copy()
    perturbed = base.copy()
    perturbed.loc[perturbed["Date"] > cutoff, "Sales"] += 5000

    X_base, _, meta_base = build_training_matrix(base, store, history_offset=48)
    X_pert, _, meta_pert = build_training_matrix(perturbed, store, history_offset=48)

    before_base = (meta_base["Date"] <= cutoff).to_numpy()
    before_pert = (meta_pert["Date"] <= cutoff).to_numpy()
    assert before_base.sum() == before_pert.sum() > 0

    difference = (
        X_base.loc[before_base].fillna(-1).to_numpy() - X_pert.loc[before_pert].fillna(-1).to_numpy()
    )
    assert np.abs(difference).max() == 0, "future sales leaked into historical features"


def test_direct_features_are_anchored_at_origin(small_history):
    history, store = small_history
    X, y, meta = build_training_matrix(history, store, history_offset=48)
    sample = meta[(meta["Store"] == 1) & (meta["Date"] == pd.Timestamp("2014-12-15"))]
    position = sample.index[0]
    origin = pd.Timestamp("2014-12-15") - pd.Timedelta(days=48)
    expected = np.log1p(_previous_day_sales(history, 1, origin + pd.Timedelta(days=1)))
    assert X.iloc[position]["sales_lag_1"] == pytest.approx(expected, rel=1e-6)


def test_direct_forecaster_completes_and_zeroes_closed_days(small_history):
    from sklearn.dummy import DummyRegressor

    history, store = small_history
    X, y, _ = build_training_matrix(history, store, history_offset=1)
    model = DummyRegressor(strategy="mean").fit(X, y)

    dates = pd.date_range("2015-01-01", periods=5, freq="D")
    future = pd.DataFrame(
        {
            "Store": np.repeat([1, 2], len(dates)),
            "Date": np.tile(dates, 2),
            "Open": [1, 1, 0, 1, 1, 1, 1, 0, 1, 1],
            "Promo": 0,
            "SchoolHoliday": 0,
            "StateHoliday_a": 0,
            "StateHoliday_b": 0,
            "StateHoliday_c": 0,
        }
    )
    forecaster = DirectForecaster(model, store, history, max_horizon=10)
    output = forecaster.predict(future)

    assert len(output.predictions) == len(future)
    assert output.predictions["Prediction"].notna().all()
    assert (output.predictions["Prediction"] >= 0).all()
    merged = future.merge(output.predictions, on=["Store", "Date"])
    assert (merged.loc[merged["Open"] == 0, "Prediction"] == 0).all()
    assert (merged.loc[merged["Open"] == 1, "Prediction"] > 0).all()
