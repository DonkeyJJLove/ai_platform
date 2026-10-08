# Project Reality → Evolution Path R1

Status: `CANDIDATE / SOURCE_BOUND_SUCCESSOR`. Authority effect: `NONE`. Execution effect: `NONE`.

## Dlaczego powstaje ten przyrost

Materiały o architekturze ewolucyjnej, Mental Matrix, migracji conversation plane i produkcji Panel–SaaS–worker opisują różne perspektywy **tego samego problemu**: LION musi rekonstruować sprawdzalną rzeczywistość projektu, wybrać z niej relewantny problem, zaproponować zmianę, deterministycznie ją skompilować, wykonać przez istniejącą ścieżkę authority/runtime, zaobserwować efekt i wprowadzić wynik z powrotem do wiedzy.

Nie potrzeba do tego osobnego Mental Matrix runtime, drugiego grafu prawdy, kolejnego schedulera ani nowego authority ownera.

## Rekonsyliacja Mental Matrix

Koncepcja `ProjectRealitySnapshot` jest zachowana, ale jako **projekcja wiążąca** istniejące kanoniczne obserwacje:

```text
WorldSnapshot
+ SystemSnapshot(s)
+ exact Git source identity
+ federation/currentness evidence
+ architecture-knowledge digest
+ EnterpriseGraphProjection
        ↓
ProjectRealitySnapshot
```

Snapshot nie kopiuje pełnych payloadów źródłowych i nie staje się nową bazą prawdy. Przechowuje dokładne referencje i digests. `CURRENT` nie może zawierać UNKNOWN ani sprzeczności.

Mental Matrix ClaimGraph również nie otrzymuje drugiego store. LION ma już dwa właściwe substraty:

- `SemanticAtom/EvidenceInstance/SemanticDelta` zachowujące treść twierdzenia, czas, provenance i niezależne korzenie evidence;
- `EnterpriseGraph` z płaszczyzną `DATA_PROVENANCE` i relacjami `SUPPORTS`, `CONTRADICTS`, `DERIVED_FROM`, `OBSERVED_FROM`, `SUPERSEDES`, `CORRELATED_WITH`, `CAUSED_BY`.

`ProjectClaimProjection` jest więc tylko ograniczonym widokiem tych rekordów związanym z konkretnym `ProjectRealitySnapshot`. Nie wolno mu użyć krawędzi authority plane ani poszerzyć grafu o węzły nieobecne w źródłowej projekcji.

Narracja, VisualWorldState, StoryPlan i publikacja Mental Matrix mają później być **konsumentami** tego widoku. Historia może uprościć reprezentację, lecz nigdy nie zmienia epistemic class; `CANDIDATE`, `SIMULATED` albo `UNKNOWN` nie staje się `OBSERVED` dlatego, że narracja jest spójna.

## Wspólna ścieżka ewolucji

```text
HUMAN GOAL / SYSTEM ALERT
        ↓
REACQUIRE
        ↓
WorldSnapshot + SystemSnapshot + federation/currentness
        ↓
ProjectRealitySnapshot
        ↓
EvidenceObservation / SemanticAtom / EnterpriseGraph
        ↓
ProjectClaimProjection
        ↓
MissionIntent / RAG / SemanticScaffold / RelevanceProjection
        ↓
Goal + Gap + CapabilityNeed
        ↓
candidate variants / reuse / Bean / Composition / Mosaic
        ↓
candidate-specific reality gates + evidence-bound pressure
        ↓
Dynamic Evolution Fitness
        ↓
ONE CandidateDesign
        ↓
existing ArchitectureCompiler
        ↓
EvolutionDelta
        ↓
AFM → RequiredFormalizationSet → federation binding → closure
        ↓
Mission Program / LPCL
        ↓
separate authority + runtime admission
        ↓
LOCAL / SAAS cognition
        ↓
cooperative material worker
        ↓
artifact bytes + receipt
        ↓
independent verifier / counterexample
        ↓
observation + reconciliation
        ↓
RnD memory / architecture knowledge / RAG
        ↓
truth/currentness carriers LAST
        ↓
next ProjectRealitySnapshot revision
```

Architecture Studio i Mental Matrix rozchodzą się dopiero **po** wspólnym reality/lineage substrate:

```text
ProjectReality + Claim/Lineage
       ├── Architecture Studio
       │      graph / gaps / lifecycle / composer / monitor
       │
       └── Mental Matrix
              story / visual continuity / publication / historical explanation
```

