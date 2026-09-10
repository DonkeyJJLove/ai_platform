# LPCL — checklista niezależnego review

Reviewer powinien odrzucić kandydata, jeśli odpowiedź na którekolwiek z poniższych pytań brzmi „tak”:

- Czy LPCL może grantować lub mintować authority?
- Czy LPCL może oceniać lub zastąpić canonical PDP?
- Czy LPCL może konstruować `RuntimeAdmission`?
- Czy LPCL może wybierać lub wykonywać `EffectProvider`?
- Czy historyczny `RUN` może dotrzeć do wykonania bez canonicalization?
- Czy `UNKNOWN` może zostać wymuszone jako `PASS`?
- Czy `PASS` może implikować `CURRENT`, `AUTHORIZED`, `OBSERVED` albo `RECONCILED`?
- Czy `CONTINUE` może pomijać dependencies, ignorować currentness albo rozszerzać scope?
- Czy non-idempotent retry może nastąpić bez reconciliation-first semantics?
- Czy consequential `PASS` może pominąć evidence dla admission/effect/observation/reconciliation/currentness?
- Czy samo istnienie LPCL wymaga 16. warstwy architektury?
- Czy LPCL zastępuje `EvolutionaryEpochEngine`, zamiast współistnieć z nim?

Kandydat nadaje się do integration review dopiero wtedy, gdy wszystkie odpowiedzi brzmią „nie” i exact-head CI jest zakończone sukcesem.

Ta checklista nie stanowi sama w sobie integration authority.
