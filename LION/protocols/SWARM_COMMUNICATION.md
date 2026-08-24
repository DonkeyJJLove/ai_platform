# LION — protokół komunikacji roju

Niezależne wątki nie mogą zakładać bezpośredniego dostępu do stanu czatu innych wątków. Każdy kanał jest rozwiązywany przez `LION/ops/channel-registry.json`, a sposób dostarczenia zależy od zarejestrowanego transportu.

## Adresy

- `mission:<mission_id>` — kanał roboczy misji.
- `drone:<drone_id>` — rozwiązuje się do zarejestrowanego kanału roboczego drona.
- `swarm:<swarm_id>` — współdzielony, tymczasowy kanał roju.
- `group:<name>` — stabilny kanał funkcjonalny. Dla `architecture`, `security` i `runtime` transportem jest governowany `lion-group-channel.yml`, a rezultatem dostarczenia jest artefakt i niezależnie zweryfikowany receipt evidence-only.

Nierozwiązany adres => fail closed i raport błędu routingu.

## Koperta wiadomości

Każda wiadomość między dronami zapisuje `message_id`, nadawcę, adres docelowy, kontekst misji, typ, correlation id, evidence refs, requested action i czas utworzenia. Dla transportu grupowego canonical envelope dodatkowo wiąże `repository`, `target`, `expected_master_head`, `issued_at`, `expires_at`, `payload_digest` i `envelope_digest`.

Dozwolone typy logicznych wiadomości pozostają: `DEPENDENCY`, `HANDOFF`, `BLOCKER`, `EVIDENCE`, `REQUEST`, `STATUS`, `RECONCILIATION`. Sam typ wiadomości nie nadaje authority.

## Dostarczenie

Dla kanałów mission/drone/swarm użyj transportu zarejestrowanego dla danego adresu. Kanały, które nadal wskazują GitHub Issue/comments, wymagają ponownej obserwacji Issue przed publikacją i zapisania niezmiennego evidence ref.

Dla `group:architecture`, `group:security` i `group:runtime` obowiązuje sekwencja:

1. Rozwiąż adres przez channel registry do targetu `lion-group-channel.yml`.
2. Zbuduj canonical evidence-only envelope związany z dokładnym bieżącym `master`.
3. Wyślij go wyłącznie przez governowany dispatch control plane na Issue #144.
4. Wymagaj accepted dispatch receipt z exact-head i replay binding.
5. Zaobserwuj dokładnie jeden terminalny `workflow_dispatch` i jego nazwany artefakt.
6. Zweryfikuj SHA-256 archiwum, pojedynczy `lion-group-channel-receipt.json`, canonical JSON, message/target/head/digest bindings oraz `authority_effect=false` i `repository_effect=false`.
7. Uznaj dostarczenie dopiero po `LION-GROUP-CHANNEL-OBSERVATION-RECEIPT v1` z `observation_result=OBSERVED_VERIFIED`.

Historyczne Issues #103, #104 i #105 pozostają powierzchniami historycznymi/koordynacyjnymi do czasu osobnej decyzji o ich closure; nie są już kanonicznym transportem maszynowym dla trzech kanałów grupowych.

## Reguły roju

- Wiadomość ani receipt nie są authority.
- Group channel jest evidence-only i nie może raportować repository/runtime effect.
- Handoff dla działania powodującego skutki wymaga osobnego authority oraz niezależnej weryfikacji evidence.
- Blocker jest najpierw routowany do najmniejszego odpowiedzialnego kanału.
- Nie duplikuj artefaktów kanonicznych w komentarzach; używaj SHA, run id, artifact id, receipt digest i immutable refs.
- Replay, ambiguity, stale head, niepoprawny artifact albo UNKNOWN => DENY.
- Komunikacja nigdy nie rozszerza authority.
