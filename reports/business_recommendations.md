# Business Recommendations

Every recommendation follows the same structure:

1. **Observation** - what the data shows.
2. **Analytical conclusion** - what can and cannot be inferred.
3. **Business meaning** - what to do differently.
4. **Limitations** - what would be needed to be certain.

The recommendations are written for a category/operations team, not for a modelling audience.

---

## 1. Plan staffing around the weekly profile, not the average day

**Observation.** Monday averages 8,216 PLN per open store-day; Saturday 5,875 PLN. The gap is ~40%. Sunday is higher on average (8,225 PLN) but only 3,593 store-days are open, concentrated in high-traffic locations.

**Analytical conclusion.** Weekly seasonality is strong, stable across the whole period and statistically significant (Kruskal-Wallis p ≈ 0). It is the most reliable pattern in the data.

**Business meaning.** Staffing and delivery schedules should peak on Monday and taper towards Saturday. A flat "average day" plan over-staffs Saturday and under-staffs Monday. Sunday opening should be evaluated store by store, not chain-wide.

**Limitations.** The data does not include hours worked, wage costs or footfall by hour. The recommendation is about relative demand, not about the optimal absolute headcount.

---

## 2. Use promotions as a traffic lever, but do not claim a causal +39%

**Observation.** Promotion days average 8,228 PLN and 844 customers vs 5,929 PLN and 697 customers on non-promo days: **+38.8% sales, +21.2% traffic**, and a higher basket (9.74 vs 8.51 PLN). The store-level paired test is positive in 99.9% of 1,115 stores (mean uplift 2,299 PLN, Cohen's dz = 2.25).

**Analytical conclusion.** The association is strong, consistent and not driven by a few large stores. It is **not** a causal effect: promotions are scheduled by the retailer, often in weeks that were already expected to be strong, and the analysis ignores post-promotion dips and cross-store cannibalisation.

**Business meaning.** Promotions can be used to pull traffic and increase basket size. Before scaling a promotion, run a controlled test (matched stores, pre-registered dates) or a difference-in-differences design; without a control group, ROI cannot be estimated. The margin data needed for a true ROI calculation is not in this dataset.

**Limitations.** No cost, margin, cannibalisation or control-group data. No post-promotion window analysis in this project (a natural next step).

---

## 3. Differentiate the playbook by store format

**Observation.**

| Format | Stores | Avg sales | Avg customers | Avg basket |
|---|---:|---:|---:|---:|
| a | 602 | 6,925 | 795 | 8.71 |
| b | 17 | 10,231 | 2,022 | 5.06 |
| c | 148 | 6,933 | 815 | 8.50 |
| d | 348 | 6,822 | 606 | 11.25 |

**Analytical conclusion.** Format is associated with a different traffic/basket mix: type b is high-traffic, low-basket; type d is low-traffic, high-basket. The differences are statistically significant, but the practical value is the profile, not the p-value.

**Business meaning.** A promotion that works in type b (traffic-driven) may be wrong for type d (basket-driven). Assortment and promotion calendars should be segmented by format. Type a is the largest group and the hardest to forecast (RMSPE 0.183), so it needs the most operational attention.

**Limitations.** Format is a coarse label; store size, catchment and local competition matter more at the individual-store level. The 17 type-b stores make its averages noisy.

---

## 4. Put the volatile tail on a tighter review cycle

**Observation.** Median store-level CV is 0.264; the 90th percentile is 0.352, identifying **112 stores** in the top volatility decile. Volatility is not strongly related to store size.

**Analytical conclusion.** A single chain-level forecast error target hides a long tail of unstable stores. Some of the worst holdout errors come from stores with fewer than 47 scored days (temporary closures or late openings).

**Business meaning.** High-CV stores need wider safety stock, more frequent re-forecasting and a manual review of local events. They are also the first candidates for a store-specific model or a rule-based override.

**Limitations.** The dataset has no local event, weather or refurbishment calendar, so the causes of volatility cannot be separated.

---

## 5. Apply a bias buffer until calibration is implemented

**Observation.** The selected ensemble under-forecasts the 2015 holdout by **7.9%** (XGBoost alone: -10.8%; random forest: -6.8%). The bias is not stable across folds (-0.5%, -10.3%, -1.6%, -7.9%), so it is a regime effect, not a constant offset.

**Analytical conclusion.** The model captures the weekly shape and promotion effects but not the level shift of summer 2015 relative to 2014. A model with RMSPE 0.14 and -8% bias can still cause stock-outs.

**Business meaning.** For the next planning cycle, multiply the model forecast by a safety factor of roughly 1.05-1.08 for inventory, or hold extra safety stock at the top-volume stores. Do not treat the raw forecast as an unbiased mean. Implement a formal calibration on the most recent observed 48-day window and refresh it monthly.

**Limitations.** The factor is based on a single holdout and may over-correct if the next period behaves like fold_3 (bias ≈ 0). Calibration should be monitored, not set once.

---

## 6. Treat competition distance as a control, not a growth lever

**Observation.** Stores with a competitor within 500 m average 7,581 PLN vs ~6,700 PLN for other buckets, but the overall Spearman correlation is **-0.028 (p = 0.35)**.

**Analytical conclusion.** There is no detectable monotonic relationship between competition distance and store sales. The bucket difference is a location-mix effect: dense city centres contain both competitors and high-footfall stores.

**Business meaning.** Do not use this chart to justify opening stores closer to competitors. Competition distance belongs in the model as a control variable; site selection needs footfall, rent, catchment and cannibalisation data.

**Limitations.** Competition distance is a static snapshot; competitor openings and closures are not observed. The analysis cannot separate competition from location quality.

---

## 7. Focus forecast review on type-a stores, Saturdays and non-promo days

**Observation (holdout, selected ensemble):**

| Segment | RMSPE | Bias |
|---|---:|---:|
| Store type a | 0.143 | -8.0% |
| Store type b | 0.098 | -2.6% |
| Saturday | 0.152 | -7.5% |
| Non-promo days | 0.136 | -4.8% |
| Promo days | 0.140 | -10.1% |

**Analytical conclusion.** Errors are not uniform. The largest relative errors are in type-a stores, Saturdays and promotion days. The ensemble corrected the base level of non-promo days but diluted part of the promotion uplift, so promo days now carry the largest bias (-10.1%).

**Business meaning.** Manual review and safety stock should target type-a stores and Saturdays, and promo-day forecasts should be checked against the promotion plan. The ensemble is well calibrated on quiet days but conservative on promotion days.

**Limitations.** 45,852 scored days sound like a large sample, but they come from one 47-day window. Segment rankings may shift in another season.

---

## 8. Invest in the data that the model is missing

**Observation.** The model has no weather, local events, competitor openings, assortment changes or stock-out flags. Residual errors cluster around periods and stores where these factors are likely to matter.

**Analytical conclusion.** The remaining error is not primarily a model-capacity problem; it is an information problem. More trees or a deeper network will not recover demand drivers that are absent from the data.

**Business meaning.** The highest-return next investment is data, not modelling: daily weather by store, local event calendars, competitor openings/closures, promotional stock availability. Even a simple "stock-out flag" would prevent the model from learning lost sales as low demand.

**Limitations.** External data adds cost, licensing and pipeline complexity. The business case should be tested on a pilot region before a chain-wide rollout.

---

## Summary table

| # | Recommendation | Evidence | Confidence | Effort |
|---|---|---|---|---|
| 1 | Staff to the weekly profile | Monday +40% vs Saturday | high | low |
| 2 | Use promos as a traffic lever, test causally | +38.8% sales, +21.2% traffic | medium (association only) | medium |
| 3 | Segment playbooks by format | b vs d basket 5.06 vs 11.25 | high | medium |
| 4 | Tighten review for 112 volatile stores | CV p90 = 0.35 | high | medium |
| 5 | Apply a bias buffer / calibrate | holdout bias -7.9% | high | low |
| 6 | Treat competition as a control | rho -0.028, p 0.35 | high | none |
| 7 | Review type-a, Saturday, promo days | RMSPE 0.14-0.15; promo bias -10% | medium | low |
| 8 | Add external data | residual analysis | medium | high |

**What this project does not support:** causal ROI of promotions, the effect of opening a store near a competitor, or a claim that the forecast is unbiased. Those require experiments or data that are not in the competition dataset.
