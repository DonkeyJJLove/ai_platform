# LION — punkt wejścia do dokumentacji projektu

LION jest systemem ewolucji architektury, kontrolowanej autonomii i rekonsyliacji skutków. Ta warstwa dokumentacji nie nadaje authority i nie zastępuje live Git/CI/runtime evidence.

## Bieżąca dokumentacja v1.5

Kanonicznym punktem wejścia do bieżącej warstwy architecture knowledge jest [`architecture/v1_5/README.md`](architecture/v1_5/README.md).

V1.5 wprowadza federacyjne architecture knowledge i traktuje dokumentację jako wersjonowaną, testowaną powierzchnię systemu. Najważniejsze artefakty to:

- `architecture/v1_5/semantic_owners.json` — globalny routing własności semantycznej;
- `architecture/v1_5/FORMALIZATION_REGISTRY_FEDERATION_R1.json` — rejestr formalizacji;
- `architecture/v1_5/ARCHITECTURE_DOCUMENT_CENSUS.json` — census dokumentów;
- `architecture/v1_5/ARCHITECTURE_DOCUMENT_GRAPH.json` — graf relacji dokumentacyjnych;
- `architecture/v1_5/CODE_DERIVED_ARCHITECTURE.json` i `DOCUMENT_DERIVED_ARCHITECTURE.json` — niezależne projekcje;
- `architecture/v1_5/ARCHITECTURE_RECONCILIATION.json` — rekonsyliacja kod/dokumentacja/federacja;
- `architecture/v1_5/DOCUMENTATION_CURRENTNESS_MODEL.json` — model currentness;
- `architecture/v1_5/AI_NATIVE_ROADMAP_NEXT.md` — dependency-derived frontier.

Root `README.md`, ten dokument oraz `architecture/v1_5/README.md` są deklarowanymi entrypointami architecture knowledge. Zmiana epoki lub źródeł unieważnia ich claim do bieżącego stanu, dopóki nie zostaną ponownie zrekonsyliowane.

## Zasada dowodowa

```text
DOCUMENTATION != AUTHORITY
DOCUMENTATION != LIVE RUNTIME EVIDENCE
RAG != LIVE TRUTH
PROPOSAL != AUTHORIZATION
PDP ALLOW != RUNTIME ADMISSION
RUNTIME ADMISSION != EFFECT
RECEIPT != OBSERVATION != RECONCILIATION
CANDIDATE != INTEGRATED
MERGE != DEPLOYMENT
```

Dla operacji zależnych od aktualnego stanu należy ponownie obserwować Git, CI i właściwy runtime. Stored snapshot jest source-bound evidence, nie samoodświeżającym się właścicielem prawdy.

## Cykl homeostazy dokumentacji

```text
REACQUIRE / BIND EXACT SOURCE
→ DERIVE CODE ARCHITECTURE
→ CENSUS DOCUMENTS
→ BUILD DOCUMENT GRAPH
→ RECONCILE CODE ↔ DOCUMENTS ↔ FEDERATION
→ DERIVE REQUIRED FORMALIZATION
→ REFRESH HUMAN ENTRYPOINTS
→ RUN DISCOVERABILITY / RAG PROBES
→ CLOSE FORMALIZATION
→ FEDERATION VECTOR
→ TRUTH CARRIERS LAST
```

Generator `tools/lion_federated_architecture_knowledge.py` może użyć exact local-owner overlay dla `ai_platform`. Dzięki temu globalny owner nie analizuje własnego starego manifestu zapisanego w starszym federation baseline.

## Granice historyczne

`architecture/v1_4/` pozostaje ważnym lineage i compatibility layer, ale:

- `architecture/v1_4/current_state.json` nie jest live właścicielem v1.5;
- `architecture/v1_4/semantic_owners.json` jest projekcją historyczno-kompatybilną;
- root `AI_NATIVE_ROADMAP.md` jest historycznym wejściem roadmapy;
- nowe decyzje architektoniczne routują przez v1.5.

Nie należy przepisywać historycznych artefaktów tak, aby udawały stan bieżący.

## Federacja i formalizacja

Globalnym właścicielem architektury jest `DonkeyJJLove/ai_platform`; repozytoria peer utrzymują lokalne manifesty, semantic exports/imports i własne artefakty. Globalna architektura nie jest kopiowana do peerów.

Zmiana architektury przechodzi przez:

```text
EvolutionDelta
→ ArchitectureFormalizationManifest
→ RequiredFormalizationSet
→ FederatedFormalizationBinding
→ candidate + verification
→ FormalizationClosureRecord
→ governed admission
```

Formalization jest warstwą poprawności i currentness, nie authority.

## Routing

- architektura v1.5: [`architecture/v1_5/README.md`](architecture/v1_5/README.md);
- architektura docelowa: [`../cyber_lion/TARGET_ARCHITECTURE.md`](../cyber_lion/TARGET_ARCHITECTURE.md);
- kontrakty: [`../cyber_lion/CONTRACT_MAP.md`](../cyber_lion/CONTRACT_MAP.md);
- Codex/runbook: [`codex/README.md`](codex/README.md);
- RAG bootstrap: [`rag/RAG_BOOTSTRAP.json`](rag/RAG_BOOTSTRAP.json);
- ewaluacje: [`evals/`](evals/);
- historyczne v1.4: [`architecture/v1_4/README.md`](architecture/v1_4/README.md).

## Current frontier

Fundament Federated Architecture Knowledge oraz `CommunicationEnvelope` są zintegrowane. Bieżący porządek successorów jest utrzymywany w [`architecture/v1_5/AI_NATIVE_ROADMAP_NEXT.md`](architecture/v1_5/AI_NATIVE_ROADMAP_NEXT.md); następnym frontierem kontraktowym jest `MissionIntent`. Standardy repozytorium znajdują się w [`standards/`](standards/), a formalny opis operator shell/panelu w [`panel/`](panel/).
