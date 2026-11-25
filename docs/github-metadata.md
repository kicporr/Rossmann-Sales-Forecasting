# GitHub repository metadata

Use these values in **Settings → General** and **Settings → Social preview**.

## About

**Description (≤350 characters):**

> End-to-end Rossmann store sales forecasting: data quality, SQL, 46 leakage-safe features, rolling-origin validation and a 65/35 XGBoost + historical-average ensemble. Holdout RMSPE 0.1381, 39.5% better than the baseline. Power BI specification and portfolio case study included.

**Website:**

```
https://kacper-teichert.pages.dev/projekty/rossmann/
```

**Topics:**

```
data-science
forecasting
time-series
xgboost
random-forest
retail
rossmann
python
sql
sqlite
power-bi
dax
portfolio
```

## Social preview

Upload `docs/social-preview.png` (1280×640). It is the same asset as the case
study OG image and shows the holdout RMSPE, the baseline delta and a dashboard
screenshot.

## Release

Create a release from tag `v1.0.0`:

- **Title:** `v1.0.0 — Rossmann sales forecasting`
- **Body:** use the `1.0.0` section of `CHANGELOG.md`.
- Attach `submission.csv` only if you are comfortable publishing the
  predictions; the file is derived from Kaggle data, not raw data.
- Do **not** attach `data/raw`, `data/processed`, `outputs/models` or
  `dashboard/data/*.csv`.

## Branch protection (optional, after the first push)

- Require the `tests / test` check to pass before merging.
- Require a pull request for changes to `main`.
- Do not require signed commits unless you already use them.

## Repository settings

- Disable Wiki and Projects if you do not use them.
- Enable Issues if you want recruiters or collaborators to leave feedback.
- Keep the repository public; the code and documentation are MIT-licensed,
  while the Kaggle data remains subject to Kaggle's terms.
