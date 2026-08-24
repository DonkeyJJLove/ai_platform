# CYBER-LION — Enterprise Control Plane AI-Native

Status: **EXECUTABLE ARCHITECTURE / ACTIVE EVOLUTION**

Cyber-Lion jest **federacyjnym systemem operacyjnym przedsiębiorstwa AI-Native** zbudowanym na ekosystemie repozytoriów DonkeyJJLove. Nie jest monolitem i nie utożsamia granic repozytoriów z granicami subsystemów ani authority.

Jego celem jest tworzenie i ewolucja agentów, składanie ich w dynamiczne Mosaic Cells i roje, łączenie badań z oprogramowaniem i execution oraz zachowanie tożsamości, provenance, obserwowalności, bezpieczeństwa i rollbacku na każdym consequential transition.

## Podstawowy model operacyjny

```text
ŚWIAT / RYNEK / SYSTEM
          ↓
      OBSERWACJA
          ↓
    R&D / HIPOTEZA
          ↓
        MISJA
          ↓
      AGENT FOUNDRY
          ↓
     AgentSpec[]
          ↓
  MosaicCell / SwarmSpec
          ↓
   proposal / software Δ
          ↓
 GLITCHLAB / INVARIANTY
          ↓
  POLICY / AUTHORITY GATE
          ↓
     EXECUTION MESH
          ↓
        EFEKT
          ↓
 OBSERVABILITY / OUTCOME
          ↓
 MEMORY / R&D / NEXT Δ
```

## Inwarianty nadrzędne

```text
OPEN INTELLIGENCE != OPEN AUTHORITY
NO ACTION WITHOUT IDENTITY
NO AUTHORITY WITHOUT PROVENANCE
NO ESCALATION WITHOUT APPLIED GATE
NO MEMORY WRITE WITHOUT POLICY
NO DECISION WITHOUT TRACE
NO CROSS-SYSTEM CALL WITHOUT CONTRACT
NO GLOBAL CLAIM FROM LOCAL OBSERVATION
NO LOST OBSERVABILITY WITHOUT AUTHORITY DEGRADATION
NO PROBABILISTIC OUTPUT DIRECTLY AS EXECUTION
NO FORMALISED RULE LEFT AS REPEATED LLM GUESS
NO SWARM MEMBER WITHOUT AGENT SPEC
NO AGENT SPAWN WITHOUT IDENTITY + BUDGET + AUTHORITY CEILING
NO ENTERPRISE CHANGE WITHOUT DELTA + TEST + ROLLBACK
```

## Zaimplementowane fundamenty

Obecny wykonywalny Cyber-Lion obejmuje:

- `EntityIdentity` i bezstratną kompatybilność SBOM/AID,
- typowane `EventEnvelope`, provenance i authority,
- `CapabilityRegistry`,
- provider plane z provenance receipts,
- Startup Evolution Agent,
- `MarketEvidenceBook` uwzględniający provenance i czas,
- `SoftwareBuildPlanner` oraz bezpieczne generowanie szablonów,
- ograniczony lokalny build runner,
- `EvolutionJournal`/replay,
- startup CLI/import JSON,
- `AgentSpec`, `MissionSpec`, `SwarmSpec`, `MosaicDelta`,
- deterministyczny `SwarmPlanner` oparty na capabilities.

## Architektura przedsiębiorstwa

Bieżący ekosystem repozytoriów jest traktowany jako zestaw federacyjnych organów:

```text
ai_platform              → Enterprise Control Plane / Agent Foundry
glitchlab                → Enterprise Evolution Compiler
chunk-chunk              → Process Semantics / HMK-9D
HA2D                     → Context / Memory / Human-AI Adaptation Lab
swarm                    → Distributed Execution Mesh
sbom                     → Identity / Provenance / Composition Intelligence
mosaic_lab_pro.py        → Structural Intelligence Engine
SymulacjaKaskadySieciowej→ Simulation / Falsification Engine
hipotezy_nadawcze_LLM    → Epistemic Hypothesis Lab
writeups                 → R&D / Enterprise Research Memory
```

