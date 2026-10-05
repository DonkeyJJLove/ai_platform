# LION RAG 1.5 — FEDERATED WORK PACKAGES

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Rozwój każdego peera musi mieć rezultat funkcjonalny

**ai_platform:** od źródłowo związanego zamiaru do generowania, kompozycji i oceny rozwiązania; spójny context provider, wejście panelowe, owner postępu i konsumenci kontraktów. Test: ta sama potrzeba zachowuje identity przez intencję, context, providera, artefakt i wynik, a nowa generacja nie dziedziczy starych uprawnień.

**swarm:** kontrolowany wykonawca workloadu, artefakty, telemetry, cancel i recovery. Test: rzeczywiste ograniczone wykonanie po admission, jawna odmowa bez admission i brak podwójnego efektu po niejednoznacznym ACK. **chunk-chunk:** walidowalna semantyka przejść i eksport dla konsumenta; test zachowania negacji, ograniczeń oraz wersji, nie pomiar „inteligencji” przez nazwę HMK.

**glitchlab:** rzeczywista headless analiza delty/inwariantów z provenance; test na zmienionych bajtach oraz kontrprzykład błędnego powiązania. **mosaic_lab_pro.py:** headless struktura grafu oddzielona od GUI, stabilny format wyniku; test dangling edges i zmiany scope bez niewidocznego dodania authority.

**HA2D:** snapshot kontekstu, odtwarzanie i izolacja epok; test replay niewłaściwej misji i częściowego odczytu. **sbom:** identity/AID związane z odczytanymi bajtami, rozmiarem i źródłem; test podmiany payloadu lub reużycia starego digestu.

**hipotezy_nadawcze_LLM:** struktury hipotezy, kontrhipotezy, eksperymentu, falsyfikatora i statusu wyniku; test niedopuszczalnego przekształcenia hipotezy w potwierdzony fakt. **SymulacjaKaskadySieciowej:** SimulationResult, seed, konfiguracja i ModelRiskStatement; test powtarzalności w zdefiniowanym zakresie oraz odrzucenie promocji SIMULATED do LIVE_OBSERVED.

**writeups:** ograniczony indeks korpusu, import dowodów, wersjonowanie publikacji i retencja; test zachowania negatywnych wyników, źródeł i epistemicznych korzeni. Nie uruchamiaj automatycznie PoC z korpusu.

## Od karty do misji

Powyższe pozycje są kierunkami projektowymi wymagającymi analizy delty, nie listą brakujących modułów do napisania od nowa. Październikowe integracje mogły już spełnić część postconditions. Dla każdego peera wybierz KEEP/EXTEND/REFACTOR/VERIFY z dowodem. Nie twórz dekoracyjnego commitu tylko dlatego, że repo figuruje w federacji.

Każda misja określa dokładne wejścia, ownera, producentów/konsumentów, użytkowy artefakt, testy, granice efektów i warunek zakończenia. Misje wspólne zamykają przekroje funkcjonalne, nie zastępują lokalnej odpowiedzialności. Merge wielu repo nie jest atomowy; dopuszczalne stany przejściowe i recovery muszą być zaprojektowane.

## Źródła i dalszy odczyt

- `Peer manifests at vector 26`
- `Prior source reconstruction S01-S10 and authoring cards K00-K13`
- `DonkeyJJLove/ai_platform:LION/architecture/v1_5/FEDERATION_FINAL_RECONCILIATION_SOURCE_R1.md`
