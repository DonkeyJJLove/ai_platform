# LION — stan poznawczy i bezpieczna kontynuacja

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

## Co jest bieżące, a co jest odziedziczone

Bieżący jest wynik pakowania i testów kontenera. Stan repozytoriów, hostów, CI oraz frontier jest odziedziczonym snapshotem. Nie wykonywano tutaj nowego audytu live. Ostatni raportowany baseline w poniższym rekordzie jest punktem porównania, nie warunkiem nakazującym utrzymać stary commit.

Nie używaj `LION_CANONICAL_STATE_v1_4_candidate.source.json` jako samodzielnej bramki dowodowej: jego rekordy mają puste evidence_refs; patrz audyt 04. Szukaj wskazanych dowodów w EVIDENCE_INDEX i poza pakietem, gdy bieżące zadanie wymaga obserwacji live. Nie zastępuj brakujących dowodów samym rekordem stanu.

## Aktywny protokół wejścia, nie historyczny skrypt

```text
RUN LION-RAG32-REACQUIRE-AND-CONTINUE
SCOPE = current user request
INPUT = verified core profile + required source closure
MODE = read-only first; candidate preparation within current authorization
1. Check profile/release and completeness of required records.
2. Read original contracts, source class, constraints and contradiction history.
3. For runtime/code claims, reacquire relevant repositories/CI/runtime at exact identities.
4. Compare observed state with the historical snapshot; do not rerun completed work.
5. Derive the first genuinely unfinished dependency inside the requested scope.
6. Prepare a bounded plan/candidate. No inferred write/merge/host authority.
7. Perform only separately permitted effects; independently read back each result.
8. Reconcile intended, reported and observed outcomes; retain unresolved differences.
9. Materialize the new state/delta into the next consistent RAG32 epoch.
```

Gdy zadanie dotyczy wyłącznie dołączonych źródeł, nie wymuszaj niepotrzebnego audytu całego systemu. Gdy brakuje narzędzi lub dowodów do działania, dostarcz osiągalny read-only/candidate wynik i precyzyjny blocker. Nigdy nie promuj UNKNOWN do PASS na podstawie kompletności ZIP-a.

## Wymagany zapis zakończenia sesji

Zapisz identyfikator epoki RAG, cel, odczytane source_id, zakres dowodów live (albo NOT_REVALIDATED), decyzje, dozwolone i wykonane efekty, exact refs, brakujące zależności, konflikty oraz następny krok. Pamięć rozmowy nie zastępuje tego zapisu. Nowy snapshot nie może sam sobie przyznać VERIFIED lub authority.

LION_DATA_BEGIN: CONTINUATION_STATE
```json
{
  "schema_version": "lion.rag-continuation/v1",
  "release_id": "lion-rag32-v1.4-r1",
  "runtime_currentness": "NOT_REVALIDATED",
  "next_step": "REACQUIRE_SCOPE_BOUND_LIVE_STATE",
  "effects": {
    "repository": "NONE",
    "host": "NONE",
    "production": "NONE",
    "authority": "NONE"
  },
  "last_reported_snapshot": {
    "repository": "DonkeyJJLove/ai_platform",
    "branch": "master",
    "head": "5d5a02b37fdfff4bcbf62f455d37ce4b86080f59",
    "tree": "9725bebf8d9766c58096cfc34af06ffcb8aa32f1",
    "truth_subject_digest": "d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726",
    "source_id": "SRC-V14C2-a3fd7931a2e1",
    "evidence_class": "PRIOR_DERIVED_CANDIDATE",
    "is_live_observation_in_this_run": false
  },
  "claim_groups": [
    {
      "id": "ARCHITECTURE_FRONTIER",
      "scope": "Earlier v1.4 snapshot reports ActionSpec → LAIR → static projection → explicit ActionProposal context → canonical PDP; next gap reported downstream at runtime effect/identity admission. Not freshly verified here.",
      "source_ids": [
        "SRC-V14C2-3b29eb27eab7",
        "SRC-V14C2-a3fd7931a2e1"
      ],
      "currentness": "NOT_REVALIDATED"
    },
    {
      "id": "FACTORY_GENERATIVITY",
      "scope": "Original snapshot NOT_PROVEN; earlier v1.4 candidate reports bounded two-family protocol PASS. General and activated child autonomy are separate claims. Direct CI/logs/code not reread in packaging run.",
      "source_ids": [
        "SRC-V13-9f6ba8598d20",
        "SRC-V14C2-fb60469523a8",
        "SRC-V14C2-a3fd7931a2e1"
      ],
      "currentness": "NOT_REVALIDATED"
    },
    {
      "id": "HOSTS",
      "scope": "Original evidence lists three WSL roles; earlier v1.4 lists four including LION-AUTH-LAB and still one physical domain. No new census in this packaging run.",
      "source_ids": [
        "SRC-V13-e84d4af24832",
        "SRC-V14C2-e84d4af24832"
      ],
      "currentness": "NOT_REVALIDATED"
    },
    {
      "id": "SCHEMA_CONTINUITY",
      "scope": "Exact original Blueprint schema and v1.4 reconstruction coexist. No automatic compatibility or supersession. Current integrated repository schema must be independently reacquired before implementation.",
      "source_ids": [
        "SRC-V13-4a418cbb0aa9",
        "SRC-V14C2-09f015ba4e6e"
      ],
      "currentness": "NOT_REVALIDATED"
    }
  ],
  "required_read_sets": {
    "packaging": [
      "00_START_HERE.md",
      "01_FORMAT_AND_LIFECYCLE.md",
      "02_ROUTING_AND_SOURCE_MAP.md",
      "04_PACKAGE_AUDIT.md",
      "05_PACKAGE_MANIFEST.md",
      "06_VALIDATION_AND_RETRIEVAL.md",
      "07_CONTAINER_TOOL.md"
    ],
    "action": [
      "16_LION_ACTION_IR.md",
      "17_LION_COMMAND_CONSOLE.md",
      "18_LION_AUTHORITY_FLEET.md",
      "22_LION_RECONCILIATION_ENTRY.md",
      "24_LION_EVIDENCE.md",
      "25_LION_CONTRADICTIONS_HISTORY.md"
    ],
    "factory": [
      "11_LION_FACTORY_BEANS_AUTONOMY.md",
      "12_LION_BEAN_SCHEMA.md",
      "13_LION_BLUEPRINT_SCHEMA.md",
      "14_LION_RECURSION_LINEAGE.md",
      "15_LION_ABSTRACTION_MATERIALIZERS.md",
      "24_LION_EVIDENCE.md",
      "25_LION_CONTRADICTIONS_HISTORY.md"
    ],
    "host": [
      "18_LION_AUTHORITY_FLEET.md",
      "19_LION_HOST_FAILURES.md",
      "22_LION_RECONCILIATION_ENTRY.md",
      "24_LION_EVIDENCE.md"
    ],
    "next_step": [
      "09_LION_AS_IS_IMPLEMENTATION.md",
      "24_LION_EVIDENCE.md",
      "25_LION_CONTRADICTIONS_HISTORY.md",
      "26_LION_ROADMAP_DELTA.md"
    ]
  }
}
```
LION_DATA_END: CONTINUATION_STATE
