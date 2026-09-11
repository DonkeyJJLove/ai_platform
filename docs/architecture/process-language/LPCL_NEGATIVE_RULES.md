# LPCL — semantyczne reguły negatywne

Ten dokument jest human-readable companion dla `cyber_lion/process_language/negative_corpus.json`.

Validator musi działać fail-closed dla następujących klas:

- epistemic coercion (`UNKNOWN -> PASS`, `PASS -> CURRENT`);
- currentness bez evidence-bound basis;
- interpretowanie wymagania authority jako grant albo jakiekolwiek process-level authority minting;
- raw effect semantics, raw shell, PDP, `RuntimeAdmission` albo wybór `EffectProvider` wewnątrz `ProcessIR`;
- consequential closure bez niezależnej observation i reconciliation;
- bezpośrednie wykonanie historycznego materiału `RUN`;
- kontynuacja po drift bez reacquisition;
- unbounded continuation/retry albo cycles bez bound/progress condition;
- równoległe transitions z nierozwiązanymi konfliktami scope/authority/replay/reconciliation;
- retry scope widening;
- non-idempotent partial-effect retry bez reconciliation-first semantics;
- dependency bypass;
- przenikanie pól wykonawczych `ActionSpec` w górę do `ProcessIR`;
- ponowne użycie istniejącego namespace `process_profile` jako semantic identity LPCL;
- traktowanie historycznej kolejności PHASE jako autorytatywnej, gdy jest sprzeczna z odtworzonymi dependencies.

Są to inwarianty architektury, a nie wyłącznie parser errors.


## Uzgodnienie LPCL 1.1 — integracja PR #309

Opis LPCL 1.0 powyżej zachowuje zakres historyczny i zgodność wsteczną.
Jawnie wersjonowane `RUN` z `LPCL_VERSION=1.1` mają osobny parser
`cyber_lion/process_language/canonical_run.py` oraz punkt interpretacji
`cyber_lion/process_language/interpretation.py`. Niewersjonowane `RUN` pozostają
danymi historycznymi. Parser wymaga pojedynczego końcowego `END`; znacząca treść
po nim jest błędem, a nie pomijanym fragmentem.

Gramatyka: `cyber_lion/process_language/lpcl_run_1_1.ebnf`.
Model ról: `cyber_lion/process_language/fleet_mission.py`; klasy LOGICAL, LOCAL,
HYBRID opisują reprezentację ról, nie uruchomione drony ani uprawnienia.
Interpretacja zwraca kandydatów ProcessIR/FleetMissionIR bez efektów. Nie zastępuje
Action/PDP/RuntimeAdmission. Projekcja `process_orchestration.py` wiąże istniejące
warstwy i nie dodaje nowej warstwy nadrzędnej.

Konstytucja, model floty i zamrożenie projektu w plikach `LPCL_LANGUAGE_CONSTITUTION.md`,
`LPCL_FLEET_MISSION_MODEL.md`, `LPCL_V1_1_DESIGN_FREEZE.md` dokumentują zakres kandydata
#309; ich stare HEAD/statusy nie są dowodem bieżącego master ani runtime.
Integrację i aktualność potwierdzają dokładne Git/CI, a nie etykieta w dokumencie.
