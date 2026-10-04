# LION RAG 1.5 — AUTHORITY ACTION RUNTIME

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Granice nie są jedną flagą READY

Probabilistyczna inteligencja tworzy reprezentację i propozycję. Authority decision dopuszcza określony zakres. Runtime admission wiąże go z konkretnym wykonawcą i efektem. Wykonanie, raport wykonawcy, obserwacja i reconciliacja pozostają odrębne. Każda strzałka wymaga odpowiedniego kontraktu i dowodu; nie zachodzi automatycznie po poprzednim PASS.

Właścicieli odczytaj z mapy 25: action_model kieruje do action_ir.py, authority do enterprise/authority_source.py, effects do effect_provider.py, runtime do runtime_enforcement.py i jego powiązań. Nie wprowadzaj drugiego PDP ani równoległego źródła zgody w pakiecie RAG.

## Adapter swarm i materialny worker

`swarm/federation/ai_platform_runtime_adapter.py` przekształca już zarządzaną projekcję identity/effect do modelu admission swarm. Sam nie wykonuje workloadu. W kodzie powstaje obiekt PDPResultBinding z ALLOW; jego utworzenie nie jest niezależnym dowodem wcześniejszej decyzji uprawnionego podmiotu. Zweryfikuj pochodzenie wejścia, obowiązujący policy binding i rzeczywisty enforcement u konsumenta.

Wykonawca ma tożsamość runtime, assignment, workspace, effect ceiling, obserwowalność i zasoby. Liczba logicznych dronów nie jest liczbą uruchomionych kontenerów. Dostęp do narzędzia nie nadaje uprawnień do każdego hosta lub każdej ścieżki. Nie przekazuj model output bezpośrednio do shell.

## Publikacja nie jest deploymentem

Zapis lokalnego kandydata, commit na gałęzi, PR, merge, zmiana bootstrapu, wdrożenie control plane oraz materialny workload są oddzielnymi efektami. Jawne polecenie umieszczenia tego RAG w repozytorium uzasadnia ograniczoną publikację artefaktów, nie automatyczny rollout wszystkich przyszłych misji. Zmiana kontekstu konsumowanego przez agenta również wymaga analizy wpływu, nie tylko etykiety DOC_ONLY.

Brak dowodu zatrzymuje zależny efekt. Nie naprawiaj odmowy przez inną ścieżkę narzędzi, zmianę ACL albo odziedziczenie uprawnień z dawnej misji. Zachowaj możliwość niezależnego tworzenia i testowania kandydata bez warunku posiadania gotowego runtime, który dopiero ma powstać.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:AGENTS.md`
- `DonkeyJJLove/ai_platform:cyber_lion/contracts/action_ir.py`
- `DonkeyJJLove/swarm:federation/ai_platform_runtime_adapter.py`
