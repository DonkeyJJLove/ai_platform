# LION — audyt źródeł, korekta wcześniejszego pakowania i wynik kontroli

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

## Ustalenie przyczyny

Nowo dołączony pełny `LION_SYSTEM_v1_3(1).zip` zawiera 61 plików: 59 tekstowych oraz dwa `.pyc`. Wszystkie 60 wpisów `SOURCE_DIGESTS.sha256` odpowiada rzeczywistym bajtom archiwum. Manifest wymienia 58 payloadów; trzy dodatkowe pliki sterujące to manifest, verification report i lista digestów. Liczby 58/60/61 opisują różne zakresy liczenia, nie uszkodzenie pełnego archiwum.

Poprzedni RAG40 był selekcją: wszystkie jego 40 plików są zgodne z pełnym źródłem, ale brakowało 19 źródeł tekstowych i dwóch cache’y. Wcześniejszy FULL v1.4 miał 64 pliki, więc odzyskiwał szerokość topologii poza limitem projektu, nie rozwiązywał limitu załączników. Nowy profil oddziela liczbę załączników od liczby zachowanych źródeł.

## Korekta kryterium „pełny successor”

Samo istnienie pliku o podobnej nazwie i przejście sha256sum nie dowodzi zachowania kontraktu. Dlatego v1.3 zachowano literalnie; wcześniejszą rekonstrukcję v1.4 zachowano osobno jako kandydat, nie zastąpiono nią oryginałów.

Oryginalny Blueprint ma 18 required pól, odtworzony v1.4 31. Oryginalne `bean_spec_refs`, `gap_refs`, `action_schema_refs` zostały w rekonstrukcji zastąpione przez `bean_specs`, `gap_ref`, `action_schemas`; część typów string/array/object rozszerzono do unii typów. Bez jawnej migracji i testów nie wolno nazwać tego bezstratnym carry-forward. Źródła: `SRC-V13-4a418cbb0aa9` — `v13/LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json` w `13_LION_BLUEPRINT_SCHEMA.md` oraz `SRC-V14C2-09f015ba4e6e` — `v14c2/LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_4_candidate.source.json` w `13_LION_BLUEPRINT_SCHEMA.md`.

Oryginalny walidator `validate_state` przyjmuje zewnętrznie zaobserwowane repository/head/tree, sprawdza exact root fields, zamknięty słownik stanów i wymagane ścieżki dowodowe. Wcześniejsze v1.4 `validate(state)` nie przyjmuje niezależnie observed_head/observed_tree, nie zachowuje wszystkich tych kontroli. Gramatyka LCMS ma w oryginale 57 linii, rekonstrukcja 11. Rozmiar nie jest sam w sobie miarą poprawności, ale analiza interfejsu i treści pokazuje, że nie są to identyczne kontrakty. Obie wersje umieszczono w plikach 29/30, bez automatycznego wyboru słabszej jako nowej bramki.

Wcześniejszy `LION_CANONICAL_STATE_v1_4_candidate.source.json` ma 31 rekordów i 31 pustych `evidence_refs`. Wydanie źródła, które samo deklaruje INTEGRATED, nie dostarcza brakujących dowodów. Źródło zachowano, lecz w nowym protokole kontynuacji nie wolno używać go samodzielnie do promocji stanu. To korekta sposobu użycia danych, a nie niewidoczna edycja archiwalnych payloadów.

## Wersje i pamięć

Nie podnoszono mechanicznie wersji JSON Schema do 1.4. Źródła zachowują własne wersje. To wydanie formatu RAG przenosi oryginalny pakiet v1.3 i wcześniejszy kandydat v1.4. Nie twierdzi świeżej zgodności repozytoriów, CI ani hostów. Ustanawia regułę limitu 40 w plikach sterujących i instrukcji projektu; nie zmienia globalnej pamięci konta ani samych ustawień projektu.

## Zakres kontroli

Wykonane lokalnie: inwentaryzacja archiwów, sprawdzenie deklarowanych hashy, porównanie RAG40 z pełnym ZIP-em, parsowanie źródeł tekstowych, składniowa analiza Python bez wykonania, budowa mapy źródeł, sprawdzenie spójności kontenerów i ich bajtowej odtwarzalności. Stare raporty testów zachowano jako materiał z przeszłości; ich PASS nie jest ponownym wykonaniem w tym przebiegu.

