"""Leakage-safe feature engineering for Rossmann daily sales.

Two feature families are created:

1. **Calendar / static features** – known in advance for the whole forecast
   horizon (day of week, month, promotions, holidays, store attributes,
   competition and Promo2 timing).
2. **Historical features** – lags and rolling statistics of *past* sales and
   customers.  Every historical feature at date ``t`` uses data up to
   ``t - 1`` only.  The rolling windows are shifted by one day, which is
   verified by automated tests in ``tests/test_features.py``.

For multi-day forecasting the module provides :class:`RecursiveForecaster`,
which rebuilds the historical features after each predicted day.  This avoids
the classic leakage pattern of using actual future sales during validation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

REFERENCE_DATE = pd.Timestamp("2013-01-01")
DATE_COL = "Date"
TARGET = "Sales"

CALENDAR_FEATURES = [
    "DayOfWeek",
    "Month",
    "WeekOfYear",
    "Quarter",
    "Day",
    "DayOfYear",
    "IsWeekend",
    "IsMonthStart",
    "IsMonthEnd",
    "SinDayOfYear",
    "CosDayOfYear",
    "SinDayOfWeek",
    "CosDayOfWeek",
    "StoreType_b",
    "StoreType_c",
    "StoreType_d",
    "Assortment_b",
    "Assortment_c",
    "CompetitionDistanceLog",
    "CompetitionOpenMonths",
    "HasCompetitionStart",
    "Promo2",
    "Promo2Active",
    "Promo2MonthsSinceStart",
    "Promo",
    "PromoYesterday",
    "PromoTomorrow",
    "SchoolHoliday",
    "StateHoliday_a",
    "StateHoliday_b",
    "StateHoliday_c",
]

HISTORY_FEATURES = [
    "sales_lag_1",
    "sales_lag_7",
    "sales_lag_14",
    "sales_lag_28",
    "sales_lag_365",
    "sales_roll_mean_7",
    "sales_roll_mean_28",
    "sales_roll_mean_90",
    "sales_roll_mean_365",
    "sales_roll_std_28",
    "sales_momentum_1_28",
    "sales_short_vs_long",
    "promo_share_28",
    "customers_roll_mean_28",
    "sales_per_customer_roll_28",
]

FEATURE_COLUMNS: list[str] = CALENDAR_FEATURES + HISTORY_FEATURES


def _min_periods(window: int) -> int:
    """Require a reasonable amount of history before trusting a rolling mean."""
    return max(2, int(round(window * 0.25)))


def _promo_month_mask(series: pd.Series) -> pd.Series:
    """Encode promotion months as a bit mask (bit 1 = January ... bit 12 = December)."""
    masks = []
    for value in series.fillna("").astype(str):
        mask = 0
        for part in value.split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= 12:
                mask |= 1 << int(part)
        masks.append(mask)
    return pd.Series(masks, index=series.index, dtype="int64")


def add_calendar_features(df: pd.DataFrame, store: pd.DataFrame) -> pd.DataFrame:
    """Attach calendar, store and promotion features to a store-day frame.

    Parameters
    ----------
    df:
        Must contain ``Store``, ``Date``, ``Promo``, ``SchoolHoliday`` and the
        three ``StateHoliday_*`` indicator columns (created by
        ``data_preparation.clean_sales``).
    store:
        Cleaned store table (one row per store).

    The function is vectorised and safe for both historical and future dates.
    """
    out = df.copy()
    out["Date"] = pd.to_datetime(out["Date"]).dt.normalize()

    iso = out["Date"].dt.isocalendar()
    out["DayOfWeek"] = out["Date"].dt.dayofweek + 1  # Kaggle convention: Monday=1 ... Sunday=7
    out["Month"] = out["Date"].dt.month
    out["WeekOfYear"] = iso["week"].astype("int16")
    out["Quarter"] = out["Date"].dt.quarter
    out["Year"] = out["Date"].dt.year
    out["Day"] = out["Date"].dt.day
    out["DayOfYear"] = out["Date"].dt.dayofyear
    out["IsWeekend"] = (out["DayOfWeek"] >= 6).astype("int8")
    out["IsMonthStart"] = out["Date"].dt.is_month_start.astype("int8")
    out["IsMonthEnd"] = out["Date"].dt.is_month_end.astype("int8")
    out["SinDayOfYear"] = np.sin(2 * np.pi * out["DayOfYear"] / 365.25)
    out["CosDayOfYear"] = np.cos(2 * np.pi * out["DayOfYear"] / 365.25)
    out["SinDayOfWeek"] = np.sin(2 * np.pi * out["DayOfWeek"] / 7)
    out["CosDayOfWeek"] = np.cos(2 * np.pi * out["DayOfWeek"] / 7)
    out["DaysSinceStart"] = (out["Date"] - REFERENCE_DATE).dt.days

    attrs = store[
        [
            "Store",
            "StoreType",
            "Assortment",
            "CompetitionDistanceLog",
            "CompetitionOpenSince",
            "HasCompetitionStart",
            "Promo2",
            "Promo2Start",
            "Promo2MonthsCsv",
        ]
    ].copy()
    attrs["Promo2MonthMask"] = _promo_month_mask(attrs["Promo2MonthsCsv"])
    # The processed split already carries store attributes; drop them first so
    # the merge cannot create _x/_y duplicate columns.
    overlap = [c for c in attrs.columns if c in out.columns and c != "Store"]
    out = out.drop(columns=overlap).merge(
        attrs.drop(columns=["Promo2MonthsCsv"]), on="Store", how="left", validate="many_to_one"
    )

    for code in ("b", "c", "d"):
        out[f"StoreType_{code}"] = (out["StoreType"] == code).astype("int8")
    for code in ("b", "c"):
        out[f"Assortment_{code}"] = (out["Assortment"] == code).astype("int8")

    competition_months = (out["Date"] - out["CompetitionOpenSince"]).dt.days / 30.44
    out["CompetitionOpenMonths"] = competition_months.clip(lower=0).fillna(-1).astype("float32")
    out["HasCompetitionStart"] = out["HasCompetitionStart"].fillna(0).astype("int8")

    out["Promo2"] = out["Promo2"].astype("int8")
    promo2_running = (out["Date"] >= out["Promo2Start"]) & out["Promo2Start"].notna()
    month_bit = (out["Promo2MonthMask"].to_numpy() >> out["Month"].to_numpy()) & 1
    out["Promo2Active"] = (
        (out["Promo2"] == 1) & promo2_running.to_numpy() & (month_bit == 1)
    ).astype("int8")
    promo2_months = (out["Date"] - out["Promo2Start"]).dt.days / 30.44
    out["Promo2MonthsSinceStart"] = np.where(
        (out["Promo2"] == 1) & out["Promo2Start"].notna(),
        np.clip(promo2_months.fillna(-1), 0, None),
        -1,
    ).astype("float32")

    out["PromoYesterday"] = out.get("PromoYesterday", pd.Series(np.nan, index=out.index)).astype("float32")
    out["PromoTomorrow"] = out.get("PromoTomorrow", pd.Series(np.nan, index=out.index)).astype("float32")

    for column in FEATURE_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    return out


def build_panel(history: pd.DataFrame, date_index: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
    """Pivot history into store x date matrices used for lag/rolling features.

    Rows are stores, columns are calendar dates.  Days without a record (store
    closed for renovation, not yet opened) stay ``NaN`` and are therefore not
    treated as zero sales.
    """
    stores = np.sort(history["Store"].unique())
    sales = history.pivot(index="Store", columns="Date", values="Sales").reindex(index=stores, columns=date_index)
    customers = history.pivot(index="Store", columns="Date", values="Customers").reindex(
        index=stores, columns=date_index
    )
    promo = history.pivot(index="Store", columns="Date", values="Promo").reindex(index=stores, columns=date_index)
    return {
        "sales_log": np.log1p(sales.astype("float64")),
        "customers": customers.astype("float64"),
        "promo": promo.astype("float64"),
        "stores": pd.Index(stores, name="Store"),
        "dates": date_index,
    }


def add_history_features(
    panel: dict[str, pd.DataFrame],
    lags: Sequence[int],
    windows: Sequence[int],
    offset: int = 1,
) -> pd.DataFrame:
    """Compute lagged and rolling features from store x date matrices.

    ``offset`` is the information lag: 1 for one-step-ahead (recursive)
    features and 48 for direct 48-day-ahead features.  With ``offset=h`` the
    feature row for date ``t`` represents the information set available at
    ``t - h``: ``sales_lag_1`` is sales at ``t-h``, and a 28-day rolling mean
    covers ``[t-h-27, t-h]``.  Nothing at or after ``t`` is ever used.
    """
    sales_log = panel["sales_log"].astype("float64")
    customers = panel["customers"].astype("float64")
    promo = panel["promo"].astype("float64")

    def stacked(frame: pd.DataFrame) -> pd.Series:
        out = frame.stack(future_stack=True)
        out.index.names = ["Store", "Date"]
        return out

    # pandas 3 removed ``axis=1`` for rolling; transpose instead so time is the
    # index axis (rows) and stores are columns.
    sales_t = sales_log.T
    customers_t = customers.T
    promo_t = promo.T
    data: dict[str, pd.Series] = {}
    for lag in lags:
        data[f"sales_lag_{lag}"] = stacked(sales_t.shift(offset + lag - 1).T)
    for window in windows:
        rolled = sales_t.shift(offset).rolling(window, min_periods=_min_periods(window))
        data[f"sales_roll_mean_{window}"] = stacked(rolled.mean().T)
        if window == 28:
            data[f"sales_roll_std_{window}"] = stacked(rolled.std().T)

    customers_roll_28 = customers_t.shift(offset).rolling(28, min_periods=7).mean().T
    data["customers_roll_mean_28"] = stacked(customers_roll_28)
    sales_roll_28 = sales_t.shift(offset).rolling(28, min_periods=_min_periods(28)).mean().T
    data["sales_per_customer_roll_28"] = stacked(
        np.log1p(np.expm1(sales_roll_28) / customers_roll_28.replace(0, np.nan))
    )
    data["promo_share_28"] = stacked(promo_t.shift(offset).rolling(28, min_periods=7).mean().T)

    out = pd.DataFrame(data)
    out["sales_momentum_1_28"] = out["sales_lag_1"] - out["sales_roll_mean_28"]
    out["sales_short_vs_long"] = out["sales_roll_mean_7"] - out["sales_roll_mean_365"]
    return out


def build_training_matrix(
    history: pd.DataFrame,
    store: pd.DataFrame,
    lags: Sequence[int] = (1, 7, 14, 28, 365),
    windows: Sequence[int] = (7, 28, 90, 365),
    history_offset: int = 1,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Build the model matrix for every open, positive-sales store-day.

    Parameters
    ----------
    history:
        Cleaned training rows **up to the forecast origin** (inclusive).  The
        caller is responsible for respecting the time split.
    store:
        Cleaned store attributes.

    Returns
    -------
    X, y, meta
        ``X`` contains :data:`FEATURE_COLUMNS`; ``y`` is ``log1p(Sales)``;
        ``meta`` keeps ``Store``, ``Date`` and ``Sales`` for evaluation.
    """
    history = history.sort_values(["Store", "Date"]).reset_index(drop=True)
    date_index = pd.date_range(history["Date"].min(), history["Date"].max(), freq="D")
    panel = build_panel(history, date_index)
    hist = add_history_features(panel, lags, windows, offset=history_offset)

    frame = history.merge(hist, left_on=["Store", "Date"], right_index=True, how="left", validate="one_to_one")
    frame = frame.sort_values(["Store", "Date"]).reset_index(drop=True)
    # Promotions on neighbouring days are known in advance; derive them from the
    # complete store-day grid so no future sales information is involved.
    promo_wide = frame.pivot(index="Store", columns="Date", values="Promo")
    prev = promo_wide.shift(1, axis=1).stack(future_stack=True).rename("PromoYesterday")
    nxt = promo_wide.shift(-1, axis=1).stack(future_stack=True).rename("PromoTomorrow")
    adjacency = pd.concat([prev, nxt], axis=1)
    adjacency.index.names = ["Store", "Date"]
    frame = frame.drop(columns=["PromoYesterday", "PromoTomorrow"], errors="ignore").merge(
        adjacency, left_on=["Store", "Date"], right_index=True, how="left", validate="one_to_one"
    )

    frame = add_calendar_features(frame, store)
    eligible = (frame["Open"] == 1) & (frame[TARGET] > 0)
    matrix = frame.loc[eligible].copy()
    X = matrix[FEATURE_COLUMNS].astype("float32")
    y = np.log1p(matrix[TARGET].astype("float64")).rename("log_sales")
    meta = matrix[["Store", "Date", TARGET, "Promo", "SchoolHoliday", "IsStateHoliday", "StoreType"]].reset_index(
        drop=True
    )
    LOGGER.info("Training matrix: %s rows x %s features", X.shape[0], X.shape[1])
    return X, y, meta