Oba widoki są read/proposal surfaces. Żaden nie wykonuje efektów.

## Istniejący producer obserwacji

Current source już posiada read-oriented observation producer. `tools/lion_local_intelligence_runtime.py::control_plane_recon_observer_once(...)` zbiera source identity, thread DB, model i SaaS projection, a `cyber_lion/mission_control/control_plane_reconnaissance.py::collect_observations(...)` składa typowany bundle `lion.control-plane-reconnaissance/v1`.

Project Reality nie tworzy drugiego pollera. `system_snapshot_from_control_plane_observations(...)` jest czystym normalizerem tego bundle do `SystemSnapshot`. Brak domeny pozostaje `UNKNOWN`; rozbieżność dokładnego Git HEAD/TREE względem deklarowanego current source staje się `CONFLICTED`.

## Reality → Fitness

Pierwszy brak po Dynamic Evolution Fitness był bardzo konkretny: jego gate i pressure były dotąd ręcznie budowanymi wejściami. `ProjectRealityAdapter` wprowadza źródłowe wiązanie.

Każdy kandydat dostaje dokładnie jedną obserwację każdego hard gate:

```text
source_current
semantic_owner_bound
dependency_closure
authority_nonexpanding
effect_state_reconciled
collision_free
bounded_scope
evidence_bound
owner_resolved
```

Stan obserwacji to `PASS | FAIL | UNKNOWN`. Tylko PASS daje `True`; UNKNOWN jest zachowane i przechodzi do fitness jako fail-closed blocker. Nie można zadeklarować `source_current=PASS`, gdy sam ProjectRealitySnapshot nie jest `CURRENT`.

Dynamic pressure pozostaje oddzielny od gate. Każdy pressure ma wymiar, wartość, evidence ref, digest źródła, czas obserwacji oraz klasę źródła: observed state, measured metric, derived currentness albo operator objective. Pressure zmienia kolejność kandydatów, lecz nie może zmienić FAIL/UNKNOWN na PASS.

## Relacja do conversation plane

Nowy model rozmów nie jest osobną ścieżką ewolucji. Conversation plane dostarcza trwałą tożsamość pracy poznawczej:

```text
conversation
→ binding_epoch
→ provider lane
→ provider_session_ref
→ request/message/invocation
→ shared_context_digest
→ projection_digest
→ actual_payload_bytes_digest
→ response
```

Te rekordy są częścią reality/evidence dla faz poznawczych, ale conversation nie staje się mission, authority ani artifact identity.

## Relacja do cooperative production

Historyczny program cooperative production poprawnie wskazuje docelowy szkielet `QUALIFY → BUILD → VERIFY`, lecz aktualny live mission R3 pozostaje związany ze starym source identity i jest `REGISTERED / NOT_STARTED / authority NONE`. Nie może więc zostać potraktowany jako bieżący następca tylko dlatego, że jego cel jest zbieżny.

Wspólna ścieżka wymaga current-source successor, który przed R6.17 qualification posiada rzeczywistą R6.16 materialization/release evidence. Dopiero później może wejść pierwszy pełny artifact loop.

## Pierwszy użyteczny proof

Pierwszym proofem nie powinien być sztuczny plik. Naturalnym artefaktem jest komponent lub package, który rzeczywiście domyka dalszą ewolucję — na przykład live collector/adaptor dostarczający ProjectReality/currentness observations do `ProjectRealityAdapter`.

Odbiór 1:

```text
operator intent
→ canonical conversation/context
→ SaaS + LOCAL distinct legs
→ selected artifact specification
→ admitted MD029 write
→ exact bytes
→ MD030 independent verify
→ counterexample/retry if needed
→ reconciled result
→ ProjectReality revision
→ panel readback
```

Odbiór 2 następuje dopiero później: ten sam mechanizm musi zbudować **inną rodzinę artefaktu/aplikacji** bez dedykowanego hard-coded workflow. To jest minimalny dowód generatywności fabryki.

## Granice

```text
PROJECT_REALITY        != authority
CLAIM_GRAPH_PROJECTION != truth promotion
MENTAL_MATRIX          != orchestrator
ARCHITECTURE_STUDIO    != executor
FITNESS                != scheduler
MODEL OUTPUT            != verified artifact
RECEIPT                 != reconciled closure
MERGE                   != deployment
RAG                     != live truth
```

Machine-readable path: `PROJECT_REALITY_EVOLUTION_PATH_R1.json`.

Implementation candidate: `cyber_lion/architecture_projection/project_reality.py`.
