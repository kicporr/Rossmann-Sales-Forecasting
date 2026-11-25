# Rossmann — integracja z portfolio

> **Status:** natywna wersja strony jest już dodana w `Desktop/Portfolio/site-v2` (PL/EN, czwarta karta, czwarte pytanie, sitemap, build w `dist`). Ten folder jest kopią zapasową i wariantem `public/` dla starszego repo `site`.

Ten folder zawiera gotową stronę case study w języku polskim i angielskim oraz snippety do dodania projektu na stronie głównej. Strona używa Twojego obecnego CSS (`page.css` to kopia `PageBackdrop.*.css`), fontów `/fonts.css` i tych samych klas co `/projekty/tfal/`, więc wygląda jak część serwisu, a nie osadzony iframe.

## Co jest w paczce

```
portfolio/
├── rossmann/
│   ├── index.html          # PL: /projekty/rossmann/
│   ├── page.css            # kopia globalnego CSS strony
│   ├── rossmann.css        # drobne poprawki (tabele, kod, brak animacji ukrywającej treść)
│   └── assets/             # cover, wykresy, screeny dashboardu, OG image
├── en/projects/rossmann/
│   └── index.html          # EN: /en/projects/rossmann/
└── snippets/
    ├── workbench-rossmann-pl.json
    ├── workbench-rossmann-en.json
    ├── question-button-pl.html
    ├── question-button-en.html
    ├── work-card-pl.html
    └── work-card-en.html
```

## Wariant A — najszybszy (public/, bez zmian w komponentach Astro)

1. Skopiuj katalogi do repo strony:

```bash
cp -r portfolio/rossmann public/projekty/rossmann
mkdir -p public/en/projects
cp -r portfolio/en/projects/rossmann public/en/projects/rossmann
```

2. Sprawdź lokalnie:

```bash
npm run dev
# http://localhost:4321/projekty/rossmann/
# http://localhost:4321/en/projects/rossmann/
```

3. Dodaj projekt do strony głównej (sekcja niżej).
4. Zbuduj i wypchnij:

```bash
npm run build
git add public/projekty/rossmann public/en/projects/rossmann
git commit -m "Add Rossmann sales forecasting case study"
git push
```

Cloudflare Pages zbuduje i opublikuje zmiany. Strona jest statyczna — nie potrzebuje nowych zależności.

> `page.css` to kopia obecnego globalnego CSS. Jeśli w przyszłości zmienisz design serwisu, podmień ten plik na nowy `PageBackdrop.*.css` albo przenieś treść do layoutu Astro (Wariant B).

## Wariant B — natywna strona Astro (opcjonalnie)

Jeśli chcesz, żeby strona dziedziczyła layout i brała udział w sitemapie:

1. Utwórz `src/pages/projekty/rossmann.astro` i `src/pages/en/projects/rossmann.astro`.
2. Przenieś zawartość `<main class="case-main">…</main>` z pliku HTML do pliku `.astro`.
3. Zaimportuj swój layout i globalny CSS w nagłówku Astro (tak jak w `src/pages/projekty/tfal.astro`).
4. Dodaj importy assetów przez `import cover from '../../../assets/rossmann-cover.webp'` albo trzymaj je w `public/` i używaj ścieżek absolutnych.
5. Nie duplikuj nawigacji i stopki — usuń je z przenoszonego HTML, zostaw tylko `<main>`.

To wariant „czystszy”, ale wymaga dostępu do repo strony. Wariant A działa bez niego.

## Strona główna — 3 miejsca do zmiany

### 1. JSON workbench (`<script id="workbench-projects">`)

W źródle Astro znajdź tablicę, która renderuje ten JSON (prawdopodobnie `src/data/projects.ts`, `src/data/workbench.ts` albo komponent strony głównej). Dodaj obiekt z:

- `snippets/workbench-rossmann-pl.json` — wersja PL,
- `snippets/workbench-rossmann-en.json` — wersja EN.

Kolejność: po `housing`, jako czwarty projekt.

### 2. Przycisk pytania w hero

Po przycisku `#q-housing` dodaj:

- `snippets/question-button-pl.html` — PL,
- `snippets/question-button-en.html` — EN.

### 3. Karta w „Wybrane prace”

Po artykule „Mieszkania a EDO” dodaj:

- `snippets/work-card-pl.html` — PL,
- `snippets/work-card-en.html` — EN.

Zmień kicker z `Wybrane prace / 01-03` na `Wybrane prace / 01-04` (EN: `Selected work / 01-03` → `01-04`). Karta jest czwarta, więc nie zmienia układu naprzemiennego.

## SEO i sitemap

- Canonical i `hreflang` są już ustawione w obu plikach.
- OG image: `assets/rossmann-og.png` (1200×630). Po deployu sprawdź podgląd na LinkedIn/Facebook.
- Jeśli używasz `@astrojs/sitemap`, strony z `public/` mogą nie trafić do sitemapy. Dodaj je ręcznie:

```js
// astro.config.mjs
sitemap({
  customPages: [
    'https://kacper-teichert.pages.dev/projekty/rossmann/',
    'https://kacper-teichert.pages.dev/en/projects/rossmann/'
  ]
})
```

- Alternatywnie zgłoś oba URL-e w Google Search Console po deployu.
- Link do case study dodaj też w `README.md` repo projektu i w opisie na LinkedIn.

## Checklist przed deployem

- [ ] `/projekty/rossmann/` otwiera się bez 404.
- [ ] `/en/projects/rossmann/` otwiera się bez 404.
- [ ] Przełącznik PL/EN prowadzi do właściwej wersji.
- [ ] Wszystkie obrazy mają `naturalWidth > 0` (zakładka Network: 200).
- [ ] Na 390 px nie ma poziomego scrolla (`scrollWidth === clientWidth`).
- [ ] Karta na stronie głównej prowadzi do `/projekty/rossmann/`.
- [ ] Kicker mówi `01-04`.
- [ ] OG image zwraca 200 i ma 1200×630.
- [ ] Sitemap zawiera oba URL-e (albo zostały zgłoszone ręcznie).
- [ ] Link `github.com/kicporr/Rossmann-Sales-Forecasting` działa po utworzeniu repo.

## Czego nie ma w paczce

- Surowych danych Kaggle (licencja) — są w `.gitignore` repo projektu.
- Pliku `.pbix` — Power BI Desktop nie był dostępny; jest specyfikacja, DAX i makiety.
- Wysyłki submission na Kaggle — wymaga Twojego konta i zgody.