Nie wykonano: uploadu do projektu, testów rzeczywistego indeksu RAG, nowego audytu repozytoriów lub hostów, integracji architektury ani efektu runtime. Nie twierdzimy, że 32 pliki gwarantują niezawodne retrieval w każdej sesji. Zestaw prób instalacyjnych znajduje się w 06.

LION_DATA_BEGIN: SOURCE_AUDIT
```json
{
  "schema_version": "lion.rag-source-audit/v1",
  "release_id": "lion-rag32-v1.4-r1",
  "scope": "ATTACHED_ARCHIVES_AND_PREVIOUS_DERIVED_PACKAGE_ONLY",
  "live_revalidation_performed": false,
  "v13": {
    "physical_files": 61,
    "text_files": 59,
    "binary_cache_files": 2,
    "sha256_entries": 60,
    "sha256_pass": 60,
    "manifest_payloads": 58,
    "manifest_unlisted_control_files": [
      "PACKAGE_MANIFEST.json",
      "SOURCE_DIGESTS.sha256",
      "VERIFICATION_REPORT.json"
    ]
  },
  "rag40": {
    "physical_files": 40,
    "content_matches_v13": 40,
    "omitted_files": [
      "LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json",
      "LION_COMMAND_ADAPTER_REGISTRY_v1_3_candidate.source.json",
      "LION_CYBER_PHYSICAL_ACTION_MODEL_v1_3_candidate.source.md",
      "LION_EVOLUTION_ROADMAP_v1_3_candidate.source.md",
      "LION_LOCAL_OPENAI_LAB_PLAN_v1_3_candidate.source.md",
      "LION_MODEL_PLANE_v1_3_candidate.source.md",
      "LION_ROBOTICS_LAB_PLAN_v1_3_candidate.source.md",
      "NEXT_EXECUTION_PROMPT.md",
      "SUPERSESSION_REGISTER.json",
      "evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md",
      "evidence/GITHUB_BASELINES.json",
      "evidence/HOST_CENSUS_SUMMARY.json",
      "evidence/OPENAI_LOCAL_MODEL_RESEARCH.md",
      "scaffold/README.md",
      "scaffold/__pycache__/test_validate_canonical_state.cpython-313.pyc",
      "scaffold/__pycache__/validate_canonical_state.cpython-313.pyc",
      "scaffold/action_ir.schema.json",
      "scaffold/canonical_state.schema.json",
      "scaffold/lcms.ebnf",
      "scaffold/test_validate_canonical_state.py",
      "scaffold/validate_canonical_state.py"
    ],
    "omitted_text_files": [
      "LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json",
      "LION_COMMAND_ADAPTER_REGISTRY_v1_3_candidate.source.json",
      "LION_CYBER_PHYSICAL_ACTION_MODEL_v1_3_candidate.source.md",
      "LION_EVOLUTION_ROADMAP_v1_3_candidate.source.md",
      "LION_LOCAL_OPENAI_LAB_PLAN_v1_3_candidate.source.md",
      "LION_MODEL_PLANE_v1_3_candidate.source.md",
      "LION_ROBOTICS_LAB_PLAN_v1_3_candidate.source.md",
      "NEXT_EXECUTION_PROMPT.md",
      "SUPERSESSION_REGISTER.json",
      "evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md",
      "evidence/GITHUB_BASELINES.json",
      "evidence/HOST_CENSUS_SUMMARY.json",
      "evidence/OPENAI_LOCAL_MODEL_RESEARCH.md",
      "scaffold/README.md",
      "scaffold/action_ir.schema.json",
      "scaffold/canonical_state.schema.json",
      "scaffold/lcms.ebnf",
      "scaffold/test_validate_canonical_state.py",
      "scaffold/validate_canonical_state.py"
    ]
  },
  "previous_v14_full": {
    "physical_files": 64,
    "sha256_entries": 63,
    "sha256_pass": 63,
    "canonical_state_record_count": 31,
    "canonical_state_empty_evidence_refs": 31,
    "blueprint_original_required_count": 18,
    "blueprint_reconstructed_required_count": 31,
    "blueprint_original_only_properties": [
      "action_schema_refs",
      "bean_spec_refs",
      "gap_refs"
    ],
    "blueprint_reconstructed_only_properties": [
      "action_schemas",
      "bean_specs",
      "gap_ref"
    ],
    "validator_original_bytes": 5110,
    "validator_reconstructed_bytes": 1230,
    "grammar_original_lines": 57,
    "grammar_reconstructed_lines": 11
  },
  "coverage": {
    "text_sources_preserved": 123,
    "source_namespaces": {
      "v13": 59,
      "v14c2": 64
    },
    "physical_attachments": 32,
    "reserved_slots": 8,
    "source_reconstruction_performed_in_this_release": false
  },
  "new_claims_status": "CONTAINER_DESIGN_AND_LOCAL_AUDIT_ONLY",
  "project_rag_upload": "NOT_PERFORMED",
  "project_retrieval": "NOT_RUN"
}
```
LION_DATA_END: SOURCE_AUDIT

