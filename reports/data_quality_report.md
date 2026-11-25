# Data Quality Report

**Pipeline stage:** `python -m src.data_preparation`  
**Machine-readable output:** `outputs/metrics/data_quality.json`  
**Processed files:** `data/processed/train_clean.parquet`, `test_clean.parquet`, `store_clean.parquet`

---

## 1. Source inventory

| File | Rows | Columns | Grain | Modified? |
|---|---:|---:|---|---|
| `train.csv` | 1,017,209 | 9 | store x day | no |
| `test.csv` | 41,088 | 8 | store x day | no |
| `store.csv` | 1,115 | 10 | store | no |
| `sample_submission.csv` | 41,088 | 2 | Id | no |

All raw files are copied to `data/raw/` and never edited. Every transformation writes a new artefact.

---

## 2. Structural checks

| Check | Result | Detail |
|---|---|---|
| Unique (Store, Date) in train | PASS | 0 duplicates |
| Unique (Store, Date) in test | PASS | 0 duplicates |
| Unique Store in store.csv | PASS | 1,115 rows, 1,115 stores |
| All test stores exist in train | PASS | 0 cold-start stores |
| Train/test date continuity | PASS | test starts 2015-08-01, one day after train ends |
| Test rows per store | PASS | 48 rows for each of 856 stores |
| Submission Id order | PASS | identical to `test.csv` |
| Negative sales | PASS | 0 rows |
| Row count preserved by JOIN | PASS | 1,017,209 -> 1,017,209; 41,088 -> 41,088 |

---

## 3. Missing values

### 3.1 Training and test transactions

| Column | Train missing | Test missing | Decision |
|---|---:|---:|---|
| All columns except `Open` | 0 | 0 | nothing to impute |
| `Open` | 0 | 11 | store modal state; `OpenImputed = 1` |

The 11 test rows are the only genuine transaction-level gap. They are imputed because a submission must cover every Id. The flag allows a reviewer to exclude them from any sensitivity analysis.

### 3.2 Store attributes

| Column | Missing | Nature | Decision |
|---|---:|---|---|
| `CompetitionDistance` | 3 | unknown | median (2,325 m) + `CompetitionDistanceMissing = 1` |
| `CompetitionOpenSinceMonth` | 354 | unknown / no competition | `CompetitionOpenSince = NaT`, `HasCompetitionStart = 0`, `CompetitionOpenMonths = -1` |
| `CompetitionOpenSinceYear` | 354 | same | same |
| `Promo2SinceWeek` | 544 | structural: `Promo2 = 0` | `Promo2Start = NaT`, `Promo2StartKnown = 0` |
| `Promo2SinceYear` | 544 | same | same |
| `PromoInterval` | 544 | same | `"None"`, `Promo2MonthsCsv = ""` |

**Principle:** no date is invented. A missing competition start is not the same as "competition opened in 1970"; a missing Promo2 start for a non-participant is not a data error.

---

## 4. Target anomalies

| Anomaly | Count | Treatment |
|---|---:|---|
| Closed store-days (`Open = 0`) | 172,817 | kept in the panel; excluded from model fitting; predicted as zero |
| Zero sales on closed days | 172,817 | consistent with closure |
| Zero sales while open | 54 | excluded from fitting and RMSPE; flagged `SalesZeroWhileOpen` |
| Sales above 40,000 PLN | 1 | kept; it is a real large-store day, not an error |

The 54 open-but-zero rows are 0.005% of the open days. Removing them from the metric avoids a division by zero and an infinite penalty; keeping them in the raw data keeps the audit trail.

---

## 5. Logical consistency

| Rule | Result |
|---|---|
| `Sales = 0` when `Open = 0` | holds for all closed rows |
| `Customers = 0` when `Open = 0` | holds for all closed rows |
| `StateHoliday` in {0, a, b, c} | holds after normalisation |
| `Promo2 = 0` implies no Promo2 start date | holds by construction |
| `CompetitionOpenSince <=` observation date | holds after clipping; future dates would be a data error |
| `Promo2Start <=` observation date where known | holds for the 571 participating stores |

---

## 6. Class balance and coverage

| Dimension | Distribution |
|---|---|
| Store type | a 602, d 348, c 148, b 17 |
| Assortment | a 593, c 513, b 9 |
| Promo2 participants | 571 of 1,115 |
| State holidays (open days) | regular 843,482; a 694; b 145; c 71 |
| School holidays | 181,721 of 1,017,209 rows |
| Stores in test | 856 of 1,115 |

The 259 stores absent from the test set were closed for renovation or permanently. They remain in training because they provide useful history for the global model, but they cannot appear in the submission.

---

## 7. Accepted risks

1. **No causal identification.** Promotion assignment is endogenous; all promotion statements are descriptive.
2. **Annual seasonality from two cycles.** The summer level is the least reliable part of the model.
3. **Static competition data.** No competitor openings/closures over time.
4. **Test `Open` imputation.** 11 rows depend on a modal rule; flagged.
5. **Raw data licence.** The Kaggle competition terms prohibit redistribution; raw files are therefore gitignored.

---

## 8. Reproducibility

* Cleaning is deterministic (no sampling, no random imputation).
* The pipeline asserts row counts and key uniqueness at every run.
* The JSON report is regenerated on every run; the table below is the current run's machine-readable gate.

| Check | Passed |
|---|---|
| `row_count_preserved_by_join` | yes |
| `unique_store_date_train` | yes |
| `unique_store_date_test` | yes |
| `no_missing_store_type` | yes |
| `non_negative_sales` | yes |
| `date_ranges_contiguous` | yes |
| `all_test_stores_in_train` | yes |
| `submission_rows_match_test` | yes |

**Overall:** PASS.
