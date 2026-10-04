# LION RAG 1.5 — MISSION PROGRAM DESIGN

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Fale zależności, nie nieskończony pojedynczy TASK

Fala A uzgadnia zmienione źródła, chronione lokalne kandydaty, pełny worklist dokumentacji i rzeczywiste miejsca interpretacji wejścia oraz budowania kontekstu. Fala B zamyka minimalny działający composition root: semantyka, kontekst, provider binding, rozmowa i wynik. Fala C rozwija tworzenie rozwiązań: Gap/CapabilityNeed, reuse, Bean, kompozycję, materializację i falsyfikację. Fala D rozwija funkcjonalne przyrosty peerów i przekroje integracyjne. Fala E wykonuje odrębnie dopuszczone odbiory materialne, recovery i aktualizację wiedzy.

To ramy do uściślenia z bieżących źródeł. Nie są nowymi nazwami faz obsługiwanymi przez LPCL. Autor promptu ma rozbić je na skończone misje o rzeczywistych zależnościach, a nie przepisać litery do fikcyjnego schedulera.

## Obowiązkowa karta misji

Każda misja określa: trwały identyfikator i cel użytkowy; exact source vector i chronionych poprzedników; ownera i peerów; wejścia/wyjścia; zależne kontrakty; stan dostępności providera; dozwolone klasy efektu i operator gate; kroki implementacji; prawdziwy parser/dialekt; guard i completion evaluator; budżet czasu, kosztu i prób; testy pozytywne/negatywne; readback; rollback/kompensację; terminalny wynik i dopuszczalną kontynuację.

Dopuszczenie publikacji, merge, deploymentu i workloadu nie jest jednym polem. Bootstrap może budować brakujący provider w izolacji, ale nie używać go jako dowodu własnej gotowości. Handoff do istniejącego drivera musi mieć trwałe powiązanie i fence: nie wolno utrzymywać dwóch ownerów tego samego kursora.

## Cztery końcowe odbiory

Pierwszy: dokładne wejście panelowe prowadzi przez rzeczywisty SaaS i worker do nowych użytecznych bajtów, testów, readbacku oraz widoku wyniku. Drugi: rozdzielne jednostki poznawcze, wykonawcze i sprawdzające przekazują wyniki; kontrolnie błędny kandydat wraca jako kontrprzykład i powstaje poprawiona generacja. Trzeci: ten sam mechanizm wytwarza kandydatów dla dwóch różnych potrzeb ownera i peera bez dwóch ręcznie zakodowanych workflow. Czwarty: awarie, duplikaty, stare odpowiedzi i odmowy nie powodują obcego bindingu, drugiego efektu ani fałszywego COMPLETE.

Autor musi zapisać dokładne scenariusze, a wykonawca później dostarczyć dowody. Projekt testu nie jest testem. Runtime i koszty mierzy się osobno od poprawności składni LPCL. Po zakończeniu misji ai_platform zapisuje checkpoint i kandydat następnego przyrostu; uruchomienie kolejnej misji należy do operatora.

## Źródła i dalszy odczyt

- `Prior task-authoring prompt K00-K13 and TEST1-TEST4`
- `DonkeyJJLove/ai_platform:LION/architecture/v1_4/LION_PROCESS_CONTRACT_PLANE.md`
- `DonkeyJJLove/ai_platform:cyber_lion/enterprise/GENERATION_EVOLUTION_PROTOCOL.md`
