# LION / ai_platform

**LION jest eksperymentalną platformą nadzorowanej autonomii Human–AI: federacyjnym control plane'em, systemem kontraktów i mechanizmem ewolucji architektury, który rozdziela probabilistyczne rozumowanie od authority, wykonania i obserwacji skutku.**

Repozytorium `ai_platform` jest globalnym właścicielem architektury LION. Historyczna nazwa **Cyber-Lion** pozostaje w przestrzeni nazw `cyber_lion` oraz w części kontraktów i dokumentacji.

> **Bieżąca epoka dokumentacji: LION architecture 1.5.**
> Publiczny punkt wejścia prowadzi do [`LION/architecture/v1_5/README.md`](LION/architecture/v1_5/README.md). Root `README.md` i [`LION/README.md`](LION/README.md) są częścią systemu architecture knowledge, a nie niezależnymi wizytówkami utrzymywanymi poza currentness.

---

## Co zostało zbudowane

LION nie jest pojedynczym agentem ani wrapperem wokół modelu. System obejmuje dziś kilka współpracujących płaszczyzn:

```text
PROBABILISTIC INTELLIGENCE
        ↓
REPRESENTATION / PROPOSAL
        ↓
FORMALIZATION / POLICY / AUTHORITY
        ↓
RUNTIME ADMISSION
        ↓
BOUNDED EFFECT
        ↓
OBSERVATION
        ↓
RECONCILIATION
        ↓
EVOLUTION
```

Najważniejszy niezmiennik pozostaje prosty:

```text
MODEL OUTPUT != AUTHORITY
PROPOSAL != AUTHORIZATION != EFFECT
RECEIPT != OBSERVATION != RECONCILIATION
DOCUMENTATION != LIVE RUNTIME TRUTH
RAG != LIVE TRUTH
```

Model może wytwarzać hipotezy, reprezentacje, plany i propozycje. Prawo do skutku jest osobną właściwością systemu i wymaga jawnego źródła authority, aktualności, bramki oraz obserwowalnego efektu.

---

## Architektura 1.5

Na `master` zintegrowana jest fundamentowa warstwa **Federated Architecture Knowledge**. Łączy ona dziesięć repozytoriów federacji przez lokalne manifesty `cyber-lion.repository.json`, jawne semantic exports/imports oraz globalnego właściciela architektury w `ai_platform`.

Kanoniczna warstwa v1.5 obejmuje między innymi:

- `semantic_owners.json` — jednego primary ownera dla każdego globalnego konceptu;
- `FORMALIZATION_REGISTRY_FEDERATION_R1.json` — rejestr powierzchni formalizacji;
- `ARCHITECTURE_DOCUMENT_CENSUS.json` — census dokumentów i artefaktów architektury;
- `ARCHITECTURE_DOCUMENT_GRAPH.json` — relacje między dokumentami, manifestami i entrypointami;
- `CODE_DERIVED_ARCHITECTURE.json` oraz `DOCUMENT_DERIVED_ARCHITECTURE.json` — niezależne projekcje kodu i dokumentacji;
- `ARCHITECTURE_RECONCILIATION.json` — rekonsyliację kod ↔ dokumentacja ↔ federacja;
- `DOCUMENTATION_CURRENTNESS_MODEL.json` — typowany model aktualności;
- `AI_NATIVE_ROADMAP_NEXT.md` — roadmapę wyprowadzaną z zależności, a nie ze starego tekstowego `NEXT_STEP`.

Pełna nawigacja: [`LION/architecture/v1_5/README.md`](LION/architecture/v1_5/README.md).

---

## Homeostaza dokumentacji

Dokumentacja LION jest elementem architektury i ma własny cykl currentness:

```text
EXACT SOURCE / FEDERATION OBSERVATION
→ CODE-DERIVED ARCHITECTURE
→ DOCUMENT CENSUS
→ DOCUMENT GRAPH
→ CODE/DOCUMENT RECONCILIATION
→ REQUIRED FORMALIZATION
→ HUMAN ENTRYPOINT REFRESH
→ RAG / DISCOVERABILITY
→ FEDERATION VECTOR
→ TRUTH CARRIERS LAST
```

Stored snapshot, README albo wynik wcześniejszego testu nie jest automatycznie bieżącą prawdą. Zmiana źródła może unieważnić projekcje zależne. Publiczny `README.md`, `LION/README.md` oraz root v1.5 muszą wskazywać tę samą epokę architektury.

Model currentness: [`LION/architecture/v1_5/DOCUMENTATION_CURRENTNESS_MODEL.json`](LION/architecture/v1_5/DOCUMENTATION_CURRENTNESS_MODEL.json).

---

## Formalization Kernel

Zmiana architektury nie powinna przechodzić bez jawnego domknięcia powierzchni zależnych. V1.5 używa ścieżki:

```text
EvolutionDelta
→ ArchitectureFormalizationManifest
→ RequiredFormalizationSet
→ FederatedFormalizationBinding
→ candidate
→ independent verification
→ FormalizationClosureRecord
→ governed admission
```

