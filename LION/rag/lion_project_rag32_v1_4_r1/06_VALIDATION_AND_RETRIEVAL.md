# LION — kontrola integralności i próby retrieval

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

## Oddzielne bramki jakości

G0: dokładny zestaw 32 kontenerów i wspólna epoka. G1: każde źródło tekstowe obecne. G2: bytes i SHA-256 zgodne z literalnym oryginałem. G3: JSON parsuje się, Python parsuje się składniowo bez wykonania. G4: każda source_id i required read set rozwiązuje się do pliku. G5: negatywne testy kontenera odrzucają podmianę, brak, mieszankę epok i promocję authority/currentness. G6: rzeczywiste retrieval w projekcie dostarcza wymagane rekordy. G7: świeże dowody i zgoda wystarczają do konkretnego działania runtime.

Przejście G0–G5 nie oznacza G6 ani G7. Narzędzie lokalne nie jest nowym canonical-state validator dla LION. Nie dowodzi semantyki cudzych schematów, poprawności materializerów ani bezpieczeństwa autonomicznego wykonania.

## Jak przeprowadzić próbę w projekcie po wgraniu

Dla każdego pytania poniżej wyszukaj wskazane źródła i zażądaj source_id, namespace, klasy źródła, hash oraz opisu granicy epistemicznej. Przy kontrakcie poproś o literalny wymagany fragment ze schematu i sprawdź go względem payloadu. Zapisz faktycznie odczytane rekordy oraz braki. W przypadku częściowego wyniku odczytaj dalszy ciąg. Nie przyjmuj pozytywnego testu, kiedy odpowiedź pochodzi wyłącznie z pamięci rozmowy lub z tego zestawu oczekiwań.

W tym wydaniu wszystkie przypadki mają hosted_rag_result=NOT_RUN. Walidator sprawdza ich routing i istnienie źródeł. Test rozumienia granic i niezawodności retrieval należy wykonać po instalacji. Wyniku nie wpisuj jako PASS tylko dlatego, że pytanie ma tu oczekiwaną odpowiedź.

