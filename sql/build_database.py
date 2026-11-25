"""Build the SQLite database and execute every analytical SQL query.

Usage (from the project root)::

    python sql/build_database.py

Outputs
-------
* ``data/processed/rossmann.sqlite`` - relational copy of the cleaned data
* ``outputs/metrics/sql/<query_name>.csv`` - result of every query
* ``outputs/metrics/sql_results.md`` - readable report with query definitions
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config  # noqa: E402
from src.data_preparation import load_processed  # noqa: E402

QUERY_PATTERN = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)


def split_queries(sql_text: str) -> dict[str, str]:
    """Split a SQL file into named statements using ``-- name:`` markers."""
    matches = list(QUERY_PATTERN.finditer(sql_text))
    queries: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(sql_text)
        statement = sql_text[start:end].strip().rstrip(";").strip()
        queries[match.group(1)] = statement
    return queries


def _none_if_nan(value: object) -> object:
    return None if pd.isna(value) else value


def build_database(cfg: dict) -> Path:
    """Create the SQLite database from processed parquet files."""
    data = load_processed(cfg)
    db_path = Path(cfg["paths"]["processed"]) / "rossmann.sqlite"
    if db_path.exists():
        db_path.unlink()

    connection = sqlite3.connect(db_path)
    try:
        connection.executescript((PROJECT_ROOT / "sql" / "create_tables.sql").read_text(encoding="utf-8"))
        store = data["store"]
        store_rows = [
            (
                int(row.Store),
                row.StoreType,
                row.Assortment,
                _none_if_nan(row.CompetitionDistance),
                _none_if_nan(row.CompetitionOpenSinceMonth),
                _none_if_nan(row.CompetitionOpenSinceYear),
                int(row.Promo2),
                _none_if_nan(row.Promo2SinceWeek),
                _none_if_nan(row.Promo2SinceYear),
                row.PromoInterval,
            )
            for row in store.itertuples(index=False)
        ]
        connection.executemany("INSERT INTO stores VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", store_rows)

        train = data["train"]
        train_rows = [
            (
                int(row.Store),
                row.Date.strftime("%Y-%m-%d"),
                int(row.DayOfWeek),
                int(row.Sales),
                int(row.Customers),
                int(row.Open),
                int(row.Promo),
                str(row.StateHoliday),
                int(row.SchoolHoliday),
            )
            for row in train.itertuples(index=False)
        ]
        connection.executemany("INSERT INTO train_sales VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", train_rows)

        test = data["test"]
        test_rows = [
            (
                int(row.Id),
                int(row.Store),
                row.Date.strftime("%Y-%m-%d"),
                int(row.DayOfWeek),
                int(row.Open),
                int(row.Promo),
                str(row.StateHoliday),
                int(row.SchoolHoliday),
            )
            for row in test.itertuples(index=False)
        ]
        connection.executemany("INSERT INTO test_sales VALUES (?, ?, ?, ?, ?, ?, ?, ?)", test_rows)
        connection.commit()
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("stores", "train_sales", "test_sales")
        }
        print(f"Database built at {db_path} with {counts}")
    finally:
        connection.close()
    return db_path


def run_queries(cfg: dict, db_path: Path) -> None:
    """Execute all named queries and export results to CSV + markdown."""
    queries = split_queries((PROJECT_ROOT / "sql" / "analytical_queries.sql").read_text(encoding="utf-8"))
    output_dir = Path(cfg["paths"]["metrics"]) / "sql"
    output_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# SQL query results", "", f"Database: `{db_path.name}`", ""]
    connection = sqlite3.connect(db_path)
    try:
        for name, statement in queries.items():
            frame = pd.read_sql_query(statement, connection)
            frame.to_csv(output_dir / f"{name}.csv", index=False)
            lines.extend(
                [
                    f"## {name}",
                    "",
                    f"Rows returned: {len(frame)}",
                    "",
                    frame.head(10).to_markdown(index=False) if not frame.empty else "_No rows_",
                    "",
                ]
            )
            print(f"{name:35s} rows={len(frame)}")
    finally:
        connection.close()
    (Path(cfg["paths"]["metrics"]) / "sql_results.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    cfg = load_config()
    db_path = build_database(cfg)
    run_queries(cfg, db_path)


if __name__ == "__main__":
    main()
