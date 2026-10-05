# LION RAG 1.5 — ARCHITECTURE REQUIREMENTS

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Cel architektury rozwojowej

Federacja ma umożliwiać przejście od potrzeby operatora do nowego, użytecznego i sprawdzonego rozwiązania, a następnie wykorzystanie rozpoznanych braków do kolejnego skończonego przyrostu. ai_platform jest miejscem integracji i wytwarzania misji; peery są rzeczywistymi dostawcami funkcji. Celem nie jest samo porządkowanie hashy, liczników, opisów zgodności lub statusów.

Architektura musi opisać spójnie: kontekst systemu, semantykę, proces, komunikację, pamięć i źródła, modele, wytwarzanie komponentów, wykonanie, uprawnienia, obserwacje, recovery, testowanie oraz ewolucję wiedzy. Te same identyfikowalne obiekty mają występować we wszystkich widokach.

## Wymagane zdolności

R01: źródłowo związane rozpoznanie intencji i luki. R02: kompozycja istniejących kontraktów Semantic Cloud. R03: różne perspektywy SaaS i LOCAL bez utraty wspólnego kontekstu. R04: trwała tożsamość rozmowy, misji i generacji. R05: działające wejście panelowe i jeden owner postępu. R06: rzeczywiści providerzy zamiast samych descriptorów. R07: ponowne użycie lub generowanie Bean/Composition/Mosaic. R08: ograniczona materializacja artefaktów przez swarm. R09: niezależne sprawdzenie i powrót kontrprzykładu. R10: lineage poprawionej generacji. R11: źródłowo związane funkcje każdego peera. R12: recovery bez podwójnego efektu. R13: spójna dokumentacja i RAG po zmianie. R14: skończone misje i kontrolowane przejście między epokami.

## Macierz śledzenia

Dla każdej zdolności wskaż wymaganie, źródło, obecną implementację lub jej brak, ownera, warianty, wybraną deltę, konsumenta, test, misję, predykat odbioru, rollback i aktualność. Sprawdź mapowanie w obie strony. Zmiana bez celu i wymaganie bez drogi wykonania są osierocone.

Nie zakładaj, że wszystkie R01–R14 są dziś niespełnione. Najpierw rozlicz aktualne źródła i zakończone przyrosty. Nie wymagaj wszystkich w jednej prostej misji. Nie maskuj braków normatywnych przez dopasowanie dokumentów do wadliwej implementacji; kod i kontrakt muszą zostać uzgodnione jawnie.

## Ograniczenia projektu

Nie wolno zastąpić sesji ChatGPT produktem API bez decyzji produktowej, nadać semantyce authority, dodać drugiego schedulera dla wygody ani zakładać atomowego merge federacji. Refaktoryzacja jest dopuszczalna, gdy analiza dowodzi potrzeby; brak duplikacji nie jest zakazem poprawienia wadliwego ownera. Nowa infrastruktura wymaga konsumenta, kosztu, migracji i mierzalnego efektu użytkowego.

## Źródła i dalszy odczyt

- `User request for whole-federation evolutionary architecture`
- `DonkeyJJLove/ai_platform:cyber_lion/TARGET_ARCHITECTURE.md`
- `Prior architecture reconstruction and task authoring inputs`
