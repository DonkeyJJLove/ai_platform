# Harness ewolucji LION

Warstwa repozytoryjna do odtwarzania znaczenia, przygotowania zmian i sprawdzania procesu. Authority effect: NONE. Runtime effect: NONE. Nie jest nowym executorem, PDP ani runtime admission.

| Płaszczyzna | Pytanie | Właściciel |
|---|---|---|
| RAG | Co projekt wie w wersjonowanych źródłach? | `LION/rag/lion_project_rag32_v1_4_r1/` |
| AGENTS | Jak wejść i znaleźć właściwe źródła? | root i scoped AGENTS |
| LIVE_STATE | Co zaobserwowano teraz, gdzie i dla jakiej tożsamości? | [schemat](LIVE_STATE.schema.json), oddzielne instancje |
| Runbook i skill | Jak powtarzać dozwoloną pracę? | [runbook](CODEX_RUNBOOK.md), skill w `.codex/skills/lion-evolution/` |
| Evals | Czy reasoner i proces zachowują granice? | `LION/evals/` |

[TIGER Geometry](TIGER_GEOMETRY.md) eksploruje relacje przed oddzielną falsyfikacją. [Scaffolding](SCAFFOLDING_PROTOCOL.md) zachowuje strukturę wejścia. ADR w `LION/ADR/` wyjaśniają powody separacji.

Czytaj szczegóły według zadania: [inwarianty](EVOLUTION_INVARIANTS.md), [klasyfikacja zmian](CHANGE_CLASSIFICATION.md), [mapa narzędzi](TOOL_AUTHORITY_MAP.yaml), [sygnatury awarii](FAILURE_SIGNATURES.md), [manifest](HARNESS_MANIFEST.json). Inwentarz zdolności i reguły opisowe nie przyznają trwałych uprawnień. Przekazanie następcy zawiera jawne artefakty, decyzje i dowody, nie ukryty tok rozumowania.