Pełna synteza: [`enterprise/README.md`](enterprise/README.md).

Kluczowe dokumenty:

1. [`enterprise/AI_NATIVE_ENTERPRISE.md`](enterprise/AI_NATIVE_ENTERPRISE.md) — model stanu przedsiębiorstwa i role repozytoriów.
2. [`enterprise/AGENT_SWARM_MODEL.md`](enterprise/AGENT_SWARM_MODEL.md) — kontrakty pojedynczego agenta, Mosaic Cell i dynamicznego roju.
3. [`enterprise/GENERATION_EVOLUTION_PROTOCOL.md`](enterprise/GENERATION_EVOLUTION_PROTOCOL.md) — reguły bezpiecznego generowania/aktualizacji polimorficznego ekosystemu.
4. [`enterprise/RND_OPERATING_MODEL.md`](enterprise/RND_OPERATING_MODEL.md) — pipeline evidence i promocji R&D.
5. [`enterprise/REPOSITORY_EVOLUTION_PLAN.md`](enterprise/REPOSITORY_EVOLUTION_PLAN.md) — konkretna roadmapa dla każdego repozytorium.

## Trzy płaszczyzny

```text
SEM  — obserwacja, cognition, reprezentacja, symulacja, proposals
MAND — tożsamość, provenance, polityka, pamięć, authority, gates
INF  — procesy, API, pliki, sieci, deployment, skutki zewnętrzne
```

Relacja fundamentalna:

```text
SEM proposal != MAND authorization != INF effect
```

## Zachowana analiza architektoniczna

Pierwotna archeologia pozostaje istotna i jest zachowana jako evidence dla decyzji migracyjnych:

- [`REPOSITORY_INVENTORY.md`](REPOSITORY_INVENTORY.md)
- [`CAPABILITY_MAP.md`](CAPABILITY_MAP.md)
- [`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md)
- [`CONTRACT_MAP.md`](CONTRACT_MAP.md)
- [`EVENT_DATA_MODEL.md`](EVENT_DATA_MODEL.md)
- [`MIGRATION_MAP.md`](MIGRATION_MAP.md)
- [`SCIENTIFIC_STATUS.md`](SCIENTIFIC_STATUS.md)

## Dyscyplina migracji

```text
archeologia
→ typowany kontrakt
→ adapter kompatybilności
→ implementacja providera
→ integracja consumera
→ testy negatywne/adversarialne
→ dowód obserwowalności
→ deterministyczna bramka
→ ograniczone wykonanie
→ outcome/replay
→ deprecate legacy only after compatibility proof
```

Cyber-Lion powinien ewoluować agresywnie w **przestrzeni proposal i research**, podczas gdy consequential execution pozostaje wąskie, rekonstruowalne i odwoływalne.

## Granica dowodu workload identity

`EntityIdentity` pozostaje tożsamością opisową; nie jest kryptograficzną atestacją. RCCM-1E-I dodaje neutralny wobec adaptera `WorkloadIdentityProof`, którego kanoniczny podpisany payload jest weryfikowany przez wstrzykniętą granicę verifiera i prowadzi do odrębnego `VerifiedWorkloadIdentity`.

Weryfikacja działa fail-closed dla niepoprawnych podpisów, manipulacji podpisanymi polami, niepoprawnych okien ważności, stale/not-yet-valid proofs, odrzucenia przez verifier oraz wyjątków verifiera. `VerifiedWorkloadIdentity` celowo nie zawiera authority ani capability grant: **verified identity != authorization**.

Profil HMAC ze standard library używany w unit tests jest wyłącznie deterministycznym test fixture. Nie jest produkcyjnym providerem workload identity, nie implementuje własnego PKI i nie uzyskuje dostępu do rzeczywistego private-key material ani go nie utrwala.
