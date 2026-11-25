# 10 pytań rekrutacyjnych z odpowiedziami

Pytania dotyczą projektu Rossmann. Odpowiedzi są napisane tak, jak można je wypowiedzieć na rozmowie — z liczbami z rzeczywistego uruchomienia i z jasnym rozdzieleniem tego, co projekt pokazuje, od tego, czego nie pokazuje.

---

## 1. Dlaczego nie użyłeś losowego podziału train/test?

**Odpowiedź.** Bo zadanie jest prognozowaniem przyszłości, a nie klasyfikacją niezależnych obserwacji. Losowy podział mieszałby dni z przyszłości z przeszłością: model trenowałby na lipcu 2015 i przewidywał styczeń 2015, co daje sztucznie dobry wynik i nie odpowiada realnemu użyciu. Zastosowałem walidację rolling-origin: trzy foldy po 48 dni, każdy trenowany tylko na danych do dnia poprzedzającego okno, plus nietknięty holdout 2015-06-15–07-31. Holdout posłużył wyłącznie do raportowania, nie do wyboru modelu. Dzięki temu wynik 0,138 RMSPE jest uczciwym oszacowaniem na przyszłość, a nie miarą dopasowania do przeszłości.

**Na co uważać:** nie mów „podział 80/20”; w tym projekcie nie ma procentowego podziału, jest podział czasowy.

---

## 2. Jak zapewniłeś brak data leakage?

**Odpowiedź.** Na trzy sposoby. Po pierwsze, wszystkie cechy historyczne są liczone wyłącznie z przeszłości: lagi i średnie kroczące są przesunięte o co najmniej jeden dzień, a w trybie direct o 48 dni. Po drugie, `Customers` nie wchodzi jako cecha bieżąca — byłoby to niedostępne w momencie prognozy; używam tylko 28-dniowej średniej zamrożonej na originie. Po trzecie, mam automatyczny test: `tests/test_features.py` zmienia sprzedaż po wybranym cutoffie o +5000, przebudowuje macierz cech i sprawdza, że żadna cecha przed cutoffem się nie zmieniła. Dodałem też test, że `sales_lag_1` równa się sprzedaży z poprzedniego dnia kalendarzowego. To jest mocniejszy dowód niż deklaracja „uważałem na leakage”.

**Na co uważać:** nie twierdź, że test dowodzi braku leakage w każdej możliwej postaci; dowodzi braku wycieku przez sprzedaż i klientów w cechach historycznych.

---

## 3. Dlaczego wybrałeś prognozę direct, a nie rekurencyjną?

**Odpowiedź.** Bo rekurencja na 48 dni kumuluje błędy. W pilocie ten sam model liniowy osiągnął RMSPE 0,195 przy prognozie jednodniowej z rzeczywistymi lagami, a 0,381 przy rekurencji 48-dniowej; bias wzrósł z -3,5% do -12,8%. W trybie direct każdy wiersz treningowy opisuje świat z perspektywy 48 dni przed celem, a przy prognozie wszystkie cechy historyczne są zamrożone na originie; zmieniają się tylko cechy kalendarzowe i promocyjne. To eliminuje dryf, ale ma koszt: model nie reaguje na szok wewnątrz horyzontu. W produkcji, przy cotygodniowym odświeżaniu i krótszym horyzoncie, rekurencja mogłaby być lepsza — to świadomy kompromis, nie „jedyna słuszna metoda”.

**Na co uważać:** nie mów, że direct jest zawsze lepszy; jest lepszy w tym 48-dniowym, jednorazowym horyzoncie.

---

## 4. Dlaczego modelujesz logarytm sprzedaży?

**Odpowiedź.** Rozkład sprzedaży jest silnie prawoskosny: mediana 6 369 PLN, średnia 6 956 PLN, maksimum powyżej 41 000 PLN. Logarytm stabilizuje wariancję i sprawia, że błąd kwadratowy w logach odpowiada w przybliżeniu błędowi procentowemu, co pasuje do RMSPE. Po odwróceniu transformacji `expm1` dostaję prognozę w PLN. Transformacja ma jednak konsekwencję: średnia w logach to mediana geometryczna, więc predykcja może być systematycznie poniżej średniej arytmetycznej. Dlatego raportuję bias osobno — na holdoucie ensemble zaniża poziom o 7,9% (sam XGBoost: 10,8%).

