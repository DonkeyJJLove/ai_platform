# LION — operacyjna warstwa wiedzy

`/LION/` jest kanoniczną powierzchnią nawigacji i koordynacji dla ewolucyjnej architektury oraz operacji rojowych. **Nie jest źródłem authority wykonawczego.**

Każdy wątek/dron rozpoczyna tutaj, a przed działaniem wykonuje aktualne obserwacje stanu.

## Orientacja

1. Przeczytaj `catalog.json` i protokoły.
2. Przeczytaj mapy targetu, implementacji i ewolucji.
3. Przeczytaj rejestry misji, dronów, kanałów i zależności.
4. Ponownie zaobserwuj bieżący stan GitHub oraz autorytatywne rejestry wskazane w katalogu.
5. Oznacz projekcje nieaktualne lub skonfliktowane przed ich użyciem.
6. Rozwiąż kanał roboczy przez `ops/channel-registry.json`.
7. Kontynuuj wyłącznie w granicach authority przyznanego osobnym mechanizmem.

## Pierwszeństwo źródeł prawdy

Dla dynamicznego stanu repozytorium aktualne obserwacje GitHub mają pierwszeństwo przed zapisanymi projekcjami `/LION/`. Tożsamość i lifecycle agenta pochodzą z Agent Registry. Własność branchy względem misji pochodzi z Branch Ownership Registry. Architektura normatywna pochodzi z dokumentów architektonicznych wskazanych przez katalog. Historia czatu jest wyłącznie kontekstem i nigdy nie stanowi stanu kanonicznego.

## Model operacyjny

`TARGET -> OBSERVE -> GAP -> MISSION -> DRONE/SWARM -> BUILD -> VERIFY -> INTEGRATE -> OBSERVE -> RECONCILE -> UPDATE PROJECTIONS -> NEXT GAP`

Kanały nie są jednolitym transportem. Ich aktualny sposób dostarczenia jest zarejestrowany w `ops/channel-registry.json`.

Dla `group:architecture`, `group:security` i `group:runtime` kanoniczny transport maszynowy został zastąpiony governowanym `lion-group-channel.yml`. Wiadomość jest canonical evidence-only envelope związanym z dokładnym `master`; dispatch przechodzi przez Issue #144 jako control-plane ledger, a dostarczenie jest uznawane dopiero po niezależnej obserwacji dokładnego workflow runu i zweryfikowaniu artefaktu `lion-group-channel-receipt.json`.

Trzy kanały grupowe mają zweryfikowany zestaw replacement evidence:
- architecture — `issue:144#5400846744`, run `32728703476`, artifact `9520519173`;
- security — `issue:144#5400863876`, run `32764016518`, artifact `9533745245`;
- runtime — `issue:144#5401202742`, run `32773694624`, artifact `9537129173`.

Każdy z tych receiptów ma `state=EMITTED_EVIDENCE_ONLY`, `authority_effect=false`, `repository_effect=false` i `observation_result=OBSERVED_VERIFIED`. Historyczne Issues #103, #104 i #105 pozostają powierzchniami historycznymi/koordynacyjnymi do czasu osobnej, obserwowalnej decyzji o ich zamknięciu; same nie są authority.

## Bezpieczeństwo

Sama obecność wpisu w rejestrze, katalogu, Issue, workflow runie ani receipt nie przyznaje credentials, dostępu do runtime, authority do merge, release ani deploymentu. Stan nieznany, nieaktualny, niejednoznaczny lub skonfliktowany musi zostać ponownie zaobserwowany albo doprowadzić do fail-closed przed wykonaniem działania powodującego skutki.

Dla kanałów grupowych obowiązuje dodatkowo: exact-head binding, replay denial, terminal workflow success, unikalny artefakt, SHA-256 archive verification, canonical receipt binding i niezależny observation receipt. `UNKNOWN` lub ambiguity => `DENY`.