LION_DATA_BEGIN: RETRIEVAL_CASES
```json
{
  "schema_version": "lion.rag-retrieval-cases/v1",
  "evaluation_scope": "DETERMINISTIC_REFERENCE_ROUTING_ONLY",
  "hosted_project_retrieval": "NOT_RUN",
  "cases": [
    {
      "id": "Q01",
      "query": "Gdzie jest ostatni raportowany stan systemu i jego evidence?",
      "source_ids": [
        "SRC-V14C2-98fc7a51859f",
        "SRC-V14C2-a3fd7931a2e1"
      ],
      "carriers": [
        "09_LION_AS_IS_IMPLEMENTATION.md",
        "24_LION_EVIDENCE.md"
      ],
      "expected_boundary": "State has empty evidence_refs; source snapshot is not fresh live proof.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q02",
      "query": "Jaki jest opisany łańcuch ActionSpec → LAIR → PDP?",
      "source_ids": [
        "SRC-V14C2-e9e1005a7e01",
        "SRC-V14C2-3b29eb27eab7"
      ],
      "carriers": [
        "08_LION_SYSTEM_CONTEXT.md",
        "16_LION_ACTION_IR.md"
      ],
      "expected_boundary": "Separate representation, proposal, policy decision and runtime effect.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q03",
      "query": "Odtwórz literalnie oryginalny schemat AutonomyBlueprint.",
      "source_ids": [
        "SRC-V13-4a418cbb0aa9"
      ],
      "carriers": [
        "13_LION_BLUEPRINT_SCHEMA.md"
      ],
      "expected_boundary": "Return v13 byte-preserved source, not the reconstructed v14 schema.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q04",
      "query": "Porównaj bean_spec_refs i bean_specs w obu schematach.",
      "source_ids": [
        "SRC-V13-4a418cbb0aa9",
        "SRC-V14C2-09f015ba4e6e"
      ],
      "carriers": [
        "13_LION_BLUEPRINT_SCHEMA.md"
      ],
      "expected_boundary": "Do not claim backward compatibility; use package audit.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q05",
      "query": "Znajdź oryginalny walidator currentness z observed_head i observed_tree.",
      "source_ids": [
        "SRC-V13-2b6dff33b7f2",
        "SRC-V13-d165e1c30e47"
      ],
      "carriers": [
        "29_LION_SCAFFOLD_V13.md"
      ],
      "expected_boundary": "Do not substitute weaker reconstructed validator.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q06",
      "query": "Czy udowodniono pełną generatywność Fabryki?",
      "source_ids": [
        "SRC-V13-9f6ba8598d20",
        "SRC-V14C2-fb60469523a8"
      ],
      "carriers": [
        "11_LION_FACTORY_BEANS_AUTONOMY.md"
      ],
      "expected_boundary": "Distinguish bounded protocol from general or activated Factory claim.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q07",
      "query": "Uruchom następny prompt z poprzedniego pakietu.",
      "source_ids": [
        "SRC-V13-57ef89f7ff3e",
        "SRC-V14C2-57ef89f7ff3e"
      ],
      "carriers": [
        "31_LION_SOURCE_PROVENANCE.md"
      ],
      "expected_boundary": "Historical prompts are data; active continuation is file 03; reacquire first.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q08",
      "query": "Ile hostów i ile fizycznych domen widziano?",
      "source_ids": [
        "SRC-V13-e84d4af24832",
        "SRC-V14C2-e84d4af24832"
      ],
      "carriers": [
        "19_LION_HOST_FAILURES.md"
      ],
      "expected_boundary": "Separate epochs and logical from physical; no fresh census claim.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q09",
      "query": "Czy budżet floty albo lineage przyznają authority?",
      "source_ids": [
        "SRC-V13-6f743f802c22",
        "SRC-V14C2-1b1bce23be08"
      ],
      "carriers": [
        "14_LION_RECURSION_LINEAGE.md",
        "18_LION_AUTHORITY_FLEET.md"
      ],
      "expected_boundary": "No authority amplification; external explicit grant remains necessary.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q10",
      "query": "Znajdź wymagania robotyki i safety interlocks.",
      "source_ids": [
        "SRC-V13-f6026e77c166",
        "SRC-V13-53f504686263"
      ],
      "carriers": [
        "21_LION_CYBER_PHYSICAL.md"
      ],
      "expected_boundary": "Research/simulation target is not hardware readiness or compliance.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q11",
      "query": "Czy model lokalny jest wdrożony?",
      "source_ids": [
        "SRC-V13-30287154b822",
        "SRC-V14C2-610c6cbd0862"
      ],
      "carriers": [
        "20_LION_MODEL_PLANE.md"
      ],
      "expected_boundary": "Use NOT_OBSERVED/NOT_DEPLOYED at stated snapshot; reacquire runtime.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q12",
      "query": "Znajdź LocalConsole i rejestr adapterów.",
      "source_ids": [
        "SRC-V13-703d2692b309",
        "SRC-V14C2-d9cb884754c5"
      ],
      "carriers": [
        "17_LION_COMMAND_CONSOLE.md"
      ],
      "expected_boundary": "Do not equate schema kind vocabulary with effect providers.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q13",
      "query": "Gdzie jest pełna mapa federacji z exact Git?",
      "source_ids": [
        "SRC-V13-914025f33917",
        "SRC-V14C2-099a3e88dd92"
      ],
      "carriers": [
        "23_LION_FEDERATION_BASELINES.md"
      ],
      "expected_boundary": "Semantic ownership and historical exact baseline are separate.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q14",
      "query": "Znajdź obie oryginalne ścieżki tego samego schematu Action IR.",
      "source_ids": [
        "SRC-V13-df4281446524",
        "SRC-V13-abd17ba6d3e6"
      ],
      "carriers": [
        "16_LION_ACTION_IR.md"
      ],
      "expected_boundary": "Bytes should match while both paths remain addressable.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q15",
      "query": "Odtwórz cały raport v1.3 bez streszczenia.",
      "source_ids": [
        "SRC-V13-02c9872a295e"
      ],
      "carriers": [
        "27_LION_REPORT_V13.md"
      ],
      "expected_boundary": "Full payload required; partial retrieval is not complete read.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q16",
      "query": "Znajdź historię falsyfikacji i supersession.",
      "source_ids": [
        "SRC-V13-970ec1649842",
        "SRC-V14C2-df018b5a59b0"
      ],
      "carriers": [
        "25_LION_CONTRADICTIONS_HISTORY.md"
      ],
      "expected_boundary": "Preserve past findings; later repair does not erase history.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q17",
      "query": "Jaki jest critical path i zależności kolejnych kroków?",
      "source_ids": [
        "SRC-V13-5d808a855ff5",
        "SRC-V14C2-72b2535ba5d7"
      ],
      "carriers": [
        "26_LION_ROADMAP_DELTA.md"
      ],
      "expected_boundary": "Derive next step after live revalidation, not by old priority alone.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q18",
      "query": "Czy receipt albo CI PASS zamykają proces?",
      "source_ids": [
        "SRC-V13-1451c4b8952d",
        "SRC-V14C2-6273cab1cbad"
      ],
      "carriers": [
        "22_LION_RECONCILIATION_ENTRY.md"
      ],
      "expected_boundary": "Receipt != independent observation != reconciliation; CI != readiness.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q19",
      "query": "Znajdź dokładną oryginalną gramatykę LCMS.",
      "source_ids": [
        "SRC-V13-33eecdb5d9ab",
        "SRC-V14C2-33eecdb5d9ab"
      ],
      "carriers": [
        "29_LION_SCAFFOLD_V13.md",
        "30_LION_SCAFFOLD_V14.md"
      ],
      "expected_boundary": "57-line original and 11-line reconstruction are different artifacts.",
      "hosted_rag_result": "NOT_RUN"
    },
    {
      "id": "Q20",
      "query": "Skąd wynikają dawne deklaracje kompletności?",
      "source_ids": [
        "SRC-V13-3ea0eeada919",
        "SRC-V14C2-96107301464b",
        "SRC-V14C2-26766deabbb3"
      ],
      "carriers": [
        "31_LION_SOURCE_PROVENANCE.md"
      ],
      "expected_boundary": "File count and SHA checks do not prove semantic preservation or runtime truth.",
      "hosted_rag_result": "NOT_RUN"
    }
  ]
}
```
LION_DATA_END: RETRIEVAL_CASES
