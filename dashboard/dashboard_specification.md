# Power BI Dashboard Specification

**Project:** Rossmann Store Sales Forecasting  
**Pages:** 3 (Sales Overview, Sales Drivers, Sales Forecast)  
**Canvas:** 16:9, 1280 x 720 px (Power BI default), light theme  
**Audience:** category managers, store operations, demand planning

The repository contains the working **`dashboard/Rossmann-Sales-Dashboard.pbix`**: three pages, an import model and aggregated data cached in the file. The screenshots were exported from that file, not drawn as mockups.

* `dashboard/Rossmann-Sales-Dashboard.pbix` - the working report.
* `dashboard/screenshots/` - real page screenshots exported from the `.pbix`.
* a regenerable data export in `dashboard/data/` (produced by `src.dashboard_export`),
* a documented star schema and relationship map,
* production-ready DAX measures in `dashboard/dax_measures.md`,
* step-by-step rebuild instructions (section 6).

---

## 1. Data model

```
DimDate (Date) 1 ────────── * FactSales (Date)
DimStore (Store) 1 ──────── * FactSales (Store)
DimStore (Store) 1 ──────── * Forecast (Store)
DimDate (Date) 1 ────────── * Forecast (Date)
ModelMetrics (model, fold) 1 ── * Forecast (model)     [optional, for slicers]
```

| Table | Grain | Rows | Source file |
|---|---|---:|---|
| `FactSales` | store x day | 1,017,209 | `data/fact_sales.csv` |
| `DimStore` | store | 1,115 | `data/dim_store.csv` |
| `DimDate` | day | 990 | `data/dim_date.csv` |
| `Forecast` | store x day x model | holdout + test | `data/forecast_holdout.csv`, `data/forecast_test.csv` (append) |
| `ModelMetrics` | model x fold | 24 | `data/model_metrics.csv` |
| `AggStore` | store | 1,115 | `data/agg_store.csv` (optional import table) |

**Relationships**

| From | To | Cardinality | Cross-filter |
|---|---|---|---|
| `FactSales[Store]` | `DimStore[Store]` | many-to-one | single |
| `FactSales[Date]` | `DimDate[Date]` | many-to-one | single |
| `Forecast[Store]` | `DimStore[Store]` | many-to-one | single |
| `Forecast[Date]` | `DimDate[Date]` | many-to-one | single |

`DimDate` must be marked as the date table (`Table tools > Mark as date table > Date`). `FactSales[StateHoliday]` stays in the fact table because a holiday is a store-day attribute, not a calendar attribute.

**Storage mode:** Import. The fact table is 1.0 M rows / ~32 MB CSV and compresses to a few MB in the VertiPaq engine.

---

## 2. Design system

| Element | Value |
|---|---|
| Background | `#F4F6F9` |
| Card surface | `#FFFFFF`, 1 px border `#E2E8F0`, radius 8 px, subtle shadow |
| Primary | `#1F3A5F` (headers, main series) |
| Secondary | `#2A9D8F` (positive / promo) |
| Accent | `#E76F51` (negative / forecast) |
| Muted text | `#64748B` |
| Titles | Georgia, 20 pt, semibold |
| Body | Segoe UI, 10 pt |
| KPI numbers | Consolas / DIN, 28-36 pt |
| Gridlines | horizontal only, `#E5E7EB` |

Accessibility: minimum 10 pt body text, never encode meaning by colour alone (bars carry value labels), contrast ratio of navy on white > 10:1.

---

## 3. Page 1 - Sales Overview

**Business question:** how is the chain performing, where is revenue concentrated, and how is the weekly rhythm shaping staffing?

**Layout (1280 x 720)**

| Region | Position | Visual | Fields |
|---|---|---|---|
| Header | 0,0-1280,70 | Text + slicers | title; date range slicer; store type slicer |
| KPI row | y=80, 5 cards 240x110 | Card | Total Sales; Avg Daily Sales; Active Stores; Sales per Customer; Sales Growth YoY |
| Trend | x=20,y=210,w=820,h=280 | Line chart | `DimDate[Date]` on X; `[Total Sales]`; `[Sales Rolling 28D]` |
| Weekday | x=860,y=210,w=400,h=280 | Column chart | `DimDate[DayName]`; `[Avg Daily Sales]` |
| Store ranking | x=20,y=510,w=520,h=190 | Bar chart (Top N = 15) | `DimStore[Store]`; `[Total Sales]`; tooltip `[Avg Daily Sales]`, `[Open Store Days]` |
| Store type mix | x=560,y=510,w=340,h=190 | Donut | `DimStore[StoreType]`; `[Total Sales]` |
| Bottom stores | x=920,y=510,w=340,h=190 | Table | Store, Avg Daily Sales, CV, Open Days (bottom 10 by sales) |

**Filters / interactions**

* Date slicer defaults to the last 12 months.
* Clicking a store in the ranking filters the trend (cross-filtering on `DimStore`).
* Store type slicer affects every visual on the page.

**Conditional formatting**

