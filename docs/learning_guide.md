# Przewodnik edukacyjny

Ten dokument wyjaśnia metody użyte w projekcie w formacie, który można wykorzystać na rozmowie rekrutacyjnej: **co robimy → dlaczego → jak to działa → jak czytać wynik → jak to opowiedzieć**.

---

## 1. JOIN (łączenie tabel)

**Co robimy?** Do tabeli sprzedaży dziennej (`train_sales`) dołączamy atrybuty sklepu (`stores`) po kolumnie `Store`.

**Dlaczego?** Sprzedaż zależy od formatu sklepu, asortymentu i konkurencji. Trzymanie tych informacji w osobnej tabeli unika duplikacji i błędów aktualizacji.

**Jak działa?** `LEFT JOIN` zachowuje wszystkie wiersze faktów i dopasowuje maksymalnie jeden wiersz wymiaru. W projekcie relacja jest `many-to-one` i jest walidowana: gdyby któryś sklep nie miał odpowiednika, kod zgłasza błąd zamiast cicho tworzyć `NULL`.

**Jak interpretować?** Liczba wierszy przed i po łączeniu musi być identyczna. To pierwszy test jakości każdego pipeline'u.

**Dla rekrutera:** „Łączę fakt sprzedaży z wymiarem sklepu po kluczu `Store`, walidując cardinality `many-to-one`; test row-count chroni przed przypadkowym zdublowaniem faktów.”

---

## 2. GROUP BY i agregacje

**Co robimy?** Liczymy średnią sprzedaż według sklepu, dnia tygodnia, typu sklepu i obecności promocji.

**Dlaczego?** Pojedynczy wiersz nie mówi nic o biznesie; dopiero agregacja pokazuje wzorce.

**Jak działa?** `GROUP BY` dzieli zbiór na grupy, a funkcje agregujące (`AVG`, `SUM`, `COUNT`) redukują każdą grupę do jednej wartości.

**Jak interpretować?** Zawsze pytaj, jaki jest mianownik. Średnia sprzedaż „na wiersz” zawiera dni zamknięte (zera), a „na dzień otwarty” już nie. W projekcie te dwie wartości różnią się o ~20% (5 774 vs 6 956 PLN).

**Dla rekrutera:** „Rozróżniam średnią na wszystkie store-days i na dni otwarte; KPI liczę na dni otwarte, bo zamknięcie nie jest zerowym popytem.”

---

## 3. CTE i funkcje okna (SQL)

**Co robimy?** W `sql/analytical_queries.sql` używamy CTE do etapowania obliczeń i funkcji okna do rankingów oraz wzrostu miesiąc do miesiąca.

**Dlaczego?** CTE czyni zapytanie czytelnym, a funkcje okna pozwalają liczyć rankingi i zmiany bez samozłączeń.

**Jak działa?** `WITH monthly AS (...)` tworzy tymczasowy zbiór. `LAG(total_sales) OVER (ORDER BY month)` sięga do poprzedniego miesiąca w tej samej „ramce” okna.

**Jak interpretować?** `RANK()` daje równe miejsca przy remisach i przeskakuje numery; `DENSE_RANK()` nie przeskakuje. `SUM(...) OVER ()` liczy udział w całości.

**Dla rekrutera:** „Ranking sklepów i dynamikę miesięczną liczę funkcjami okna, a nie podzapytaniami skorelowanymi, bo są czytelniejsze i szybsze.”

---

## 4. Korelacja

**Co robimy?** Badamy związek sprzedaży z liczbą klientów, promocją i odległością od konkurencji.

**Dlaczego?** Korelacja wskazuje potencjalne zależności i pomaga wybrać cechy.

**Jak działa?** Współczynnik Pearsona mierzy liniowy związek; Spearman mierzy monotoniczny i jest odporny na skosy. W projekcie Spearman dla odległości od konkurencji jest używany, bo zależność nie jest liniowa.

