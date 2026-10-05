# Edge Yoke R6 — komponent repozytorium ai_platform

Status: **SOURCE_CANDIDATE / NOT_DEPLOYED**. R6 przenosi nadzór i skończoną kwalifikację produktu do istniejących przestrzeni `cyber_lion`, `tools` i `docs`. Nie instaluj równolegle starego ZIP-a jako drugiej aplikacji `lion_edge`.

Baza zależności: PR408/R5 `59f21b0db4c2d516c7e6f37df8affef3aca36d28`, tree `23dcafbcf42d0bd8947c88bd068b81dde0b7b040`. Pakiet patch ma wariant dla tej bazy oraz wariant zbiorczy dla master `0e24fd481697bf85fd5c4a4fdb93c39a757ff463`. Wariant master zawiera dokładny wcześniejszy przyrost R5, nie jego ręcznie wymyślony zamiennik. Publikacja PR, merge i deployment są osobne; ten patch żadnego z nich nie wykonuje.

## Wejście

[Instrukcja Windows](MOON_WINDOWS.md), [integracja R5 i semantyka](INTEGRATION.md), [testy i granice](VALIDATION_AND_LIMITS.md).

```powershell
# Z korzenia właściwego checkoutu, po bezpiecznym nałożeniu patcha:
.\tools\lion_edge_yoke_windows.ps1 -Action Prepare -PythonExe python -InstallDependencies
.\tools\lion_edge_yoke_windows.ps1 -Action Test
.\tools\lion_edge_yoke_windows.ps1 -Action Demo
```

Kod jest w repozytorium. Prywatne klucze, snapshoty, dzienniki i produkty przebiegów pozostają poza nim, domyślnie w `%LOCALAPPDATA%\LION\EdgeYokeR6` i `%LOCALAPPDATA%\LION\EdgeR6Runs`. Pomocnicze `.venv-edge-yoke` jest osobnym, ignorowanym środowiskiem tego komponentu; istniejące `.venv`, `pyproject.toml` i `uv.lock` użytkownika nie są nadpisywane.

## Jeden owner każdej funkcji

`cyber_lion/enterprise/edge_yoke` dostarcza obserwatora, maszynę weta, evidence oraz wrapper rodzimego R5. `cyber_lion/mission_control/edge_*` dostarcza ograniczoną jednostkę kwalifikacji, komunikat korekcji i przepis produktu. Transfer importuje **oryginalny** `cyber_lion.mission_control.artifact_transfer`; nie ma nowego `vendor/artifact_transfer.py` ani konkurencyjnej semantyki AID.

`tools/lion_edge_yoke.py` jest pojedynczym CLI repozytorium. Wrapper PowerShell nie uruchamia usług przy starcie komputera, nie zmienia ExecutionPolicy i nie konfiguruje hostów federacji. `tools/lion_r24_cooperative_pilot.py` korzysta z dwóch istniejących kontenerów R24, dopiero gdy operator uruchomi odpowiednią akcję. Nie tworzy klastra, nie restartuje workerów i nie wpisuje testowej zgody do Mission Control.

Przygotowany produkt to mały weryfikator manifestów: kod z zatwierdzonego szablonu, korpus ośmiu przypadków oraz wynik niezależnego procesu weryfikującego. Opcjonalny model lokalny generuje wyłącznie dane JSON w zamkniętym schemacie. Ten profil nie wykonuje arbitralnego kodu zwróconego przez model.
