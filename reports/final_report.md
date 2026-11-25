# Final Project Report

**Project:** Rossmann Store Sales Forecasting — Data Analytics & Predictive Modeling  
**Status:** all analytical stages completed; dashboard delivered as a fully specified, reproducible Power BI package (no PBIX); submission generated but not uploaded.  
**Date of run:** 2026-11-25  
**Environment:** Windows 11, Python 3.12.7, 6 CPU cores, 16 GB RAM, no Power BI Desktop, no LibreOffice.

---

## 1. Stage-by-stage status

| Stage | Status | Main artefact |
|---|---|---|
| I. Data understanding | completed | `notebooks/01_data_understanding.ipynb`, `reports/data_quality_report.md` |
| II. Data cleaning + SQL | completed | `src/data_preparation.py`, `data/processed/*.parquet`, `rossmann.sqlite`, 13 queries |
| III. EDA | completed | `reports/eda_report.md`, `notebooks/03_exploratory_analysis.ipynb`, 14 figures |
| IV. Econometrics | completed | `reports/econometric_analysis.md`, `notebooks/04_econometric_analysis.ipynb`, ADF/ACF/OLS/SARIMAX |
| V. Feature engineering | completed | `src/features.py`, 46 leakage-safe features, `tests/test_features.py` |
| VI. Modelling | completed | `src/train.py`, 6 single models + 65/35 ensemble, 3 rolling folds + holdout |
| VII. Evaluation | completed | `reports/model_comparison.md`, `notebooks/08_model_evaluation.ipynb` |
| VIII. Forecasting | completed | `outputs/predictions/submission.csv` (41,088 rows), not uploaded |
| IX. Power BI | specification + mockups delivered; **no PBIX** | `dashboard/dashboard_specification.md`, `dax_measures.md`, 3 mockups, CSV export |
| X. Business recommendations | completed | `reports/business_recommendations.md` |
| XI. Portfolio | completed | `README.md`, `docs/cv_description.md`, `docs/interview_questions.md` |

---

## 2. Actual results

### Validation (RMSPE, open days with positive sales)

| Model | Fold 1 | Fold 2 | Fold 3 | Mean (selection) | Holdout |
|---|---:|---:|---:|---:|---:|
| **Ensemble 65/35** | **0.2303** | **0.1772** | **0.1553** | **0.1876** | **0.1381** |
| XGBoost | 0.2546 | 0.1911 | 0.1744 | 0.2067 | 0.1714 |
| Random forest | 0.2827 | 0.2041 | 0.1742 | 0.2203 | **0.1700** |
| Historical average | 0.2625 | 0.2616 | 0.2189 | 0.2477 | 0.2283 |
| Linear regression | 0.3500 | 0.2716 | 0.2380 | 0.2866 | 0.2209 |
| Seasonal naive | 0.3966 | 0.3502 | 0.4967 | 0.4145 | 0.2304 |

**Selected model:** 65% XGBoost + 35% historical store-weekday average, chosen on folds 1-3 only.  
**Holdout:** RMSPE 0.1381, MAE 827 PLN, WAPE 11.6%, bias -7.9%.  
**Baseline improvement:** -24.3% RMSPE on selection folds, -39.5% on the holdout.  
**Econometric benchmark:** SARIMAX Store 1 RMSPE 0.1234 on its 41 scored holdout days.

### Submission

| Property | Value |
|---|---|
| Rows | 41,088 |
| Unique Ids | 41,088 |
| Id order matches sample | yes |
| Min / max sales | 0 / 29,260 PLN |
| Mean / median sales | 5,642 / 5,760 PLN |
| Zero predictions | 14.6% (closed days) |
| Model | 65% XGBoost (600 trees, direct 48-day features) + 35% historical average |

The file exists at `outputs/predictions/submission.csv` and `submission.csv` (project root). It has **not** been sent to Kaggle.

---

## 3. Quality control performed

| Check | Result |
|---|---|
| Data quality checks (8) | all passed; `outputs/metrics/data_quality.json` |
| Row count preserved by JOIN | 1,017,209 and 41,088 unchanged |
| Duplicate store-day keys | 0 in train and test |
| Leakage perturbation test | passed: future sales do not alter past features |
| Lag correctness test | `sales_lag_1` equals previous calendar day |
| Rolling-window test | 7-day mean covers exactly the prior 7 days |
| Direct-origin test | 48-day features anchored at `t-48` |
| Closed-day handling | 0 predictions for closed stores; RMSPE excludes them |
| Submission validation | 41,088 rows, Id order, no NaN, no negatives |
| Pytest suite | **17 passed** |
| Notebook execution | all 8 executed without errors, outputs embedded |

---

## 4. Limitations and accepted risks

1. **Bias -7.9% on the holdout.** The ensemble still under-forecasts the 2015 summer level. The submission is deliberately uncalibrated; calibration is the first production task.
2. **No causal inference.** Promotion effects are associations; the promotion calendar is endogenous.
3. **Annual seasonality from two cycles.** The summer level estimate is fragile.
4. **No external data.** Weather, local events, competitor openings and stock-outs are absent.
5. **Single holdout.** Rolling folds reduce, but do not eliminate, seasonal luck.
6. **No PBIX.** Power BI Desktop is not installed. A complete specification, DAX layer, CSV export and mockups are provided instead of a fabricated binary.
7. **Submission not uploaded.** Kaggle requires the user's credentials and explicit authorisation.
8. **Raw data licence.** Kaggle files are not redistributed; they are gitignored.

---

## 5. Blockers requiring user action

| Blocker | What is needed |
|---|---|
| Kaggle leaderboard submission | user's Kaggle API token and explicit approval; commands are in the README / project notes |
| Real `.pbix` file | Power BI Desktop (Windows); import `dashboard/data/*.csv`, follow the specification |
| Raw data in a fresh clone | download the four competition files into `data/raw/` (licence restriction) |

No analytical blocker remains.

---

## 6. Acceptance criteria (master prompt section 18)

| Criterion | Met? | Evidence |
|---|---|---|
| Reproducible data pipeline | yes | `src/data_preparation.py`, config, tests |
| EDA report | yes | `reports/eda_report.md`, 14 figures |
| At least one correct baseline | yes | historical average, seasonal naive |
| At least one correct forecasting model | yes | XGBoost, RF, LR, SARIMAX, 65/35 ensemble |
| Rigorous time validation | yes | 3 rolling folds + holdout, no random split |
| Metrics compared on the same data | yes | `validation_results.json` |
| Final predictions file | yes | `submission.csv`, 41,088 rows |
| SQL + documentation | yes | schema, 13 queries, results |
| Dashboard or full specification | yes | specification, DAX, mockups, export |
| Business interpretation | yes | `business_recommendations.md` |
| README | yes | `README.md` |
| Run documentation | yes | README + `docs/methodology.md` |
| CV description | yes | `docs/cv_description.md` (PL + EN) |
| Learning guide | yes | `docs/learning_guide.md` |

---

## 7. Recommended next steps

1. Calibrate the forecast on the most recent 48-day window and monitor bias monthly.
2. Build the PBIX from the specification; validate DAX RMSPE against `validation_results.json`.
3. Add weather and local-event data; test whether they reduce the residual of type-a stores on Saturdays.
4. Try hierarchical reconciliation (store → region → chain).
5. Upload one submission to Kaggle **only after** the user authorises it; record the public score separately from the internal holdout.
6. Add experiment tracking (MLflow/DVC) before the next modelling iteration.
