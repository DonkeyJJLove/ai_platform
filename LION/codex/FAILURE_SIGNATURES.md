# Sygnatury awarii

Sygnatura uruchamia hipotezę diagnostyczną, nie automatyczną naprawę. Zawsze sprawdź discriminating observations i bieżący zakres.

## F001_STALE_SCAN_DIGEST_CASCADE

- **OBSERVED_SYMPTOMS:** wiele błędów scan
- **POSSIBLE_ROOT_CAUSES:** zmiana source lub zły pin
- **DISCRIMINATING_OBSERVATIONS:** porównaj dokładne źródła i recompute
- **LIKELY_CASCADE:** testy zależne od jednego digest
- **SAFE_REPAIR_PATTERN:** refreeze proven live pin
- **FORBIDDEN_SHORTCUT:** zmień wszystkie hashe
- **TERMINAL_RECHECK:** pełne testy inwentarza

## F002_STALE_SOURCE_COUNT

- **OBSERVED_SYMPTOMS:** source count różni się
- **POSSIBLE_ROOT_CAUSES:** dodanie/usunięcie źródła lub selector
- **DISCRIMINATING_OBSERVATIONS:** git ls-files i selector
- **LIKELY_CASCADE:** inventory assertions
- **SAFE_REPAIR_PATTERN:** uzasadnij delta i przelicz
- **FORBIDDEN_SHORTCUT:** wpisz expected bez sprawdzenia
- **TERMINAL_RECHECK:** dokładny source set

## F003_STALE_SURFACE_COUNT

- **OBSERVED_SYMPTOMS:** surface count różni się
- **POSSIBLE_ROOT_CAUSES:** zmiana efektu lub parsera
- **DISCRIMINATING_OBSERVATIONS:** porównaj powierzchnie i klasy
- **LIKELY_CASCADE:** taxonomy/mediation
- **SAFE_REPAIR_PATTERN:** zbadaj każdą nową powierzchnię
- **FORBIDDEN_SHORTCUT:** ukryj UNKNOWN
- **TERMINAL_RECHECK:** taxonomy i regresje

## F004_TRUTH_SUBJECT_DIGEST_CONTRADICTION

- **OBSERVED_SYMPTOMS:** truth digest contradiction
- **POSSIBLE_ROOT_CAUSES:** materialny source lub uszkodzony carrier
- **DISCRIMINATING_OBSERVATIONS:** ls-tree, domena wykluczeń i pełna struktura
- **LIKELY_CASCADE:** currentness tests
- **SAFE_REPAIR_PATTERN:** carrier-last recompute
- **FORBIDDEN_SHORTCUT:** maskuj records/history
- **TERMINAL_RECHECK:** oba carriers i structural tests

## F005_BASE_DRIFT

- **OBSERVED_SYMPTOMS:** base SHA przesunął się
- **POSSIBLE_ROOT_CAUSES:** równoległy merge
- **DISCRIMINATING_OBSERVATIONS:** remote master i ancestry
- **LIKELY_CASCADE:** synthetic CI
- **SAFE_REPAIR_PATTERN:** zrekoncyliuj nową bazę
- **FORBIDDEN_SHORTCUT:** odziedzicz stare CI
- **TERMINAL_RECHECK:** nowi rodzice i CI

## F006_HEAD_DRIFT

- **OBSERVED_SYMPTOMS:** HEAD przesunął się
- **POSSIBLE_ROOT_CAUSES:** push innego aktora
- **DISCRIMINATING_OBSERVATIONS:** remote branch readback
- **LIKELY_CASCADE:** head-bound evidence
- **SAFE_REPAIR_PATTERN:** unieważnij stare dowody
- **FORBIDDEN_SHORTCUT:** dopasuj raport do zamiaru
- **TERMINAL_RECHECK:** exact-head checks

## F007_SUPERSEDED_HEAD_CI