**Jak interpretować?** Korelacja ≠ przyczynowość. Promocje są planowane przez sieć, więc „wzrost sprzedaży w promocji” może częściowo odzwierciedlać wybór tygodni, w których i tak spodziewano się wysokiej sprzedaży. W projekcie mówimy o „współwystępowaniu”, nie o „wpływie”.

**Dla rekrutera:** „Liczę korelację jako screening, ale wnioski przyczynowe formułuję ostrożnie; promocja nie jest losowo przypisana.”

---

## 5. Regresja liniowa i interpretacja parametrów

**Co robimy?** OLS na logarytmie sprzedaży: `log(Sales) ~ Promo + C(DayOfWeek) + SchoolHoliday + trend`.

**Dlaczego?** Regresja daje interpretowalne parametry i stanowi benchmark dla modeli ML.

**Jak działa?** Współczynnik przy `Promo` mówi, o ile zmienia się średni log sprzedaży przy przejściu z 0 na 1, przy pozostałych zmiennych stałych. Po transformacji `exp(beta) - 1` otrzymujemy przybliżoną zmianę procentową.

**Jak interpretować?** Standardowe błędy HC3 odpornościowe na heteroskedastyczność. Ale Durbin-Watson w tym projekcie jest znacznie poniżej 2, co oznacza silną autokorelację reszt — standardowe błędy mogą być zaniżone. To nie unieważnia kierunku efektów, ale ogranicza precyzję wnioskowania.

**Dla rekrutera:** „Regresję traktuję jako narzędzie interpretacji, nie jako finalny model; reszty są autokorelowane, co pokazuję w diagnostyce.”

---

## 6. Sezonowość

**Co robimy?** Rozkładamy szereg na trend, składnik tygodniowy i resztę; liczymy średnie według dnia tygodnia i miesiąca.

**Dlaczego?** Sprzedaż ma silny rytm tygodniowy (poniedziałek szczyt, sobota dołek) i roczny (lato mocniejsze, styczeń słabszy).

**Jak działa?** Dekompozycja addytywna: `y_t = trend_t + seasonal_t + resid_t`. Przy okresie 7 dni składnik sezonowy powtarza się co tydzień.

**Jak interpretować?** Sezonowość tygodniowa jest dobrze oszacowana (2,5 roku danych). Roczna jest oparta tylko na dwóch pełnych cyklach — to opis, nie precyzyjny model. Dlatego w modelu ML miesiąc i dzień roku są cechami, ale nie wyciągamy z nich daleko idących wniosków.

**Dla rekrutera:** „Tygodniowa sezonowość jest stabilna; roczną traktuję ostrożnie, bo mam tylko dwa sezony letnie.”

---

## 7. ACF i PACF

**Co robimy?** Rysujemy autokorelację (ACF) i autokorelację częściową (PACF) dla sprzedaży sklepu oraz jej pierwszych różnic.

**Dlaczego?** Wskazują rząd modelu AR/MA i siłę sezonowości.

**Jak działa?** ACF mierzy korelację szeregu z jego opóźnieniami. PACF mierzy związek z opóźnieniem po usunięciu wpływu opóźnień pośrednich.

**Jak interpretować?** Skok przy lag 7 potwierdza sezonowość tygodniową. Powolne wygaszanie ACF sugeruje niestacjonarność. Po różnicowaniu skok przy 7 nadal zostaje, więc potrzebne jest różnicowanie sezonowe.

**Dla rekrutera:** „Na podstawie ACF/PACF wybrałem SARIMAX z komponentem sezonowym (1,1,1,7); nadal jednak reszty nie są białym szumem.”

---

## 8. Test ADF

**Co robimy?** Testujemy stacjonarność szeregu dziennego i tygodniowego oraz ich pierwszych różnic.

**Dlaczego?** Wiele modeli (ARIMA, regresja) zakłada stacjonarność lub wymaga różnicowania.