**Na co uważać:** nie mów „logarytm usuwa skewness i problem znika”; mów, że poprawia zachowanie modelu, ale wprowadza interpretacyjny niuans.

---

## 5. Czym jest RMSPE i jakie ma ograniczenia?

**Odpowiedź.** RMSPE to pierwiastek ze średniej kwadratów błędów względnych: `sqrt(mean(((y - y_hat)/y)^2))`. Jest zdefiniowany tylko dla `y > 0`, więc dni zamknięte i 54 wiersze z zerową sprzedażą przy otwartym sklepie są wyłączone z metryki. Jego zaletą jest to, że karze błąd procentowy, a nie absolutny, więc mały i duży sklep są traktowane podobnie. Ograniczenia: mocno karze pojedyncze duże błędy względne, faworyzuje sklepy o małej sprzedaży (mały mianownik) i nie mówi nic o biasie. Dlatego raportuję też MAE, RMSE i WAPE. Na holdoucie ensemble ma RMSPE 0,138 i MAE 827 PLN, a sam XGBoost 0,171 i 1 008 PLN — w tym przypadku obie metryki wskazują ten sam kierunek, ale to nie musi się zdarzać.

**Na co uważać:** nie utożsamiaj RMSPE z accuracy; 0,138 to nie „86% dokładności”.

---

## 6. Dlaczego ensemble wygrał, a regresja liniowa nie?

**Odpowiedź.** Najlepszy okazał się ensemble 65% XGBoost + 35% średniej historycznej: 0,188 vs 0,287 dla regresji liniowej i 0,248 dla historical average na średniej z trzech foldów. Sam XGBoost był najlepszym pojedynczym modelem (0,207), ale jego bias był niestabilny, dlatego blend z prostym baseline'em poprawił i RMSPE, i kalibrację. Powody są trzy. Po pierwsze, nieliniowości i interakcje: efekt promocji zależy od formatu sklepu i poziomu sprzedaży, czego liniowy model nie reprezentuje bez ręcznych interakcji. Po drugie, braki danych: wczesne wiersze nie mają 365-dniowej historii; XGBoost obsługuje `NaN` natywnie, a regresja wymaga imputacji medianą, co wprowadza szum. Po trzecie, skala: 800 tys. wierszy i 46 cech to dobry reżim dla boosting, a nie dla OLS. Regresja nie jest „zła” — jest użyteczna interpretacyjnie, ale nie wygrywa konkursu na tym zbiorze. Ensemble wygrywa, bo łączy nieliniowy sygnał XGBoost z odpornym poziomem średniej store-weekday.

**Na co uważać:** nie mów, że regresja jest bezużyteczna; w analizie ekonometrycznej daje interpretowalne efekty (promocja +31,7% dla sklepu 1).

---

## 7. Co oznacza bias -7,9% i jak byś go naprawił?

**Odpowiedź.** Bias to średnia różnica `prediction - actual` podzielona przez średnią sprzedaż. Wartość -7,9% oznacza, że ensemble systematycznie prognozuje poniżej rzeczywistości na holdoucie (sam XGBoost: -10,8%) — nie chodzi o losowy szum, ale o przesunięcie poziomu. Przyczyna jest prawdopodobnie strukturalna: lato 2015 jest silniejsze niż lato 2014, na którym model się uczył, a cechy kalendarzowe nie ekstrapolują wzrostu poziomu. Naprawiłbym to kalibracją multiplikatywną na ostatnim obserwowanym oknie 48 dni, a nie na holdoucie, oraz monitorował faktor co miesiąc. Drugie podejście to model różnicowy względem baseline'u store-dzień, który częściowo zdejmuje poziom. Trzecie — więcej danych zewnętrznych i dłuższa historia.

**Na co uważać:** nie mów „wystarczy dodać 10% do prognozy”; bias nie jest stały — w fold_3 wynosił -1,6%, w fold_2 -10,3% (dla ensemble). Kalibracja musi być monitorowana.

---

## 8. Jak oceniłeś jakość danych i co zrobiłeś z brakami?

