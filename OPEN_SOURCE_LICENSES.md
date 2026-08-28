# LION — Open Source License Inventory

**Stan obserwacji:** 2026-08-28  
**Baseline:** `master@7adb0de8036e98f346d7ecac113876157c2abebf`  
**Zakres:** repozytorium `DonkeyJJLove/ai_platform`, zarejestrowane laboratoria LION oraz bezpośrednio wykryte komponenty/tooling open source.

> Ten plik jest inwentarzem zgodności, a nie opinią prawną i nie zmienia licencji żadnego projektu.

## 1. Licencja samego LION / ai_platform

Na badanym baseline **nie znaleziono root `LICENSE`** dla `DonkeyJJLove/ai_platform`.

W konsekwencji:

```text
PUBLIC REPOSITORY != OPEN-SOURCE LICENSE
NO ROOT LICENSE -> NOASSERTION FOR FIRST-PARTY LION CODE
```

Ten commit **nie relicencjonuje LION** i nie dopisuje automatycznie MIT/Apache/GPL do kodu first-party. Wybór licencji dla samego `ai_platform` jest odrębną decyzją właściciela praw i powinien zostać wykonany jawnie.

## 2. Status licencji laboratoriów / repozytoriów ekosystemu

Poniższy stan został sprawdzony bezpośrednio w publicznych repozytoriach wskazanych przez [`cyber_lion/registry/repositories.json`](cyber_lion/registry/repositories.json).

| Repozytorium | Zaobserwowana licencja | Status | Uwagi |
| --- | --- | --- | --- |
| `DonkeyJJLove/ai_platform` | brak root `LICENSE` | `NOASSERTION` | publiczne repo nie jest przez to automatycznie open source |
| `DonkeyJJLove/chunk-chunk` | MIT | `METADATA_INCOMPLETE` | plik `LICENSE` zawiera standardowy tekst MIT, ale copyright ma placeholder `[ROK] [IMIĘ I NAZWISKO / NAZWA ORGANIZACJI]` |
| `DonkeyJJLove/glitchlab` | MIT | `VERIFIED_FILE` | root `LICENSE`, copyright `2025 GlitchLab` |
| `DonkeyJJLove/HA2D` | brak root `LICENSE` | `NOASSERTION` | nie przyjmować licencji na podstawie publiczności repo |
| `DonkeyJJLove/hipotezy_nadawcze_LLM` | brak root `LICENSE` | `NOASSERTION` | research source, ale bez jawnej licencji reuse |
| `DonkeyJJLove/mosaic_lab_pro.py` | Apache-2.0 | `VERIFIED_FILE` | root `LICENSE` z Apache License 2.0 |
| `DonkeyJJLove/sbom` | brak root `LICENSE` | `NOASSERTION` | integracja kodu wymaga osobnego ustalenia praw |
| `DonkeyJJLove/swarm` | MIT deklarowana w `README.md` | `CLAIM_ONLY_FILE_MISSING` | README odsyła do `LICENSE`, ale root `LICENSE` na badanym branchu nie istnieje; naprawić przed redystrybucją/reuse |
| `DonkeyJJLove/SymulacjaKaskadySieciowej` | Apache-2.0 | `VERIFIED_FILE` | root `LICENSE` z Apache License 2.0 |
| `DonkeyJJLove/writeups` | brak root `LICENSE` | `NOASSERTION` | materiał publikacyjny/research wymaga osobnej decyzji licencyjnej |

### Reguła integracyjna

`NOASSERTION`, brak pliku licencji albo sprzeczność README↔LICENSE nie oznacza automatycznie `DENY` dla prywatnej analizy. Oznacza jednak **brak podstaw do automatycznego kopiowania, vendoringu, dystrybucji albo traktowania kodu jako open-source dependency** bez wyjaśnienia statusu.

## 3. Bezpośrednio wykryte komponenty i tooling open source w ai_platform

| Komponent | Użycie / lokalizacja | Wersja/ref obserwowany w repo | Licencja upstream | Klasa |
| --- | --- | --- | --- | --- |
| PlantUML | vendored binary `.lion/tools/plantuml/plantuml-1.2026.6.jar` | `1.2026.6` | GPL-3.0 | `BUNDLED_BINARY` |
| `actions/checkout` | GitHub Actions | `@v6` (m.in. Bandit workflow) | MIT | `CI_ACTION` |
| `actions/setup-python` | GitHub Actions | `@v6` | MIT | `CI_ACTION` |
| `actions/upload-artifact` | GitHub Actions | workflow-dependent | MIT | `CI_ACTION` |
| Bandit / `PyCQA/bandit` | security scan installed by CI | `1.9.4` | Apache-2.0 | `CI_TOOL` |

### PlantUML

Repozytorium zawiera skompilowany artefakt PlantUML. Upstream `plantuml/plantuml` publikuje kod na warunkach **GNU GPL v3**. Ponieważ artefakt jest vendored w repozytorium, jego redystrybucja powinna zachowywać właściwe notice/licence obligations oraz wymogi GPL dotyczące Corresponding Source w zakresie, w jakim mają zastosowanie do sposobu dystrybucji.

