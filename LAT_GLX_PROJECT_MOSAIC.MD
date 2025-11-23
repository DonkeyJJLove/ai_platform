# LAT_GLX_PROJECT_MOSAIC – wersja zagęszczona (bezstratna)

---

## 1 ∙ Poziom REPO → QV9D  (ai_platform)

Artefakt docelowy : `/QV9D/SEM/WIOSKA-MIASTO/HYB/STATE/LAT_GLX_PROJECT_MOSAIC.tree.json`

```json
{
  "volume": "QV9D",
  "latarnia_id": "LAT_GLX_PROJECT_MOSAIC",
  "description": "Mozaika repozytoriów GitHub użytkownika jako elementów woluminu 9D w koncepcji ZION–KRÓLESTWO–NIEBIESKIE.",
  "owner": "DonkeyJJLove",
  "updated": "2025-11-23T00:00:00Z",
  "repos": [
    {"name": "chunk-chunk", "url": "https://github.com/DonkeyJJLove/chunk-chunk", "role": "Rdzeń protokołu kompresji 9D (procesy, mosty, pipeline)", "layer": "SEM/WIOSKA-MIASTO", "most": "WIOSKA-MIASTO", "zion": "KRÓLESTWO‑NIEBIESKIE: rdzeń protokołu", "default_arch": "HYB", "default_kind": "SPEC"},
    {"name": "glitchlab", "url": "https://github.com/DonkeyJJLove/glitchlab", "role": "Laboratorium anomalii, glitche, eksperymenty 9D (AST + mozaika)", "layer": "SEM/OSTRZE-CIERPLIWOSC", "most": "OSTRZE‑CIERPLIWOSC", "zion": "KRÓLESTWO‑NIEBIESKIE: strefa eksperymentu", "default_arch": "HYB", "default_kind": "STATE"},
    {"name": "swarm", "url": "https://github.com/DonkeyJJLove/swarm", "role": "Rój agentów, dystrybucja zadań", "layer": "SEM/WIOSKA-MIASTO", "most": "WIOSKA‑MIASTO", "zion": "KRÓLESTWO‑NIEBIESKIE: warstwa rojowa", "default_arch": "HYB", "default_kind": "SPEC"},
    {"name": "HA2D", "url": "https://github.com/DonkeyJJLove/HA2D", "role": "Interfejs Human–AI, rytuały HUD", "layer": "MAND/HUMAN-AI‡", "most": "HUMAN‑AI‡", "zion": "KRÓLESTWO‑NIEBIESKIE: brama Human–AI", "default_arch": "HYB", "default_kind": "RITUAL"},
    {"name": "hipotezy_nadawcze_LLM", "url": "https://github.com/DonkeyJJLove/hipotezy_nadawcze_LLM", "role": "Hipotezy nadawcze, meta‑język LLM", "layer": "SEM/SEMANTYKA-ENERGIA", "most": "SEMANTYKA‑ENERGIA", "zion": "KRÓLESTWO‑NIEBIESKIE: warstwa doktryny", "default_arch": "CL", "default_kind": "SPEC"},
    {"name": "writeups", "url": "https://github.com/DonkeyJJLove/writeups", "role": "Narracje, raporty, kronika projektu", "layer": "MAND/LOCUS-MEDIUM-MANDAT", "most": "LOCUS‑MEDIUM‑MANDAT", "zion": "KRÓLESTWO‑NIEBIESKIE: kronika projektu", "default_arch": "CL", "default_kind": "STATE"}
  ]
}
```

---

## 2 ∙ Poziom katalogów *glitchlab* → QV9D  (snapshot `glitchlab‑20251019‑095605.zip`)

