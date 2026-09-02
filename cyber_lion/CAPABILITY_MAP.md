# CYBER-LION — mapa capabilities

Capability jest definiowana jako wielokrotnego użytku zdolność do rozwiązywania określonej klasy problemów. Nie jest tożsama z repozytorium, usługą ani zapamiętanym workflow.

## Graf capabilities

```text
OBSERWACJA
  ├─ ingest telemetrii ..................... swarm
  ├─ obserwacja stanu software ............. sbom
  ├─ obserwacja kodu/delty ................. glitchlab
  └─ retrieval badań/evidence .............. writeups

STRUKTURYZACJA
  ├─ AST / graf zależności ................. glitchlab
  ├─ graf wielopoziomowy / abstrakcja λ .... mosaic_lab_pro.py
  └─ mapowanie semantyczne QV9D ............ ai_platform + chunk-chunk

REPREZENTACJA STANU / KONTEKSTU
  ├─ HMK-9D Δ / relacje 9D ................. chunk-chunk
  ├─ PCE / MCV / SNAP / revision ........... HA2D
  └─ tożsamość w czasie .................... sbom/AID

GENEROWANIE / TESTOWANIE HIPOTEZ
  ├─ jawne badania falsyfikacyjne .......... hipotezy_nadawcze_LLM
  ├─ analiza anomalii/niezgodności modeli .. glitchlab
  └─ korpus evidence ....................... writeups

SYMULACJA
  └─ scenariusze / MC / Morris / Sobol ..... SymulacjaKaskadySieciowej

AUTORYZACJA
  ├─ evidence bramki CI .................... sbom
  ├─ lokalne inwarianty / Guard ............ glitchlab
  ├─ Kubernetes RBAC ....................... swarm
  └─ TARGET wspólnych kontraktów mandate ... ai_platform

WYKONANIE
  ├─ rozproszony runtime usług .............. swarm
  ├─ pipeline'y analizy/naprawy kodu ........ glitchlab
  ├─ aggregate effect budget ................ ai_platform / FleetEffectBudgetStore [VERIFIED candidate]
  └─ TARGET workerów sandbox/tool ........... swarm adapters

OBSERWACJA WYNIKU / REPLAY
  ├─ telemetria / trace'y ................... swarm
  ├─ EGDB / koncepcje historii delty ........ glitchlab
  ├─ analityka czasu zdarzeń ................ sbom
  ├─ koncepcja revision viewer .............. HA2D
  └─ TARGET cross-repo replay ............... ai_platform contract + adapters
```

## Model ownership capabilities

| Capability | Główny owner | Providerzy/adaptery | Status docelowy |
|---|---|---|---|
| Tożsamość encji | kontrakt `ai_platform` | adapter AID `sbom` | NEW shared contract |
| Koperta provenance | kontrakt `ai_platform` | `sbom`, `glitchlab`, `writeups` | GENERALIZE |
| Typowana koperta zdarzenia | kontrakt `ai_platform` | wszystkie repo | NEW shared contract |
| Capability registry | `ai_platform` | manifesty providerów | NEW |
| Mapowanie QV9D | `ai_platform` | `chunk-chunk`, lokalne manifesty | REFINE |
| Kompresja kontekstu | `chunk-chunk` | przyszły adapter API | EXPERIMENTAL→FORMALISE |
| Stan poznawczy | `HA2D` | adapter pamięci | SPEC→CONTRACT |
| Ekstrakcja grafu strukturalnego | `glitchlab` | `mosaic_lab_pro.py` | KEEP |
| Abstrakcja λ / supergraf | `mosaic_lab_pro.py` | adapter grafu GlitchLab | EXTRACT |
| Analiza delty/anomalii | `glitchlab` | lokalni providerzy | KEEP |
| Rekordy evidence hipotez | schema `ai_platform` | `hipotezy`, `writeups` | NEW metadata contract |
| Symulacja | `SymulacjaKaskadySieciowej` | adapter scenariuszy | WRAP |
| Decyzja policy/gate | kontrakt `ai_platform` | lokalne Guard/RBAC/bramki CI | NEW common decision model |
| Aggregate effect budget | `ai_platform` | `FleetEffectBudgetStore`, `RepositoryMutationPEP` | VERIFIED candidate; restrictive only |
| Rozproszone wykonanie | `swarm` | adaptery tool/sandbox | KEEP + REFINE |
| Evidence supply-chain | `sbom` | zdarzenia AID/BOM | KEEP |
| Evidence badawcze | `writeups` | adapter metadanych/indeksu | KEEP + INDEX |
| Obserwowalność cross-repo | kontrakt `ai_platform` | eksportery swarm/glitchlab/sbom | NEW |
| Replay | kontrakt `ai_platform` | event stores + viewer HA2D | NEW |

