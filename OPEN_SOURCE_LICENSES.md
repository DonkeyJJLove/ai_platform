# LION — Open Source License Inventory & Superkrowa Manifest

**Stan:** 2026-10-05  
**Zakres:** `DonkeyJJLove/ai_platform`, zarejestrowane laboratoria LION oraz bezpośrednio wykryte komponenty/tooling open source.  
**Polityka:** first-party LION jest open source. Third-party zachowuje własne licencje upstream.

> Ten plik jest inwentarzem zgodności, polityką projektu i manifestem technologicznym. Nie zastępuje tekstu licencji znajdującego się w root `LICENSE` danego repozytorium. W razie rozbieżności wiążący jest właściwy plik `LICENSE` oraz prawa do konkretnych składników.

---

## 1. Deklaracja: LION jest open source

LION nie jest już publicznym repozytorium bez rozstrzygniętej licencji. Kod first-party w zarejestrowanym ekosystemie został doprowadzony do jawnego modelu open-source.

Nie obowiązuje już:

```text
PUBLIC REPOSITORY != OPEN-SOURCE LICENSE
NO ROOT LICENSE -> NOASSERTION FOR FIRST-PARTY LION CODE
```

Obowiązuje:

```text
FIRST-PARTY LION -> EXPLICIT OPEN-SOURCE LICENSE
THIRD-PARTY -> KEEP UPSTREAM LICENSE
LICENSE PROVENANCE -> PART OF SUPPLY-CHAIN PROVENANCE
```

Domyślną licencją dla wcześniej nieokreślonego kodu first-party w tym ekosystemie jest **Apache License 2.0**, chyba że dane repozytorium posiada jawnie zachowaną licencję MIT albo inną kompatybilną licencję open-source. Apache-2.0 została wybrana dla głównych projektów infrastrukturalnych ze względu na szerokie prawa do użycia, modyfikacji i redystrybucji oraz jawny grant patentowy.

To nie jest próba „przelicencjonowania internetu”. LION nie zmienia licencji PlantUML, Bandita, GitHub Actions, Artisan ani żadnego innego komponentu, do którego prawa należą do upstreamu. Open source first-party i zgodność third-party są dwiema różnymi warstwami.

## 2. Status repozytoriów first-party

| Repozytorium | Licencja | Status |
| --- | --- | --- |
| `DonkeyJJLove/ai_platform` | Apache-2.0 | `OPEN_SOURCE` |
| `DonkeyJJLove/chunk-chunk` | MIT | `OPEN_SOURCE` |
| `DonkeyJJLove/glitchlab` | MIT | `OPEN_SOURCE` |
| `DonkeyJJLove/HA2D` | Apache-2.0 | `OPEN_SOURCE` |
| `DonkeyJJLove/hipotezy_nadawcze_LLM` | Apache-2.0 | `OPEN_SOURCE` |
| `DonkeyJJLove/mosaic_lab_pro.py` | Apache-2.0 | `OPEN_SOURCE` |
| `DonkeyJJLove/sbom` | Apache-2.0 | `OPEN_SOURCE` |
| `DonkeyJJLove/swarm` | MIT | `OPEN_SOURCE` |
| `DonkeyJJLove/SymulacjaKaskadySieciowej` | Apache-2.0 | `OPEN_SOURCE` |
| `DonkeyJJLove/writeups` | Apache-2.0 | `OPEN_SOURCE` |

`chunk-chunk` zachowuje MIT, ale placeholder copyright został zastąpiony rzeczywistą atrybucją projektu. `swarm` zachowuje deklarowany wcześniej w README model MIT i posiada teraz faktyczny root `LICENSE`.

## 3. Manifest Superkrowy

**SUPERKROWA** nie jest nazwą modelu governance. To antybiurokratyczny znacznik projektu: jeżeli system jest tak skomplikowany, że do uruchomienia eksperymentu potrzeba pięciu komitetów, siedmiu akceptacji i dwunastu dokumentów, to problemem nie jest brak kolejnego formularza. Problemem jest architektura.

Superkrowa oznacza budowę systemów, które można obejrzeć, uruchomić, sfalsyfikować, zmodyfikować, złamać w laboratorium, naprawić i uruchomić ponownie. Kod ma być czytelny. Decyzje mają zostawiać ślad. Zależności mają mieć pochodzenie. Agent ma mieć granice. Eksperyment ma mieć reprodukowalność. Nie interesuje nas magia demonstracyjna; interesuje nas system, który wytrzymuje kontakt z rzeczywistością.

Hasło jest proste:

> **Nie chowaj inteligencji za rytuałem. Pokaż mechanizm. Pokaż kod. Pokaż granicę. Pokaż dowód.**

