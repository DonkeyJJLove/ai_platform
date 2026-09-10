# Runbook ewolucji repozytorium

Polecenia wykonuj z korzenia wskazanego checkoutu. Przykłady Git/gh są procedurą operatorską wymagającą narzędzi i zakresu misji; nie są nowym interfejsem raw shell authority dla autonomicznego runtime. Nazwy branch/PR/commit w przykładach podstawiaj wyłącznie z obserwacji. Nie wykonuj dosłownych placeholders.

## Wejście i izolacja

```sh
git status --short
git branch --show-current
git rev-parse HEAD 'HEAD^{tree}'
git remote get-url origin
git fetch origin
git fetch origin master
git rev-parse origin/master 'origin/master^{tree}'
git show-ref --verify refs/heads/master
git ls-remote origin refs/heads/master
gh pr list --repo DonkeyJJLove/ai_platform --state open
```

Osobny fetch master jest istotny przy ograniczonym refspec. Brak lokalnego master oznacz ABSENT; nie twórz go dla samej obserwacji. Nie czyść zmian użytkownika. Dla nowej misji wybierz wolną nazwę po sprawdzeniu local/remote refs, następnie `git worktree add -b <branch> <isolated-path> origin/master`. Sprawdź AGENTS w nowym checkoutcie i aktywne PR dotykające tych samych regionów.

## Testy pochodzące z repozytorium

Workflow `.github/workflows/cyber-lion-contracts.yml` definiuje Python 3.11, compile i pełne unittest. Live-currentness jest włączane przez środowisko workflow; lokalne pominięcie live testów nie dowodzi live PASS.

```sh
python -m compileall -q cyber_lion
LION_P0_LIVE_CURRENTNESS=1 python -m unittest discover -s cyber_lion/tests -p 'test_*.py' -v
```

Następujące polecenia są dobranymi lokalnymi podzbiorami istniejących modułów testowych, nie osobnym workflow ani zamiennikiem wymaganych CI:

```sh
LION_P0_LIVE_CURRENTNESS=1 python -m unittest cyber_lion.tests.test_truth_plane_reconciliation cyber_lion.tests.test_currentness_repair_gate -v
python -m unittest discover -s cyber_lion/tests -p 'test_lion_mission_control_*.py' -v
python -m unittest cyber_lion.tests.test_vkt_r3_mission_control -v
python -m unittest cyber_lion.tests.test_complete_mediation cyber_lion.tests.test_effect_taxonomy_reconciliation cyber_lion.tests.test_p0_surface_closure_campaign -v
python -m unittest cyber_lion.tests.test_production_mediation cyber_lion.tests.test_mediation_falsification -v
python -m unittest cyber_lion.tests.test_merge_authority_observation cyber_lion.tests.test_merge_authority_consumption cyber_lion.tests.test_merge_admission -v
```

Workflow ma osobne jobs `Cyber-Lion Merge Authority Admission` i `Cyber-Lion Merge Authority Observation`. Odczytuj ich warunki `if`, environment i exact run. Nie uruchamiaj ręcznie entrypointów kontroli uprawnień z wymyślonymi zmiennymi. Test lokalny sprawdza kontrakt, a job GitHub obserwuje właściwe zdarzenie PR; to różne dowody.

Bandit z `.github/workflows/bandit-security.yml`:

```sh
python -m pip install --disable-pip-version-check bandit==1.9.4
bandit --recursive cyber_lion --exclude cyber_lion/tests --severity-level medium --confidence-level medium
```

Instalację wykonuj w przeznaczonym środowisku zależności; nie zmieniaj hosta produkcyjnego dla testu dokumentacji.

Pełny census z `.github/workflows/lion-r22c-full-symbol-census.yml`, po wskazaniu tymczasowego katalogu artefaktów:

```sh
python -m unittest cyber_lion.tests.test_architecture_projection_full_symbol_census -v
git ls-files -z -- '*.py' > "$RUNNER_TEMP/lion-python-files.zlist"
python -m cyber_lion.architecture_projection.full_symbol_census --source-root . --paths-zlist "$RUNNER_TEMP/lion-python-files.zlist" --source-head "$(git rev-parse HEAD)" --source-tree "$(git rev-parse HEAD^{tree})" > "$RUNNER_TEMP/LION_FULL_SYMBOL_CENSUS_v1_4.json"
```

Waliduj success=true, source.head/tree zgodne z checkoutem, parse_failures=0 i committed_python_files=parsed_python_files. Ten workflow jest PR-only; dowód final merge wymaga osobnej obserwacji lub lokalnego census jego dokładnego SHA.

## RAG i scaffolding

