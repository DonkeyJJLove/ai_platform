# LION UML — derived architecture projection

Ta warstwa generuje deterministyczne projekcje architektury LION do PlantUML. Projekcje są artefaktami pochodnymi: **nie są źródłem authority, canonical state, currentness, runtime evidence ani CI proof**.

Źródłem prawdy pozostają kod repozytorium, kontrakty, canonical durable state, event model i capability model. `CanonicalDiagramModel` przechowuje wyłącznie typowane relacje opisowe. `UNKNOWN` pozostaje `UNKNOWN`; import lub statyczne wywołanie nigdy nie jest promowane do runtime proof ani authority.

## Dostępne projekcje

`lion-system-component-map`, `authority-and-effect-chain-R17-R22`, `builder-lifecycle-state-machine`, `persistent-authority-store-model`, `fleet-topology`, `evolutionary-epoch-loop`, `startup-agent-evolution-loop`, `repository-mutation-boundaries`, `event-and-causality-map`, `capability-map`.

Łańcuch buildera kończy się dziś na `BuilderProcessLaunchBoundary`; `BuilderProcessCompletionObservation` jest oznaczony wyłącznie jako następna granica projektowa, nie jako zaimplementowana authority.

## Renderer

Renderer jest domyślnie wyłączony. Do renderowania SVG trzeba jawnie podać lokalny, istniejący plik wykonywalny lub JAR PlantUML, dokładną wersję i SHA-256. Warstwa nie używa publicznego serwera PlantUML i nie pobiera zależności przy imporcie ani podczas zwykłego test suite. Wywołanie procesu ma stały argv, `shell=False`, bounded input/output, timeout i izolowany katalog tymczasowy.

Przykład wygenerowania tylko `.puml`:

```bash
python tools/render_lion_uml.py --source-tree <git-tree-sha> --diagram authority-and-effect-chain-R17-R22 --puml-out /tmp/lion.puml
```

Renderowanie SVG jest opcjonalne i wymaga `--plantuml`, `--plantuml-version` oraz `--plantuml-sha256`.

Manifest wiąże source-tree SHA, digest modelu projekcji, wersję i digest PlantUML, tryb renderowania oraz digest wygenerowanego artefaktu. Manifest również nie jest authority.