## Ważne nierównoważności

### Tożsamość nie jest adresem

```text
pod IP != service name != workload identity != entity identity != authority
```

Tożsamość sieciowa `swarm`, AID z `sbom`, identyfikatory Latarni QV9D i tożsamości kontekstu HA2D reprezentują różne mechanizmy. Wymagają korelacji, a nie bezwarunkowego ujednolicenia.

### Lokalny rejestr nie jest globalnym capability registry

Callable registry GlitchLab jest użyteczny wewnątrz GlitchLab. Nie może stać się rejestrem całego systemu przez samo rozszerzenie namespace. Cyber-Lion potrzebuje osobnego rejestru descriptorów capabilities, wersji, kontraktów i wymaganego authority.

### Reprezentacja grafowa nie jest prawdą semantyczną

GlitchLab i Mosaic Lab mogą tworzyć reprezentacje strukturalne. QV9D może przypisywać współrzędne semantyczne. Transformacja grafu lub abstrakcja λ jest operacją reprezentacji; nie może po cichu tworzyć evidence ani authority.

### Istnienie bramki nie oznacza zastosowania bramki

Plik polityki, reguła CI lub obiekt RBAC nie dowodzą, że consequential transition rzeczywiście przez nie przeszło. Cyber-Lion wymaga applied gate event powiązanego z tożsamością wykonania i receiptem.

### Budżet efektów nie jest authority

Zweryfikowany candidate `FLEET_AGGREGATE_EFFECT_BUDGET_ENFORCEMENT` jest dodatkowym ograniczeniem admission, a nie źródłem uprawnienia. Literalne evidence jest związane z `PR#249`, dedicated run `33615802655` i full Core run `33615802648`.

```text
CAN_RESTRICT_AUTHORITY=YES
CAN_CREATE_AUTHORITY=NO
CAN_EXPAND_AUTHORITY=NO
CAN_SUBSTITUTE_AUTHORITY=NO

valid authority + no budget => DENY
budget + no authority => DENY
```

Zweryfikowana capability obejmuje atomową rezerwację oraz limity `max_concurrent_writers`, `max_active_repository_effects`, `max_active_branch_effects` i `max_active_path_effects`. Nie dowodzi distributed consensus, globalnej multi-host linearizability journala, monetary/token budget ani production deployment. `RepositoryMutationPEP` pozostaje `SINGLE_RUNTIME_ATTACH_ONLY`; stan tej capability jest `VERIFIED` candidate, nie `INTEGRATED` ani `OBSERVED`.

## Reguła dynamicznej kompozycji

Nowy workflow powinien być składany z capabilities dopiero wtedy, gdy control plane potrafi odpowiedzieć:

```text
Jaka capability jest wymagana?
Który provider ją implementuje?
Jaką wersję kontraktu udostępnia?
Jaka tożsamość ją wykonuje?
Jakie wejścia i provenance konsumuje?
O jakie authority może wnioskować?
Jaka bramka jest wymagana?
Jakie zdarzenia i evidence zostaną wyemitowane?
Czy wynik można odtworzyć przez replay?
```

Jeżeli na te pytania nie da się odpowiedzieć, capability może być co najwyżej wykrywalna do celów analitycznych; nie kwalifikuje się do wykonania powodującego skutki.
