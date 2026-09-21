# LION R17.4 — runtime architecture reconciliation

**Semantic owner:** bieżące znaczenie runtime, który przeszedł dostarczoną akceptację live R17.4.  
**Audit date:** 2026-09-21.  
**Documentation authority effect:** NONE.  
**Runtime effect:** NONE.

## Currentness and provenance

Audyt rozdziela dwa różne evidence planes.

Audytowany GitHub default branch to `master` przy HEAD `da4dbd7b27b4833c0debddf839e003f2ce170d5c`, TREE `20fa96a86857cecacc5a3c772e2a4dcd7f797dad`. Ten tree nadal zawiera Pythonowy gateway 8780 oraz browser-mediated Node/UIA lineage scalony przez PR #362.

Dostarczona tożsamość akceptacji R17.4 to HEAD `745e2672dbf326d4c210efea6bd279f4880efdd0`, TREE `9f262a92f3cd74773eeaf5b4202666757df34e7f`, branch `lion-node-express-r17-c552dcf0f28b`. W czasie audytu GitHub nie rozwiązywał tego commitu, branch nie istniał, a na default branch nie znaleziono implementacji Node/Express 8780 odpowiadającej tej tożsamości.

```text
PROVEN_R17_4_LIVE_OBSERVATION != CURRENT_GITHUB_MASTER_EXECUTABLE_SOURCE
```

Dla pytań o runtime, który przeszedł akceptację R17.4, ten dokument jest semantic ownerem. Dla pytań o to, co może wykonać aktualny GitHub `master`, pierwszeństwo ma aktualny executable source. Brak publikacji źródła R17.4 w audytowanym GitHub jest jawną luką currentness, a nie powodem do wymyślania brakującej architektury.

## R17.4 proven runtime topology

| Port | R17.4 role |
| --- | --- |
| `8780` | Node.js + Express panel/runtime orchestration |
| `8772` | materialized local model inference endpoint |
| `8766` | Mission Control / SaaS broker |
| `8767` | operator control |
| `8791` | durable Turn Ingress |
| `8792` | MCP transport/tunnel |

Kanoniczny tor durable SaaS R17.4:

```text
PANEL
-> Node.js / Express
-> Mission Control broker
-> Node durable-turn relay
-> Turn Ingress
-> MCP transport
-> external ChatGPT session may consume and complete the durable turn
-> receipt reconciliation
-> exactly-once same-thread delivery
```

Nie wolno dokumentować:

```text
Node -> MCP -> automatic ChatGPT inference
```

bez bieżącego executable evidence model-execution providera. MCP jest granicą transport/tooling, nie ChatGPT model inference API. Durable turn dowodzi handoffu, nie autonomicznego wykonania przez ChatGPT.

## Local model boundary

Port `8772` jest materializowanym endpointem lokalnego modelu. Node/Express może go wywoływać przez provider/adapter boundary.

```text
LOCAL_MODEL_INFERENCE != CHATGPT_SAAS_DURABLE_HANDOFF
PROVIDER_SELECTION != AUTHORITY_SELECTION
```

Output modelu pozostaje outputem kognitywnym/proposal, dopóki osobna ścieżka authority nie dopuści consequential effect.

## Layered readiness

| Readiness dimension | R17.4 accepted state |
| --- | --- |
| `CONTROL_PLANE_READY` | `true` |
| `TURN_INGRESS_READY` | `true` |
| `MCP_TRANSPORT_READY` | `true` |
| `DURABLE_TURN_DISPATCH_READY` | `true` |
| `LOCAL_MODEL_READY` | `true` |
| `MODEL_EXECUTOR_READY` | `false` |
| `AUTONOMOUS_DISPATCH_READY` | `false` |
| `BROWSER_AUTOMATION` | `DISABLED_BY_POLICY` |

Dodatkowo zaakceptowano: jeden proces panelu Node/Express, zero legacy Python panel processes w zaakceptowanym runtime, jeden relay process, `relay_fresh=true` oraz `thread_persistence_canary=PASS`.

```text
TRANSPORT_READY != MODEL_EXECUTION_READY
HANDOFF_READY != AUTONOMOUS_EXECUTION_READY
MCP_TRANSPORT != MODEL_INFERENCE_ENDPOINT
CHATGPT_MCP_TURN != CHATGPT_MODEL_ENDPOINT
```

