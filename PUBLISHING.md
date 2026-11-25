# Publikacja — GitHub i portfolio

> **Status:** repo `kicporr/Rossmann-Sales-Forecasting` jest publiczne, CI zielone, release `v1.0.0` utworzony, a strona wdrożona na Cloudflare Pages. Pozostaje ręczne wgranie social preview w GitHub Settings (API tego nie udostępnia).

Repozytorium jest zainicjalizowane, ma commit i tag `v1.0.0`. Poniżej są kroki odtwarzalne od zera.

## 1. GitHub — utworzenie repo i push

1. Wejdź na [github.com/new](https://github.com/new).
2. Nazwa: `Rossmann-Sales-Forecasting`.
3. Widoczność: **Public**.
4. **Nie** dodawaj README, `.gitignore` ani licencji — one już są w lokalnym repo.
5. Utwórz repo, a potem w katalogu projektu:

```bash
cd rossmann-sales-forecasting

git remote add origin https://github.com/kicporr/Rossmann-Sales-Forecasting.git
git push -u origin main
git push origin v1.0.0
```

6. W **Settings → General → About** wklej opis i topics z `docs/github-metadata.md`.
7. W **Settings → Social preview** wgraj `docs/social-preview.png`.
8. W **Releases** utwórz release z tagu `v1.0.0`; treść weź z `CHANGELOG.md`.
9. Sprawdź, że zakładka **Actions** pokazuje zielony workflow `tests`. Testy feature'owe pominą się bez danych (`11 passed, 6 skipped`), bo Kaggle nie jest w repo — to oczekiwane.

Po pushu sprawdź:

- `https://github.com/kicporr/Rossmann-Sales-Forecasting` otwiera się publicznie.
- README renderuje badges i obrazki.
- `submission.csv` jest w repo, ale `data/raw`, `data/processed`, `outputs/models` i `dashboard/data/*.csv` — nie.
- Link do case study w README działa po wdrożeniu strony (krok 2).

## 2. Portfolio — wdrożenie case study

**Natywna integracja jest już wykonana** w lokalnym projekcie `Desktop/Portfolio/site-v2`:

- `src/data/projects.ts` i `src/data/en/projects.ts` — czwarty projekt w workbenchu i na liście prac,
- `src/data/rossmannCase.ts` i `src/data/en/rossmannCase.ts` — pełne case studies PL/EN,
- `src/data/caseStudies.ts` i `src/data/en/caseStudies.ts` — wpis w routingu `/projekty/rossmann/` i `/en/projects/rossmann/`,
- `src/components/CaseStudyView.astro` — obsługa okładki i obrazów w sekcjach,
- `src/components/PageBackdrop.astro` + `src/data/traces.ts` — tło z przebiegiem sprzedaży,
- `src/data/ui.ts` — `01-04`, „Cztery pytania. Cztery dowody.”,
- `public/img/rossmann-*` — okładka, wykresy, screeny dashboardu i OG image.

Build został już wykonany: `site-v2/dist` zawiera oba adresy i sitemapę. Wystarczy wdrożyć `dist` przez Cloudflare Pages (direct upload) albo wypchnąć repo strony, jeśli jest podłączone do Cloudflare. Nie ma potrzeby ręcznego kopiowania plików.

Jeśli wdrażasz starsze repo `site` albo chcesz wariant `public/`, użyj `portfolio/INTEGRACJA.md`: tam są gotowe pliki HTML, CSS i snippety do strony głównej.

```bash
cd Desktop/Portfolio/site-v2
npm run build
# wgraj zawartość dist/ przez Cloudflare Pages
```

## 3. Weryfikacja po deployu

- [ ] `/projekty/rossmann/` i `/en/projects/rossmann/` zwracają 200.
- [ ] Przełącznik PL/EN działa w obie strony.
- [ ] Wszystkie 5 obrazów ma `naturalWidth > 0`.
- [ ] Na 390 px `scrollWidth === clientWidth`.
- [ ] Karta na stronie głównej prowadzi do case study.
- [ ] Kicker mówi `01-04`.
- [ ] OG image `/img/rossmann-og.png` ma 1200×630 i 200.
- [ ] Link do repo w README i w case study prowadzi do publicznego repo.
- [ ] Release `v1.0.0` jest widoczny.

## 4. Czego nie robić

- Nie commituj `data/raw`, `data/processed`, `outputs/models`, `outputs/predictions` ani `dashboard/data/*.csv` — to dane Kaggle lub artefakty pochodne.
- Nie wgrywaj `.pbix`, którego nie ma; dashboard jest specyfikacją, nie plikiem.
- Nie wysyłaj submission na Kaggle bez własnego konta i świadomej zgody.
- Nie zmieniaj wyniku `0.1381` na „accuracy 86%” — to RMSPE na holdoucie, nie accuracy.

## 5. Rollback

- GitHub: `git revert <commit>` albo usuń repo w Settings → Danger Zone.
- Portfolio: cofnij zmiany w `site-v2` (dane projektów, case studies, UI, obrazy) i ponownie zbuduj `dist`; Cloudflare wdroży poprzednią wersję.
- Tag: `git tag -d v1.0.0` lokalnie i `git push origin :refs/tags/v1.0.0` na zdalnym (jeśli release nie jest potrzebny).