## Wynik testów kontenera

LION_DATA_BEGIN: CONTAINER_TEST_REPORT
```json
{
  "scope": "OFFLINE_CONTAINER_ONLY",
  "container_checks": {
    "status": "PASS",
    "tests": [
      {
        "test": "missing_carrier",
        "status": "PASS_REJECTED",
        "reason": "missing or unexpected attachment"
      },
      {
        "test": "payload_corruption",
        "status": "PASS_REJECTED",
        "reason": "attachment SHA-256/length mismatch"
      },
      {
        "test": "unexpected_33rd_file",
        "status": "PASS_REJECTED",
        "reason": "missing or unexpected attachment"
      },
      {
        "test": "mixed_epoch_header",
        "status": "PASS_REJECTED",
        "reason": "mixed release/profile header"
      },
      {
        "test": "authority_promotion",
        "status": "PASS_REJECTED",
        "reason": "packaging cannot promote runtime authority/currentness"
      },
      {
        "test": "unobserved_currentness_promotion",
        "status": "PASS_REJECTED",
        "reason": "packaging cannot promote runtime authority/currentness"
      },
      {
        "test": "source_omitted_from_map",
        "status": "PASS_REJECTED",
        "reason": "source cardinality mismatch"
      },
      {
        "test": "duplicate_source_id",
        "status": "PASS_REJECTED",
        "reason": "source cardinality mismatch"
      },
      {
        "test": "source_path_traversal",
        "status": "PASS_REJECTED",
        "reason": "unsafe relative path"
      },
      {
        "test": "source_misrouting",
        "status": "PASS_REJECTED",
        "reason": "source metadata differs from manifest"
      },
      {
        "test": "source_authority_from_document",
        "status": "PASS_REJECTED",
        "reason": "source data cannot grant authority"
      },
      {
        "test": "invalid_source_class",
        "status": "PASS_REJECTED",
        "reason": "invalid source epistemic class"
      },
      {
        "test": "unknown_budget",
        "status": "PASS_REJECTED",
        "reason": "attachment budget mismatch"
      },
      {
        "test": "false_source_count",
        "status": "PASS_REJECTED",
        "reason": "source cardinality mismatch"
      },
      {
        "test": "unknown_manifest_field",
        "status": "PASS_REJECTED",
        "reason": "manifest fields must be exact"
      },
      {
        "test": "unknown_source_metadata_field",
        "status": "PASS_REJECTED",
        "reason": "source fields must be exact"
      },
      {
        "test": "frame_corruption_even_when_carrier_rehashed",
        "status": "PASS_REJECTED",
        "reason": "record boundary/length mismatch"
      },
      {
        "test": "extract_rebuild_32_files_byte_identical",
        "status": "PASS"
      }
    ],
    "test_count": 18,
    "scope": "OFFLINE_CONTAINER_NOT_LIVE_RUNTIME_OR_HOSTED_RAG"
  },
  "source_archive_comparisons": [
    {
      "status": "PASS",
      "archive_id": "v13",
      "archive_members": 61,
      "text_sources_byte_identical": 59,
      "binary_cache_recorded_outside_rag": 2
    },
    {
      "status": "PASS",
      "archive_id": "v14c2",
      "archive_members": 64,
      "text_sources_byte_identical": 64,
      "binary_cache_recorded_outside_rag": 0
    }
  ],
  "live_state_revalidated": false,
  "historical_scaffolds_executed": false,
  "project_retrieval": "NOT_RUN"
}
```
LION_DATA_END: CONTAINER_TEST_REPORT