**Jak działa?** H0: szereg ma pierwiastek jednostkowy (jest niestacjonarny). Mała p-value → odrzucamy H0 → szereg stacjonarny.

**Jak interpretować?** Test jest wrażliwy na sezonowość deterministyczną i złamania strukturalne. Wynik „niestacjonarny” nie oznacza automatycznie „różnicuj”; trzeba patrzeć na wykres i kontekst.

**Dla rekrutera:** „ADF traktuję jako diagnostykę, nie wyrocznię; przy sezonowości tygodniowej wynik zależy od specyfikacji.”

---

## 9. Podział train / validation / test

**Co robimy?** Dzielimy chronologicznie: 3 foldy walidacyjne (po 48 dni) + holdout (47 dni) + finalny trening na wszystkich danych.

**Dlaczego?** Losowy podział mieszałby przyszłość z przeszłością i zawyżał wynik. Test Kaggle to przyszłość, więc walidacja też musi być przyszłością.

**Jak działa?** Expanding window: każdy fold trenuje na wszystkim do `train_end` i ocenia na kolejnych 48 dniach. Holdout jest używany tylko raz, po wyborze modelu.

**Jak interpretować?** Wynik na holdoucie jest jedynym uczciwym oszacowaniem. Foldy służą do porównania modeli; holdout do raportowania końcowego.

**Dla rekrutera:** „Nigdy nie używam `train_test_split`; walidacja jest rolling-origin, a holdout nietknięty do końca.”

---

## 10. RMSPE

**Co robimy?** Liczymy oficjalną metrykę konkursu: pierwiastek ze średniej kwadratów błędów względnych.

**Dlaczego?** Konkurs ją narzuca; jest też sensowna biznesowo, bo karze błąd procentowy, a nie absolutny.

**Jak działa?** `sqrt(mean(((y - y_hat) / y)^2))` tylko dla `y > 0`. Dzielenie przez zero jest wykluczone, dlatego dni zamknięte nie wchodzą do metryki.

**Jak interpretować?** RMSPE 0,14 oznacza typowy błąd względny ~14%. Metryka faworyzuje małe sklepy (mały mianownik), więc raportujemy też MAE i WAPE.

**Dla rekrutera:** „RMSPE liczę tylko na dni otwarte z dodatnią sprzedażą; dni zamknięte są przewidywane jako zero z reguły biznesowej.”

---

## 11. Feature engineering

**Co robimy?** Tworzymy cechy kalendarzowe, sklepowe, promocyjne i historyczne (lagi, średnie kroczące, odchylenie standardowe).

**Dlaczego?** Model nie wie, że poniedziałek jest inny niż sobota, ani że sklep 817 jest duży — musi dostać te informacje w cechach.

**Jak działa?** Lag `sales_lag_1` to sprzedaż sprzed jednego dnia; rolling mean 28 to średnia z ostatnich 28 dni; `Promo2Active` to flaga, czy program lojalnościowy działa w danym miesiącu.

**Jak interpretować?** Ważność cech z XGBoost pokazuje, że poziom sklepu i sezonowość dominują. Wysoka ważność `Promo` nie oznacza causality.

**Dla rekrutera:** „Cechy historyczne buduję wyłącznie z przeszłości; test perturbacji przyszłej sprzedaży potwierdza brak wycieku.”

---

## 12. Data leakage

**Co robimy?** Upewniamy się, że żadna cecha w chwili `t` nie używa danych z `t` ani późniejszych.

**Dlaczego?** Wyciek daje świetne wyniki w walidacji i katastrofę na produkcji.

**Jak działa?** Lagi i rolling są przesunięte o co najmniej 1 dzień; w trybie direct — o 48 dni. Statystyki imputacji liczone są tylko na treningu.

**Jak interpretować?** Test perturbacyjny: zmieniamy przyszłą sprzedaż o +5000 i sprawdzamy, czy cechy sprzed cutoffu się nie zmieniły. Jeśli tak — mamy wyciek.

