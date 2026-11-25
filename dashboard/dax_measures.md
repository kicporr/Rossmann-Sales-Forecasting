# Power BI DAX Measures

All measures assume the model and relationships described in `dashboard_specification.md`.  
`DimDate` is marked as the date table; `FactSales` is filtered to `Open = 1` only where the measure is explicitly about trading days.

---

## 1. Core sales measures

```dax
Total Sales = SUM ( FactSales[Sales] )
```
Sum of turnover in PLN. Includes zero-sales closed days, which contribute nothing.

```dax
Open Store Days =
CALCULATE ( COUNTROWS ( FactSales ), FactSales[Open] = 1 )
```
Number of trading store-days. This is the correct denominator for average daily sales.

```dax
Avg Daily Sales = DIVIDE ( [Total Sales], [Open Store Days] )
```
Average sales per open store-day. Expected value on the full history: **6,955.51 PLN**.

```dax
Total Customers = SUM ( FactSales[Customers] )
```

```dax
Sales per Customer = DIVIDE ( [Total Sales], [Total Customers] )
```
Historical basket value; expected full-history value **9.12 PLN**. It is a historical KPI only - future customer counts are unknown.

```dax
Active Stores =
CALCULATE ( DISTINCTCOUNT ( FactSales[Store] ), FactSales[Open] = 1 )
```

```dax
Sales YTD = TOTALYTD ( [Total Sales], DimDate[Date] )
Sales MTD = TOTALMTD ( [Total Sales], DimDate[Date] )
```

```dax
Sales LY = CALCULATE ( [Total Sales], SAMEPERIODLASTYEAR ( DimDate[Date] ) )
```

```dax
Sales Growth YoY % = DIVIDE ( [Total Sales] - [Sales LY], [Sales LY] )
```
Format as percentage. Guard against a blank prior year (new stores) - `DIVIDE` returns blank.

```dax
Sales Rolling 28D =
CALCULATE (
    [Total Sales],
    DATESINPERIOD ( DimDate[Date], MAX ( DimDate[Date] ), -28, DAY )
)
```
Smoothed trend line for Page 1.

```dax
Store Sales Rank = RANKX ( ALLSELECTED ( DimStore[Store] ), [Total Sales] )
```
Respects slicers on store type; use `ALL` instead of `ALLSELECTED` for a fixed ranking.

```dax
% of Chain Sales = DIVIDE ( [Total Sales], CALCULATE ( [Total Sales], ALLSELECTED ( DimStore ) ) )
```
Format as percentage; used for the concentration insight ("top 10% of stores = 18% of sales").

```dax
Store CV =
DIVIDE (
    CALCULATE ( STDEV.P ( FactSales[Sales] ), FactSales[Open] = 1 ),
    CALCULATE ( AVERAGE ( FactSales[Sales] ), FactSales[Open] = 1 )
)
```
Coefficient of variation at the store level. Requires a store context (matrix or tooltip).

```dax
High Volatility Stores =
COUNTROWS ( FILTER ( VALUES ( DimStore[Store] ), [Store CV] > 0.3 ) )
```
Operational flag: stores above the 90th percentile of volatility.

---

## 2. Promotion and holiday measures

```dax
Promo Store Days =
CALCULATE ( COUNTROWS ( FactSales ), FactSales[Promo] = 1, FactSales[Open] = 1 )
```

```dax
Promo Sales Share =
DIVIDE ( CALCULATE ( [Total Sales], FactSales[Promo] = 1 ), [Total Sales] )
```

```dax
Avg Sales Promo = CALCULATE ( [Avg Daily Sales], FactSales[Promo] = 1 )
Avg Sales Non Promo = CALCULATE ( [Avg Daily Sales], FactSales[Promo] = 0 )
```

```dax
Promo Uplift % = DIVIDE ( [Avg Sales Promo] - [Avg Sales Non Promo], [Avg Sales Non Promo] )
```
Descriptive association, not a causal effect. Expected full-history value: **+38.8%** on average sales.

```dax
Promo Uplift by Store Type =
CALCULATE (
    DIVIDE ( [Avg Sales Promo] - [Avg Sales Non Promo], [Avg Sales Non Promo] ),
    ALLEXCEPT ( DimStore, DimStore[StoreType] )
)
```

```dax
Holiday Sales = CALCULATE ( [Total Sales], FactSales[StateHoliday] <> "0" )
Holiday Share = DIVIDE ( [Holiday Sales], [Total Sales] )
```

---

## 3. Competition

Calculated column in `DimStore` (not a measure):

```dax
Competition Band =
SWITCH (
    TRUE (),
    DimStore[CompetitionDistance] = BLANK (), "Unknown",
    DimStore[CompetitionDistance] < 500, "<500 m",
    DimStore[CompetitionDistance] < 1000, "500-999 m",
    DimStore[CompetitionDistance] < 2500, "1-2.5 km",
    DimStore[CompetitionDistance] < 5000, "2.5-5 km",
    ">=5 km"
)
```