@dataclass
class ForecastOutput:
    """Container for recursive forecast results."""

    predictions: pd.DataFrame
    feature_snapshot: pd.DataFrame


class RecursiveForecaster:
    """Recursive multi-step forecaster for a fitted scikit-learn/XGBoost model.

    For every future day the model receives calendar features plus historical
    features rebuilt from *actual history extended with earlier predictions*.
    Closed days are set to zero and written back to the history panel, exactly
    as they appear in the training data.
    """

    def __init__(
        self,
        model: Any,
        store: pd.DataFrame,
        history: pd.DataFrame,
        feature_columns: Iterable[str] = FEATURE_COLUMNS,
        lags: Sequence[int] = (1, 7, 14, 28, 365),
        windows: Sequence[int] = (7, 28, 90, 365),
        max_horizon: int = 48,
    ) -> None:
        self.model = model
        self.feature_columns = list(feature_columns)
        self.lags = tuple(lags)
        self.windows = tuple(windows)
        self.max_horizon = max_horizon
        self.store = store.copy()
        self.history = history.sort_values(["Store", "Date"]).reset_index(drop=True)
        self.date_index = pd.date_range(self.history["Date"].min(), self.history["Date"].max(), freq="D")
        self.panel = build_panel(self.history, self.date_index)
        self.sales_log = self.panel["sales_log"].to_numpy(dtype="float64").copy()
        self.promo = self.panel["promo"].to_numpy(dtype="float64").copy()
        stores = self.panel["stores"]
        self.store_index = {store_id: pos for pos, store_id in enumerate(stores)}
        self.origin_customers = self._origin_customer_features()
        self.last_date = self.date_index[-1]

    def _origin_customer_features(self) -> pd.DataFrame:
        customers = self.panel["customers"].T
        roll = customers.rolling(28, min_periods=7).mean().T
        sales_roll = np.expm1(self.panel["sales_log"].T.rolling(28, min_periods=7).mean().T)
        per_customer = np.log1p(sales_roll / roll.replace(0, np.nan))
        return pd.DataFrame(
            {
                "customers_roll_mean_28": roll.iloc[:, -1].to_numpy(),
                "sales_per_customer_roll_28": per_customer.iloc[:, -1].to_numpy(),
            },
            index=self.panel["stores"],
        )

    def _window_stats(self, matrix: np.ndarray, end: int, window: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        start = max(0, end - window)
        block = matrix[:, start:end]
        count = np.sum(~np.isnan(block), axis=1)
        total = np.nansum(block, axis=1)
        mean = np.where(count >= _min_periods(window), total / np.maximum(count, 1), np.nan)
        std = np.where(count >= _min_periods(window), np.nanstd(block, axis=1), np.nan)
        return mean, std, count

    def _future_calendar(self, future: pd.DataFrame, promo_extended: np.ndarray, dates_extended: pd.DatetimeIndex) -> pd.DataFrame:
        """Calendar features for future rows, including promo adjacency."""
        future = future.copy()
        positions = dates_extended.get_indexer(pd.to_datetime(future["Date"]))
        store_pos = future["Store"].map(self.store_index).to_numpy()
        previous = np.full(len(future), np.nan)
        following = np.full(len(future), np.nan)
        has_prev = positions > 0
        has_next = positions < len(dates_extended) - 1
        previous[has_prev] = promo_extended[store_pos[has_prev], positions[has_prev] - 1]
        following[has_next] = promo_extended[store_pos[has_next], positions[has_next] + 1]
        future["PromoYesterday"] = previous
        future["PromoTomorrow"] = following
        for column in ("StateHoliday_a", "StateHoliday_b", "StateHoliday_c"):
            if column not in future.columns:
                future[column] = 0
        future["SchoolHoliday"] = future["SchoolHoliday"].fillna(0).astype("int8")
        return add_calendar_features(future, self.store)

    def predict(self, future: pd.DataFrame) -> ForecastOutput:
        """Generate predictions for ``future`` (Store, Date, Open, Promo, ...)."""
        future = future.copy()
        future["Date"] = pd.to_datetime(future["Date"]).dt.normalize()
        future = future.sort_values(["Date", "Store"]).reset_index(drop=True)
        future_dates = pd.DatetimeIndex(sorted(future["Date"].unique()))
        if len(future_dates) > self.max_horizon:
            raise ValueError(f"Horizon {len(future_dates)} exceeds configured maximum {self.max_horizon}")
        if future_dates.min() <= self.last_date:
            raise ValueError("Future dates must be strictly after the history end")

        all_dates = self.date_index.append(future_dates)
        history_len = len(self.date_index)
        promo_future = (
            future.pivot(index="Store", columns="Date", values="Promo")
            .reindex(index=self.panel["stores"], columns=future_dates)
            .to_numpy(dtype="float64")
        )
        # Extend the work matrices with one column per forecast day.  Values are
        # filled as the recursion advances: predictions for open days, 0 for
        # closed days, NaN for days that have not been reached yet.
        future_block = np.full((self.sales_log.shape[0], len(future_dates)), np.nan)
        self.sales_log = np.concatenate([self.sales_log, future_block], axis=1)
        self.promo = np.concatenate([self.promo, promo_future], axis=1)
        calendar = self._future_calendar(future, self.promo, all_dates)

        predictions = np.full(len(future), np.nan)
        future_dates_sorted = future_dates.sort_values()
        snapshots = []
        for day_number, date in enumerate(future_dates_sorted):
            end = history_len + day_number
            mask = (future["Date"] == date).to_numpy()
            rows = calendar.loc[mask].copy()
            positions = rows["Store"].map(self.store_index).to_numpy()
            feature_frame = pd.DataFrame(index=rows.index)

            for lag in self.lags:
                feature_frame[f"sales_lag_{lag}"] = self.sales_log[positions, end - lag]
            for window in self.windows:
                mean, std, _ = self._window_stats(self.sales_log, end, window)
                feature_frame[f"sales_roll_mean_{window}"] = mean[positions]
                if window == 28:
                    feature_frame[f"sales_roll_std_{window}"] = std[positions]
            promo_mean, _, _ = self._window_stats(self.promo, end, 28)
            feature_frame["promo_share_28"] = promo_mean[positions]
            feature_frame["customers_roll_mean_28"] = self.origin_customers["customers_roll_mean_28"].to_numpy()[positions]
            feature_frame["sales_per_customer_roll_28"] = self.origin_customers["sales_per_customer_roll_28"].to_numpy()[
                positions
            ]
            feature_frame["sales_momentum_1_28"] = (
                feature_frame["sales_lag_1"] - feature_frame["sales_roll_mean_28"]
            )
            feature_frame["sales_short_vs_long"] = (
                feature_frame["sales_roll_mean_7"] - feature_frame["sales_roll_mean_365"]
            )

            X_day = pd.concat([rows[self.feature_columns].reset_index(drop=True), feature_frame.reset_index(drop=True)], axis=1)
            X_day = X_day.loc[:, ~X_day.columns.duplicated()]
            X_day = X_day.reindex(columns=self.feature_columns).astype("float32")
            raw_prediction = np.expm1(self.model.predict(X_day))
            raw_prediction = np.clip(raw_prediction, 0, None)
            open_mask = rows["Open"].to_numpy() == 1
            day_prediction = np.where(open_mask, raw_prediction, 0.0)
            predictions[mask] = day_prediction

            self.sales_log[positions, end] = np.where(open_mask, np.log1p(day_prediction), 0.0)
            if len(snapshots) < 3:
                snapshot = X_day.copy()
                snapshot.insert(0, "Date", date)
                snapshots.append(snapshot.head(50))

        result = future[["Store", "Date"]].copy()
        result["Prediction"] = predictions
        snapshot_frame = pd.concat(snapshots, ignore_index=True) if snapshots else pd.DataFrame()
        return ForecastOutput(predictions=result, feature_snapshot=snapshot_frame)


class DirectForecaster:
    """Direct multi-step forecaster with origin-frozen historical features.

    For a 48-day horizon, recursive lag updates accumulate error: the pilot
    run showed RMSPE rising from 0.195 (one-step) to 0.38 (recursive).  This
    class instead represents every future day with the information set
    available at the forecast origin: ``sales_lag_1`` is the last observed
    day, 28-day rolling means end at the origin, and calendar/promotion
    features vary by target date.  Training rows are built with
    ``history_offset = horizon`` so the model never sees information that
    would not be available 48 days earlier.
    """

    def __init__(
        self,
        model: Any,
        store: pd.DataFrame,
        history: pd.DataFrame,
        feature_columns: Iterable[str] = FEATURE_COLUMNS,
        lags: Sequence[int] = (1, 7, 14, 28, 365),
        windows: Sequence[int] = (7, 28, 90, 365),
        max_horizon: int = 48,
    ) -> None:
        self.model = model
        self.feature_columns = list(feature_columns)
        self.lags = tuple(lags)
        self.windows = tuple(windows)
        self.max_horizon = max_horizon
        self.store = store.copy()
        self.history = history.sort_values(["Store", "Date"]).reset_index(drop=True)
        self.date_index = pd.date_range(self.history["Date"].min(), self.history["Date"].max(), freq="D")
        self.panel = build_panel(self.history, self.date_index)
        self.sales_log = self.panel["sales_log"].to_numpy(dtype="float64")
        self.customers = self.panel["customers"].to_numpy(dtype="float64")
        self.promo = self.panel["promo"].to_numpy(dtype="float64")
        self.store_index = {store_id: pos for pos, store_id in enumerate(self.panel["stores"])}
        self.last_date = self.date_index[-1]
        self.origin_features = self._origin_features()

    def _origin_features(self) -> pd.DataFrame:
        """Feature vector per store computed on the last observed day."""
        end = self.sales_log.shape[1]
        data: dict[str, np.ndarray] = {}
        for lag in self.lags:
            position = end - lag
            data[f"sales_lag_{lag}"] = (
                self.sales_log[:, position] if position >= 0 else np.full(self.sales_log.shape[0], np.nan)
            )
        for window in self.windows:
            start = max(0, end - window)
            block = self.sales_log[:, start:end]
            count = np.sum(~np.isnan(block), axis=1)
            mean = np.where(count >= _min_periods(window), np.nansum(block, axis=1) / np.maximum(count, 1), np.nan)
            data[f"sales_roll_mean_{window}"] = mean
            if window == 28:
                data[f"sales_roll_std_{window}"] = np.where(
                    count >= _min_periods(window), np.nanstd(block, axis=1), np.nan
                )
        promo_block = self.promo[:, max(0, end - 28) : end]
        data["promo_share_28"] = np.nanmean(promo_block, axis=1)
        customer_block = self.customers[:, max(0, end - 28) : end]
        customers_mean = np.nanmean(customer_block, axis=1)
        data["customers_roll_mean_28"] = customers_mean
        data["sales_per_customer_roll_28"] = np.log1p(
            np.expm1(data["sales_roll_mean_28"]) / np.where(customers_mean > 0, customers_mean, np.nan)
        )
        data["sales_momentum_1_28"] = data["sales_lag_1"] - data["sales_roll_mean_28"]
        data["sales_short_vs_long"] = data["sales_roll_mean_7"] - data["sales_roll_mean_365"]
        frame = pd.DataFrame(data, index=self.panel["stores"])
        frame.index.name = "Store"
        return frame

    def _future_calendar(self, future: pd.DataFrame, promo_extended: np.ndarray, dates_extended: pd.DatetimeIndex) -> pd.DataFrame:
        future = future.copy()
        positions = dates_extended.get_indexer(pd.to_datetime(future["Date"]))
        store_pos = future["Store"].map(self.store_index).to_numpy()
        previous = np.full(len(future), np.nan)
        following = np.full(len(future), np.nan)
        has_prev = positions > 0
        has_next = positions < len(dates_extended) - 1
        previous[has_prev] = promo_extended[store_pos[has_prev], positions[has_prev] - 1]
        following[has_next] = promo_extended[store_pos[has_next], positions[has_next] + 1]
        future["PromoYesterday"] = previous
        future["PromoTomorrow"] = following
        for column in ("StateHoliday_a", "StateHoliday_b", "StateHoliday_c"):
            if column not in future.columns:
                future[column] = 0
        future["SchoolHoliday"] = future["SchoolHoliday"].fillna(0).astype("int8")
        return add_calendar_features(future, self.store)

    def predict(self, future: pd.DataFrame) -> ForecastOutput:
        """Forecast every row of ``future`` from a single forecast origin."""
        future = future.copy()
        future["Date"] = pd.to_datetime(future["Date"]).dt.normalize()
        future = future.sort_values(["Date", "Store"]).reset_index(drop=True)
        future_dates = pd.DatetimeIndex(sorted(future["Date"].unique()))
        if len(future_dates) > self.max_horizon:
            raise ValueError(f"Horizon {len(future_dates)} exceeds configured maximum {self.max_horizon}")
        if future_dates.min() <= self.last_date:
            raise ValueError("Future dates must be strictly after the history end")

        all_dates = self.date_index.append(future_dates)
        promo_future = (
            future.pivot(index="Store", columns="Date", values="Promo")
            .reindex(index=self.panel["stores"], columns=future_dates)
            .to_numpy(dtype="float64")
        )
        promo_extended = np.concatenate([self.promo, promo_future], axis=1)
        calendar = self._future_calendar(future, promo_extended, all_dates)
        calendar = calendar.drop(columns=[column for column in HISTORY_FEATURES if column in calendar.columns])
        merged = calendar.merge(self.origin_features.reset_index(), on="Store", how="left", validate="many_to_one")
        X_future = merged.reindex(columns=self.feature_columns).astype("float32")
        raw_prediction = np.clip(np.expm1(self.model.predict(X_future)), 0, None)
        open_mask = merged["Open"].to_numpy() == 1
        prediction = np.where(open_mask, raw_prediction, 0.0)

        result = future[["Store", "Date"]].copy()
        result["Prediction"] = prediction
        snapshot = X_future.head(200).copy()
        snapshot.insert(0, "Date", merged["Date"].to_numpy()[: len(snapshot)])
        return ForecastOutput(predictions=result, feature_snapshot=snapshot)