Formalizacja nie nadaje authority. Dowodzi jedynie, że kandydat został związany z właściwymi źródłami, właścicielami semantycznymi, testami i projekcjami.

---

## Federacja

Globalna architektura nie jest kopiowana do repozytoriów peer. Każde repozytorium utrzymuje lokalne:

```text
AGENTS.md
cyber-lion.repository.json
local architecture artifacts
semantic exports / imports
invalidation triggers
```

a pytania federacyjne są routowane do `ai_platform`.

Peery mogą dostarczać pamięć kontekstową, semantykę procesu, kompilację ewolucji, grafy strukturalne, provenance/SBOM, wykonanie rojowe, symulację i corpus badawczy, ale lokalna implementacja nie staje się przez to globalnym ownerem semantyki.

---

## Runtime i authority

LION utrzymuje ścisłe rozdzielenie:

```text
OPEN INTELLIGENCE != OPEN AUTHORITY
CAPABILITY != AUTHORITY
PDP ALLOW != RUNTIME ADMISSION
RUNTIME ADMISSION != EFFECT
COMMIT != INTEGRATION
MERGE != DEPLOYMENT
```

Warstwa runtime obejmuje m.in. identity/provenance, policy gates, admission, execution receipts, observation sources, reconciliation i currentness. Dowód konkretnego toru wykonawczego nie jest automatycznie dowodem pełnej mediacji wszystkich możliwych skutków.

---

## RAG i źródła prawdy

RAG jest wersjonowaną pamięcią wiedzy projektu. Nie zastępuje obserwacji GitHub, CI ani runtime.

Dla twierdzeń dynamicznych obowiązuje zasada dopasowania evidence do twierdzenia:

```text
LIVE OBSERVATION / REPRODUCED EFFECT
> EXACT GIT + CURRENT CI
> FRESH SOURCE-BOUND PROJECTION
> VERSIONED RAG / DOCUMENTATION
> HISTORY / CHAT CONTEXT
```

Nie jest to jedna liniowa skala: Git nie dowodzi runtime, test nie dowodzi authority, a dokumentacja nie dowodzi deploymentu.

---

## Bieżący frontier

Fundament v1.5 jest zintegrowany. Następne kroki są wyprowadzane w [`AI_NATIVE_ROADMAP_NEXT.md`](LION/architecture/v1_5/AI_NATIVE_ROADMAP_NEXT.md).

`CommunicationEnvelope` jest rozwijany jako osobny, formalizowany successor i **nie należy go traktować jako zintegrowanej funkcji `master`, dopóki jego własny cykl publikacji i rekonsyliacji nie zostanie domknięty**.

---

## Struktura repozytorium

```text
ai_platform/
├── README.md
├── AGENTS.md
├── cyber-lion.repository.json
├── LION/
│   ├── README.md
│   ├── architecture/
│   │   ├── v1_4/
│   │   └── v1_5/
│   ├── codex/
│   ├── evals/
│   ├── evolution/
│   └── rag/
├── cyber_lion/
│   ├── architecture_projection/
│   ├── contracts/
│   ├── enterprise/
│   ├── mission_control/
│   ├── process_language/
│   ├── registry/
│   └── tests/
├── tools/
└── .github/workflows/
```

Najważniejsze punkty wejścia:

- [`LION/architecture/v1_5/README.md`](LION/architecture/v1_5/README.md) — bieżąca architektura knowledge/currentness;
- [`LION/README.md`](LION/README.md) — nawigacja projektu;
- [`AGENTS.md`](AGENTS.md) — instrukcje i routing pracy agentowej;
- [`cyber_lion/TARGET_ARCHITECTURE.md`](cyber_lion/TARGET_ARCHITECTURE.md) — architektura docelowa;
- [`cyber_lion/CONTRACT_MAP.md`](cyber_lion/CONTRACT_MAP.md) — mapa kontraktów;
- [`LION/rag/RAG_BOOTSTRAP.json`](LION/rag/RAG_BOOTSTRAP.json) — bootstrap wersjonowanej pamięci RAG.

---

## Testy

```bash
python -m compileall -q cyber_lion
python -m unittest discover -s cyber_lion/tests -p 'test_*.py' -v
```

CI, test lokalny, merge authority, runtime authority i deployment są osobnymi klasami evidence.

---

## Status epistemiczny

```text
OBSERVED      — stan lub efekt zaobserwowany
DERIVED       — deterministyczna projekcja ze związanych źródeł
IMPLEMENTED   — kod istnieje
TESTED        — określony kontrakt przeszedł test
CANDIDATE     — zmiana nie została jeszcze zintegrowana
INTEGRATED    — zmiana znajduje się w kanonicznym repozytorium
DEPLOYED      — stan runtime potwierdzony osobnym dowodem
TARGET        — kierunek, nie stan bieżący
```

LION ma umożliwiać szeroką inteligencję przy wąskiej, jawnej, obserwowalnej i odwoływalnej władzy wykonawczej.