```dax
Avg Sales by Competition Band =
CALCULATE ( [Avg Daily Sales], ALLEXCEPT ( DimStore, DimStore[Competition Band] ) )
```

```dax
Competition Correlation =
VAR StoreTable =
    ADDCOLUMNS (
        VALUES ( DimStore[Store] ),
        "@avg", CALCULATE ( [Avg Daily Sales] ),
        "@dist", CALCULATE ( MAX ( DimStore[CompetitionDistance] ) )
    )
RETURN
    CORRELX ( FILTER ( StoreTable, NOT ISBLANK ( [@dist] ) ), [@dist], [@avg] )
```
Power BI's `CORRELX` mirrors the Spearman/Pearson diagnostic in the Python report (the Python report uses Spearman because the relationship is monotonic rather than linear).

---

## 4. Forecast accuracy measures

`Forecast` contains one row per store-day-model with `Sales` (actual) and `Prediction`. Closed days are included with `Prediction = 0` but excluded from the percentage metrics.

```dax
Forecast Sales = SUM ( Forecast[Prediction] )
Actual Sales = SUM ( Forecast[Sales] )
Forecast Error = [Forecast Sales] - [Actual Sales]
Forecast Bias % = DIVIDE ( [Forecast Error], [Actual Sales] )
```

```dax
Forecast Absolute Error =
SUMX ( FILTER ( Forecast, Forecast[Sales] > 0 ), ABS ( Forecast[Prediction] - Forecast[Sales] ) )
```

```dax
Scored Rows = CALCULATE ( COUNTROWS ( Forecast ), Forecast[Sales] > 0 )
```

```dax
MAE = DIVIDE ( [Forecast Absolute Error], [Scored Rows] )
```

```dax
WAPE = DIVIDE ( [Forecast Absolute Error], [Actual Sales] )
Forecast Accuracy % = 1 - [WAPE]
```

```dax
RMSPE =
VAR Scored = FILTER ( Forecast, Forecast[Sales] > 0 )
VAR N = COUNTROWS ( Scored )
VAR Squared =
    SUMX (
        Scored,
        ( ( Forecast[Sales] - Forecast[Prediction] ) / Forecast[Sales] ) ^ 2
    )
RETURN
    IF ( N = 0, BLANK (), SQRT ( DIVIDE ( Squared, N ) ) )
```
This is the official competition metric. Expected holdout value for the selected ensemble: **≈0.14** (see `outputs/metrics/validation_results.json` for the exact number after a run).

```dax
Forecast Coverage =
DIVIDE ( COUNTROWS ( FILTER ( Forecast, Forecast[Sales] > 0 && NOT ISBLANK ( Forecast[Prediction] ) ) ), [Scored Rows] )
```
Should be 100%; a value below 1 means the submission pipeline missed rows.

```dax
Best Model by RMSPE =
VAR Ranking =
    ADDCOLUMNS (
        VALUES ( Forecast[model] ),
        "@rmspe", CALCULATE ( [RMSPE] )
    )
RETURN
    FIRSTNONBLANK ( TOPN ( 1, Ranking, [@rmspe], ASC ), 1 )
```

```dax
RMSPE vs Best Model =
DIVIDE ( [RMSPE], CALCULATE ( [RMSPE], Forecast[model] = [Best Model by RMSPE] ) ) - 1
```

---

## 5. Segment error analysis

```dax
RMSPE by Store Type =
CALCULATE ( [RMSPE], ALLEXCEPT ( DimStore, DimStore[StoreType] ) )
```

```dax
RMSPE by Weekday =
CALCULATE ( [RMSPE], ALLEXCEPT ( DimDate, DimDate[DayName] ) )
```

```dax
RMSPE by Promo =
CALCULATE ( [RMSPE], ALLEXCEPT ( FactSales, FactSales[Promo] ) )
```
`Promo` is a fact column, so it must be surfaced through a slicer or a matrix on `FactSales[Promo]`; alternatively add a disconnected `PromoFlag` table with values 0/1 and a measure using `TREATAS`.

```dax
Worst Store-Day Error =
MAXX (
    TOPN (
        1,
        FILTER ( Forecast, Forecast[Sales] > 0 ),
        ABS ( Forecast[Prediction] - Forecast[Sales] ) / Forecast[Sales],
        DESC
    ),
    ABS ( Forecast[Prediction] - Forecast[Sales] ) / Forecast[Sales]
)
```

---

## 6. Validation checklist

| Measure | Expected value | Source |
|---|---:|---|
| Total Sales | 5,873,180,623 | `eda_summary.json` |
| Avg Daily Sales | 6,955.51 | `eda_summary.json` |
| Sales per Customer | 9.12 | `eda_summary.json` |
| Promo Uplift % | ≈ 38.8% | `eda_summary.json` |
| Holdout RMSPE (ensemble) | 0.1381 | Python pipeline |
| Forecast Coverage | 100% | `submission_summary.json` |

If a DAX measure disagrees with the Python value, check the `Open = 1` filter first: the most common error is averaging sales over closed days.
