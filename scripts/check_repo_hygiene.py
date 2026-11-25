#!/usr/bin/env python3
"""Repository hygiene checks for the public GitHub release.

The Kaggle data may not be redistributed, so this script fails if raw or
processed data, model binaries, prediction files or dashboard CSV exports are
tracked by git. It also catches absolute local paths in notebooks/docs and
validates the committed submission shape.
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []

REQUIRED = [
    "README.md",
    "LICENSE",
    "requirements.txt",
    "config/config.yaml",
    "src/data_preparation.py",
    "src/features.py",
    "src/train.py",
    "src/predict.py",
    "src/evaluation.py",
    "sql/create_tables.sql",
    "sql/analytical_queries.sql",
    "reports/model_comparison.md",
    "docs/methodology.md",
    "tests/test_evaluation.py",
    "submission.csv",
]

FORBIDDEN_PREFIXES = (
    "data/raw/",
    "data/processed/",
    "outputs/models/",
    "outputs/predictions/",
)
FORBIDDEN_PATTERNS = (
    re.compile(r"^dashboard/data/.+\.csv$"),
    re.compile(r"^outputs/metrics/.+\.log$"),
)
TEXT_SUFFIXES = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".ipynb", ".sql", ".html", ".css", ".toml"}


def tracked_files() -> list[Path]:
    """Return git-tracked files, or walk the tree when git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        ignored = {".git", "__pycache__", ".pytest_cache", "venv", ".venv"}
        return [
            path.relative_to(ROOT)
            for path in ROOT.rglob("*")
            if path.is_file() and not any(part in ignored for part in path.parts)
        ]
    return [Path(item) for item in result.stdout.decode("utf-8").split("\0") if item]


def check_required() -> None:
    for name in REQUIRED:
        if not (ROOT / name).exists():
            ERRORS.append(f"missing required file: {name}")


def check_forbidden(files: list[Path]) -> None:
    for path in files:
        posix = path.as_posix()
        if posix.endswith("/.gitkeep"):
            continue
        if posix.startswith(FORBIDDEN_PREFIXES):
            ERRORS.append(f"forbidden data/artifact tracked: {posix}")
        if any(pattern.match(posix) for pattern in FORBIDDEN_PATTERNS):
            ERRORS.append(f"forbidden derived file tracked: {posix}")


def check_absolute_paths(files: list[Path]) -> None:
    pattern = re.compile(r"[A-Za-z]:[\\/]{1,2}Users[\\/]", re.IGNORECASE)
    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern.search(text):
            ERRORS.append(f"absolute local path found: {path.as_posix()}")


def check_submission() -> None:
    path = ROOT / "submission.csv"
    if not path.exists():
        return
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["Id", "Sales"]:
            ERRORS.append(f"submission header is {reader.fieldnames}, expected ['Id', 'Sales']")
            return
        rows = 0
        ids: set[str] = set()
        for row in reader:
            rows += 1
            ids.add(row["Id"])
            try:
                value = float(row["Sales"])
            except (TypeError, ValueError):
                ERRORS.append(f"submission row {rows} has a non-numeric Sales")
                return
            if value < 0:
                ERRORS.append(f"submission row {rows} has negative Sales")
                return
            if value != value:  # NaN
                ERRORS.append(f"submission row {rows} has NaN Sales")
                return
    if rows != 41088:
        ERRORS.append(f"submission has {rows} rows, expected 41088")
    if len(ids) != rows:
        ERRORS.append("submission Id values are not unique")


def check_notebooks(files: list[Path]) -> None:
    for path in files:
        if path.suffix != ".ipynb":
            continue
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except OSError:
            continue
        if "kacpe" in text.lower():
            ERRORS.append(f"notebook contains a local user path: {path.as_posix()}")


def main() -> int:
    files = tracked_files()
    check_required()
    check_forbidden(files)
    check_absolute_paths(files)
    check_notebooks(files)
    check_submission()

    if ERRORS:
        print("Repository hygiene: FAIL")
        for error in ERRORS:
            print(f"  - {error}")
        return 1
    print(f"Repository hygiene: PASS ({len(files)} tracked files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
