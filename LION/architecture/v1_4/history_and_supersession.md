# LION v1.4 — historia, supersession i granice falsyfikacji

Ten katalog zachowuje historię, jednocześnie umożliwiając evidence-bound reconciliation dla v1.4. Nie przepisuje v1.3, v14c2 ani wcześniejszych rekordów RAG32. Twierdzenia historyczne pozostają historyczne, dopóki nie zostaną ponownie odtworzone z live Git/source/test evidence.

## Superseded currentness

`LION/status.json` pozostaje historyczną projekcją epoki E003, której etykieta `CURRENT` jest `STALE` względem późniejszego live `master`. Późniejsze procesy nie powinny po cichu przepisywać tego consumer-sensitive state file. Dla currentness dokumentacji v1.4 używane są nowsze projekcje, ale również one stają się `STALE` po materialnym driftcie baseline'u i wymagają ponownego wygenerowania lub walidacji.

## Lineage R22C–R22H source/truth

R22C wprowadził workflow i implementację full-symbol-census. Literalna rekonstrukcja `host_authority_separation._production_path` sfalsyfikowała odziedziczone założenie: `.github/workflows/*.yml` i `*.yaml` są production sources, natomiast Python pod `cyber_lion/tests/**` jest wyłączony z production source set. Liczba production sources na ówczesnym `master` wynosiła 256. Obserwacja kandydata R22H zawierała cztery production additions i zero removals, co dawało 260 sources.

Dwa późniejsze production additions R22F to `cyber_lion/contracts/action_runtime_binding.py` oraz `cyber_lion/contracts/model_plane_adapter.py`. Exact Core inventory na lineage R22H zaobserwował 236 effect surfaces i sześć raw unclassified references; warstwa taxonomy rozwiązała wszystkie sześć bez ich ukrywania. Jest to jawny source-set identity drift przy stabilnej effect surface, a nie dowód, że zmiany source można ignorować.

R22G naprawił wyłącznie literalnie udowodnione stale source-count/scan pins oraz same-tree regression fixture. Następnie R22H zakończył documentation reconciliation i carrier-last binding na zamrożonym noncarrier tree. Historyczne subject digests R22H pozostają historyczne i nie są ponownie używane po późniejszych noncarrier changes R22I.

## R22I — kontrolowane użycie Action runtime binder

R22I rozpoczął od falsyfikacji pytania, czy `RuntimeAdmissionEngine` już konsumował dokładny output `bind_allowed_action_to_runtime_inputs`. Nie konsumował: istniejąca ścieżka admission niezależnie przyjmowała `gate`, PDP receipt, effect i runtime identity, podczas gdy canonical PDP evidence było rozwiązywane osobno. Brakującym frontierem było więc exact binder-output consumption, a nie brak `RuntimeAdmissionEngine`.

R22I zmaterializował `RuntimeAdmissionEngine.admit_bound_action` jako wysokopoziomową governed path. Wywołuje istniejący inert binder, weryfikuje zwrócone `CanonicalPDPDecisionEvidence` względem canonical PDP source i przekazuje dokładnie binder-produced `RequestedRuntimeEffect` oraz `RuntimeIdentityBinding` do istniejącego prymitywu `admit`. Nie tworzy nowego executora, providera, generic effect entrypoint, authority source, secret-resolution path ani deployment path.

Falsification ujawniła następnie węższą lukę kontraktu: wcześniejszy `RuntimeBindingCurrentness` nie wiązał exact digestu `ProvisionedExecutor`. Spójny alternate provisioning tuple mógł zatem pozostać wewnętrznie self-consistent. R22I zamknął tę lukę przez `provisioned_executor_digest`, dzięki czemu coherent provisioning substitution jest odrzucane przez trusted currentness, a nie tylko przypadkowy field mismatch.