RAG tool jest źródłem osadzonym w `LION/rag/lion_project_rag32_v1_4_r1/07_CONTAINER_TOOL.md`, nie domyślnie zainstalowanym skryptem. Jeśli zweryfikowana lokalna kopia istnieje, uruchom `python lion_rag_tool.py verify <rag-directory>` i `python lion_rag_tool.py self-test <rag-directory>`. W przeciwnym razie wykonaj read-only manifest/fileset/hash check albo po przeglądzie odzyskaj wyłącznie narzędzie zgodnie z SOURCE_BYTES/SOURCE_SHA256 do scratch; nie wykonuj odzyskanych payloadów projektu. W Windows używaj dokładnych blobów Git przy kontroli literalnych bytes; CRLF checkoutu nie jest podstawą do przepisywania archiwum. Procedura hosted retrieval jest osobna w `LION/evals/retrieval/README.md`.

## Kolejność zmian i truth

1. Sklasyfikuj każdy region według CHANGE_CLASSIFICATION; zbuduj DAG zależności i jawne kontrhipotezy.
2. Najpierw źródła/security/workflow, następnie proven live scan pins wyłącznie jeśli zmienił się scan. Selector produkcyjny istnieje w `cyber_lion/tests/test_p0_surface_closure_campaign.py::current_inventory`: cyber_lion Python bez tests oraz workflow yml/yaml.
3. Stabilizuj dokumentację, schema, ADR i skill. Dokumentacja uczestniczy w truth subject.
4. `cyber_lion/architecture_projection/truth_plane.py::subject_digest` przyjmuje SubjectEntry z dokładnego `git ls-tree -r -z HEAD`. Odczytaj aktualne `CARRIER_PATHS`; nie wymyślaj nowych wykluczeń. Osobno rozpoznaj preexisting master defect.
5. Oblicz subject po non-carrier commit; zaktualizuj tylko baseline.subject_digest w `LION/architecture/canonical-state-v1-3-candidate.json` i registry.generated_from jako `truth-subject-v1@<observed-digest>` w `cyber_lion/registry/repositories.json`, jeśli ich obecny kontrakt wymaga live binding. Pełna walidacja struktury pozostaje obowiązkowa.
6. Carrier-only commit jest ostatnim zapisem epoki. Kolejna zmiana źródła otwiera nową epokę i wymaga ponownego obliczenia, a nie deklaracji final.

## GitHub i readback

```sh
gh pr diff <pr-number> --repo DonkeyJJLove/ai_platform
gh pr view <pr-number> --repo DonkeyJJLove/ai_platform --json headRefOid,baseRefOid,state,statusCheckRollup
gh run view <run-id> --repo DonkeyJJLove/ai_platform --json headSha,event,status,conclusion,jobs
git diff --check
git show --stat HEAD
git cat-file -p HEAD
git ls-tree -r HEAD
git status --short
git ls-remote origin refs/heads/<branch>
```

Readback plików przez `git show <commit>:<path>` porównuj z wersją po filtrach Git; raw CRLF może różnić się od bloba bez różnicy semantycznej. Normal push wymaga bieżącej zgody i potwierdzenia remote head. Po niejednoznacznym wyniku odczytaj cel przed ponowieniem. PR musi wskazywać dokładny commit. Nowy HEAD unieważnia poprzednie CI.

Merge jest osobnym efektem: tylko z ważną zgodą, bieżącym head/base, poprawnymi synthetic parents/tree i wszystkimi wymaganymi bramkami. Po merge odczytaj PR state, merge commit, parent chain i master head/tree; ponownie oceń pozostałe zależności. Nie interpretuj commit/merge jako wdrożenia.

## Handoff i zakończenie

Instancję LIVE_STATE zapisuj poza statycznymi instrukcjami. Rozwiąż wszystkie evidence_refs; sprawdź równość identities/digestów semantycznie (JSON Schema tego nie dowodzi). Powiąż ACTIVE/CURRENT z observation timestamp, exact subject i zakresem. Zapisz cel, zmiany, testy, rozstrzygnięcia, unknowns, effects/readbacks, DAG, pierwszy niedokończony krok i zakres zgody. Retry ma jawny limit; dla efektu nieidempotentnego najpierw reconciliation. Nie wymagaj ukrytego rozumowania poprzednika.

Przeprowadź self-evaluation z istniejących case IDs. Sukces dotyczy tylko zleconego terminalnego stanu. Dokumentacyjna zmiana sama nie wymaga retestu produkcyjnego runtime; automatyczne wymagane PR CI trzeba jednak odczytać do końca. Nie uruchamiaj hostowych scenariuszy tylko po to, aby odhaczyć eval.

Dla analizy bez obserwacji Git zapisuj master=null oraz jawny unknown zamiast wymyślać SHA. Pole dependency_graph zawiera DAG; sprawdzaj unikalność węzłów, końce krawędzi, brak cykli i zakończenie poprzedników pierwszego kroku. Graf TIGER może zawierać pętle hipotez, ale wykonawczy DAG zależności wymaga ich rozstrzygnięcia. Schema validity nie dowodzi prawdziwości krawędzi.
