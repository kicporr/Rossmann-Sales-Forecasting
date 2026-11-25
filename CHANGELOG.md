# Changelog

All notable changes to this project are documented here.

## [1.0.0] - 2026-11-25

### Added

- Reproducible data pipeline: validation, cleaning, store join, parquet output and quality report.
- SQLite layer with 13 analytical queries using JOIN, CTE and window functions.
- 46 leakage-safe features and a direct multi-horizon forecaster for a 48-day horizon.
- Rolling-origin validation (three 48-day folds) and an untouched holdout.
- Six single models: historical average, seasonal naive, OLS, SARIMAX, random forest, XGBoost.
- 65/35 XGBoost + store-weekday historical-average ensemble, selected on folds 1-3.
- Final submission for 41,088 store-days and a model comparison report.
- Power BI specification, 30+ DAX measures, three HTML mockups and CSV exports.
- Eight executed notebooks, 17 pytest tests, EDA and econometric reports.
- Portfolio case study in Polish and English, plus home-page integration snippets.

### Results

- Holdout RMSPE: **0.1381** (ensemble), vs **0.2283** for the historical-average baseline.
- Holdout MAE: **PLN 827**; WAPE **11.6%**; bias **-7.9%**.
- Mean RMSPE on selection folds 1-3: **0.1876**.

### Known limitations

- The model under-forecasts the 2015 summer level by 7.9%.
- No external regressors (weather, footfall, local events).
- No `.pbix` file: Power BI Desktop was not available.
- Submission was generated but not uploaded to Kaggle.

[1.0.0]: https://github.com/kicporr/rossmann-sales-forecasting/releases/tag/v1.0.0