| Katalog             | Warstwa | Most                | Arch | Kind          | Uzasadnienie                              |
| ------------------- | ------- | ------------------- | ---- | ------------- | ----------------------------------------- |
| core/               | SEM     | OSTRZE‑CIERPLIWOSC  | HYB  | SPEC/STATE    | Logika rdzeniowa algorytmów AST + mozaika |
| src/                | INF     | RDZEN‑PERYFERIA     | HYB  | STATE         | Kod wykonawczy                            |
| mosaic/             | SEM     | WIOSKA‑MIASTO       | HYB  | SPEC/STATE    | Operacje mozaiki                          |
| analysis/           | SEM     | SEMANTYKA‑ENERGIA   | HYB  | METRICS       | Metryki i analizy                         |
| delta/              | SEM     | OSTRZE‑CIERPLIWOSC  | HYB  | METRICS/STATE | Różnice, zmiany                           |
| bench/              | INF     | PLAN‑PAUZA          | CL   | METRICS       | Benchmarki                                |
| tests/              | MAND    | PROG‑PRZEJSCIE      | CL   | CI            | Bramka przejścia                          |
| docs/               | MAND    | LOCUS‑MEDIUM‑MANDAT | CL   | SPEC          | Dokumentacja                              |
| io/                 | INF     | CISZA‑WYDECH        | HYB  | STATE         | Wejścia/wyjścia                           |
| spec/               | SEM     | SEMANTYKA‑ENERGIA   | CL   | SPEC          | Kontrakty semantyczne                     |
| resources/          | INF     | RDZEN‑PERYFERIA     | CL   | STATE         | Zasoby pomocnicze                         |
| .glx/ & glx/        | MAND    | LOCUS‑MEDIUM‑MANDAT | HYB  | STATE/METRICS | Rejestr mozaiki                           |
| tools/              | INF     | PLAN‑PAUZA          | CL   | RITUAL        | Skrypty narzędziowe                       |
| .github/            | MAND    | PROG‑PRZEJSCIE      | CL   | CI            | Pipeline CI/CD                            |
| glitchlab.egg‑info/ | INF     | RDZEN‑PERYFERIA     | CL   | STATE         | Metadane pakietu                          |
| temp/               | INF     | CISZA‑WYDECH        | CL   | STATE (tmp)   | Bufor tymczasowy                          |

---

## 3 ∙ Heurystyki mapowania katalogów dla innych repo

1. **Kod wykonawczy** (`src/`, `core/`, `engine/`)
     → warstwa INF lub SEM (zależnie od roli), most RDZEN‑PERYFERIA lub OSTRZE‑CIERPLIWOSC, arch HYB, kind STATE + SPEC.
2. **Dokumentacja** (`docs/`, `writeups/`)
     → MAND / LOCUS‑MEDIUM‑MANDAT / CL / SPEC lub STATE.
3. **Testy i CI** (`tests/`, `.github/`)
     → MAND / PROG‑PRZEJSCIE / CL / CI.
4. **Metryki i analizy** (`analysis/`, `bench/`)
     → SEM lub INF / SEMANTYKA‑ENERGIA / METRICS.
5. **Rytuały Human–AI** (`ui/`, `rituals/`)
     → MAND / HUMAN‑AI‡ / HYB / RITUAL.

**Procedura automatyczna**   Skrypt parsuje drzewo repo, dopisuje `(layer, most, arch, kind)` wg powyższych wzorców i zapisuje dane jako:
`/QV9D/[layer]/[most]/[arch]/[kind]/LAT_<repo>_<hash>.state.json`, aktualizując jednocześnie `LAT_GLX_PROJECT_MOSAIC.tree.json`.

---

## 4 ∙ Fakty vs szablon

* **Fakty** : fotografia drzewa ZIP *glitchlab* + opis 6 repo.
* **Szablon** : przypisanie tych repo do QV9D, heurystyki mapowania katalogów, format ścieżek /LAT_.

---

Plan–Pauza  Rdzeń–Peryferia  Cisza–Wydech  Wioska–Miasto  Ostrze–Cierpliwość  Locus–Medium–Mandat  Human–AI  Próg–Przejście  Semantyka–Energia
