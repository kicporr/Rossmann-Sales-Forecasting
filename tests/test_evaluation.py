"""Tests for the competition metric and the error breakdown."""

import numpy as np
import pandas as pd
import pytest

from src.evaluation import error_breakdown, evaluate_predictions, mae, rmspe, rmse, wape


def test_rmspe_known_value():
    actual = np.array([100.0, 200.0])
    predicted = np.array([110.0, 180.0])
    expected = np.sqrt((((-10 / 100) ** 2) + ((20 / 200) ** 2)) / 2)
    assert rmspe(actual, predicted) == pytest.approx(expected)


def test_rmspe_ignores_zero_and_negative_targets():
    actual = np.array([0.0, 100.0, -5.0])
    predicted = np.array([999.0, 90.0, 1.0])
    assert rmspe(actual, predicted) == pytest.approx(0.1)
    assert rmspe(np.zeros(3), np.ones(3)) != rmspe(np.zeros(3), np.ones(3))  # NaN


def test_absolute_metrics():
    actual = np.array([100.0, 200.0])
    predicted = np.array([110.0, 180.0])
    assert mae(actual, predicted) == pytest.approx(15.0)
    assert rmse(actual, predicted) == pytest.approx(np.sqrt((100 + 400) / 2))
    assert wape(actual, predicted) == pytest.approx(30 / 300)


def test_evaluate_predictions_excludes_closed_days_and_reports_bias():
    frame = pd.DataFrame(
        {
            "Open": [1, 1, 0],
            "Sales": [100.0, 200.0, 0.0],
            "Prediction": [110.0, 180.0, 0.0],
        }
    )
    result = evaluate_predictions(frame, label="demo")
    assert result["n_rows_total"] == 3
    assert result["n_rows_scored"] == 2
    assert result["rmspe"] == pytest.approx(np.sqrt((((-10 / 100) ** 2) + ((20 / 200) ** 2)) / 2))
    assert result["bias_mean"] == pytest.approx(-5.0)
    assert result["model"] == "demo"


def test_error_breakdown_groups_and_filters_small_segments():
    frame = pd.DataFrame(
        {
            "StoreType": ["a", "a", "b", "b", "c"],
            "Sales": [100.0, 200.0, 300.0, 400.0, 500.0],
            "Prediction": [90.0, 220.0, 330.0, 360.0, 450.0],
        }
    )
    table = error_breakdown(frame, "StoreType", min_rows=2)
    assert set(table["StoreType"]) == {"a", "b"}
    assert table.loc[table.StoreType == "a", "n"].item() == 2
    assert table["rmspe"].notna().all()
