# R10 — natywna faza poznawcza LPCL przed flotą materialną

Status: **SOURCE CANDIDATE / NOT MERGED / NOT DEPLOYED**. Wydanie źródłowe po R9. Scope: pierwszy etap `CROSS_MODEL_RECON` dokładnej misji `LION-APPLICATION-FACTORY-CROSS-MODEL-R1` pod istniejącym schedulerem Mission Control. Authority: jawny exact user launch LPCL i aktualne operator fence, nie dokument lub model.

## Faktyczny defekt

R7/R8 udostępniały trwały `DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED`, ale `bind_lpcl_execution` nie tworzył aktywnej ścieżki faz przed uzyskaniem 32/32 workerów. `control_plane_reconnaissance.ensure_material_leases` tworzył 4–16 dzierżaw `MD` także dla `execution_class=COGNITIVE`, a `ensure_local_trajectories` wydawał trzy `LOCAL_MODEL_INFERENCE` assignmenty do `MD025–MD027`. Jednocześnie zweryfikowany `PhaseExecutionContract` Application Factory przypisuje fazie `CROSS_MODEL_RECON` **0 materialnych workerów**.

## Nowa ścieżka R10

Istniejący `global_scheduler_once` uruchamia dodatkowy *bounded phase handler*, nie drugi scheduler: `advance_native_cognitive_phase_zero_once`. Kandydat musi mieć:
`EXPLICIT_USER_ACTIVATION`, `operator_control.autonomy_allowed`,
dokładnie `LION-APPLICATION-FACTORY-CROSS-MODEL-R1`,
niepowiązany materialnie `LPCL_MISSION`, fazę 0 z kontraktem
`execution_class=COGNITIVE / effect_ceiling=NONE /
capability=CONTROL_PLANE_RECONNAISSANCE`,
trwały R7 WAIT driver bez lease_owner oraz aktualny `master` HEAD/TREE
pobrany **niezależnie** od danych misji. Source drift lub utrata generacji
przerywa przed wywołaniem modelu.

`control_plane_reconnaissance.execute_phase` zachowuje wszystkie istniejące
obserwacje, obowiązek Windows evidence i kanał `saas_broker`, lecz tylko
dla tego dokładnego wywołania przyjmuje `native_current_source` i
`native_transport`. Pomija wtedy jedynie `ensure_material_leases`
i przekazuje lokalne trzy trajektorie do
`native_cognitive_phase_zero`. **Nie wstawia** do baz
`material_workers`, `mission_recon_material_leases` ani sztucznych
`MD025–MD027` dla fazy 0.

Pojedyncza trajektoria ma własny `call_id`, `role`,
`evidence_bundle_digest`, `contract_digest`, `lpcl_digest`,
source HEAD/TREE, driver generation, context_revision, digest treści
promptu, digest kanonicznego żądania oraz SHA-256 **dokładnie wysłanego
HTTP request body**. Dziennik w bazie Mission Control jest trwały:

```text
INTENT_DURABLE
  -> SEND_UNKNOWN (COMMIT przed wysłaniem bajtów)
  -> RESPONSE_RECONCILED (tylko po HTTP 200 + raw HTTP payload + text)
```

Nie ma automatycznego retry z `SEND_UNKNOWN`; nieznany rezultat
wymaga odrębnej rekonsyliacji. Po odbiorze zapisuje digest rzeczywistej
odpowiedzi HTTP, treści modelu i receipt; następny odczyt weryfikuje
cały rekord. Model deklaruje swoje ID, ale
`model_attested=None`: nie wolno zamieniać identyfikatora z payloadu
na niezależną atestację modelu. Model output jest proposal data.

Przesłanie modelowe odbywa się tylko na dokładny, obecnie działający
wewnętrzny endpoint `http://172.25.128.1:8772/v1/chat/completions`.
Brak proxy, redirectów, arbitralnego hosta, adresu użytkownika, uploadu
artefaktów lub wykonania kodu modelu. Ten `POST` jest jawną nową
powierzchnią efektu `external.network.post` i wymaga bieżącej
aktywacji/PEP oraz przeglądu bezpieczeństwa; nie jest
`RuntimeAdmission` dla późniejszych efektów Docker.

Każdy krok schedulera wysyła najwyżej jedną nową trajektorię
LOCAL. Trzy role mają odrębne prompty i trwałe receipts, lecz mogą
pochodzić z **tego samego modelu**. W szczegółach analizy oznaczamy
`SHARED_NATIVE_LOCAL_MODEL_ANCESTOR` i nie traktujemy trzech
odpowiedzi jako niezależnych modeli. SaaS jest nadal oddzielnym
wymaganym źródłem odpowiedzi/receipt; gdy sesja ma `EXPIRED`,
`CROSS_MODEL_INTELLIGENCE_BOUND` nie może stać się PASS.

Dopiero po prawdziwym zakończeniu kontraktu fazy 0 istniejący
`_driver_phase_result` zapisuje PASS i ustawia
`WAIT_FOR_ADMITTED_ONE_WORKER` dla fazy
`PREACTIVATE_BUILDER`. Nie nadaje uprawnień do zapisania artefaktu
ani nie obchodzi R8 `RuntimeAdmission`.

## Wykonywalne testy i różnica wobec produkcji

