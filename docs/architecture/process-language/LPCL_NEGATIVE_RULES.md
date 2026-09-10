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