Regression matrix R22I dowodzi exact allow consumption oraz fail-closed behavior dla `DENY`, stale currentness, action/resource/payload/authority/mission/provisioning/runtime-identity/PDP-receipt substitution i replay. High-level path nie przyjmuje caller-supplied effect ani runtime identity i nie dodaje alternate effect surface. Na exact candidate `b4045878be064586a61efa0f3ec8be5103a5a08c` wszystkie testy R22I przechodzą. Core uruchomił 2283 testy z dokładnie jednym failure i dwoma skips; jedynym failure był celowo stale truth carrier (`CHECKOUT_SUBJECT_DIGEST_DRIFT`).

Ta sama exact pre-documentation observation zachowała production source count 260, effect surfaces 236, sześć raw unclassified references i zero reconciled unclassified references. Production scan digest: `c643ab174bec81dc86fde535be72230c88cfc557a2ca5596f9362db259d02724`. `GlobalCompleteMediation` pozostawało `UNKNOWN`.

## Model plane / ASTRA

`cyber_lion/contracts/model_plane_adapter.py` jest provider-independent contract z ASTRA jako compatibility target. Nie wybiera providera, nie konfiguruje endpointu, nie odczytuje secretu, nie wykonuje inference, nie wdraża runtime ani nie mintuje authority. ASTRA runtime pozostaje w tym evidence epoch `NOT_OBSERVED`.

## Twierdzenia Factory

B0 pozostaje bounded `PASS` dla dwóch unseen problem families wewnątrz closed grammar. R22F dodał counterexample poza tą gramatyką (`float-list`), odrzucany przez `GenerativityProtocolError`. Dlatego general Factory generativity została jawnie sfalsyfikowana poza B0 grammar, zamiast być wyprowadzona z ograniczonego sukcesu. Activated child autonomy i Factory-of-Factories pozostają nieudowodnione; real child activation pozostaje human-authority boundary.

## Federation drift odziedziczony z R22H

Ostatni jawny live federation sweep w tej części lineage pozostawał dziesięciorepozytoryjnym wektorem R22H. R22I nie promował historycznego sweepu do nowej federation observation i nie zmieniał registry membership, default-branch assignments ani repository authority. Federation reads nie nadają authority i nie powodują runtime effect.

## Reguła truth carrier dla R22I

Wszystkie production, test i documentation mutations R22I były noncarrier work. Dopiero po ich zweryfikowaniu i zamrożeniu truth subject mógł zostać ponownie obliczony z wyłączeniem dokładnie `LION/architecture/canonical-state-v1-3-candidate.json` oraz `cyber_lion/registry/repositories.json`. Te dwa carriers musiały następnie stanowić ciągłe final repository-file commits. Po drugim carrier commit nie wolno było zmieniać plików repozytorium; dozwolone pozostawały jedynie readback, exact-head verification i PR metadata.

## Human authority boundaries

R22I zachował `R22E-HAB-BRANCH-MAINTENANCE-001`, real child activation, mark-ready, merge, RAG publication, runtime deployment i production deployment jako granice poza tym autonomous repository-documentation/truth-reconciliation lane.

## R23 — konsolidacja frontiera i reconciliation process plane

R23 odtworzył live candidate graph z master `67a4f8243aa6805e47035e572bd458f73fd0b358` i skonsolidował lineage R21 LPCL/Process, lineage R21/P0 `TEST_ONLY` materialization oraz R22C→R22H→R22I governed Action→Runtime w jeden krótkotrwały integration train. Zbiór merge conflicts dotyczył currentness/truth-carrier material, a nie sprzecznej semantyki implementacji. Ponowne obliczenie połączonego production set dało 268 production sources, 236 effect surfaces, sześć raw unclassified references, zero unresolved taxonomy references i scan digest `5f6561edcd368c2acce5f0e216bc9e21324da2913035e92ef175b7aca5b773a2`; żaden predecessor scan digest nie został ponownie użyty jako current truth.

