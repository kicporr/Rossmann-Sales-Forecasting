# SQL Layer Documentation

## 1. Purpose

The SQL layer shows that the same analysis can be reproduced in a relational engine, independently of pandas. It is built from the processed parquet files and runs on SQLite (window functions require SQLite 3.25+).

## 2. Schema

```text
stores(Store PK, StoreType, Assortment, CompetitionDistance, CompetitionOpenSinceMonth, CompetitionOpenSinceYear, Promo2, Promo2SinceWeek, Promo2SinceYear, PromoInterval)
train_sales(Store, Date, DayOfWeek, Sales, Customers, Open, Promo, StateHoliday, SchoolHoliday, PK(Store, Date), FK Store -> stores)
test_sales(Id PK, Store, Date, DayOfWeek, Open, Promo, StateHoliday, SchoolHoliday, FK Store -> stores)
```

DDL: `sql/create_tables.sql`. Build and run: `python sql/build_database.py`.

## 3. Query catalogue

| # | Query | Technique | Purpose |
|---|---|---|---|
| 1 | `avg_sales_by_store` | JOIN, GROUP BY, RANK, SUM OVER | store ranking and share of chain sales |
| 2 | `sales_by_day_of_week` | GROUP BY | weekly seasonality and basket |
| 3 | `monthly_sales_trend` | CTE, LAG | monthly trend and MoM growth |
| 4 | `promo_effect` | GROUP BY, NULLIF | promo vs non-promo sales and traffic |
| 5 | `sales_by_store_type` | JOIN, GROUP BY | format comparison |
| 6 | `sales_by_assortment` | JOIN, GROUP BY | assortment comparison |
| 7 | `holiday_effect` | GROUP BY | holiday trading |
| 8 | `competition_distance_buckets` | CTE, CASE, JOIN | competition proximity |
| 9 | `top_bottom_stores_by_growth` | CTE, conditional aggregation | 90-day momentum leaders |
| 10 | `worst_momentum_stores` | CTE, conditional aggregation | 90-day momentum laggards |
| 11 | `promo2_effect` | JOIN, GROUP BY | loyalty programme comparison |
| 12 | `store_running_average` | window frame (ROWS BETWEEN) | 28-day smoothed series |
| 13 | `sales_per_customer_history` | JOIN, GROUP BY, NULLIF | basket evolution by format |

All 13 queries are executed by the build script; result CSVs are in `outputs/metrics/sql/` and a readable digest is in `outputs/metrics/sql_results.md`.

## 4. Example results

### Promotion effect

| period   |   open_store_days |   avg_sales |   avg_customers |   avg_basket |
|:---------|------------------:|------------:|----------------:|-------------:|
| Promo    |            376896 |     8228.28 |          844.43 |        10.18 |
| No promo |            467496 |     5929.41 |          696.86 |         8.94 |

### Monthly trend (head)

| month   |   total_sales |   total_customers |   active_stores |   previous_month_sales |   mom_growth_pct |
|:--------|--------------:|------------------:|----------------:|-----------------------:|-----------------:|
| 2013-01 |     180132207 |          20380423 |            1112 |          nan           |           nan    |
| 2013-02 |     171534275 |          19244468 |            1112 |            1.80132e+08 |            -4.77 |
| 2013-03 |     201180369 |          21969462 |            1112 |            1.71534e+08 |            17.28 |
| 2013-04 |     183431432 |          20882365 |            1113 |            2.0118e+08  |            -8.82 |
| 2013-05 |     185411063 |          20723886 |            1113 |            1.83431e+08 |             1.08 |
| 2013-06 |     180702351 |          20473046 |            1113 |            1.85411e+08 |            -2.54 |

### Top stores by average daily sales

|   Store | StoreType   |   avg_daily_sales |   total_sales |   open_days |   sales_rank |   pct_of_chain_sales |
|--------:|:------------|------------------:|--------------:|------------:|-------------:|---------------------:|
|     817 | a           |           21757.5 |      17057867 |         784 |            1 |                 0.29 |
|     262 | b           |           20718.5 |      19516842 |         942 |            2 |                 0.33 |
|    1114 | a           |           20666.6 |      16202585 |         784 |            3 |                 0.28 |
|     251 | a           |           19123.1 |      14896870 |         779 |            4 |                 0.25 |
|     842 | d           |           18574.8 |      11553523 |         622 |            5 |                 0.2  |

## 5. Design notes

* `Date` is stored as ISO-8601 text so SQLite date functions (`strftime`, `date(..., '-90 days')`) work without extensions.
* Closed days stay in the fact table; every sales-per-day query filters `Open = 1`.
* `NULLIF(Customers, 0)` prevents division by zero in basket calculations.
* `RANK()` is used for store rankings, `LAG()` for month-over-month growth and `SUM() OVER ()` for revenue share.
* The schema is intentionally a star: one fact table, one store dimension, one test table. It is small enough to rebuild in seconds and large enough to demonstrate real SQL.

## 6. Verified row counts

| Table | Rows |
|---|---:|
| stores | 1,115 |
| train_sales | 1,017,209 |
| test_sales | 41,088 |