- **OBSERVED_SYMPTOMS:** zielone CI starego HEAD
- **POSSIBLE_ROOT_CAUSES:** stary run
- **DISCRIMINATING_OBSERVATIONS:** run/job/head binding
- **LIKELY_CASCADE:** pozorna gotowość merge
- **SAFE_REPAIR_PATTERN:** obserwuj bieżący run
- **FORBIDDEN_SHORTCUT:** użyj starego PASS
- **TERMINAL_RECHECK:** current HEAD

## F008_SYNTHETIC_MERGE_PARENT_MISMATCH

- **OBSERVED_SYMPTOMS:** synthetic parents mismatch
- **POSSIBLE_ROOT_CAUSES:** zmiana bazy/head lub błędny checkout
- **DISCRIMINATING_OBSERVATIONS:** cat-file commit parents/tree
- **LIKELY_CASCADE:** CI identity
- **SAFE_REPAIR_PATTERN:** odtwórz właściwy merge
- **FORBIDDEN_SHORTCUT:** zignoruj parent check
- **TERMINAL_RECHECK:** oba rodzice i tree

## F009_CODEQL_QUERY_SUPPRESSION_MASQUERADING_AS_FIX

- **OBSERVED_SYMPTOMS:** alert znika po suppression
- **POSSIBLE_ROOT_CAUSES:** query wyłączone zamiast naprawy
- **DISCRIMINATING_OBSERVATIONS:** diff i przepływ źródła
- **LIKELY_CASCADE:** fałszywy security PASS
- **SAFE_REPAIR_PATTERN:** usuń przyczynę
- **FORBIDDEN_SHORTCUT:** wycisz query
- **TERMINAL_RECHECK:** regresja i exact analysis

## F010_CODEQL_DISMISSAL_MASQUERADING_AS_FIX

- **OBSERVED_SYMPTOMS:** dismissed zamiast fixed
- **POSSIBLE_ROOT_CAUSES:** ręczna dyspozycja alertu
- **DISCRIMINATING_OBSERVATIONS:** alert state i source diff
- **LIKELY_CASCADE:** fałszywe closure
- **SAFE_REPAIR_PATTERN:** napraw kod
- **FORBIDDEN_SHORTCUT:** nazwij dismissal fix
- **TERMINAL_RECHECK:** alert i scan

## F011_CURRENTNESS_SELF_REFERENCE

- **OBSERVED_SYMPTOMS:** hash zmienia własny input
- **POSSIBLE_ROOT_CAUSES:** samoreferencja
- **DISCRIMINATING_OBSERVATIONS:** sprawdź domenę subject
- **LIKELY_CASCADE:** nieskończone rebind
- **SAFE_REPAIR_PATTERN:** stosuj jawne wykluczenia kontraktu
- **FORBIDDEN_SHORTCUT:** nowe wykluczenia dla PASS
- **TERMINAL_RECHECK:** stabilny recompute

## F012_PARTIAL_REFREEZE

- **OBSERVED_SYMPTOMS:** część live pinów stara
- **POSSIBLE_ROOT_CAUSES:** niepełny refreeze
- **DISCRIMINATING_OBSERVATIONS:** klasyfikacja wszystkich pinów
- **LIKELY_CASCADE:** kolejne cascade
- **SAFE_REPAIR_PATTERN:** popraw tylko proven live carriers
- **FORBIDDEN_SHORTCUT:** masowy replace
- **TERMINAL_RECHECK:** pełny zależny zestaw

## F013_CARRIER_UPDATED_BEFORE_NON_CARRIER_SOURCE

- **OBSERVED_SYMPTOMS:** carrier sprzed źródła
- **POSSIBLE_ROOT_CAUSES:** zła kolejność
- **DISCRIMINATING_OBSERVATIONS:** historia commitów i DAG
- **LIKELY_CASCADE:** stale truth
- **SAFE_REPAIR_PATTERN:** final source potem carrier
- **FORBIDDEN_SHORTCUT:** kolejny source po final carrier
- **TERMINAL_RECHECK:** końcowy subject

## F014_MODEL_REPORTS_SUCCESS_GIT_READBACK_DISAGREES