**Dla rekrutera:** „Mam automatyczny test antyleakowy w `tests/test_features.py`; to rzadko spotykane w projektach portfolio.”

---

## 13. XGBoost

**Co robimy?** Trenujemy gradient boosting na 46 cechach, 600 drzew, głębokość 8.

**Dlaczego?** Drzewa obsługują nieliniowości i interakcje, a boosting sekwencyjnie poprawia błędy poprzednich drzew.

**Jak działa?** Każde drzewo uczy się na resztach (gradiencie) poprzednich. `learning_rate` kontroluje wielkość kroku, `max_depth` złożoność, `subsample` i `colsample_bytree` losowość.

**Jak interpretować?** Feature importance (gain) mówi, które cechy najczęściej poprawiają podział. To nie jest wpływ przyczynowy. RMSPE na holdoucie jest miarą jakości, nie „prawdą” o rynku.

**Dla rekrutera:** „XGBoost był najlepszym pojedynczym modelem, ale końcowy wybór to ensemble 65% XGBoost + 35% średniej store-weekday; wagi dobrałem tylko na foldach, bez tuningu na holdoucie.”

---

## 14. Random forest vs boosting

**Co robimy?** Porównujemy las losowy (60 drzew, `max_samples=0.7`) z XGBoostem.

**Dlaczego?** Las jest odporny i równoległy, boosting zwykle dokładniejszy na danych tabelarycznych.

**Jak działa?** Las buduje wiele niezależnych drzew na bootstrapach i uśrednia. Boosting buduje drzewa sekwencyjnie, każde na błędach poprzednich.

**Jak interpretować?** W projekcie las jest blisko XGBoosta na niektórych foldach, ale wolniejszy. To typowy kompromis dokładność vs koszt.

**Dla rekrutera:** „Las dał RMSPE zbliżone do boostingu, ale trening był ~2× dłuższy; w produkcji wybrałbym XGBoost lub ensemble z prostym baseline'em ze względu na koszt i stabilność.”

---

## 15. Transformacja logarytmiczna

**Co robimy?** Modelujemy `log1p(Sales)`, a predykcję odwracamy `expm1`.

**Dlaczego?** Sprzedaż jest silnie prawoskosna; log stabilizuje wariancję i przybliża błąd procentowy.

**Jak działa?** Duże wartości są „ściśnięte”, małe rozciągnięte. Model uczy się względnych różnic, co pasuje do RMSPE.

**Jak interpretować?** Średnia w logach to mediana geometryczna; po odwróceniu dostajemy niższą wartość niż średnia arytmetyczna. Stąd możliwy systematyczny bias — w projekcie raportowany jawnie.

**Dla rekrutera:** „Log-transform uzasadniam skosem rozkładu i zgodnością z metryką procentową; bias weryfikuję osobno.”

---

## 16. Prognoza rekurencyjna vs direct multi-horizon

**Co robimy?** Porównujemy dwa podejścia i wybieramy direct.

**Dlaczego?** Rekurencja na 48 dni kumuluje błędy: w pilocie RMSPE wzrosło z 0,195 (one-step) do 0,38 (recursive).

**Jak działa?** Direct: cechy zamrożone na originie, kalendarz targetu się zmienia. Recursive: przewidywany dzień trafia do lagów następnego.

**Jak interpretować?** Direct jest stabilniejszy, ale nie reaguje na szok w horyzoncie. Recursive lepszy przy krótkim horyzoncie i częstym odświeżaniu.

**Dla rekrutera:** „Wybrałem direct, bo w 48-dniowym horyzoncie rekurencja dryfowała; pokazuję to liczbami, nie opinią.”

---

## 17. SARIMAX i ograniczenia modeli klasycznych

**Co robimy?** Dopasowujemy SARIMAX(1,0,1)(1,1,1,7) dla sklepu 1 z egzogenicznymi promocjami i świętami.