**Odpowiedź.** Rozdzieliłem braki na trzy typy. Strukturalne: `Promo2Since*` i `PromoInterval` brakują dla 544 sklepów, bo `Promo2 = 0` — nie imputuję, tylko ustawiam flagę `Promo2Active = 0`. Nieznane: `CompetitionDistance` brakuje dla 3 sklepów — imputuję medianą i dodaję flagę. `CompetitionOpenSince*` brakuje dla 354 sklepów — zostawiam jako nieznane (`-1`), bo wymyślona data byłaby gorsza niż brak informacji. Osobno: 11 brakujących `Open` w teście uzupełniam modalnym stanem sklepu i flagą. Do tego 8 automatycznych kontroli: unikalność `(Store, Date)`, zgodność liczby wierszy po JOIN, brak ujemnej sprzedaży, ciągłość dat, pokrycie sklepów. Wynik zapisuję w `data_quality.json`.

**Na co uważać:** nie mów „uzupełniłem braki średnią”, bo to nieprawda i byłoby metodologicznie słabe.

---

## 9. Po co SQL i Power BI, skoro analiza jest w Pythonie?

**Odpowiedź.** SQL pokazuje, że potrafię pracować z danymi w silniku relacyjnym, a nie tylko w pandas. Model to prosta gwiazda: fakt `train_sales` i wymiary `stores` oraz `test_sales`. 13 zapytań używa JOIN, GROUP BY, CTE i funkcji okna: ranking sklepów z `RANK()`, wzrost miesiąc do miesiąca z `LAG()`, udział w sprzedaży z `SUM() OVER ()`, średnia krocząca 28 dni z ramką `ROWS BETWEEN`. Power BI z kolei jest warstwą decyzyjną: specyfikacja modelu, relacji i 30+ miar DAX, w tym RMSPE i WAPE. Nie dostarczyłem pliku PBIX, bo Power BI Desktop nie był dostępny w środowisku — zamiast fikcyjnego pliku dałem pełną specyfikację, eksporty CSV i makiety. To jest uczciwe: rekruter może odtworzyć dashboard w 15 minut.

**Na co uważać:** nie twierdź, że „zbudowałem dashboard w Power BI”, jeśli plik PBIX nie istnieje; mów „zaprojektowałem i udokumentowałem dashboard oraz makiety”.

---

## 10. Jak wyglądałoby wdrożenie produkcyjne i co byś zrobił dalej?

**Odpowiedź.** Wdrożenie wymagałoby czterech elementów, których projekt nie ma. Po pierwsze, harmonogramu: model odświeżany co tydzień na nowych danych, z wersjonowaniem cech i modelu. Po drugie, monitoringu: RMSPE i bias na bieżąco, alert przy przekroczeniu progu, rozbicie na sklepy i formaty. Po trzecie, kalibracji: faktor korygujący poziom, estymowany na ostatnim oknie i aktualizowany. Po czwarte, danych zewnętrznych: pogoda, wydarzenia lokalne, otwarcia konkurencji, dostępność towaru. Od strony inżynierskiej dodałbym MLflow lub DVC do śledzenia eksperymentów, testy integracyjne na danych produkcyjnych i kontener. W samym modelu największy potencjał widzę w hierarchicznej rekoncyliacji (sklep → region → sieć) oraz w rozszerzeniu obecnego ensemble o las losowy i model liniowy per segment.

**Na co uważać:** nie opowiadaj o Kubernetes i chmurze, jeśli projekt tego nie zawiera; mów o tym jako o planie, nie o doświadczeniu.

---

## Dodatkowe pytania, na które warto być przygotowanym

* **Czym różni się feature importance od wpływu przyczynowego?** Importance mówi, jak często cecha poprawia podział w drzewach; nie mówi, co się stanie, gdy interwencyjnie zmienisz promocję.
* **Dlaczego SARIMAX wygrał na sklepie 1, a przegrał globalnie?** Bo jest dopasowany do jednej serii; globalny model dzieli siłę między 1 115 sklepów i nie może poświęcić całej pojemności jednemu.
* **Jak dobrałbyś hiperparametry?** Grid/random search na foldach 1-3, z ograniczonym budżetem, nigdy na holdoucie.
* **Co byś zrobił, gdyby w teście pojawił się nowy sklep?** Fallback na średnią według formatu i asortymentu; model nie ma historii, więc prognoza byłaby niepewna.
* **Dlaczego 54 wiersze z zerową sprzedażą przy otwartym sklepie są wyłączone?** Bo RMSPE dzieli przez zero, a zerowa sprzedaż przy otwartym sklepie to najprawdopodobniej błąd danych lub chwilowe zamknięcie, nie popyt.
