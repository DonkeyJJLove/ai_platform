# CYBER-LION — mapa migracji

Migracja jest przyrostowa i prowadzona w modelu **compatibility-first**.

```text
CURRENT
→ COMPATIBILITY
→ MIGRATION
→ TARGET
```

Żadna faza nie może usunąć działającej ścieżki legacy, dopóki jej zamiennik nie posiada testów kontraktowych, obserwowalności i evidence rollbacku.

## Faza 0 — Archeologia repozytoriów — UKOŃCZONA DLA BASELINE'U

Artefakty dostarczone w tej gałęzi:

- inwentarz repozytoriów,
- mapa capabilities,
- architektura docelowa,
- mapa kontraktów,
- model zdarzeń/danych,
- status naukowy,
- kolejność migracji.

Istniejące PR-y podnoszące jakość procesu są traktowane jako oczekujące zależności, a nie po cichu duplikowane.

## Faza 1 — Higiena repozytoriów / baseline kompatybilności

Przed federacją należy zintegrować albo supersedować bieżące PR-y hardeningowe, jeżeli pozostają poprawne:

- PR process-upgrade `ai_platform`: kanoniczny README, czystość źródeł;
- PR-y `chunk-chunk`: usunięcie śledzonego virtualenv; sanityzacja/redakcja run IDs;
- PR process-upgrade `glitchlab`: cleanup stanu generowanego/lokalnego i CI ratchet;
- PR process-upgrade `HA2D`: guard trwałego kontekstu;
- PR process-upgrade `hipotezy_nadawcze_LLM`: kontrakt falsyfikacji.

Dla pozostałych providerów należy tworzyć analogiczne kontrole source-purity i regresji tylko tam, gdzie archeologia repozytorium potwierdzi taką potrzebę.

**Kryteria wyjścia**

```text
source tree != local runtime state
canonical repository entrypoint documented
CI/test status known
no new Cyber-Lion integration built on hidden local artifacts
```

## Faza 2 — Wspólna Entity Identity

Owner: `ai_platform`  
Anchor kompatybilności: `sbom/AID`

Dodaj wersjonowany schemat Entity Identity oraz adapter z AID.

**Nie** zastępuj pól AID. Udowodnij kompatybilność round-trip:

```text
AID event
→ Entity Envelope adapter
→ Cyber-Lion event
→ extract original AID
== original AID
```

**Testy**

- walidacja schematu,
- rozdzielenie stabilnej tożsamości od version/ref,
- obsługa invalid/unknown owner,
- AID round trip,
- zakaz traktowania adresu sieciowego jako tożsamości.

## Faza 3 — Wspólny Event Schema

Owner: `ai_platform`.

Zaimplementuj wersjonowaną event envelope i typowane nazwy zdarzeń. Najpierw utwórz adaptery dla:

1. zdarzeń SBOM,
2. zdarzeń delta/BUS GlitchLab,
3. telemetrii Swarm,
4. zdarzeń wyników symulatora.

**Kryteria wyjścia**

- wspólny correlation ID przechodzi przez co najmniej dwa repozytoria,
- upstream provenance jest zachowane,
- consumer odrzuca niekompatybilną główną wersję schematu.

## Faza 4 — Capability Registry

Owner: `ai_platform`.

Zbuduj discovery manifestów. Provider rejestruje:

- capability id/version,
- schematy input/output,
- side effects,
- wymagania authority,
- emitowane zdarzenia,
- provider entity/version.

Nie używaj lokalnego registry filtrów GlitchLab jako stanu globalnego. Dodaj adapter tylko wtedy, gdy jest użyteczny.

**Pierwsze manifesty providerów**

- analiza AST/delta/grafu GlitchLab,
- abstrakcja struktury Mosaic Lab,
- symulacja kaskadowa,
- obserwacja SBOM/evidence bramki,
- telemetria/wykonanie Swarm.

## Faza 5 — Odświeżenie QV9D / Mosaic Registry

Zastąp nieaktualną statyczną listę repozytoriów generowanymi manifestami, zachowując adnotacje QV9D.

```text
GitHub/repository manifest
→ deterministic physical inventory
→ semantic QV9D annotation
→ validation against actual repository/ref
```

QV9D jest przestrzenią metadanych/współrzędnych. Nie może tworzyć authority.

## Faza 6 — Provenance + LBOM / Decision BOM

Uogólnij provenance z evidence supply-chain na wejścia decyzji.

Początkowe rekordy Decision BOM zawierają:

- wersję modelu/providera,
- refs elementów kontekstu,
- refs evidence,
- refs promptów/instrukcji tam, gdzie są dostępne,
- refs pamięci,
- polityki,
- wersje capability/tool,
- gate event,
- transformation chain.

Rozpocznij od odwołań/digestów metadanych, a nie od kopiowania pełnych payloadów.

## Faza 7 — Global Graph State

Owner: kontrakt/usługa `ai_platform`.

Na początku graf jest projekcją wyprowadzoną append-only z typowanych zdarzeń. Nie czyń z niego systemu rekordowego dla lokalnego stanu providerów.

Graf musi rozróżniać:

