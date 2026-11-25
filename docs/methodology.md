# Methodology

This document explains the analytical decisions behind the Rossmann forecasting project: how the problem is framed, how leakage is prevented, how models are validated, and what the results can and cannot support.

---

## 1. Problem framing

**Business problem.** Predict daily turnover for 856 drugstores over a 48-day horizon (2015-08-01 .. 2015-09-17) to support inventory, staffing and promotion planning.

**Statistical problem.** A panel of 1,017,209 store-day observations with:

* a strong weekly cycle (Sunday closures, Monday peaks),
* annual seasonality estimated from only 2.5 years,
* store heterogeneity of an order of magnitude,
* promotion and holiday effects,
* a hard out-of-time test boundary.

**Metric.** The official competition metric is RMSPE:

```
RMSPE = sqrt(mean(((y - y_hat) / y)^2))  over rows with y > 0
```

It is undefined for zero sales. Closed days are therefore a **business rule** (predict zero), not a modelling target, and are excluded from the metric. The project reports MAE, RMSE and WAPE alongside RMSPE because RMSPE over-weights small stores.

---

## 2. Data preparation

| Decision | Rationale |
|---|---|
| Keep closed days in the training table | they encode the store's weekly closure pattern and are needed for correct lag/rolling features |
| Fit the model only on open, positive-sales days | a closed day has no demand to learn; the 54 open-but-zero rows are data anomalies |
| Median-impute `CompetitionDistance` and flag it | 3 missing values; a flag preserves the uncertainty |
| Keep competition start unknown (`-1`) | inventing a date would fabricate a competition age |
| Keep Promo2 dates missing for `Promo2 = 0` | structural missingness, not a data error |
| Impute 11 missing `Open` values in test with the store mode | required to produce a complete submission; flagged |
| Left join store attributes, validate `many_to_one` | row count must not change; unmatched stores raise an error |

Raw files are never modified. The processed outputs are `data/processed/*.parquet`; the SQL copy is `data/processed/rossmann.sqlite`.

---

## 3. Leakage prevention

Leakage is the single largest risk in time-series competitions. The project enforces four rules:

1. **No future target.** Features at date `t` use sales only up to `t - 1` (one-step mode) or up to the forecast origin (direct mode).
2. **No future customers.** Customers are unknown for future days. Only a 28-day average frozen at the origin is used.
3. **Causal statistics.** Store-level summaries, lags and rolling windows are computed from the training window only. No imputation statistic is computed on validation or test data.
4. **Chronological splits.** `train_test_split` is never used. All validation is rolling-origin with a 48-day horizon.

**Automated evidence.** `tests/test_features.py` perturbs all sales after a cutoff date, rebuilds the feature matrix, and asserts that no feature before the cutoff changes. It also checks that `sales_lag_1` equals the previous calendar day's sales and that a 7-day rolling mean covers exactly the seven preceding days.

---

## 4. Forecast strategy: direct multi-horizon

A recursive strategy trains a one-step model and feeds its predictions back as lags for the next day. On this dataset it failed the stability test:

| Strategy | Holdout RMSPE (linear regression) |
|---|---:|
| One-step-ahead with actual lags (oracle) | 0.195 |
| Recursive 48-day forecast | 0.381 |

The bias grew from -3.5% to -12.8%: errors compound, and the model gradually drifts below the actual level.

The final pipeline therefore uses **direct multi-horizon features**:

* Every training row at date `t` is described by the information set at `t - 48`.
* `sales_lag_1` is sales on the origin day, 28-day rolling means end at the origin, and calendar/promotion features describe the target day.
* At prediction time, the origin is the last observed day, and the same feature vector is reused for all 48 future days, with only calendar and promotion features changing.

**Trade-off.** The model cannot react to a demand shock inside the horizon. In exchange, the forecast is stable, reproducible and leakage-free. A production system would re-run the model weekly with a shorter horizon.

---

## 5. Feature set

| Group | Count | Examples |
|---|---:|---|
| Calendar | 13 | weekday, month, week of year, day of year, sin/cos, month start/end |
| Store | 9 | type, assortment, log competition distance, competition age, Promo2 |
| Promotion | 6 | promo flag, yesterday/tomorrow promo, Promo2 active, promo share 28d |
| Holiday | 4 | school holiday, state holiday a/b/c |
| Sales history | 12 | lags 1/7/14/28/365, rolling means 7/28/90/365, rolling std 28, momentum |
| Customer history | 2 | 28-day customers, sales per customer at the origin |

`Store` ID is deliberately excluded: a tree model would memorise individual stores instead of learning transferable patterns, and the store's level is already captured by its rolling history.

**Target transform.** `log1p(Sales)`. Sales are right-skewed; the log stabilises variance and aligns the squared-error objective with a percentage-error metric.

---

## 6. Models

