# LION RAG 1.5 — ROUTING AND SOURCE MAP

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Trzy poziomy odczytu

Pierwszy poziom to poniższa mapa i właściciele z `25_SEMANTIC_OWNERS.json`. Drugi to pełne źródła wskazanych ownerów na odczytanym ref. Trzeci to testy, aktualne obserwacje i zależności wymagane przez twierdzenie. Zamrożony wektor źródeł jest w pliku 26. Plik 27 określa pochodzenie i ograniczenia; historyczne source_id rozwiązuje plik 24.

## Trasy problemowe

**Globalna architektura i ewolucja:** 04, 05, 15, 20 i 21. Wejście źródłowe: `LION/architecture/v1_5/README.md`, `semantic_owners.json`, `FORMALIZATION_REGISTRY_FEDERATION_R1.json`, `cyber_lion/TARGET_ARCHITECTURE.md`, źródła projekcji w `cyber_lion/architecture_projection/`. Sprawdź, czy powstał jawny następca v1.5.

**Semantyka, scaffold i relevance:** 06–07, 11, 13 i 17; `mission_intent.py`, `query_plan.py`, `rag_context_envelope.py`, `semantic_scaffold.py`, `semantic_relevance.py`. HMK-9D i semantyka procesu rozszerzają odczyt o chunk-chunk; analiza delty o glitchlab; struktura grafu o mosaic_lab_pro.py. Nie traktuj wszystkich tych repozytoriów jako obowiązkowych wykonawców jednej inferencji.

**SaaS–LOCAL i zgubiona odpowiedź:** 08–10 i 16; `communication_envelope.py`, `cognitive_invocation.py`, `model_call_v2.py`, `model_release.py`, `cyber_lion/app_coordination/conversation_schema.py`, `conversation_domain.py`, `conversation_chat.py`, `local_intelligence_gateway.py`, `lion_context_provider.py`, `browser_broker/src/canonical-conversation-consumer.cjs` i odpowiadające im testy. Sprawdź durable bridge, nie tylko widoczne okno.

**Panel/LPCL i brak postępu:** 10, 12, 16 i 21; `tools/lion_mission_control_v3.py`, `cyber_lion/process_language/interpretation.py`, `canonical_run.py`, `phase_execution_contract.py`, istniejący execution_driver i scheduler odnaleziony przez importy. Nazwa fazy nie zastępuje wykonawcy ani evaluatora completion.

**Worker, Docker, artefakt:** 12–14; `swarm/federation/ai_platform_runtime_adapter.py`, lokalna dokumentacja runtime i konsument ai_platform; `action_ir.py`, `action_runtime_binding.py`; `tools/lion_federation_e2e_verify.py`. Tożsamość artefaktu kieruje do sbom, snapshot kontekstu do HA2D. Sprawdź osobno faktyczne bytes, receipt i obserwację.

**Badania i falsyfikacja:** 13, 17 i 18; hipotezy_nadawcze_LLM, SymulacjaKaskadySieciowej oraz writeups. Wynik SIMULATED pozostaje symulacją. Korpus badań nie jest magazynem skryptów do automatycznego wykonania.

**Uruchomienie programu rozwoju:** przeczytaj 20–23. Karty K00–K13 wcześniejszego autora są wymaganiami do uzgodnienia, nie zarejestrowanymi enumami LPCL. Nie generuj języka wykonania z samej nazwy karty.

## Reguła zamknięcia zależności

Dla każdej trasy zapisz producenta, format wejścia/wyjścia, konsumenta, wersję, dowód i potrzebny test. Przejdź krawędź, jeśli wynik danego komponentu jest rzeczywistym wejściem następnego lub jego normatywnym ograniczeniem. Pusta odpowiedź search nie dowodzi braku komponentu. W kodzie źródłowym zweryfikuj import, symbol i call site. Przy historycznej nazwie najpierw ustal relację następstwa.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:LION/architecture/v1_5/semantic_owners.json`
- `DonkeyJJLove/ai_platform:cyber_lion/registry/repositories.json`
