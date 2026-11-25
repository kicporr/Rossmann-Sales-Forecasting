-- ============================================================================
-- Rossmann Store Sales - analytical queries
-- Each query is preceded by a `-- name:` marker used by the Python runner.
-- Only open days are used for sales-per-day metrics; closed days are retained
-- in the fact table because they are informative about opening patterns.
-- ============================================================================

-- name: avg_sales_by_store
-- Average daily sales per store (open days), with a rank and share of chain sales.
WITH store_stats AS (
    SELECT
        s.Store,
        st.StoreType,
        ROUND(AVG(s.Sales), 2)              AS avg_daily_sales,
        SUM(s.Sales)                        AS total_sales,
        COUNT(*)                            AS open_days
    FROM train_sales AS s
    JOIN stores AS st ON st.Store = s.Store
    WHERE s.Open = 1
    GROUP BY s.Store, st.StoreType
)
SELECT
    Store,
    StoreType,
    avg_daily_sales,
    total_sales,
    open_days,
    RANK() OVER (ORDER BY avg_daily_sales DESC)                       AS sales_rank,
    ROUND(100.0 * total_sales / SUM(total_sales) OVER (), 2)          AS pct_of_chain_sales
FROM store_stats
ORDER BY sales_rank
LIMIT 20;

-- name: sales_by_day_of_week
-- Weekly seasonality: average sales and customers by weekday (open days only).
SELECT
    DayOfWeek,
    COUNT(*)                                AS open_days,
    ROUND(AVG(Sales), 2)                    AS avg_sales,
    ROUND(AVG(Customers), 2)                AS avg_customers,
    ROUND(AVG(1.0 * Sales / NULLIF(Customers, 0)), 2) AS avg_sales_per_customer
FROM train_sales
WHERE Open = 1
GROUP BY DayOfWeek
ORDER BY DayOfWeek;

-- name: monthly_sales_trend
-- Monthly chain sales with month-over-month growth (window function LAG).
WITH monthly AS (
    SELECT
        strftime('%Y-%m', Date) AS month,
        SUM(Sales)              AS total_sales,
        SUM(Customers)          AS total_customers,
        COUNT(DISTINCT Store)   AS active_stores
    FROM train_sales
    WHERE Open = 1
    GROUP BY month
)
SELECT
    month,
    total_sales,
    total_customers,
    active_stores,
    LAG(total_sales) OVER (ORDER BY month) AS previous_month_sales,
    ROUND(100.0 * (total_sales - LAG(total_sales) OVER (ORDER BY month))
          / NULLIF(LAG(total_sales) OVER (ORDER BY month), 0), 2) AS mom_growth_pct
FROM monthly
ORDER BY month;

-- name: promo_effect
-- Promotion vs non-promotion: sales, traffic, basket value and promo share.
SELECT
    CASE WHEN Promo = 1 THEN 'Promo' ELSE 'No promo' END AS period,
    COUNT(*)                                AS open_store_days,
    ROUND(AVG(Sales), 2)                    AS avg_sales,
    ROUND(AVG(Customers), 2)                AS avg_customers,
    ROUND(AVG(1.0 * Sales / NULLIF(Customers, 0)), 2) AS avg_basket
FROM train_sales
WHERE Open = 1
GROUP BY Promo
ORDER BY Promo DESC;

-- name: sales_by_store_type
-- Chain performance by store format (sales, traffic, basket).
SELECT
    st.StoreType,
    COUNT(DISTINCT s.Store)                 AS stores,
    ROUND(AVG(s.Sales), 2)                  AS avg_sales,
    ROUND(AVG(s.Customers), 2)              AS avg_customers,
    ROUND(AVG(1.0 * s.Sales / NULLIF(s.Customers, 0)), 2) AS avg_basket
FROM train_sales AS s
JOIN stores AS st ON st.Store = s.Store
WHERE s.Open = 1
GROUP BY st.StoreType
ORDER BY avg_sales DESC;

-- name: sales_by_assortment
-- Assortment comparison, including average competition distance.
SELECT
    st.Assortment,
    COUNT(DISTINCT s.Store)                 AS stores,
    ROUND(AVG(s.Sales), 2)                  AS avg_sales,
    ROUND(AVG(st.CompetitionDistance), 0)   AS avg_competition_distance
FROM train_sales AS s
JOIN stores AS st ON st.Store = s.Store
WHERE s.Open = 1
GROUP BY st.Assortment
ORDER BY avg_sales DESC;

-- name: holiday_effect
-- Sales around state holidays.  `a` = public holiday, `b` = Easter, `c` = Christmas.
SELECT
    StateHoliday,
    COUNT(*)                                AS open_store_days,
    ROUND(AVG(Sales), 2)                    AS avg_sales,
    ROUND(AVG(Customers), 2)                AS avg_customers
FROM train_sales
WHERE Open = 1
GROUP BY StateHoliday
ORDER BY StateHoliday;