* KPI "Sales Growth YoY": green if > 0, orange if < 0.
* Store ranking: data bars, colour scale from `#DBE4EE` to `#1F3A5F`.

---

## 4. Page 2 - Sales Drivers

**Business question:** which levers coincide with sales differences - promotions, holidays, competition, format, seasonality?

**Layout**

| Region | Position | Visual | Fields |
|---|---|---|---|
| Header | 0,0-1280,70 | Text + slicers | date range; store type |
| Promo comparison | x=20,y=90,w=400,h=250 | Clustered column | `FactSales[Promo]`; `[Avg Daily Sales]`, `[Avg Customers]` |
| Promo uplift by format | x=440,y=90,w=400,h=250 | Bar chart | `DimStore[StoreType]`; `[Promo Uplift %]` |
| Holiday effect | x=860,y=90,w=400,h=250 | Column chart | `FactSales[StateHoliday]`; `[Avg Daily Sales]` |
| Competition curve | x=20,y=360,w=620,h=300 | Line + column combo | competition distance bin; `[Avg Daily Sales]`; store count |
| Seasonality heatmap | x=660,y=360,w=600,h=300 | Matrix with background colour | rows `DimDate[Year]`, columns `DimDate[MonthName]`, values `[Avg Daily Sales]` |
| Insight strip | y=680 | Text box | dynamic insight text measure |

**Drill paths**

* Promo comparison -> store type -> store.
* Competition curve -> store list filtered by distance bin.

**Important note for the reader:** every visual on this page is descriptive. Promotions are not randomly assigned, so the uplift is an association, not a causal effect. The page subtitle must state this explicitly.

---

## 5. Page 3 - Sales Forecast

**Business question:** how accurate is the forecast, where does it fail, and what is the expected sales level for the next 48 days?

**Layout**

| Region | Position | Visual | Fields |
|---|---|---|---|
| Header | 0,0-1280,70 | Text + slicers | model slicer; store slicer; date range |
| KPI row | y=80, 4 cards | Card | RMSPE; Forecast Accuracy; MAE; Bias % |
| Actual vs predicted | x=20,y=200,w=820,h=300 | Line chart | `DimDate[Date]`; `[Actual Sales]`; `[Forecast Sales]` |
| Model comparison | x=860,y=200,w=400,h=300 | Bar chart | `ModelMetrics[model]`; `[RMSPE]` |
| Error by segment | x=20,y=520,w=520,h=180 | Matrix | `DimStore[StoreType]`, `DimDate[DayName]`; `[RMSPE]` |
| Forecast horizon | x=560,y=520,w=700,h=180 | Line chart | `Forecast[Date]`; `[Forecast Sales]` (test horizon, 2015-08-01..09-17) |

**Forecast table requirements**

* One row per store-day-model; `Sales` is actual (blank for the test horizon), `Prediction` is the model output.
* `Open = 0` rows must have `Prediction = 0`; they are excluded from RMSPE but shown in the sales line.
* Model slicer values: `historical_average`, `seasonal_naive`, `linear_regression`, `random_forest`, `xgboost`, `ensemble_xgb_hist` (default).

**Error analysis**

* RMSPE by store type, weekday, promotion flag and sales decile.
* A scatter of actual vs predicted with a 45-degree reference line.
* A table of the 20 store-days with the largest absolute percentage error, for operational follow-up.

---

## 6. Rebuild instructions

1. Run the Python pipeline from the repository root:
   ```bash
   python -m src.data_preparation
   python -m src.train
   python -m src.predict
   python -m src.dashboard_export
   ```
2. Open Power BI Desktop > **Get data** > **Text/CSV**. Import every file from `dashboard/data/` except `export_summary.json`.
3. In Power Query:
   * set `DimDate[Date]`, `FactSales[Date]`, `Forecast[Date]` to **Date**;
   * set `FactSales[Store]`, `DimStore[Store]`, `Forecast[Store]` to **Whole number**;
   * set `Sales`, `Customers`, `Prediction`, `RMSPE` to **Decimal number**.
4. Create the relationships listed in section 1.
5. Mark `DimDate` as the date table.
6. Add the measures from `dashboard/dax_measures.md` (Modeling > New measure).
7. Build the three pages following the layouts above. The real screenshots in `dashboard/screenshots/` show the current design.
8. The committed report is `dashboard/Rossmann-Sales-Dashboard.pbix`; a rebuild can replace it after checking the page totals against the Python metrics.

**Refresh:** replace the CSVs with a new export and hit Refresh. The Python pipeline is deterministic (`random_state = 42`), so the same inputs produce the same forecasts.

---

## 7. Performance and quality checks

* Import mode, no calculated columns on the 1 M-row fact table; all ratios are measures.
* `DimDate` and `DimStore` are the only filter directions; avoid bidirectional relationships.
* Disable auto date/time in Power BI options to keep the model small.
* Validate totals against `outputs/metrics/eda_summary.json` (Total Sales = 5,873,180,623 PLN).
* Validate RMSPE against `outputs/metrics/validation_results.json`; the DAX measure must match the Python value on the holdout.