## Browser/UIA retirement in R17.4

Dla zaakceptowanego R17.4:

```text
BROWSER_AUTOMATION=DISABLED_BY_POLICY
```

Poniższy łańcuch nie jest bieżącą instrukcją routingu R17.4:

```text
mediator.js
-> background_driver.cjs
-> edge_session_worker.ps1
-> Edge
-> ChatGPT
```

Te pliki i testy są nadal obecne w audytowanym `master` z powodu PR #362. Dlatego są klasyfikowane jako **superseded for R17.4 live-runtime guidance, while still present in current GitHub source**. Dokumentacyjna rekonsyliacja nie usuwa executable source.

## Codex boundary

```text
CODEX_PROJECT_HARNESS != LION_RUNTIME
```

Materiały `LION/codex/` opisują repository-development, analysis, evaluation i runbook tooling. Nie ustanawiają `codex.exe`, Codex CLI, Codex App Server ani Codex model executora jako komponentu R17.4. Codex nie jest właścicielem panel execution, ChatGPT execution, MCP completion ani authority.

## Authority separation

```text
MODEL_OUTPUT != AUTHORITY
TURN != EFFECT
MCP_TRANSPORT != AUTHORITY
RECEIPT != AUTHORITY
PROVIDER_SELECTION != AUTHORITY_SELECTION
LOGICAL_DRONE != MATERIAL_EXECUTOR
EXPECTED != REPORTED != OBSERVED != RECONCILED
```

Model output jest proposal/cognitive output. Transport transportuje. Turn utrwala i przekazuje pracę. Receipt jest evidence. Żaden z tych obiektów samodzielnie nie mintuje authority, nie podejmuje decyzji i nie dowodzi external effect.

## Exactly-once and same-thread semantics

Akceptacja R17.4 obejmuje durable delivery semantics: broker request/turn jest rekonsyliowany przez receipt evidence i dostarczany dokładnie raz do tego samego durable panel thread. Nie wolno scalać transportu, model execution i delivery w jeden stan. Turn może być transport-ready i niezużyty; zużyty i nieukończony; ukończony i nierekonsyliowany.

## Repository-source divergence found by this audit

Przy audytowanym `master`:

- `cyber_lion/app_coordination/local_intelligence_gateway.py` nadal definiuje Pythonowy gateway z domyślnym `port=8780`;
- `tools/firefox_mediator/mediator.js`, `background_driver.cjs` i `edge_session_worker.ps1` pozostają executable browser/UIA components;
- `tools/lion_secure_mcp_broker_relay.py` celuje w Turn Ingress `127.0.0.1:8791` i sprawdza Node background browser-driver readiness;
- bieżące testy jawnie asercjonują browser/background-driver path;
- nie znaleziono pasującego źródła R17.4 Node/Express 8780, dostarczonego commitu, dostarczonego branchu ani wykonywalnej implementacji 8792 odpowiadającej opisowi R17.4.

To jest luka publikacji/currentness, nie zgoda na uzupełnianie architektury domysłem.

## Documentation routing policy

Dla pytań o `8780`, Node/Express, ChatGPT routing, SaaS broker, MCP, browser automation lub bieżący runtime R17.4 należy najpierw czytać ten dokument.

Starsze dokumenty pozostają ważne jako dated evidence, jeżeli zachowują provenance. Browser-mediated T03/TASK022 oraz Python 8780 nie mogą być po cichu używane jako opis zaakceptowanego runtime R17.4.

```text
CURRENT_EXECUTABLE_SOURCE
-> CURRENT_TESTS
-> CURRENT_RUNTIME_CONFIG_CONTRACTS
-> EXACT_GIT_IDENTITY
-> CURRENT_DOCUMENTATION
-> HISTORICAL_REPORTS
```

Live-runtime observation może dowodzić deployment state bez dowodu publikacji tego samego source w GitHub. Source presence może dowodzić implementacji bez dowodu deploymentu.

## Open reconciliation gap

`R17_4_EXECUTABLE_SOURCE_PUBLICATION=NOT_MATERIALIZED_IN_AUDITED_GITHUB_STATE`.

Closure wymaga rozwiązywalnej Git identity zawierającej Node.js + Express 8780 oraz R17.4 MCP/turn architecture, a następnie exact-source comparison i documentation readback.