| Model | Role | Key settings |
|---|---|---|
| Historical average | baseline | mean by store x weekday |
| Seasonal naive | baseline | last observed week, same weekday; 4-week fallback |
| Linear regression | interpretable benchmark | median imputation, standardisation, OLS |
| Random forest | non-linear benchmark | 60 trees, depth 18, `max_samples=0.7` |
| XGBoost | production candidate | 600 trees, depth 8, lr 0.05, subsample 0.8, `lambda=2` |
| 65% XGBoost + 35% historical average | selected ensemble | weight chosen on folds 1-3 only |
| SARIMAX | single-store econometric benchmark | (1,0,1)(1,1,1,7) with promo/holiday/weekday exog |

All models share the same features, folds and evaluation code. Hyperparameters were set a priori from common tabular defaults, not tuned on the holdout.

---

## 7. Validation protocol

```
fold_1: train <= 2014-12-31   validate 2015-01-01 .. 2015-02-17
fold_2: train <= 2015-02-17   validate 2015-02-18 .. 2015-04-06
fold_3: train <= 2015-04-06   validate 2015-04-07 .. 2015-05-24
holdout: train <= 2015-06-14  validate 2015-06-15 .. 2015-07-31
```

* Expanding window, fixed 48-day horizon, identical evaluation dates for every model.
* Model selection uses the mean RMSPE of folds 1-3 only.
* The 65/35 ensemble weight is also chosen on folds 1-3; the holdout is evaluated once, after all choices are frozen.
* The holdout is evaluated once, after selection, and never used to choose hyperparameters or features.
* The final XGBoost component is refitted on all data through 2015-07-31; the historical average is recomputed and the 65/35 blend is applied to the test horizon.

**Why not k-fold?** Random folds would train on future data and evaluate on the past, producing optimistic and meaningless scores.

---

## 8. Evaluation

**Primary:** RMSPE on open days with positive sales.

**Secondary:** MAE and RMSE in PLN; WAPE (volume-weighted); mean bias and bias as a percentage of mean sales.

**Error analysis:** by store, store type, weekday, promotion, holiday and actual-sales decile. The breakdown is produced by `src/evaluation.py` and visualised in notebook 08.

**Interpretation guardrails**

* A lower RMSPE does not mean a better business forecast if the bias is large: a model can be precise on average and still systematically under-stock every store. The 65/35 ensemble reduces both RMSPE and bias relative to XGBoost alone.
* Differences of a few thousandths of RMSPE between folds are within seasonal noise; the ranking is more meaningful than the absolute gap.
* Segment-level RMSPE on small groups (store type b, Christmas holidays) is noisy and should not drive decisions.

---

## 9. Econometric analysis

* ADF tests on chain and single-store series.
* Additive decomposition with a 7-day period.
* ACF/PACF of levels and first differences.
* OLS of log sales on promotion, weekday, holidays and trend, with HC3 standard errors.
* SARIMAX(1,0,1)(1,1,1,7) for Store 1, trained and evaluated on the same holdout as the ML models.

**Findings**

* Weekly seasonality dominates the autocorrelation structure.
* OLS residuals are strongly autocorrelated (Durbin-Watson far below 2), heteroskedastic and non-normal. HC3 fixes the standard errors for heteroskedasticity but not for autocorrelation.
* SARIMAX captures the weekly shape and the promotion effect, but Ljung-Box still rejects white-noise residuals.
* A single-store model cannot borrow strength across 1,115 stores; the global gradient-boosted model is more accurate, while SARIMAX remains useful for interpretation and uncertainty.

Full numbers are in `outputs/metrics/econometrics_summary.json` and `reports/econometric_analysis.md`.

---

## 10. Limitations

1. **Summer level shift.** The holdout summer of 2015 is stronger than the 2014 summer used in training; the ensemble under-forecasts it by roughly 8%. This is documented rather than hidden, and it remains the main driver of the holdout RMSPE.
2. **No bias calibration in the submission.** A production system would estimate a calibration factor on the most recent observed 48-day window and refresh it periodically.
3. **Annual seasonality from two cycles.** The summer level estimate is fragile.
4. **No weather, local events, competitor openings or assortment changes.** These are plausible drivers not present in the data.
5. **Static competition distance.** The dataset provides one snapshot, not a time series.
6. **Closed-day rule.** An unexpected opening is forecast as zero by construction.
7. **Single holdout.** Rolling folds mitigate but do not eliminate seasonal luck.
8. **No causal claims.** Promotions, holidays and competition effects are associations; the promotion calendar is not random.

---

## 11. Reproducibility

* Python 3.12, pinned versions in `requirements.txt`.
* `random_state = 42` for every stochastic model.
* Configuration in `config/config.yaml`; no hardcoded paths in `src/`.
* One-command pipeline: `python -m src.data_preparation && python -m src.train && python -m src.predict`.
* Tests: `pytest -q`.
* Every metric in the reports is generated by code; no number is typed by hand.
