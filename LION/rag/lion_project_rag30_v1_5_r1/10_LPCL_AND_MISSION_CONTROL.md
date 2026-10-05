# LION RAG 1.5 — LPCL AND MISSION CONTROL

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Zamiar, kontrakt fazy i wykonanie

PHASE_INTENT, PHASE_EXECUTION_CONTRACT, CAPABILITY_BINDING, ACTION_IR, EFFECT i COMPLETION są odrębnymi etapami. LPCL/1.2 wymaga jawnych kontraktów faz. Obsługa historycznego 1.1 zachowuje fail-closed LEGACY_INFERRED_SAFE. Wygenerowany program nie jest uruchomieniem ani zgodą; operator uruchamia dokładne bajty pod konkretnym bindingiem.

Zanim powstanie nowy program, odczytaj prawdziwy parser, compile_canonical_run, interpret_process_source, schemat fazy, guard handlers, completion evaluators oraz rejestrację/aktywację. Nie wymyślaj enumów i pól z brzmienia kart projektowych. Skończony DAG programu oraz pętla generacji są różnymi obiektami: iteracja musi mieć limit, nową generację i warunek zakończenia.

## Wejście panelowe wymaga własnego testu

Historyczna rekonstrukcja wskazała `_compile_and_store_phase_contracts` w tools/lion_mission_control_v3.py i `interpret_process_source` w process_language jako odmienne ścieżki interpretacji. Sukces prawdziwego kompilatora poza panelem nie dowodzi poprawnego wejścia RUN/PHASE przez panel. Sprawdź bieżące bajty obu ścieżek i ich testy, zanim uznasz tę rozbieżność za nadal otwartą lub już naprawioną.

Test autora musi skompilować rzeczywisty plik, zachować source digest, IR i kontrakty oraz wykonać izolowany test właściwego ingressu. Fałszywy parser liczący słowa PHASE nie daje TASK_READY. Gdy naprawa ingressu jest dopiero pierwszą misją, jawnie oddziel aktualnie zwalidowany bootstrap od późniejszego odbioru naprawionej ścieżki.

## Jeden właściciel postępu

Odnajdź istniejący driver i scheduler przez ich implementacje. Każda faza ma konkretnego providera, scope, wejście, wynik, evaluator, readback i recovery. Descriptor capability nie tworzy providera; heartbeat nie dowodzi wykonania; RUNNING w bazie nie oznacza powstania artefaktu. Sekwencyjny bootstrap jest poprawniejszy niż fikcyjna równoległość wynikająca z zapisania liczby workerów.

W programie rozwoju ai_platform ma generować kandydatów następnych misji i rozliczać bieżącą, lecz nie aktywować bez końca własnych nowych scope. Po zakończeniu uzgodnionej misji kolejny dokładny program uruchamia operator.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:LION/architecture/v1_4/LION_PROCESS_CONTRACT_PLANE.md`
- `DonkeyJJLove/ai_platform:cyber_lion/process_language/interpretation.py`
- `DonkeyJJLove/ai_platform:cyber_lion/process_language/canonical_run.py`
- `DonkeyJJLove/ai_platform:tools/lion_mission_control_v3.py`
