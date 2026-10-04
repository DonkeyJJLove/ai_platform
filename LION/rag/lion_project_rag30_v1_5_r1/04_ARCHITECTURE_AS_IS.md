# LION RAG 1.5 — ARCHITECTURE AS IS

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Model, który rzeczywiście wynika ze źródeł

LION jest federacją repozytoriów, kontraktów, reprezentacji, modeli, laboratoriów i wykonawców. ai_platform jest globalnym ownerem architektury i integracji; peery zachowują lokalne implementacje oraz local architecture_knowledge. Granica repozytorium, hosta, procesu, domeny awarii i jednostki logicznej nie jest tą samą granicą.

Warstwa semantyczna rozdziela wiadomość, intencję, plan pytań, kontekst źródłowy, scaffold, atom/deltę i projekcję relewancji. Warstwa poznawcza odróżnia wywołanie, binding sesji i tożsamość modelu od transportu. Conversation plane zachowuje trwałe rozmowy, epoki, lane'y i powiązania z zewnętrznym wątkiem. Materialny efekt należy do odrębnej ścieżki Action/PDP/runtime/admission, a jego obserwacja i rekonsyliacja nie wynikają z wygenerowania odpowiedzi.

## Powierzchnie źródłowe

`LION/architecture/v1_5/README.md` opisuje zintegrowany fundament architecture knowledge oraz nieefektową warstwę Semantic Cloud. `cyber_lion/contracts/` przechowuje typy; `cyber_lion/enterprise/` odpowiedzialności polityki, runtime i ewolucji; `cyber_lion/app_coordination/` oraz `cyber_lion/mission_control/` integrację aplikacji i rozmów. `browser_broker/` jest aplikacyjną integracją sesji SaaS. Są to podsystemy repo ai_platform, nie oddzielne repozytoria odkryte na podstawie nazw katalogów.

RAG ma własnego ownera `LION/rag/RAG_BOOTSTRAP.json`. Source-sety v1.5, historyczne archiwum R9 i runtime `RagContextEnvelope` mają odrębne funkcje. Source-set wskazuje wiedzę; envelope opisuje konkretne pozyskane wejście; żaden z nich nie dowodzi aktualnego deploymentu.

## Co nie zostało wykazane

Nie potwierdzono całej ścieżki panel–rzeczywisty model–worker–nowy artefakt–obserwator–panel. Obecność adaptera `swarm` i weryfikatora receiptów nie zamyka tej luki. Nie zbadano globalnie wszystkich potencjalnych backendów retrieval; brak podstaw do narzucenia nowej vector database nie jest dowodem nieistnienia embeddings w całym korpusie.

## Trzy perspektywy tego samego systemu

AS-IS opisuje odczytane źródła i oddzielne obserwacje. CANDIDATE opisuje konkretną deltę i jej walidację. TARGET opisuje postconditions po przyszłych misjach. Relacje muszą mieć tę samą klasyfikację co węzły; niedopuszczalny jest diagram z aktualnymi nazwami, ale przyszłymi strzałkami opisanymi jako działający obieg.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:LION/architecture/v1_5/README.md`
- `DonkeyJJLove/ai_platform:cyber_lion/CONTRACT_MAP.md`
- `DonkeyJJLove/ai_platform:browser_broker/src/canonical-conversation-consumer.cjs`
