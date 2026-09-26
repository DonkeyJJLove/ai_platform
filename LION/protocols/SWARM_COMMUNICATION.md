# LION — protokół komunikacji roju

Niezależne wątki nie mogą zakładać bezpośredniego dostępu do stanu czatu innych wątków. Każdy kanał jest rozwiązywany przez `LION/ops/channel-registry.json`, a sposób dostarczenia zależy od zarejestrowanego transportu.

## Adresy

- `operator:primary` — uwierzytelniony operator człowiek.
- `model:local` — lokalny wykonawca poznawczy `gpt-oss-20b-MXFP4`; wynik jest advisory, nie authority.
- `model:saas` — ChatGPT SaaS supervisor przez bieżący zarejestrowany transport; wynik jest advisory, nie authority.
- `mission:<mission_id>` — kanał roboczy misji.
- `drone:<logical_id>` — **wyłącznie logiczny dron/rola misji**, np. `drone:LD001`.
- `worker:<material_id>` — **wyłącznie materialny worker/executor**, np. `worker:MD001`.
- `swarm:<swarm_id>` — współdzielony, tymczasowy kanał roju.
- `group:<name>` — stabilny kanał funkcjonalny. Dla `architecture`, `security` i `runtime` transportem jest governowany `lion-group-channel.yml`, a rezultatem dostarczenia jest artefakt i niezależnie zweryfikowany receipt evidence-only.

Historyczne `drone:MDxxx` może być rozpoznane jako alias kompatybilności, ale nowe receipts i odpowiedzi materialnego wykonawcy MUSZĄ używać `worker:MDxxx`. Dron logiczny i worker materialny nie są tym samym uczestnikiem.

Nierozwiązany adres => fail closed i raport błędu routingu.

## Koperta wiadomości

Każda wiadomość między dronami zapisuje `message_id`, nadawcę, adres docelowy, kontekst misji, typ, correlation id, evidence refs, requested action i czas utworzenia. Dla transportu grupowego canonical envelope dodatkowo wiąże `repository`, `target`, `expected_master_head`, `issued_at`, `expires_at`, `payload_digest` i `envelope_digest`.

Dozwolone typy logicznych wiadomości pozostają: `DEPENDENCY`, `HANDOFF`, `BLOCKER`, `EVIDENCE`, `REQUEST`, `STATUS`, `RECONCILIATION`. Sam typ wiadomości nie nadaje authority.

Każdy hop poznawczy lub wykonawczy musi zachować pięć rozdzielnych ról: operator formułuje intencję; dron logiczny utrzymuje rolę/kontekst zadania; worker materialny odbiera bounded assignment i wystawia receipt; `model:local` wykonuje inferencję jako proposal-only executor; `model:saas` może niezależnie weryfikować lub rozszerzać inferencję przez zarejestrowany transport. Brak bezpośredniej authority modelu **nie oznacza braku komunikacji**: modele komunikują się z systemem wyłącznie przez mediowane koperty, assignments, receipts i Mission Control.

Minimalna koperta komunikacyjna v2 przenosi: `source`, `target`, `mission_id`, `logical_drone_id`, `material_worker_id`, `correlation_id`, `causation_id`, `cognitive_route`, `evidence_refs`, `authority_effect`, `hop_count`, `hop_limit` i digest. Odbiorca nie może zamienić koperty komunikacyjnej w authority.

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