Open source jest tu elementem epistemologii, a nie wyłącznie modelem dystrybucji. Jeżeli twierdzimy, że system działa, powinno być możliwe sprawdzenie, gdzie działa, dlaczego działa, kiedy przestaje działać i kto może go zmienić.

## 4. FUCK THE SYSTEM

**FUCK THE SYSTEM** w LION nie znaczy „niszcz systemy”. Znaczy: nie fetyszyzuj systemu tylko dlatego, że już istnieje.

Fuck zamknięte chokepointy, których nikt nie potrafi audytować. Fuck architekturę, w której zgodność zastępuje bezpieczeństwo. Fuck governance, które potrafi wyprodukować dokument, ale nie potrafi wyprodukować działającej granicy uprawnień. Fuck vendor lock-in jako substytut strategii. Fuck security-through-obscurity. Fuck pipeline, w którym nikt nie umie powiedzieć, skąd wziął się artefakt, model, decyzja albo dostęp.

Ale także: fuck kult chaosu. Open source nie znaczy braku odpowiedzialności. Swoboda bez provenance, SBOM, testów, granic wykonania i review jest tylko trudniejszym do audytu bałaganem.

Dlatego LION ma być otwarty **i** egzekwowalny: prawa są szerokie, ale stan systemu ma być mierzalny; kod jest dostępny, ale działania agentów mają mieć kontrolę; eksperyment jest wolny, ale wynik ma dać się odtworzyć.

## 5. AGI FIRST

**AGI FIRST** to zasada projektowa: kiedy podejmujemy decyzję architektoniczną, pytamy najpierw, czy ma ona sens w świecie, w którym inteligencja maszynowa jest tańsza, szybsza, bardziej autonomiczna i obecna praktycznie wszędzie.

Nie projektujemy platformy wyłącznie dla dzisiejszego chatbota. Projektujemy dla świata agentów wykonujących zadania wieloetapowe, używających narzędzi, kodu, pamięci, danych, sieci i delegowanej władzy. To oznacza, że provenance, semantyka uprawnień, obserwowalność, odwoływalność decyzji, izolacja narzędzi i rekonstruowalność wykonania nie są dodatkami. Są szkieletem.

AGI First nie znaczy **human last**. Przeciwnie: im większa autonomia systemu, tym ważniejsze stają się jawne granice odpowiedzialności, możliwość audytu i prawo człowieka do zrozumienia, zakwestionowania i zatrzymania procesu.

Open source jest naturalnym elementem tej strategii, bo przyszłej infrastruktury inteligencji nie powinno się budować jako nieweryfikowalnej czarnej skrzynki kontrolowanej wyłącznie przez kilka punktów dostępu.

## 6. KOSMOS ALBO ŚMIERĆ!

**KOSMOS ALBO ŚMIERĆ!** jest skrótem myślowym dla radykalnego wyboru między ekspansją możliwości a stagnacją.

Nie chodzi o śmierć ludzi. Chodzi o śmierć systemów, które utraciły zdolność uczenia się, eksperymentowania i przekraczania własnych ograniczeń.

Kosmos oznacza skalę problemu: autonomiczne laboratoria, robotykę, naukę wspomaganą przez AI, federacje agentów, infrastrukturę rozproszoną, nowe modele produkcji, eksplorację i budowę systemów zdolnych działać daleko poza pojedynczym workstationem, firmą czy państwem.

Jeżeli AGI ma zwiększyć zakres tego, co cywilizacja potrafi wykonać, to infrastruktura wokół niej musi być możliwa do badania i rozwijania przez więcej niż jeden zamknięty krąg dostawców. **Open source jest mechanizmem dyfuzji możliwości.**

Wersja LION:

```text
OPEN THE CODE.
OPEN THE METHOD.
VERIFY THE BOUNDARY.
KEEP THE RECEIPT.
BUILD THE INTELLIGENCE.
GO FURTHER.

AGI FIRST.
FUCK THE SYSTEM.
SUPERKROWA.
KOSMOS ALBO ŚMIERĆ!
```

## 7. Bezpośrednio wykryte komponenty i tooling open source w ai_platform

| Komponent | Użycie / lokalizacja | Wersja/ref obserwowany | Licencja upstream | Klasa |
| --- | --- | --- | --- | --- |
| PlantUML | vendored binary `.lion/tools/plantuml/plantuml-1.2026.6.jar` | `1.2026.6` | GPL-3.0 | `BUNDLED_BINARY` |
| `actions/checkout` | GitHub Actions | `@v6` | MIT | `CI_ACTION` |
| `actions/setup-python` | GitHub Actions | `@v6` | MIT | `CI_ACTION` |
| `actions/upload-artifact` | GitHub Actions | workflow-dependent | MIT | `CI_ACTION` |
| Bandit / `PyCQA/bandit` | security scan installed by CI | `1.9.4` | Apache-2.0 | `CI_TOOL` |

