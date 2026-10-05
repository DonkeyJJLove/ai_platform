# MOON Windows — krok po kroku po nałożeniu patcha

## Terminal i checkout

Użyj Windows PowerShell na MOON, nie terminala `LION-AUTH-LAB:/mnt/c/...`. Przejdź do root repozytorium `C:\Users\d2j3\PycharmProjects\ai_platform` albo do jawnie utworzonego, czystego worktree tego samego repo. Nie kopiuj luźnego ZIP-a do katalogu `cyber_lion`.

Pakiet patch zawiera osobny preflight i rollback. Najpierw zweryfikuj jego manifest i wykonaj `check`. Istniejące zmiany w plikach objętych patchem zatrzymują aplikację; nie używaj reset/clean/stash/force jako obejścia. CRLF jest oceniane przez mechanizm Git. Ręczne przepisanie zakończeń linii lub niezgodny index także może prawidłowo zatrzymać `git apply --index`; wtedy użyj czystego worktree, nie masowej renormalizacji.

## Python i testy

```powershell
Set-Location 'C:\Users\d2j3\PycharmProjects\ai_platform'
.\tools\lion_edge_yoke_windows.ps1 -Action Prepare -PythonExe python -InstallDependencies
.\tools\lion_edge_yoke_windows.ps1 -Action Test
```

Wymagany Python 3.12+. Wrapper tworzy `.venv-edge-yoke` w repo i nie zmienia istniejącego `.venv`. `-InstallDependencies` jest jawną zgodą na pobranie zależności do tego jednego środowiska. `requirements/edge-yoke.txt` zawiera wersje użyte do kwalifikacji autora, nie ogólny lock supply chain. Można zamiast tego dostarczyć zatwierdzone koła offline. Nie zmieniaj globalnej ExecutionPolicy; przy wymaganiu podpisanych skryptów użyj zatwierdzonego procesu organizacji lub uruchom CLI Python bez wrappera.

Test zakończony FAIL/ERROR zatrzymuje dalszą ścieżkę. Sześć testów oryginalnego R5 writer ma profil Linux (descriptor-relative storage) i na Windows jest jawnie SKIPPED, nie zaliczone jako PASS. Pozostała kwalifikacja obserwatora, transportu, jednostek pracy oraz Win32 jest natywna. Testy R5 wykonaj dodatkowo w Ubuntu/Docker przed powrotem do żywego runtime. Szczególnie testy Win32 Job Object muszą rzeczywiście przejść na Windows; wynik autora na Linux nie jest ich substytutem.

## Lokalna kwalifikacja produktu

```powershell
.\tools\lion_edge_yoke_windows.ps1 -Action Demo
```

Ta próba uruchamia własnego obserwatora oraz dwa ograniczone procesy, bez Dockera i modelu. Tworzy produkt, transfer i readback oraz wykonuje wyprodukowany CLI. Wypisuje katalog wyniku i `PILOT_RECEIPT.json`. `live_mission_executed=false` jest prawidłowe: ta próba nie jest misją LPCL. Bez `-LocalModel` metadane produktu jawnie podają zero inferencji.

## Jarzmo osobno i istniejąca grupa R24

Jednorazowo przygotuj prywatny katalog nowego obserwatora. Nie kasuj starego katalogu, aby odblokować QUARANTINE.

```powershell
.\tools\lion_edge_yoke_windows.ps1 -Action Init
.\tools\lion_edge_yoke_windows.ps1 -Action Watch
```

Zostaw to okno otwarte. W drugim oknie, z tego samego checkoutu:

```powershell
.\tools\lion_edge_yoke_windows.ps1 -Action State
.\tools\lion_edge_yoke_windows.ps1 -Action R24Pilot
```

Po przejściu obiegu bez modelu:

```powershell
.\tools\lion_edge_yoke_windows.ps1 -Action R24Pilot -LocalModel
```

Pilot wybiera tylko istniejące `lion-r24-md001` i `lion-r24-md002` z poprawnym projektem Compose i UID65532. Nie używa compose up/down, nie restartuje głównych workerów, nie publikuje Git i nie zapisuje do żywej bazy misji. Potrzebne moduły są przenoszone do nowych katalogów `/tmp`; nie jest montowany zapisywalny globalny checkout. Model jest odpytywany z MD001 przez `host.docker.internal:8772`.

Dla każdego przebiegu powstaje nowy katalog poza repo. `built.bundle.json`, `verified.bundle.json`, `verification.json` i `PILOT_RECEIPT.json` opisują jego dokładne bytes. Nie wybieraj po samej nazwie „ostatniego PASS” z innego przebiegu. Zawsze korzystaj ze ścieżki wypisanej przez daną komendę.

## Zatrzymanie i przypadki niejednoznaczne

Ctrl+C w oknie obserwatora kończy tylko ten program i wystawia HOLD albo zachowuje QUARANTINE; niczego nie odinstalowuje. Snapshot zgaszonego obserwatora wygasa. Działający lokalny child process jest pod nadzorem; zakończenie klienta Docker nie jest dowodem zakończenia procesu w kontenerze. Przy timeout zachowaj dowody i uzgodnij stan przed ponowieniem. Kod kwalifikacyjnego workera ma własny skończony watchdog, lecz nie zastępuje to pełnego produkcyjnego sterownika cancellation.

Odbiór tej ścieżki umożliwia dopiero dalsze podłączenie do rzeczywistego assignmentu R5. Nie uznawaj operatorowego pilota za wykonanie autoryzowanego programu autonomii.
