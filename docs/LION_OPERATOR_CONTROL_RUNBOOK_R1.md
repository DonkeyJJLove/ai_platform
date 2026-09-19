# LION Operator Control R1 — deployment and recovery runbook

## Provision

1. Zweryfikuj dokładny commit/tree wdrażanego źródła i czysty CI.
2. Zmaterializuj exact Mission Control package zgodny z `MISSION_CONTROL_V3_REQUIRED_SHA256`.
3. Uruchom `tools/lion_operator_provision.py --confirm LION-OPERATOR-DRONE-SUPREMACY-AND-LIVE-MISSION-INTERVENTION-R1`. Provisioner wykonuje SQLite backup przed migracją, weryfikuje integrity i tworzy odrębne sekrety primary, SentinelX proxy, panel transport oraz pairing. Surowych sekretów nie zapisuj do promptów/logów.
4. Zainstaluj `deploy/systemd/lion-operator-control.service`, daemon-reload, enable/start. Oczekiwany bind: wyłącznie `127.0.0.1:8767`.
5. Restartuj 8766 z exact package. Zweryfikuj `/api/v3/capabilities/process-contracts`, integrity DB i brak regresji SaaS receipt/thread delivery.
6. Na Windows wdroż aktualne `lion_local_intelligence_runtime.py` i `local_intelligence_gateway.py`. Panel transport oraz pairing przechowuj lokalnie; pairing może być zabezpieczony DPAPI CurrentUser.
7. Restart 8780 nie może tworzyć misji/komendy. Pierwsza akcja operatorska wymaga sparowania człowieka.

## Health/readback

Sprawdź osobno: 8766 Mission Control, 8767 Operator Control, 8780 panel, 8772 model. Kontrola operatora nie może zależeć od 8772 ani Firefox/SaaS. Zweryfikuj owner, epoch, pause/stop latch, command receipt, worker admissions i in-flight assignments.

## Emergency containment

Jeżeli 8766 jest niedostępny, 8767 nadal przyjmuje containment. Jeżeli 8767/DB również są niedostępne, użyj helpera tylko dla wcześniej zarejestrowanego exact inventory. Nie zastępuj go `pkill`, grepem nazwy procesu ani szerokim kill. Po przywróceniu usług zaimportuj/porównaj receipt helpera i nie wykonuj RESUME przed rekonsyliacją.

## Rollback

Kod można cofnąć dopiero po zatrzymaniu nowych admissions i wykonaniu backupu. Nie przywracaj starej bazy jako sposobu usunięcia STOP/TAKE_CONTROL. Epoch floor ma pierwszeństwo nad cofniętym snapshotem. Po rollbacku bazy gateway wymusza containment, a wznowienie wymaga nowego, aktualnego polecenia operatora.

## SAT

Użyj benign canary. Wykonaj: status → message to drone → context amendment → take control → stop → reassign remaining work → release control → explicit resume → readback, a następnie wariant bez modeli/Firefoksa. Powtórz containment przez SentinelX proxy oraz z niedostępnym 8766. Wynik pełny jest dopuszczalny wyłącznie, gdy brak niepotwierdzonych in-flight zasobów; w przeciwnym razie raportuj PARTIAL.