Exact pre-documentation candidate `5f90f1c11e9f997ed9c5e3ac1b02c6d802d15745` / `5dd5dc653c24bdd810faeb61f901328ad246e3a7` przechodził 2410 repository tests. LPCL/Canonical Process IR został zintegrowany jako non-effectful layer: może wybierać process transitions i emitować non-authoritative `ActionIntentCandidate`, ale nie może mintować authority, oceniać PDP, konstruować RuntimeAdmission, wybierać EffectProvider ani wykonywać effect. R22I binder consumption pozostaje governed Action→Runtime path i nie staje się drugim execution plane.

Podczas transportu currentness w R23 przypadkowo utworzono transient commit `tools/.r23-placeholder`. Mutacja została natychmiast wykryta, usunięta przed freeze i wyłączona z final exact tree. Proces zachowuje ją jako operational counterexample zamiast ją zacierać; exact tree equality z lokalnie zwalidowanym kandydatem zapobiegła wejściu artefaktu transient do frozen state.

Truth closure R23 stosuje ten sam carrier-last invariant: po zweryfikowaniu całego noncarrier source/test/documentation reconciliation należy obliczyć `LION/TRUTH-SUBJECT/1`, wyłączając dokładnie `LION/architecture/canonical-state-v1-3-candidate.json` i `cyber_lion/registry/repositories.json`; następnie aktualizować wyłącznie te carriers jako final repository-file commits i wykonać read-only exact-head verification. Runtime/merge/production authority pozostają oddzielne.

## R24 → R23 post-merge reconciliation

R24 repository-ref authority provisioning został scalony do `master` jako `ab1ab2f2cbdeda1f10b2c73e78acf230f5be21da` / tree `0dea4254efc0c3da3db5fa994a9b87e9a2f85ba2` zanim opublikowano konsolidację R23. Wcześniej frozen R23 head przestał więc nadawać się do bezpośredniego merge i został potraktowany jako historical source evidence, a nie stale publication authority.

Fresh three-way reconciliation względem merged R24 baseline dał dokładnie 13 textual conflicts. Jedenaście było current scan/count expectation carriers w testach/narzędziach MOON; dwa były global truth carriers. Nie wystąpił conflict w implementacji process/runtime R23 ani w implementacji repository-ref authority R24. Połączony clean pre-documentation candidate `93afd90f781d5421ad30dfcad92650347965dd0d` / tree `e7f56e9de9a014a2371192c191e8f5471a547a37` zawierał 268 production sources i 239 effect surfaces, sześć raw unclassified references i zero unresolved references po taxonomy reconciliation. Jego stable scan digest: `861d7e2aed0d5e1dbf32aa6e13ae942682876cec4efcf4985bed4d14815725e2`.

Exact clean pre-documentation reconciliation candidate przechodził 2425 repository tests z pięcioma controlled skips. Historical R23 evidence pozostaje historyczne i nie jest przepisywane do nowego digestu. Reconciliation pozostaje non-promoting do chwili zamrożenia dokumentacji, carrier-last truth rebind, exact-head CI/security i zaobserwowania osobno administrowanego exact merge authority dla PR #303.

## Późniejsza ewolucja po R23/R24

Po opisanym wyżej lineage repozytorium przeszło dalsze etapy R2/R3 oraz integracje VKT-R3. W tej epoki dokumentacyjnej live `master` został odtworzony przed utworzeniem kandydata jako HEAD `5e40338511fe2a5f0a891c823b03f9855d6ad1e8`, TREE `306b8cf245299517278ab0959a7aca79f66e5343`. Wartości R22/R23/R24 powyżej pozostają celowo niezmienione jako historyczne evidence.

Z tego powodu żadna wcześniejsza deklaracja `CURRENT` z tego dokumentu nie może być automatycznie interpretowana jako currentness 10 września 2026. Nowy stan wymaga świeżego exact Git/runtime readback; historia jest superseded przez późniejszy stan w wymiarze currentness, ale nie jest kasowana.
