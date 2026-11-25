"""Shared pytest configuration."""

import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def processed():
    """Load processed data once for the whole test session.

    Skips the integration tests gracefully if the pipeline has not been run.
    """
    from src.config import load_config
    from src.data_preparation import load_processed

    processed_dir = PROJECT_ROOT / "data" / "processed"
    if not (processed_dir / "train_clean.parquet").exists():
        pytest.skip("Processed data missing; run `python -m src.data_preparation` first")
    data = load_processed(load_config())
    return data


@pytest.fixture(scope="session")
def small_history(processed):
    """A two-store, one-year slice that keeps feature tests fast and readable."""
    train = processed["train"]
    stores = [1, 2]
    history = train[(train["Store"].isin(stores)) & (train["Date"] <= pd.Timestamp("2014-12-31"))].copy()
    return history, processed["store"]