- **OBSERVED_SYMPTOMS:** model success, Git inaczej
- **POSSIBLE_ROOT_CAUSES:** nieudany/nieznany efekt
- **DISCRIMINATING_OBSERVATIONS:** lokalny i remote readback
- **LIKELY_CASCADE:** fałszywy terminal
- **SAFE_REPAIR_PATTERN:** uzgodnij actual effect
- **FORBIDDEN_SHORTCUT:** powtórz ślepo push
- **TERMINAL_RECHECK:** dokładne SHA

## F015_EFFECT_EXIT_ZERO_WITHOUT_POSTCONDITION

- **OBSERVED_SYMPTOMS:** exit 0 bez wyniku
- **POSSIBLE_ROOT_CAUSES:** no-op albo zły cel
- **DISCRIMINATING_OBSERVATIONS:** postcondition observer
- **LIKELY_CASCADE:** pozorny efekt
- **SAFE_REPAIR_PATTERN:** odczytaj cel
- **FORBIDDEN_SHORTCUT:** uznaj kod wyjścia za dowód
- **TERMINAL_RECHECK:** stan celu

## F016_RAG_HISTORICAL_CURRENT_USED_AS_LIVE_CURRENT

- **OBSERVED_SYMPTOMS:** RAG CURRENT jako teraz
- **POSSIBLE_ROOT_CAUSES:** pomieszanie epok
- **DISCRIMINATING_OBSERVATIONS:** source metadata i live read
- **LIKELY_CASCADE:** stare decyzje
- **SAFE_REPAIR_PATTERN:** scope-bound reacquisition
- **FORBIDDEN_SHORTCUT:** nadpisz historię
- **TERMINAL_RECHECK:** aktualna płaszczyzna

## F017_MULTIPLE_PRS_SHARE_CURRENTNESS_DEPENDENCY

- **OBSERVED_SYMPTOMS:** wspólne carriers w PR-ach
- **POSSIBLE_ROOT_CAUSES:** zależny subject
- **DISCRIMINATING_OBSERVATIONS:** pairwise diff i DAG
- **LIKELY_CASCADE:** wzajemne stale
- **SAFE_REPAIR_PATTERN:** źródło przed carrier PR
- **FORBIDDEN_SHORTCUT:** last writer wins
- **TERMINAL_RECHECK:** readback po każdym merge

## F018_ONE_ROOT_PIN_CAUSES_MANY_TEST_ERRORS

- **OBSERVED_SYMPTOMS:** dziesiątki identycznych błędów
- **POSSIBLE_ROOT_CAUSES:** jeden root pin
- **DISCRIMINATING_OBSERVATIONS:** grupuj sygnatury i recompute
- **LIKELY_CASCADE:** wiele assertions
- **SAFE_REPAIR_PATTERN:** napraw root cause
- **FORBIDDEN_SHORTCUT:** patch każdej kaskady
- **TERMINAL_RECHECK:** pełne testy zależne

## F019_LOCAL_DIRTY_MASTER_CONFUSED_WITH_REMOTE_MASTER

- **OBSERVED_SYMPTOMS:** lokalne master różni się
- **POSSIBLE_ROOT_CAUSES:** dirty checkout lub stara gałąź
- **DISCRIMINATING_OBSERVATIONS:** status i ls-remote
- **LIKELY_CASCADE:** zła baza
- **SAFE_REPAIR_PATTERN:** izolowany worktree
- **FORBIDDEN_SHORTCUT:** reset user changes
- **TERMINAL_RECHECK:** lokalny/remote opis osobno

## F020_RUNNING_PROCESS_CONFUSED_WITH_DEPLOYMENT

- **OBSERVED_SYMPTOMS:** proces istnieje, brak deployment proof
- **POSSIBLE_ROOT_CAUSES:** stary/testowy runtime
- **DISCRIMINATING_OBSERVATIONS:** identity, readiness i postcondition
- **LIKELY_CASCADE:** fałszywa produkcyjność
- **SAFE_REPAIR_PATTERN:** zbierz ograniczony runtime evidence
- **FORBIDDEN_SHORTCUT:** merge = deployed
- **TERMINAL_RECHECK:** weryfikacja scope/runtime
