# LION — protokół komunikacji roju

Niezależne wątki nie mogą zakładać bezpośredniego dostępu do stanu czatu innych wątków. Koordynacja między wątkami korzysta z GitHub Issues/komentarzy zarejestrowanych w `LION/ops/channel-registry.json`.

## Adresy

- `mission:<mission_id>` — kanał roboczy misji.
- `drone:<drone_id>` — rozwiązuje się do zarejestrowanego kanału roboczego drona.
- `swarm:<swarm_id>` — współdzielony, tymczasowy kanał roju.
- `group:<name>` — stabilny kanał funkcjonalny, np. architecture/security/runtime.

Nierozwiązany adres => fail closed i raport błędu routingu.

## Koperta wiadomości

Każda wiadomość między dronami zapisuje: `message_id`, `from`, `to`, `mission_id`, `type`, `correlation_id`, `evidence_refs`, `requested_action`, `created_at` oraz opcjonalne `expires_at`.

Dozwolone typy wiadomości: `DEPENDENCY`, `HANDOFF`, `BLOCKER`, `EVIDENCE`, `REQUEST`, `STATUS`, `RECONCILIATION`.

## Dostarczenie

1. Rozwiąż adres docelowy przez channel registry.
2. Ponownie zaobserwuj stan Issue/kanału.
3. Opublikuj jedną ustrukturyzowaną kopertę jako komentarz.
4. Nadawca zapisuje odwołanie evidence/correlation id we własnym stanie misji, gdy jest to wymagane.
5. Odbiorca odczytuje kanał podczas bootstrap/checkpoint i przed działaniem waliduje wskazane evidence.

## Reguły roju

- Wiadomości grupowe nie zmieniają po cichu stanu każdego drona.
- Handoff dla działania powodującego skutki wymaga jawnego potwierdzenia odbiorcy/evidence.
- Blocker jest najpierw routowany do najmniejszego odpowiedzialnego kanału; eskalacja następuje dopiero wtedy, gdy ownership zależności nie pozwala go rozwiązać.
- Nie duplikuj artefaktów kanonicznych w komentarzach; linkuj niezmienne odwołania SHA/PR/run/evidence.
- Komunikacja nigdy nie rozszerza authority.
