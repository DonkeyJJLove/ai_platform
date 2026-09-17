# LION Operator Intervention R1

`OPERATOR_PRIMARY` jest człowiekiem uczestniczącym w komunikacji misji oraz nadrzędnym właścicielem decyzji w zatwierdzonym zakresie. Implementacja rozdziela komunikację, inferencję i sterowanie: modele pozostają proposal-only, natomiast egzekwowalny stan kontroli znajduje się w `operator_control` i jest konsumowany przez scheduler, claim workera oraz granice skutku.

## Trust root

Warstwa operatorska ma trzy rozdzielone principal identities. `OPERATOR_PRIMARY` otrzymuje pełny grant operatorski dopiero po jawnym bootstrapie aktywowanego TASK-u. `OPERATOR_PANEL_PROXY` uwierzytelnia wyłącznie lokalny transport 8780→8767; nie posiada praw człowieka. Przeglądarka uzyskuje `OPERATOR_PRIMARY` dopiero przez osobne lokalne parowanie, po którym 8767 wydaje krótkotrwały, niejawny token sesji przechowywany wyłącznie po stronie serwera 8780. `OPERATOR_SENTINELX_PROXY` ma własny klucz i ograniczony, wygasający/revocable grant: status, message, annotation, pause, stop i take-control. Proxy nigdy nie może wykonać resume, reassign, plan amendment ani grant expansion.

Sekrety 8767 nie są umieszczane w DOM, localStorage, promptach ani receiptach. Panel wymaga lokalnego Host, serwerowej sesji HttpOnly/SameSite=Strict, CSRF i kontroli Origin. Gateway pozostaje loopback-only.

## Fencing

`TAKE_CONTROL`, `PAUSE_SCOPE`, `STOP_SCOPE` i revocation zmieniają trwały `control_epoch`. Scheduler nie wybiera misji przy aktywnym operatorskim fence; nowy assignment wiąże epoch i dispatch authority; claim ponownie sprawdza currentness; worker receipt nie może zaakceptować starej generacji/epoch. Generic executor oraz historyczne bezpośrednie ścieżki materialne sprawdzają fence przed skutkiem.

READY work może zostać anulowany lub reassignowany. CLAIMED work po containment staje się `CANCEL_REQUESTED`; system raportuje `PARTIAL` i nie twierdzi, że nieprzerywalna operacja została cofnięta. Opóźniony rezultat starego wykonawcy jest zachowywany w `mission_stale_assignment_results` jako historyczne evidence, ale nie trafia do ważnego ledgeru decyzji. Reassign aktywnego workera czeka na checkpoint/reconciliation przed utworzeniem replacement assignment.

Każdy claim lokalnego workera posiada ograniczony czasowo lease. Po wygaśnięciu worker nie rozpoczyna nowej inferencji/skutku. Utrata łączności nie daje bezterminowej authority.

## Continuation

`RELEASE_CONTROL` oddaje decision ownership, ale nie zwalnia pause/stop latch. Operator musi wydać osobny `RESUME_SCOPE` z aktualnym `expected_revision`. READY assignment przygotowany przez operatora może zostać bezpiecznie przekazany nowej generacji schedulera; zakończone efekty nie są powtarzane. Terminalne oraz historyczne misje pozostają read-only z wyjątkiem statusu/adnotacji.

`AMEND_CONTEXT` działa w aktualnym zatwierdzonym zakresie. `AMEND_PLAN` zawierający rozszerzenie effect ceiling / authority scope nie staje się aktywną rewizją; trafia do `operator_pending_plan_amendments` w stanie `AWAITING_SCOPE_ACTIVATION`.

## Recovery

Gateway 8767 jest osobnym procesem od Mission Control 8766 i nie zależy od modeli ani Firefoksa. Zewnętrzny monotoniczny epoch floor zapobiega cichym rollbackom starej bazy: po wykryciu cofniętego epoch system odzyskuje co najmniej poprzedni epoch i ustawia containment przed wznowieniem.

Awaryjny `lion_operator_containment_helper.py` działa tylko na wcześniej przygotowanym exact inventory. Weryfikuje PID, executable, `/proc` starttime i hash cmdline; nie używa wyszukiwania po nazwie, arbitralnego shell ani sieci. Brak zgodności identity oznacza brak sygnału. Helper zapisuje niezależny receipt do późniejszej rekonsyliacji.

## Interfejsy

Panel 8780 udostępnia rozmowę, korektę kontekstu/planu oraz jawne akcje Pause/Stop/Take/Release/Resume wraz z owner/epoch/latch i stanem `PARTIAL/UNKNOWN`. SSE jest wyłącznie transportem projekcji; authority pozostaje w ledgerze 8767.

`lion_operator_client.py` jest klientem `OPERATOR_SENTINELX_PROXY`, nie klientem primary. Nie przyjmuje arbitralnego URL/SQL/shell i lokalnie ogranicza słownik czynności do zakresu proxy.

## Kryterium dowodowe

Zielony heartbeat, ACK kolejki albo odpowiedź modelu nie są dowodem interwencji. Dowód wymaga admission receipt, aktualnego control state, egzekwowania fence na granicy skutku oraz — gdy możliwe — niezależnego readbacku. Dla nieosiągalnych lub aktywnych zasobów poprawnym wynikiem jest `PARTIAL/UNKNOWN`, a nie fałszywe `COMPLETE`.
