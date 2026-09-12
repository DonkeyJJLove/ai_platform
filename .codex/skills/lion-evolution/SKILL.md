---
name: lion-evolution
description: Prowadź zmiany repozytorium LION od źródeł RAG i bieżących dowodów przez klasyfikację, falsyfikację, walidację i uzgodnione przekazanie stanu. Stosuj do ewolucji LION oraz analizy jego scaffoldingu.
---

# Ewolucja LION

Ścieżki w tej umiejętności są względem korzenia repozytorium. Najpierw odczytaj root i właściwe scoped AGENTS. Nie przenoś tej procedury automatycznie na inne projekty.

1. **Reacquire i route.** Ustal bieżący cel i istniejący zakres zgody. Przed consequential effect odczytaj `LION/architecture/v1_4/AUTHORIZATION_LIFECYCLE_CONTRACT.json`; wygenerowany LPCL nie jest authority, a exact scope aktywuje dopiero jawny user launch tego LPCL. Resolve `LION/rag/RAG_BOOTSTRAP.json`, then read `00_START_HERE.md`, `03_STATE_AND_CONTINUATION.md`, `02_ROUTING_AND_SOURCE_MAP.md` from the newest verified available release; if only the embedded R1 fallback exists, treat it as historical and reacquire live state. Gdy zadanie zależy od currentness, odczytaj exact Git/CI/runtime w wymaganym zakresie. Niepełne źródło oznacza UNKNOWN dla zależnej decyzji.
2. **Classify i graph.** Korzystaj z `LION/codex/CHANGE_CLASSIFICATION.md`. Oddziel source, carrier, fixture, politykę i historię. Zbuduj state graph oraz zależności. Jeśli pomaga to wyjaśnić relacje, użyj `LION/codex/TIGER_GEOMETRY.md`; wejście oznaczone scaffolding zachowaj według `LION/codex/SCAFFOLDING_PROTOCOL.md`.
3. **Hypothesize i falsify.** Zapisz hipotezę, kontrhipotezę i obserwację rozstrzygającą. Spójność grafu nie jest proof. Wybierz pierwszy legalny niedokończony krok z DAG, nie najbardziej widoczny błąd kaskady.
4. **Execute tylko w aktywowanym zakresie.** Użyj `LION/codex/CODEX_RUNBOOK.md`, `TOOL_AUTHORITY_MAP.yaml` i canonical Authorization Lifecycle. Dostępność narzędzia nie nadaje authority. Jawne uruchomienie exact LPCL przez użytkownika jest zewnętrznym activation event tylko dla identities/currentness/effect classes zapisanych w tym LPCL. Nowy successor HEAD/tree/ref/runtime poza bindingiem wymaga nowego LPCL i nowego user launch. PR, merge i runtime są oddzielne, chyba że uruchomiony LPCL jawnie obejmuje te klasy. Nie obchodź odmowy interpreterem ani zmianą polityki.
5. **Readback i reconcile.** Porównaj zamiar, raport narzędzia i rzeczywisty stan celu. Po zmianie HEAD/base unieważnij zależne stare dowody. Stabilizuj source przed refreeze i carrier-last rebind. Pełna walidacja struktury pozostaje obowiązkowa nawet przy znanej przyczynie stale digest.
6. **Continue i terminal.** Ustal jawny limit ponowień proporcjonalny do zadania. Nie ponawiaj nieidempotentnego efektu przed reconciliation. Wykonaj wymagane kontrole do końca; pending nie jest sukcesem. Brak zdolności zewnętrznej dokumentuj jako blocker, zachowując ukończoną pracę. Nie przechodź do niepowiązanych zadań.

Do oceny procesu użyj `LION/evals/evolution/README.md` i właściwych przypadków; dla scaffoldingu `LION/evals/scaffolding/README.md`. Self-review nie jest independent verification. Przy wymaganej niezależności potrzebny jest inny verifier i jawne pochodzenie dowodów.

Handoff opisz instancją `LION/codex/LIVE_STATE.schema.json`: cel, observed identities, dowody, decyzje, efekty/readbacks, blockers, unknowns, DAG, pierwszy niedokończony krok i obowiązujący zakres zgody. Nie wymagaj od następcy dostępu do ukrytego rozumowania. Schemat nie dowodzi prawdziwości instancji; rozwiąż refs i zweryfikuj tożsamości semantycznie. Nie zapisuj live SHA, scan digest ani credentials w tej umiejętności. Model self-report nie jest terminalnym dowodem.