Wniosek architektoniczny: PlantUML powinien pozostawać **narzędziem odseparowanym od first-party LION code**, a jego presence w repo nie może być interpretowane jako nadanie GPL całemu LION. Granica i sposób agregacji muszą być zachowane oraz przeglądane przed packaging/release.

### GitHub Actions i Bandit

`actions/checkout`, `actions/setup-python` i `actions/upload-artifact` mają upstreamowy tekst MIT. Bandit ma upstreamowy Apache-2.0. Są to narzędzia/akcje CI, a nie automatyczne źródło licencji dla first-party source tree.

## 4. Zewnętrzne projekty badawcze / planowane integration surfaces

Nie każdy projekt analizowany w dokumentacji LION jest dependency. Przykład: **Artisan** jest wskazywany w researchu The Bean Factory jako potencjalny integration surface dla roast telemetry i pozostaje projektem AGPL-3.0. Dopóki kod Artisan nie jest vendored/importowany jako część LION, należy klasyfikować go jako `RESEARCHED_EXTERNAL_COMPONENT`, nie jako bieżący dependency.

Jeżeli dojdzie do integracji komponentu copyleft/AGPL, preferowana ścieżka projektowa powinna jawnie rozdzielać proces/protokół/API od proprietary/first-party core i przejść formalny OSS review. Sama separacja procesowa nie zastępuje analizy prawnej konkretnego sposobu dystrybucji i modyfikacji.

## 5. Minimalny kontrakt OSS dla nowych zależności

Każdy nowy third-party component, vendored binary, container image, GitHub Action albo kod przejmowany z repo laboratoryjnego powinien posiadać co najmniej:

```text
component_name
source_repository
version_or_exact_commit
artifact_digest (jeżeli bundlowany)
SPDX_license_id albo NOASSERTION
license_source_ref
copyright_notice
usage_class
  BUNDLED
  RUNTIME_DEPENDENCY
  BUILD_DEPENDENCY
  CI_ONLY
  RESEARCH_ONLY
distribution_mode
modification_state
source_offer_or_source_location (jeżeli wymagane)
compatibility_review_status
reviewed_at
```

Przed release/distribution wymagane jest usunięcie stanów niejednoznacznych dla komponentów rzeczywiście dystrybuowanych.

## 6. License gates

Zalecane bramki w CI/release:

```text
BUNDLED + NOASSERTION -> DENY RELEASE
BUNDLED + LICENSE_FILE_MISSING -> DENY RELEASE
COPYLEFT + UNKNOWN_DISTRIBUTION_BOUNDARY -> REVIEW_REQUIRED
LICENSE_TEXT != DECLARED_SPDX -> DENY / CONFLICTED
DEPENDENCY_VERSION_CHANGED -> RECHECK LICENSE + NOTICE
VENDORED_BINARY_CHANGED -> RECHECK DIGEST + SOURCE + LICENSE
FIRST_PARTY_ROOT_LICENSE_MISSING -> DO NOT CLAIM PROJECT IS OPEN SOURCE
```

SBOM powinien rejestrować licencję jako własność komponentu, nie całego produktu. License evidence powinno być versioned/current i podlegać supersession przy zmianie wersji dependency.

## 7. Naprawy wskazane przez ten audyt

1. **`ai_platform`** — właściciel praw powinien jawnie zdecydować, czy LION ma otrzymać licencję open-source; do tego czasu pozostaje `NOASSERTION`.
2. **`chunk-chunk`** — uzupełnić placeholder copyright w MIT LICENSE.
3. **`swarm`** — dodać rzeczywisty `LICENSE` zgodny z deklaracją MIT w README albo poprawić deklarację README.
4. **Vendored PlantUML** — utrzymywać wersję, digest, upstream source i GPL notice w inventory/SBOM.
5. **Release pipeline** — dodać automatyczny license/SBOM gate przed dystrybucją artefaktów.

## 8. Źródła upstream zweryfikowane przy aktualizacji

- `plantuml/plantuml` — root `LICENSE`: GNU General Public License v3.
- `actions/checkout` — root `LICENSE`: MIT.
- `actions/setup-python` — root `LICENSE`: MIT.
- `actions/upload-artifact` — root `LICENSE`: MIT.
- `PyCQA/bandit` — root `LICENSE`: Apache License 2.0.
- `DonkeyJJLove/glitchlab` — root `LICENSE`: MIT.
- `DonkeyJJLove/chunk-chunk` — root `LICENSE`: MIT text z nieuzupełnionym placeholderem copyright.
- `DonkeyJJLove/mosaic_lab_pro.py` — root `LICENSE`: Apache License 2.0.
- `DonkeyJJLove/SymulacjaKaskadySieciowej` — root `LICENSE`: Apache License 2.0.
- `DonkeyJJLove/swarm` — README deklaruje MIT, root `LICENSE` nie znaleziony.

---

**Zasada końcowa:** license provenance jest częścią supply-chain provenance. `CODE PRESENT` nie znaczy `RIGHT TO REDISTRIBUTE`, tak jak `CAPABILITY PRESENT` nie znaczy `AUTHORITY TO EXECUTE`.