Testy R10 na **izolowanej SQLite** tworzą oryginalnym
`register_lpcl_mission` exact Application Factory, symulują jawny
testowy stan operatora, używają prawdziwego R7
`park_activated_docker_lpcl_runtime_need`, oryginalnych
`PhaseExecutionContract` i `control_plane_reconnaissance`.
Weryfikują trwały model receipt, brak fake worker ID i lease,
source drift, stale generation, tampering, request-bytes digest,
nieznany send bez retry, niedozwolony endpoint/redirect/proxy,
trzy trajektorie ze wspólnym modelem oraz użycie jedynego
`global_scheduler_once` hook.

Dodatkowo bez misji produkcyjnej wykonano już pojedynczy
odizolowany, rzeczywisty `POST` do natywnego llama.cpp.
Otrzymano model response i obliczono SHA faktycznych bajtów żądania
i odpowiedzi. Jest to **dowód zdatności transportu**, nie dowód
ukończenia fazy ani misji.

Przed scaleniem wymagane są aktualne kompletne testy, Source Validation,
exact Git tree, jawne przeliczenie Host Authority effect census,
manifestu **93 plików** Mission Control i truth carriers. Wdrożenie
wymaga kanonicznego instalatora, aktualnego backupu SQLite i
niezależnego HTTP/API readback.

## Nierozwiązane działania

R10 nie materializuje jeszcze 1 workera kwalifikacyjnego ani 32
materialnych wykonawców; brak zainstalowanego zaufanego producenta
`RuntimeAdmission` do R8 i niezależnych
`COOPERATIVE_ARTIFACT_PRODUCTION/VERIFY` materializerów.
Sesja SaaS jest `EXPIRED` i nie ma nowego, odpowiednio związanego
receipt; brak operator-launched exact LPCL w produkcji. Jeśli panel
nie prześle wymaganej Windows observation, faza 0 pozostaje
`EVIDENCE_INCOMPLETE`, nigdy PASS.

Pierwszy kolejny krok: po źródłowo dopuszczonym R10 potwierdzić
w produkcyjnym `mission_model_calls` / native journal stan testowy
z dokładnego **jawnie uruchomionego** LPCL; następnie rozwiązać
one-worker admission i rozdzielone role BUILD/VERIFY bez uruchamiania
starej R24 floty.

## Regresja bramek 0/1/32 i brakujące dowody

Kolejna kontrola wykazała, że wcześniejszy R7 auto-rebinder próbował
przywrócić gate `DOCKER_FLEET_CURRENTNESS_REQUIRED` podczas oczekiwania
na dane fazy poznawczej. R10 zapisuje teraz w istniejącym driverze
`WAIT_FOR_PHASE_ZERO_EVIDENCE` z dokładną przyczyną oczekiwania,
a R7 chroni tę bramkę przed podmianą. Po rzeczywistym `PASS` fazy 0
kolejny gate to `WAIT_FOR_ADMITTED_ONE_WORKER`; wcześniejsza obecność
32 workerów również nie może przeskoczyć jeszcze niewykonanej fazy 0.
Dawne testy R5/R7 weryfikujące full-fleet binding zachowują rygor
rebindu, ale fixture przenosi je explicite do późniejszej fazy 32-MD.

W nowej natywnej ścieżce brak wymaganej obserwacji Windows daje
`EVIDENCE_INCOMPLETE`, a stary lub częściowy bundle, któremu brakuje
kanonicznego `model_view`, `contract_digest` lub pasującego SHA,
kończy się `NATIVE_EVIDENCE_BUNDLE_REACQUIRE_REQUIRED` bez wysłania
żądania LOCAL i bez assignmentu MD. Wciąż wymagany jest rzeczywiście
zarejestrowany SaaS `RESPONDED` + digest odpowiedzi i receipt;
`EXPIRED` nie może spełnić `CROSS_MODEL_INTELLIGENCE_BOUND`.

R10 nie instaluje jeszcze one-worker preactivation i nie deklaruje,
że pełny materialny LPCL BUILD/VERIFY zakończył się sukcesem.

## PR #444 — bieżący inwentarz P0 po R10

Niezależny `Cyber-Lion Core` na pierwotnym kandydacie PR #444
wykonał 4304 testy i znalazł trzy błędne oczekiwania w teście
`test_p0_current_candidate_inventory_delta.py`. Historyczne P0
zachowuje **567** powierzchni; aktualny kod R10 posiada **578**
rozpoznanych powierzchni, **0** nierozstrzygniętych referencji
po taxonomy reconciliation i **0** nierozwiązanych klas.
Dokładna różnica identyfikatorów to 544 wspólne, 23 usunięte z
powodu przemieszczenia punktów wywołania i 34 nowe; tylko
**11 z 34** reprezentuje nowe efekty, pozostałe 23 to przesunięcia.

Osiem historycznych `conn.execute` w
`control_plane_reconnaissance.py` uzgodniono niezależnie przez
identyczne SHA-256 AST ich kompletnych wywołań, zamiast dopasowania
samych numerów linii. Piętnaście zapisów w
`conversation_chat.py` nadal ma tylko historyczne przesunięcie
`+1`. Nowe, jawnie rozliczone efekty to sześć zapisów providera
przygotowania runtime, jeden nowy zapis trajektorii natywnej w
rekonesansie, trzy trwałe zapisy w nowym native ledger oraz jeden
`external.network.post` do zamkniętego endpointu LOCAL.
Nie oznaczono żadnej z tych powierzchni jako automatycznie
zaautoryzowanej, zaobserwowanej w produkcji lub odziedziczonej
z historycznego P0. Test historii P0 i osobny freeze fingerprint
`conversation_chat.py` pozostają bez zmiany.
