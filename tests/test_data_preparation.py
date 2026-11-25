"""Unit tests for cleaning decisions and join integrity."""

import numpy as np
import pandas as pd
import pytest

from src.data_preparation import clean_sales, clean_store, merge_datasets


@pytest.fixture
def store_frame():
    return pd.DataFrame(
        {
            "Store": [1, 2, 3],
            "StoreType": ["a", "b", "c"],
            "Assortment": ["a", "b", "c"],
            "CompetitionDistance": [1000.0, np.nan, 5000.0],
            "CompetitionOpenSinceMonth": [1.0, np.nan, 5.0],
            "CompetitionOpenSinceYear": [2010.0, np.nan, 2012.0],
            "Promo2": [1, 0, 0],
            "Promo2SinceWeek": [10.0, np.nan, np.nan],
            "Promo2SinceYear": [2013.0, np.nan, np.nan],
            "PromoInterval": ["Jan,Apr,Jul,Oct", np.nan, np.nan],
        }
    )


def test_competition_distance_median_imputation_and_flag(store_frame):
    cleaned = clean_store(store_frame)
    assert cleaned["CompetitionDistance"].isna().sum() == 0
    assert cleaned.loc[cleaned.Store == 2, "CompetitionDistanceMissing"].item() == 1
    assert cleaned.loc[cleaned.Store == 2, "CompetitionDistance"].item() == pytest.approx(3000.0)
    assert cleaned.loc[cleaned.Store == 1, "CompetitionDistanceMissing"].item() == 0


def test_competition_start_is_not_invented(store_frame):
    cleaned = clean_store(store_frame).set_index("Store")
    assert pd.isna(cleaned.loc[2, "CompetitionOpenSince"])
    assert cleaned.loc[2, "HasCompetitionStart"] == 0
    assert cleaned.loc[1, "HasCompetitionStart"] == 1


def test_promo2_structural_missing(store_frame):
    cleaned = clean_store(store_frame).set_index("Store")
    assert cleaned.loc[2, "Promo2StartKnown"] == 0
    assert pd.isna(cleaned.loc[2, "Promo2Start"])
    assert cleaned.loc[1, "Promo2MonthsCsv"] == "1,4,7,10"


def test_clean_sales_flags_and_imputation():
    frame = pd.DataFrame(
        {
            "Store": [1, 1, 1],
            "DayOfWeek": [1, 2, 3],
            "Date": ["2015-01-01", "2015-01-02", "2015-01-03"],
            "Sales": [0, 100, 0],
            "Customers": [0, 10, 0],
            "Open": [0.0, 1.0, np.nan],
            "Promo": [0, 1, 0],
            "StateHoliday": ["0", "a", 0],
            "SchoolHoliday": [0, 0, 1],
        }
    )
    cleaned = clean_sales(frame, is_train=False)
    assert cleaned["Open"].tolist() == [0, 1, 1]
    assert cleaned["OpenImputed"].tolist() == [0, 0, 1]
    assert cleaned["StateHoliday"].tolist() == ["0", "a", "0"]
    assert cleaned["StateHoliday_a"].tolist() == [0, 1, 0]
    assert "Sales" not in cleaned.columns


def test_join_preserves_rows(store_frame):
    clean = clean_store(store_frame)
    sales = pd.DataFrame(
        {
            "Store": [1, 1, 2, 3, 3],
            "Date": pd.to_datetime(["2015-01-01"] * 5),
            "Sales": [0, 100, 200, 0, 300],
            "Customers": [0, 10, 20, 0, 30],
            "Open": [0, 1, 1, 0, 1],
            "Promo": [0, 1, 0, 0, 0],
            "StateHoliday": ["0"] * 5,
            "SchoolHoliday": [0] * 5,
        }
    )
    merged = merge_datasets(sales, clean)
    assert len(merged) == len(sales)
    assert merged["StoreType"].notna().all()


def test_join_detects_unmatched_store(store_frame):
    clean = clean_store(store_frame)
    sales = pd.DataFrame(
        {
            "Store": [99],
            "Date": pd.to_datetime(["2015-01-01"]),
            "Sales": [100],
            "Customers": [10],
            "Open": [1],
            "Promo": [0],
            "StateHoliday": ["0"],
            "SchoolHoliday": [0],
        }
    )
    with pytest.raises(ValueError, match="unmatched"):
        merge_datasets(sales, clean)