-- name: competition_distance_buckets
-- Stores grouped by distance to the nearest competitor.
WITH bucketed AS (
    SELECT
        s.Store,
        s.Sales,
        CASE
            WHEN st.CompetitionDistance IS NULL THEN 'unknown'
            WHEN st.CompetitionDistance < 500  THEN '< 500 m'
            WHEN st.CompetitionDistance < 1000 THEN '500-999 m'
            WHEN st.CompetitionDistance < 2500 THEN '1-2.5 km'
            WHEN st.CompetitionDistance < 5000 THEN '2.5-5 km'
            ELSE '>= 5 km'
        END AS distance_bucket
    FROM train_sales AS s
    JOIN stores AS st ON st.Store = s.Store
    WHERE s.Open = 1
)
SELECT
    distance_bucket,
    COUNT(DISTINCT Store)                   AS stores,
    COUNT(*)                                AS open_store_days,
    ROUND(AVG(Sales), 2)                    AS avg_sales
FROM bucketed
GROUP BY distance_bucket
ORDER BY avg_sales DESC;

-- name: top_bottom_stores_by_growth
-- Stores with the strongest and weakest recent momentum:
-- last 90 days vs the preceding 90 days (CTE + conditional aggregation).
WITH bounds AS (
    SELECT MAX(Date) AS max_date FROM train_sales
),
periods AS (
    SELECT
        s.Store,
        SUM(CASE WHEN s.Date > date(b.max_date, '-90 days') THEN s.Sales ELSE 0 END) AS last_90d,
        SUM(CASE WHEN s.Date <= date(b.max_date, '-90 days')
                  AND s.Date > date(b.max_date, '-180 days') THEN s.Sales ELSE 0 END) AS previous_90d
    FROM train_sales AS s
    CROSS JOIN bounds AS b
    WHERE s.Open = 1
    GROUP BY s.Store
)
SELECT
    Store,
    last_90d,
    previous_90d,
    ROUND(100.0 * (last_90d - previous_90d) / NULLIF(previous_90d, 0), 2) AS growth_pct
FROM periods
WHERE previous_90d > 0
ORDER BY growth_pct DESC
LIMIT 10;

-- name: worst_momentum_stores
-- The same momentum metric, weakest stores first.
WITH bounds AS (
    SELECT MAX(Date) AS max_date FROM train_sales
),
periods AS (
    SELECT
        s.Store,
        SUM(CASE WHEN s.Date > date(b.max_date, '-90 days') THEN s.Sales ELSE 0 END) AS last_90d,
        SUM(CASE WHEN s.Date <= date(b.max_date, '-90 days')
                  AND s.Date > date(b.max_date, '-180 days') THEN s.Sales ELSE 0 END) AS previous_90d
    FROM train_sales AS s
    CROSS JOIN bounds AS b
    WHERE s.Open = 1
    GROUP BY s.Store
)
SELECT
    Store,
    last_90d,
    previous_90d,
    ROUND(100.0 * (last_90d - previous_90d) / NULLIF(previous_90d, 0), 2) AS growth_pct
FROM periods
WHERE previous_90d > 0
ORDER BY growth_pct ASC
LIMIT 10;

-- name: promo2_effect
-- Stores participating in the Promo2 programme vs non-participants.
SELECT
    CASE WHEN st.Promo2 = 1 THEN 'Promo2 store' ELSE 'Non-Promo2 store' END AS promo2_group,
    COUNT(DISTINCT s.Store)                 AS stores,
    ROUND(AVG(s.Sales), 2)                  AS avg_sales,
    ROUND(AVG(s.Customers), 2)              AS avg_customers
FROM train_sales AS s
JOIN stores AS st ON st.Store = s.Store
WHERE s.Open = 1
GROUP BY st.Promo2
ORDER BY st.Promo2 DESC;

-- name: store_running_average
-- 28-day running average of sales for one store (window frame), illustrating
-- how a BI layer can smooth daily noise without leaking future data.
WITH daily AS (
    SELECT Date, Sales
    FROM train_sales
    WHERE Store = 1 AND Open = 1
)
SELECT
    Date,
    Sales,
    ROUND(AVG(Sales) OVER (
        ORDER BY Date
        ROWS BETWEEN 27 PRECEDING AND CURRENT ROW
    ), 2) AS rolling_28d_avg
FROM daily
ORDER BY Date
LIMIT 60;

-- name: sales_per_customer_history
-- Historical sales per customer by year and store type.
SELECT
    strftime('%Y', s.Date) AS year,
    st.StoreType,
    ROUND(AVG(1.0 * s.Sales / NULLIF(s.Customers, 0)), 2) AS avg_sales_per_customer,
    COUNT(*) AS open_store_days
FROM train_sales AS s
JOIN stores AS st ON st.Store = s.Store
WHERE s.Open = 1 AND s.Customers > 0
GROUP BY year, st.StoreType
ORDER BY year, st.StoreType;