**Dlaczego?** To klasyczny benchmark ekonometryczny i narzędzie interpretacji.

**Jak działa?** AR i MA opisują autokorelację, różnicowanie sezonowe usuwa tygodniowy cykl, egzogeniczne zmienne wchodzą jako regresory.

**Jak interpretować?** Ljung-Box odrzuca brak autokorelacji reszt — model nie wyczerpał struktury. Jeden model na sklep nie wykorzystuje informacji z 1115 lokalizacji.

**Dla rekrutera:** „SARIMAX daje interpretowalne parametry i przedziały, ale globalny XGBoost jest dokładniejszy; trzymam oba jako benchmark i narzędzie diagnostyczne.”

---

## 18. Bias i kalibracja

**Co robimy?** Raportujemy średni błąd znakowy (`prediction - actual`) i bias procentowy.

**Dlaczego?** Model może mieć niski RMSPE i jednocześnie systematycznie zaniżać poziom, co w praktyce oznacza braki towaru.

**Jak działa?** Bias = średnia różnica; dodatni = nadprognoza, ujemny = niedoprognoza.

**Jak interpretować?** W holdoucie 2015 ensemble zaniża poziom o ~8%. To nie jest losowy szum — tydzień po tygodniu widać ten sam kierunek. Przyczyną jest prawdopodobnie zmiana poziomu lata 2015 względem 2014.

**Dla rekrutera:** „Bias raportuję osobno; nie ukrywam go w metryce. W produkcji dodałbym kalibrację na ostatnim obserwowanym oknie.”

---

## 19. DAX i model gwiazdy w Power BI

**Co robimy?** Budujemy model: fakt sprzedaży + wymiary sklepu i daty + tabela prognoz; miary DAX liczą KPI, RMSPE i błąd.

**Dlaczego?** Model gwiazdy jest wydajny i zrozumiały; miary liczą się w kontekście filtra, więc jeden zestaw działa dla wszystkich sklepów i okresów.

**Jak działa?** `CALCULATE` zmienia kontekst filtra; `DIVIDE` bezpiecznie dzieli; `SUMX` iteruje po wierszach; `SAMEPERIODLASTYEAR` wymaga tabeli dat.

**Jak interpretować?** RMSPE w DAX musi filtrować `Sales > 0`, inaczej dzielenie przez zero zepsuje wynik.

**Dla rekrutera:** „Dashboard opieram na gwieździe i miarach, nie na obliczanych kolumnach w tabeli faktów; dzięki temu model jest lekki i szybki.”

---

## 20. Jak mówić o projekcie

**Struktura odpowiedzi (60–90 s):**

1. **Problem:** prognoza dziennej sprzedaży 856 sklepów na 48 dni.
2. **Dane:** 1,017,209 store-days, 1,115 sklepów, 2,5 roku, silna sezonowość i promocje.
3. **Metoda:** czyszczenie + SQL, EDA, cechy antyleakowe, direct multi-horizon, XGBoost, walidacja rolling-origin.
4. **Wynik:** RMSPE na holdoucie ~0,14 vs baseline ~0,23; bias ~-8% jawnie raportowany (ensemble XGBoost + średnia historyczna).
5. **Wnioski:** promocje +38.8% (asocjacja), poniedziałek szczyt, najmniejsze sklepy najtrudniejsze.
6. **Ograniczenia:** brak pogody i zdarzeń lokalnych, tylko dwa cykle roczne, brak kalibracji.

**Czego nie mówić:** „model przewiduje sprzedaż z dokładnością 95%” — RMSPE to nie accuracy. „Promocje zwiększają sprzedaż o 38.8%” — to związek, nie eksperyment.

**Dobre pytanie do rekrutera na koniec:** „Czy w Państwa setupie prognoza jest odświeżana codziennie, czy raz na horyzoncie? To zmienia wybór między direct a recursive.”