```text
supports / contradicts
from
caused / authorized
```

## Faza 8 — Policy / Gate / Authority Engine

Owner: wspólny interfejs decyzyjny `ai_platform`. Enforcement pozostaje federacyjny.

Adaptery:

- evidence bramki SBOM,
- GlitchLab Guard/invariants,
- Kubernetes RBAC/workload authorization,
- human approval.

Wymagany inwariant:

```text
consequential ActionExecuted
⇒ GateApplied reference
```

## Faza 9 — Agent Execution Mesh

Owner: `swarm` jako provider wykonawczy.

Ścieżka migracji:

```text
current domain JSON/API
→ event-envelope adapter
→ workload/entity identity
→ deterministic ExecutionContract consumer
→ receipt emitter
→ sandbox/tool-worker extraction
```

Przejrzyj istniejący RBAC względem rzeczywistego zachowania usług. Usuń authority, które nie ma udokumentowanego consumera.

## Faza 10 — Cognitive State / Memory

Owner semantyki: `HA2D`; wspólny kontrakt: `ai_platform`.

Najpierw zaimplementuj typy i politykę, następnie storage.

```text
WORKING
EPISODIC
SEMANTIC
PROCEDURAL
POLICY
EVIDENCE
QUARANTINE
```

Niezaufane wejście może zostać `MemoryCandidateCreated`; trwały commit wymaga policy/gate.

## Faza 11 — Hypothesis Engine

Używaj machine-readable rekordów hypothesis/evidence. `hipotezy_nadawcze_LLM` staje się jednym z providerów rekordów; nie staje się uprzywilejowanym silnikiem inferencji.

## Faza 12 — Glitch / Novelty Engine

Udostępnij analizę GlitchLab przez stabilne kontrakty capabilities. Preferuj adaptery wokół istniejących modułów graph/delta/invariant.

`glitch` oznacza niezgodność z preferowanym modelem, a nie automatycznie podatność/błąd.

## Faza 13 — Propagation / Risk Simulator

Najpierw opakuj istniejące `run_model`. Następnie wprowadź uogólniony protokół providera symulacji.

Nie przepisuj obecnego modelu Iran SD na uniwersalny model propagacji. Nowe modele propagacji stają się osobnymi implementacjami providera za tym samym kontraktem symulacji.

## Faza 14 — Human–AI HUD

Użyj koncepcji HUD/revision z HA2D do wizualizacji:

- bieżącego grafu/modelu świata,
- alternatywnych hipotez,
- evidence i unknowns,
- delty,
- proponowanego działania,
- requested/effective authority,
- blast radius/scenariuszy,
- abstrakcji λ.

Widok HUD jest projekcją stanu, a nie źródłem authority.

## Faza 15 — Obserwowalność cross-repository

Minimalny trace end-to-end:

```text
Observation
→ Reasoning result
→ DecisionProposal
→ GateApplied
→ ActionExecuted
→ OutcomeObserved
```

Każde przejście musi współdzielić identyfikatory correlation/causation.

## Faza 16 — Replay

Rekord replay rekonstruuje:

- zaobserwowane wejścia,
- znane niewiadome,
- hipotezy,
- evidence,
- wersje modelu/providera,
- polityki/bramki,
- authority,
- execution receipt,
- outcome.

Replay musi jawnie tolerować brakujące dane; nie może fabrykować nieobecnego stanu.

## Faza 17 — Distillation

Dla wielokrotnie zwalidowanego zachowania:

```text
UNDERSTOOD
→ deterministic function/schema/test/policy
→ FORMALISED
```

Zapisuj supersession pomiędzy mechanizmem heurystycznym i sformalizowanym.

## Faza 18 — Deterministyczny enforcement

Wszyscy providerzy powodujący skutki konsumują zwalidowane execution contracts zamiast free-form outputów modelu.

## Faza 19 — Walidacja adversarialna

Testy na poziomie architektury obejmują:

```text
Can DATA become AUTHORITY?
Can MEMORY bypass a GATE?
Can a child agent inherit parent mandate implicitly?
Can compression lose provenance?
Can λ abstraction hide a critical dependency?
Can observability disappear without authority degradation?
Can a probabilistic output reach execution without a deterministic contract?
```

## Strategia stacked PR

Zalecana sekwencja PR-ów:

```text
PR-00 architecture analysis
PR-01 shared identity contract
PR-02 event envelope
PR-03 capability/repository manifests
PR-04 provider adapters: sbom + glitchlab
PR-05 provider adapter: swarm
PR-06 provider adapter: simulator
PR-07 graph projection
PR-08 gate/authority contract
...
```

Body każdego PR-a musi zawierać:

```text
WHY
CURRENT
TARGET
ARCHITECTURAL INVARIANTS
CHANGED CONTRACTS
MIGRATION
TESTS
ROLLBACK
```

## Zasada rollbacku

Dopóki ścieżka legacy nie zostanie jawnie zdeprecjonowana, wyłączenie adaptera Cyber-Lion musi przywracać providerowi jego wcześniejsze samodzielne zachowanie. Federacja cross-repo musi zatem rozpoczynać się jako warstwa addytywna.
