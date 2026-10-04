# LION RAG 1.5 — PROVENANCE MEMORY AND EVIDENCE

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Pochodzenie jako część znaczenia

Twierdzenie ma obiekt, scope, czas i klasę źródła. Zapisuj repo/plik/ref/blob lub hash bajtów, zakres odczytu i relacje do dowodów. Nie używaj jednego liniowego rankingu do zastępowania kodu runtime'em, a runtime'u zgodą. Kod dowodzi treści implementacji, nie jej wdrożenia. Hash dowodzi zgodności bajtów, nie autora. Podpis nie dowodzi niezależności weryfikatora.

HA2D odpowiada za kontekst i snapshot/replay provenance; sbom za identyfikację rzeczywistych artefaktów; writeups za korpus źródeł i publikację. Integracja wymaga wejścia i konsumenta: sama mapa ról nie dowodzi, że snapshot pochodzi od wskazanej misji albo że AID opisuje odczytane bytes.

## Świadomość operacyjna

Lokalna perspektywa agenta powinna mówić, co wiadomo, dlaczego, z jakiej epoki i czego nie wiadomo. Taka „świadomość” jest reprezentacją operacyjną, nie twierdzeniem o fenomenalnych przeżyciach modelu. Graf pozwala zestawiać perspektywy bez kasowania ich granic.

EvidenceInstance zachowuje root_ref. Dwa modele o tym samym korzeniu nie tworzą dwóch niezależnych obserwacji. Deduplikacja treści nie usuwa odrębnych łańcuchów pochodzenia. Reconciliation może wskazać konflikt, różny czas, różny scope albo różną klasę epistemiczną zamiast wymuszać jedną odpowiedź.

## Uczenie i retencja

EvidenceBoundLearningEpisode musi wiązać źródła, wejście, decyzje, wynik i falsyfikację. Odpowiedź nauczyciela nie jest ground truth. Dataset uczący powinien odróżniać obserwację, symulację, tekst koncepcyjny, fixture i model output; nie mieszać ich pod jedną etykietą sukcesu.

Zachowuj wyniki negatywne i odrzucone generacje. Retencja wynika z wartości dowodowej, kosztu i ograniczeń danych, nie z liczby plików. Wydziel SOURCE_DATA, GOLDEN_FIXTURE, CANONICAL_RESULT, REPRODUCIBLE_OUTPUT, PUBLICATION_ARTIFACT i ARCHIVED_RUN zgodnie z istniejącym standardem. Nie kasuj dużego korpusu jako cache bez klasyfikacji.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:cyber_lion/contracts/evidence_bound_learning_episode.py`
- `DonkeyJJLove/ai_platform:cyber_lion/contracts/semantic_relevance.py`
- `DonkeyJJLove/ai_platform:LION/standards/LION_GENERATED_OUTPUT_POLICY.md`
- `Peer HA2D/sbom/writeups manifests`
