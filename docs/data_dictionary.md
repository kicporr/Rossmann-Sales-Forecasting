# Data Dictionary

Processed tables are written by `src/data_preparation.py`. The raw Kaggle files are never modified.

## `train_clean.parquet` / `test_clean.parquet`

| Column | dtype | Description |
|---|---|---|
| `Store` | int64 | Store identifier (1-1115) |
| `DayOfWeek` | int8 | Day of week, 1=Monday ... 7=Sunday |
| `Date` | datetime64[us] | Trading day (normalised timestamp) |
| `Sales` | int64 | Turnover in PLN (target; training only) |
| `Customers` | int64 | Number of customers (training only) |
| `Open` | int8 | 1 if the store was open |
| `Promo` | int8 | 1 if a daily promotion was active |
| `StateHoliday` | string | 0 = none, a = public holiday, b = Easter, c = Christmas |
| `SchoolHoliday` | int8 | 1 if a school holiday |
| `OpenImputed` | int64 | 1 if Open was missing and imputed (11 test rows) |
| `IsOpen` | int8 | Copy of Open for readability |
| `StateHoliday_a` | int8 | Binary flag for StateHoliday = a |
| `StateHoliday_b` | int8 | Binary flag for StateHoliday = b |
| `StateHoliday_c` | int8 | Binary flag for StateHoliday = c |
| `IsStateHoliday` | int8 | 1 if StateHoliday != 0 |
| `SalesZero` | int8 | 1 if Sales = 0 |
| `SalesZeroWhileOpen` | int8 | 1 if Sales = 0 and Open = 1 (anomaly) |
| `StoreType` | string | Store format a-d |
| `Assortment` | string | Assortment level a-c |
| `CompetitionDistance` | float64 | Distance to nearest competitor in metres (median-imputed for 3 stores) |
| `CompetitionOpenSinceMonth` | float64 | Month the competitor opened (raw) |
| `CompetitionOpenSinceYear` | float64 | Year the competitor opened (raw) |
| `Promo2` | int8 | 1 if the store participates in Promo2 |
| `Promo2SinceWeek` | float64 | ISO week Promo2 started (raw) |
| `Promo2SinceYear` | float64 | Year Promo2 started (raw) |
| `PromoInterval` | string | Months with Promo2 promotions |
| `CompetitionDistanceMissing` | int8 | 1 if CompetitionDistance was imputed |
| `CompetitionDistanceLog` | float64 | log1p(CompetitionDistance) |
| `HasCompetitionStart` | int8 | 1 if the competition opening date is known |
| `CompetitionOpenSince` | datetime64[us] | Derived competition start date (NaT if unknown) |
| `Promo2StartKnown` | int8 | 1 if the Promo2 start date is known |
| `Promo2Start` | datetime64[us] | Derived Promo2 start date (NaT if not applicable) |
| `Promo2MonthsCsv` | str | Promo2 months as a comma-separated list |

## `store_clean.parquet`

| Column | dtype | Description |
|---|---|---|
| `Store` | int64 | Store identifier (1-1115) |
| `StoreType` | string | Store format a-d |
| `Assortment` | string | Assortment level a-c |
| `CompetitionDistance` | float64 | Distance to nearest competitor in metres (median-imputed for 3 stores) |
| `CompetitionOpenSinceMonth` | float64 | Month the competitor opened (raw) |
| `CompetitionOpenSinceYear` | float64 | Year the competitor opened (raw) |
| `Promo2` | int8 | 1 if the store participates in Promo2 |
| `Promo2SinceWeek` | float64 | ISO week Promo2 started (raw) |
| `Promo2SinceYear` | float64 | Year Promo2 started (raw) |
| `PromoInterval` | string | Months with Promo2 promotions |
| `CompetitionDistanceMissing` | int8 | 1 if CompetitionDistance was imputed |
| `CompetitionDistanceLog` | float64 | log1p(CompetitionDistance) |
| `HasCompetitionStart` | int8 | 1 if the competition opening date is known |
| `CompetitionOpenSince` | datetime64[us] | Derived competition start date (NaT if unknown) |
| `Promo2StartKnown` | int8 | 1 if the Promo2 start date is known |
| `Promo2Start` | datetime64[us] | Derived Promo2 start date (NaT if not applicable) |
| `Promo2MonthsCsv` | str | Promo2 months as a comma-separated list |