### PlantUML

Repozytorium zawiera skompilowany artefakt PlantUML. Upstream `plantuml/plantuml` publikuje kod na warunkach GNU GPL v3. Jego obecność nie nadaje automatycznie GPL całemu LION, ale dystrybucja bundlowanego artefaktu musi zachować obowiązki wynikające z GPL i właściwe źródła/notice.

Granica architektoniczna pozostaje jawna: PlantUML jest narzędziem third-party, a nie źródłem licencji first-party LION.

### GitHub Actions i Bandit

`actions/checkout`, `actions/setup-python` i `actions/upload-artifact` pozostają na MIT. Bandit pozostaje na Apache-2.0. Są to komponenty CI/tooling; ich licencje nie zastępują licencji kodu LION.

## 8. Zewnętrzne projekty badawcze i integration surfaces

Nie każdy projekt analizowany w dokumentacji LION jest dependency. Przykładowo Artisan może występować jako research/integration surface i zachowuje własną licencję upstream.

Zasada jest bezwzględna:

```text
WE OPEN WHAT WE OWN.
WE PRESERVE WHAT WE IMPORT.
WE DO NOT INVENT RIGHTS WE DO NOT HAVE.
```

Jeżeli dojdzie do integracji komponentu copyleft/AGPL, architektura może separować proces, protokół i API, ale separacja techniczna nie jest magicznym obejściem licencji. Konkretny model dystrybucji nadal wymaga zgodności z warunkami upstream.

## 9. Minimalny kontrakt OSS dla zależności

Każdy nowy third-party component, vendored binary, container image, GitHub Action albo kod przejmowany z innego repozytorium powinien posiadać co najmniej:

```text
component_name
source_repository
version_or_exact_commit
artifact_digest
SPDX_license_id albo NOASSERTION
license_source_ref
copyright_notice
usage_class
distribution_mode
modification_state
source_offer_or_source_location
compatibility_review_status
reviewed_at
```

Open source bez provenance jest niepełne. Reprodukowalność bez wersji jest fikcją. SBOM bez źródła prawnego jest tylko listą nazw.

## 10. License gates

```text
BUNDLED + NOASSERTION -> DENY RELEASE
BUNDLED + LICENSE_FILE_MISSING -> DENY RELEASE
COPYLEFT + UNKNOWN_DISTRIBUTION_BOUNDARY -> REVIEW_REQUIRED
LICENSE_TEXT != DECLARED_SPDX -> DENY / CONFLICTED
DEPENDENCY_VERSION_CHANGED -> RECHECK LICENSE + NOTICE
VENDORED_BINARY_CHANGED -> RECHECK DIGEST + SOURCE + LICENSE
FIRST_PARTY_ROOT_LICENSE_MISSING -> DENY RELEASE
FIRST_PARTY_NEW_REPOSITORY -> REQUIRE EXPLICIT OSS LICENSE
```

Dla nowego repozytorium first-party domyślnym wyborem jest Apache-2.0, chyba że istnieje dobry powód, aby użyć MIT albo innej licencji zatwierdzonej jako open-source.

## 11. Zasady wkładu i forkowania

Fork jest funkcją, nie zdradą. Krytyka jest funkcją, nie błędem. Eksperyment konkurencyjny jest funkcją, nie naruszeniem hierarchii.

Jeżeli ktoś potrafi zrobić LION lepiej, powinien móc to zrobić. Jeżeli ktoś potrafi wykazać błąd w heurystyce, powinien mieć możliwość opublikowania testu. Jeżeli ktoś chce uruchomić system w innym środowisku, powinien mieć legalną i techniczną drogę do wykonania tego bez proszenia o pozwolenie na sam akt eksperymentowania.

To jest praktyczny sens open source w systemach AI: dystrybucja możliwości badawczych i wykonawczych przy zachowaniu śladu pochodzenia.

## 12. Zasada końcowa

LION ma być systemem, który można otworzyć bez utraty kontroli, rozszerzyć bez utraty pochodzenia i zautomatyzować bez utraty odpowiedzialności.

```text
CODE PRESENT != AUTHORITY TO EXECUTE
PUBLIC REPOSITORY != VERIFIED SUPPLY CHAIN
OPEN SOURCE != NO GOVERNANCE
AGENT CAPABILITY != AGENT AUTHORITY

OPEN SOURCE + PROVENANCE + SEMANTIC CONTROL + EXECUTION RECEIPTS
= INTELLIGENCE THAT CAN SCALE WITHOUT BECOMING MAGIC
```

**Superkrowa nie prosi systemu o pozwolenie na myślenie. Buduje system, który można zrozumieć, sprawdzić i przekroczyć.**

**AGI First. Fuck the System. Kosmos albo śmierć!**
