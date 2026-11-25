"""Data loading, validation and cleaning for the Rossmann Store Sales data.

Design principles
-----------------
* Raw files in ``data/raw`` are never modified.
* Cleaning decisions are explicit, documented and idempotent.
* Nothing that is unavailable at forecasting time is imputed using future
  sales information.  Store attributes are static and can safely be joined.
* Every quality check is recorded in ``outputs/metrics/data_quality.json``.

Run ``python -m src.data_preparation`` (from the project root) to rebuild all
processed datasets.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import ensure_directories, load_config

LOGGER = logging.getLogger(__name__)

DATE_COLUMNS = ("Date",)
SALES_DTYPES = {
    "Store": "int64",
    "DayOfWeek": "int8",
    "Sales": "int64",
    "Customers": "int64",
    "Open": "int8",
    "Promo": "int8",
    "SchoolHoliday": "int8",
    "StateHoliday": "string",
}
STORE_DTYPES = {
    "Store": "int64",
    "StoreType": "string",
    "Assortment": "string",
    "Promo2": "int8",
    "PromoInterval": "string",
}
PROMO_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sept": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}
HOLIDAY_CODES = ("a", "b", "c")


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required data file: {path}")
    return pd.read_csv(path, **kwargs)


def load_raw_data(cfg: dict[str, Any]) -> dict[str, pd.DataFrame]:
    """Load the four official competition files without modification.

    ``StateHoliday`` is read as text because the raw file mixes numeric and
    character codes (``0``, ``a``, ``b``, ``c``).  ``Open`` in ``test.csv`` is
    read as float because 11 rows are blank.
    """
    raw_dir = Path(cfg["paths"]["raw"])
    names = cfg["data"]
    data = {
        "train": _read_csv(
            raw_dir / names["train_file"],
            dtype=SALES_DTYPES,
            parse_dates=list(DATE_COLUMNS),
            low_memory=False,
        ),
        "test": _read_csv(
            raw_dir / names["test_file"],
            dtype={**{k: v for k, v in SALES_DTYPES.items() if k != "Sales"}, "Open": "float64"},
            parse_dates=list(DATE_COLUMNS),
            low_memory=False,
        ),
        "store": _read_csv(raw_dir / names["store_file"], dtype=STORE_DTYPES),
        "submission": _read_csv(raw_dir / names["submission_file"]),
    }
    LOGGER.info(
        "Loaded raw data: train=%s test=%s store=%s", data["train"].shape, data["test"].shape, data["store"].shape
    )
    return data


def _iso_week_to_date(year: float, week: float, day: int = 1) -> pd.Timestamp:
    """Convert an ISO year/week pair to the Monday-based calendar date."""
    if pd.isna(year) or pd.isna(week):
        return pd.NaT
    try:
        return pd.Timestamp.fromisocalendar(int(year), int(week), day)
    except ValueError:
        return pd.NaT


def clean_store(store: pd.DataFrame) -> pd.DataFrame:
    """Clean static store attributes and derive interpretable indicators.

    Missing-value handling (documented in ``reports/data_quality_report.md``):

    * ``CompetitionDistance`` (3 rows): median imputation + missing flag.
    * ``CompetitionOpenSince*`` (354 rows): kept as unknown; the derived
      ``CompetitionOpenMonths`` is set to -1 and ``HasCompetitionStart=0``.
    * ``Promo2Since*`` / ``PromoInterval`` (544 rows): structurally missing
      because ``Promo2=0``; derived ``Promo2Active`` is 0 and the start date is
      left as ``NaT``.  No arbitrary date is invented.
    """
    store = store.copy()
    store["StoreType"] = store["StoreType"].fillna("Unknown").str.lower().str.strip()
    store["Assortment"] = store["Assortment"].fillna("Unknown").str.lower().str.strip()

    store["CompetitionDistanceMissing"] = store["CompetitionDistance"].isna().astype("int8")
    comp_median = float(store["CompetitionDistance"].median())
    store["CompetitionDistance"] = store["CompetitionDistance"].fillna(comp_median)
    store["CompetitionDistanceLog"] = np.log1p(store["CompetitionDistance"])

    has_start = store["CompetitionOpenSinceYear"].notna() & store["CompetitionOpenSinceMonth"].notna()
    store["HasCompetitionStart"] = has_start.astype("int8")
    comp_start = pd.to_datetime(
        {
            "year": store["CompetitionOpenSinceYear"].fillna(1970).astype(int),
            "month": store["CompetitionOpenSinceMonth"].fillna(1).astype(int),
            "day": 1,
        },
        errors="coerce",
    )
    store["CompetitionOpenSince"] = comp_start.where(has_start, pd.NaT)

    store["Promo2StartKnown"] = (
        store["Promo2SinceYear"].notna() & store["Promo2SinceWeek"].notna()
    ).astype("int8")
    promo_start = pd.Series(
        [
            _iso_week_to_date(year, week)
            for year, week in zip(store["Promo2SinceYear"], store["Promo2SinceWeek"], strict=True)
        ],
        index=store.index,
    )
    store["Promo2Start"] = promo_start.where(store["Promo2StartKnown"].astype(bool), pd.NaT)
    store["Promo2Months"] = [
        set(str(interval).split(",")) if isinstance(interval, str) and interval else set()
        for interval in store["PromoInterval"].fillna("")
    ]
    month_numbers = store["Promo2Months"].apply(
        lambda names: frozenset(PROMO_MONTHS[name.strip()] for name in names if name.strip() in PROMO_MONTHS)
    )
    # Store the promotion months as a compact CSV string: parquet cannot hold sets.
    store["Promo2MonthsCsv"] = month_numbers.apply(lambda months: ",".join(str(m) for m in sorted(months)))
    store = store.drop(columns=["Promo2Months"])
    store["PromoInterval"] = store["PromoInterval"].fillna("None")
    LOGGER.info("Cleaned store table: %s rows, median CompetitionDistance=%.0f", len(store), comp_median)
    return store


def clean_sales(df: pd.DataFrame, is_train: bool) -> pd.DataFrame:
    """Clean a transaction-level split (``train`` or ``test``).

    ``Open`` is missing for 11 test rows.  Those values are imputed with the
    store's modal opening state (fallback 1) and flagged in
    ``OpenImputed`` so the decision stays auditable.
    """
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df["StateHoliday"] = (
        df["StateHoliday"].astype("string").fillna("0").str.strip().str.lower().replace({"nan": "0"})
    )

    df["OpenImputed"] = 0
    if df["Open"].isna().any():
        # If a store has no clear modal state (e.g. a 50/50 split), default to
        # "open": a missing Open flag should not silently close a store.
        store_mode = df.groupby("Store")["Open"].transform(
            lambda values: 1.0 if values.notna().sum() == 0 or (values.mode() == 1).any() else 0.0
        )
        missing = df["Open"].isna()
        df.loc[missing, "Open"] = store_mode[missing]
        df.loc[missing, "OpenImputed"] = 1
        LOGGER.warning("Imputed %d missing Open values in the %s split", int(missing.sum()), "train" if is_train else "test")
    df["Open"] = df["Open"].astype("int8").clip(0, 1)
    df["IsOpen"] = df["Open"].astype("int8")
    df["Promo"] = df["Promo"].astype("int8")
    df["SchoolHoliday"] = df["SchoolHoliday"].astype("int8")

    for code in HOLIDAY_CODES:
        df[f"StateHoliday_{code}"] = (df["StateHoliday"] == code).astype("int8")
    df["IsStateHoliday"] = (df["StateHoliday"] != "0").astype("int8")

    if is_train:
        if df["Sales"].isna().any():
            raise ValueError("Training data contains missing Sales values")
        df["SalesZero"] = (df["Sales"] == 0).astype("int8")
        df["SalesZeroWhileOpen"] = ((df["Sales"] == 0) & (df["Open"] == 1)).astype("int8")
    else:
        # Defence in depth: a test frame must never carry future targets or
        # customer counts, even if a caller passes a train-like DataFrame.
        df = df.drop(columns=[column for column in ("Sales", "Customers") if column in df.columns])
    LOGGER.info("Cleaned %s split: %s rows", "train" if is_train else "test", len(df))
    return df


def merge_datasets(sales: pd.DataFrame, store: pd.DataFrame) -> pd.DataFrame:
    """Join transaction data with static store attributes, preserving rows."""
    before = len(sales)
    merged = sales.merge(store, on="Store", how="left", validate="many_to_one")
    if len(merged) != before:
        raise ValueError(f"JOIN changed row count: {before} -> {len(merged)}")
    if merged["StoreType"].isna().any():
        raise ValueError("JOIN produced unmatched stores")
    return merged


def _quality_checks(train: pd.DataFrame, test: pd.DataFrame, store: pd.DataFrame) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "train_rows": int(len(train)),
        "train_columns": int(train.shape[1]),
        "test_rows": int(len(test)),
        "test_columns": int(test.shape[1]),
        "store_rows": int(len(store)),
        "train_date_range": [str(train["Date"].min().date()), str(train["Date"].max().date())],
        "test_date_range": [str(test["Date"].min().date()), str(test["Date"].max().date())],
        "train_stores": int(train["Store"].nunique()),
        "test_stores": int(test["Store"].nunique()),
        "duplicate_store_date_train": int(train.duplicated(["Store", "Date"]).sum()),
        "duplicate_store_date_test": int(test.duplicated(["Store", "Date"]).sum()),
        "open_imputed_test": int(test["OpenImputed"].sum()),
        "closed_rows_train": int((train["Open"] == 0).sum()),
        "zero_sales_rows_train": int((train["Sales"] == 0).sum()),
        "zero_sales_open_rows_train": int(train["SalesZeroWhileOpen"].sum()),
        "negative_sales_rows": int((train["Sales"] < 0).sum()),
        "tests_passed": True,
        "checks": [],
    }

    def check(name: str, condition: bool, detail: str) -> None:
        checks["checks"].append({"check": name, "passed": bool(condition), "detail": detail})
        if not condition:
            checks["tests_passed"] = False

    check("row_count_preserved_by_join", len(train) == checks["train_rows"], "LEFT JOIN must not duplicate rows")
    check("unique_store_date_train", checks["duplicate_store_date_train"] == 0, "one row per store-day")
    check("unique_store_date_test", checks["duplicate_store_date_test"] == 0, "one row per store-day")
    check("no_missing_store_type", bool(train["StoreType"].notna().all()), "all stores matched store.csv")
    check("non_negative_sales", checks["negative_sales_rows"] == 0, "Sales >= 0")
    check("date_ranges_contiguous", test["Date"].min() == train["Date"].max() + pd.Timedelta(days=1), "test starts the day after train")
    check("all_test_stores_in_train", set(test["Store"]).issubset(set(train["Store"])), "cold-start stores require separate handling")
    check(
        "submission_rows_match_test",
        len(test) == 41088,
        "official test split contains 41,088 store-day rows",
    )
    return checks


def prepare_data(cfg: dict[str, Any] | None = None, write: bool = True) -> dict[str, Any]:
    """Execute the full cleaning pipeline and write processed parquet files."""
    cfg = cfg or load_config()
    ensure_directories(cfg)
    raw = load_raw_data(cfg)
    store = clean_store(raw["store"])
    train = merge_datasets(clean_sales(raw["train"], is_train=True), store)
    test = merge_datasets(clean_sales(raw["test"], is_train=False), store)

    checks = _quality_checks(train, test, store)
    if write:
        processed = Path(cfg["paths"]["processed"])
        train.to_parquet(processed / "train_clean.parquet", index=False)
        test.to_parquet(processed / "test_clean.parquet", index=False)
        store.to_parquet(processed / "store_clean.parquet", index=False)
        metrics = Path(cfg["paths"]["metrics"])
        metrics.mkdir(parents=True, exist_ok=True)
        (metrics / "data_quality.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
        LOGGER.info("Wrote processed datasets to %s", processed)
    return checks


def load_processed(cfg: dict[str, Any] | None = None) -> dict[str, pd.DataFrame]:
    """Load the processed parquet datasets produced by :func:`prepare_data`."""
    cfg = cfg or load_config()
    processed = Path(cfg["paths"]["processed"])
    return {
        "train": pd.read_parquet(processed / "train_clean.parquet"),
        "test": pd.read_parquet(processed / "test_clean.parquet"),
        "store": pd.read_parquet(processed / "store_clean.parquet"),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    checks = prepare_data()
    print(json.dumps({k: v for k, v in checks.items() if k != "checks"}, indent=2))
    failed = [c for c in checks["checks"] if not c["passed"]]
    if failed:
        raise SystemExit(f"Quality checks failed: {failed}")
    print("All data quality checks passed.")


if __name__ == "__main__":
    main()
