# LION UML — derived architecture projection

Ta warstwa generuje deterministyczne projekcje architektury LION do PlantUML. Projekcje są artefaktami pochodnymi: **nie są źródłem authority, canonical state, currentness, runtime evidence ani CI proof**.

Źródłem prawdy pozostają kod repozytorium, kontrakty, canonical durable state, event model i capability model. `CanonicalDiagramModel` przechowuje wyłącznie typowane relacje opisowe. `UNKNOWN` pozostaje `UNKNOWN`; import lub statycznie dowiedzione bezpośrednie wywołanie nigdy nie jest promowane do runtime proof ani authority.

## Tożsamość i provenance projekcji

Każdy canonical fact posiada `source_path` i `source_digest`. Identyfikator nie jest sanitizowaną nazwą pliku, lecz domenowo odseparowanym digestem funkcji `canonical_projection_identity(relation_domain, canonical_source_path, semantic_kind, qualified_name)`. Dzięki temu różne ścieżki, takie jak `a-b.py` i `a_b.py`, nie mogą zlać się w jeden węzeł. Każda kolizja identyfikatora z inną treścią kończy się fail-closed.

Identyfikatory w modelu muszą spełniać zamkniętą gramatykę `^[A-Za-z][A-Za-z0-9_]{0,127}$`. Węzły canonical wymagają jawnego source provenance, a relacje inne niż `UNKNOWN` wymagają `provenance_ref`. `BuilderProcessCompletionObservation` jest jedynym dopuszczonym w tej fazie `DECLARED_NEXT_FRONTIER` i nie reprezentuje istniejącej authority.

## Projekcje związane z rzeczywistym repozytorium

`lion-system-component-map`, `authority-and-effect-chain-R17-R22`, `builder-lifecycle-state-machine`, `persistent-authority-store-model`, `fleet-topology`, `evolutionary-epoch-loop`, `startup-agent-evolution-loop`, `repository-mutation-boundaries`, `event-and-causality-map`, `capability-map` są budowane z istniejących canonical source files i sprawdzanych symboli lub stałych. Zwykły unit fixture może służyć do edge cases, ale nie jest dowodem poprawności produkcyjnego projection map. Test integracyjny projection plane przechodzi po rzeczywistym checkoutcie repozytorium i wymaga, aby wszystkie dziesięć projekcji rozwiązało swoje realne źródła i tokeny.

`capability-map` nie opiera się na syntetycznym `contracts/capability.py`. Koncept read-only jest związany z `ReadOnlyProviderSnapshot` w `enterprise/conformance.py`; lokalny write ceiling z realnym `local_write` w canonical PDP; `BUILDER_PROCESS_START` z `EFFECT_CLASS` w kontrakcie R22; a granica repository-ref mutation z rzeczywistą polityką `repository_ref_mutation` w `builder_start_admission.py`.

`startup-agent-evolution-loop` nie używa narracyjnych klas `Explore`/`Learn`. Projekcja jest związana z rzeczywistym `AIDrivenStartupAgent` oraz jego realnymi etapami `plan`, `build_local` i `apply_outcome` w `startup_agent/orchestrator.py`.

Zmiana relevant canonical source zmienia source digest faktów i digest modelu; zmiana pliku nieużywanego przez daną projekcję nie zmienia jej semantycznej zawartości.

Extractor używa AST i odczytu plików tekstowych. Nie importuje ani nie wykonuje analizowanego kodu. `CALLS_STATIC` jest celowo wąskie: powstaje wyłącznie dla bezpośredniego bare-name call z top-level funkcji do dokładnej top-level funkcji w tym samym module. Analiza nie schodzi do zagnieżdżonych funkcji, async functions, lambd ani klas, więc ich wywołania nie są błędnie przypisywane callerowi z zewnętrznego scope. Attribute/dynamic dispatch nie jest traktowany jako runtime proof.

## Renderer PlantUML

Renderer jest domyślnie wyłączony. Do renderowania SVG trzeba jawnie podać lokalny, istniejący plik wykonywalny lub JAR PlantUML, dokładną wersję i SHA-256. Warstwa nie używa publicznego serwera PlantUML i nie pobiera zależności przy imporcie ani podczas zwykłego test suite.

Granica renderera jest podwójna. Po pierwsze executable/JAR jest wiązany przez exact SHA-256, a `-version` musi zwrócić dokładnie jeden rozpoznany token `PlantUML version X`; token musi być identyczny z przypiętą wersją. Substring, prefix, suffix i wieloznaczny output są odrzucane. Po drugie model nie może przenosić surowych fragmentów PlantUML: identyfikatory są generowane i walidowane, relacje pochodzą z zamkniętego enum, a etykiety są danymi escapowanymi i odrzucają dyrektywy takie jak `!include`, `!includeurl`, `!pragma`, `@startuml`, `@enduml` oraz `skinparam`.

Wywołanie procesu ma stały argv, `shell=False`, bounded input/output, timeout i izolowany katalog tymczasowy.

Przykład wygenerowania tylko `.puml`:

```bash
python tools/render_lion_uml.py --source-tree <git-tree-sha> --diagram authority-and-effect-chain-R17-R22 --puml-out /tmp/lion.puml
```

Renderowanie SVG jest opcjonalne i wymaga `--plantuml`, `--plantuml-version` oraz `--plantuml-sha256`.

Manifest wiąże source-tree SHA, domenowo odseparowany digest canonical projection model, wersję i digest PlantUML, tryb renderowania oraz digest wygenerowanego artefaktu. Manifest również nie jest authority ani runtime evidence.
