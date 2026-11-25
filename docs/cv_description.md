# Opis projektu do CV i LinkedIn

> Wszystkie liczby pochodzą z rzeczywistego uruchomienia pipeline'u. Projekt nie przypisuje autorowi kompetencji, których nie potwierdza kod i wyniki.

---

## 1. CV — wersja polska (skrócona)

**Prognozowanie dziennej sprzedaży sklepów Rossmann (Python, SQL, Power BI)**

Projekt end-to-end na 1,017 mln rekordów store-days: czyszczenie danych i walidacja jakości, analiza eksploracyjna (14 wykresów), model SQL z 13 zapytaniami (JOIN, CTE, funkcje okna), inżynieria cech bez wycieku danych oraz porównanie 7 wariantów: historical average, seasonal naive, regresja liniowa, random forest, XGBoost, SARIMAX i ensemble 65/35. Walidacja rolling-origin z horyzontem 48 dni i nietkniętym holdoutem. Ensemble 65% XGBoost + 35% średniej historycznej osiągnął RMSPE **0,138** na holdoucie vs **0,228** dla baseline'u (poprawa ~40%); zidentyfikowano i jawnie zaraportowano bias -7,9%. Dostarczono prognozę 41 088 rekordów, działający dashboard Power BI (.pbix) z 3 stronami i ponad 30 miarami DAX oraz 17 testów automatycznych, w tym test antyleakowy.

**Stack:** Python (pandas, scikit-learn, XGBoost, statsmodels), SQL (SQLite), Power BI (.pbix + DAX), pytest, Git.

**Case study:** [kacper-teichert.pages.dev/projekty/rossmann](https://kacper-teichert.pages.dev/projekty/rossmann/)

---

## 2. CV — English version (short)

**Rossmann Store Sales Forecasting (Python, SQL, Power BI)**

End-to-end project on 1.017M store-day records: data cleaning and quality validation, exploratory analysis (14 annotated charts), a SQL layer with 13 analytical queries (JOIN, CTE, window functions), leakage-safe feature engineering, and a model comparison covering historical average, seasonal naive, linear regression, random forest, XGBoost and SARIMAX. Rolling-origin validation with a 48-day horizon and an untouched holdout. A 65% XGBoost + 35% historical-average ensemble reached **0.138 RMSPE** on the holdout vs **0.228** for the baseline (~40% improvement); a -7.9% bias was identified and reported transparently. Delivered a 41,088-row submission, a working Power BI dashboard (.pbix) with 3 pages and 30+ DAX measures, and 17 automated tests including an anti-leakage test.

**Stack:** Python (pandas, scikit-learn, XGBoost, statsmodels), SQL (SQLite), Power BI (.pbix + DAX), pytest, Git.

**Case study:** [kacper-teichert.pages.dev/en/projects/rossmann](https://kacper-teichert.pages.dev/en/projects/rossmann/)

---

## 3. LinkedIn post

**PL**

> Ukończyłem projekt prognozowania sprzedaży dla sieci Rossmann — 1,017 mln store-days, 1 115 sklepów, horyzont 48 dni.
>
> Co zawiera:
> • pipeline danych z 8 automatycznymi kontrolami jakości i testem antyleakowym,
> • analizę EDA (14 wykresów) i warstwę SQL z 13 zapytaniami (CTE, funkcje okna),
> • porównanie 7 wariantów: od historical average po XGBoost, SARIMAX i ensemble 65/35,
> • walidację rolling-origin i nietknięty holdout,
> • dashboard Power BI (.pbix, 3 strony, 30+ miar DAX),
> • prognozę 41 088 rekordów i README umożliwiające reprodukcję.
>
> Wynik: ensemble XGBoost + średnia historyczna RMSPE 0,138 vs baseline 0,228 na holdoucie. Równie ważne: model zaniża poziom lata 2015 o ~8% — ten bias jest opisany, a nie ukryty. W biznesie to różnica między „model działa” a „model działa i wiadomo, kiedy mu nie wierzyć”.
>
> #DataScience #Python #SQL #PowerBI #Forecasting #XGBoost #Portfolio

**EN**

> I completed an end-to-end sales forecasting project on the Rossmann dataset — 1.017M store-days, 1,115 stores, 48-day horizon.
>
> What is inside:
> • a data pipeline with 8 automated quality checks and an anti-leakage test,
> • EDA (14 charts) and a SQL layer with 13 queries (CTEs, window functions),
> • a comparison of 7 candidates, from historical average to XGBoost, SARIMAX and a 65/35 ensemble,
> • rolling-origin validation and an untouched holdout,
> • a working Power BI dashboard (.pbix) with 30+ DAX measures,
> • a 41,088-row submission and a reproducible README.
>
> Result: XGBoost + historical-average ensemble RMSPE 0.138 vs 0.228 baseline on the holdout. Equally important: the model under-forecasts the 2015 summer level by ~8%. That bias is documented, not hidden — in business it is the difference between "the model works" and "the model works and we know when not to trust it".
>
> #DataScience #Python #SQL #PowerBI #Forecasting #XGBoost #Portfolio

---

## 4. Jak uczciwie mówić o projekcie

**Można powiedzieć:**

* „Zbudowałem powtarzalny pipeline i porównałem 7 wariantów na wspólnych foldach.”
* „Ensemble XGBoost + średnia historyczna poprawił RMSPE o ~24% względem baseline'u na foldach walidacyjnych i o ~40% na holdoucie.”
* „Zaimplementowałem test antyleakowy, który perturbuje przyszłą sprzedaż i sprawdza, czy cechy historyczne się nie zmieniają.”
* „Zidentyfikowałem bias -7,9% na holdoucie i opisałem, jak go kalibrować.”
* „Warstwa SQL i dashboard Power BI są odtwarzalne z jednego polecenia.”

**Czego nie mówić:**

* „Model przewiduje sprzedaż z dokładnością 95%.” — RMSPE to nie accuracy; 0,138 oznacza ~14% typowego błędu względnego na dni otwarte.
* „Promocje zwiększają sprzedaż o 39%.” — to asocjacja; brak grupy kontrolnej.
* „Model jest gotowy produkcyjnie.” — brak kalibracji, monitoringu i danych zewnętrznych.
* „Użyłem 1 mln obserwacji, więc wyniki są na pewno istotne.” — istotność statystyczna nie zastępuje trafności prognozy.

---

## 5. Poziom zaawansowania — uczciwa samoocena

| Obszar | Poziom potwierdzony projektem |
|---|---|
| Python / pandas | samodzielne przygotowanie danych, funkcje, testy, typowanie |
| SQL | JOIN, GROUP BY, CTE, funkcje okna, projekt schematu |
| Modelowanie | walidacja czasowa, XGBoost, RF, regresja, SARIMAX, metryki |
| Inżynieria cech | lagi, rolling, bez wycieku, testy perturbacyjne |
| Power BI | działający plik .pbix (3 strony), model i miary DAX |
| MLOps | podstawy: konfiguracja, reproducibility, zapis modelu; **brak** wdrożenia produkcyjnego |
| Statystyka | ADF, ACF/PACF, OLS z HC3, testy nieparametryczne, interpretacja z zastrzeżeniami |

Projekt **nie** potwierdza: doświadczenia produkcyjnego, pracy z chmurą, budowy API, zaawansowanego MLOps, głębokiego uczenia ani znajomości niemieckiego rynku detalicznego.
