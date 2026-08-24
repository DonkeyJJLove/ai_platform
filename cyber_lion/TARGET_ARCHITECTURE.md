# LION — Architektura docelowa

**Status dokumentu: TARGET / NORMATIVE DESIGN**

Ten dokument opisuje architekturę, do której zmierza **LION**. Nie jest dowodem, że wszystkie opisane mechanizmy działają produkcyjnie, nie jest źródłem execution authority i nie zastępuje obserwacji bieżącego stanu repozytorium, CI ani runtime.

Historyczna nazwa **Cyber-Lion** pozostaje w przestrzeni nazw `cyber_lion` i w starszych dokumentach. Nazwą całego systemu jest obecnie **LION**.

---

## 1. Pozycja architektoniczna

LION jest eksperymentalną platformą **nadzorowanej autonomii Human–AI**. Jej podstawowym zadaniem nie jest maksymalizacja autonomii modelu, lecz rozdzielenie dwóch klas zdolności:

```text
probabilistyczna inteligencja
!=
deterministyczna władza wykonawcza
```

`ai_platform` pełni rolę control plane'u i miejsca rozwoju wspólnych kontraktów, polityk, runtime'ów referencyjnych oraz mechanizmów obserwacji i rekonsyliacji. Nie oznacza to, że repozytorium ma docelowo zawierać każdą implementację wykonawczą albo przejąć stan wszystkich zewnętrznych providerów.

Zewnętrzne repozytoria, modele, usługi i runtime'y mogą uczestniczyć w LION jako providery, ale dopiero po związaniu ich z jawnym kontraktem, provenance, trust bindingiem i granicą authority.

Dla dynamicznego stanu obowiązuje pierwszeństwo źródeł:

```text
LIVE GITHUB + CURRENT CI
>
EXACT GIT STATE
>
MACHINE-GENERATED RUNTIME EVIDENCE
>
FRESH DERIVED PROJECTION
>
TARGET / ARCHITECTURE DOCUMENT
>
HISTORY / CHAT CONTEXT
```

Architektura może określać wymaganie. Nie może sama udowodnić, że wymaganie jest spełnione.

---

## 2. Trzy płaszczyzny systemu

LION rozdziela trzy podstawowe płaszczyzny:

```text
SEM  — percepcja, reprezentacja, analiza, hipotezy, planowanie, symulacja
MAND — tożsamość, provenance, polityka, authority, pamięć, audyt
INF  — procesy, pliki, API, sieć, sandboxy, workflow i realne skutki
```

Fundamentalna relacja brzmi:

```text
SEM proposal
!=
MAND authorization
!=
INF effect
```

To, że dane, instrukcja, model i credential znajdują się w jednym procesie, promptcie albo kontekście, nie scala ich klas zaufania.

Minimalnie należy rozróżniać:

```text
DATA
INSTRUCTION
CONTEXT
IDENTITY
AUTHORITY
MEMORY
DECISION
ACTION
EFFECT
EVIDENCE
```

---

## 3. Kanoniczna ścieżka od obserwacji do skutku

LION nie powinien posiadać legalnej ścieżki:

```text
LLM / dokument / hipoteza
        ↓
bezpośredni consequential effect
```

Docelowa ścieżka ma postać:

```text
OBSERVATION / SOURCE
        ↓
EVIDENCE + PROVENANCE
        ↓
REASONING / HYPOTHESIS
        ↓
ACTION PROPOSAL
        ↓
INTENT NORMALIZATION
        ↓
IDENTITY + MISSION + BASELINE
        ↓
PDP / POLICY DECISION
        ↓
TYPED, BOUNDED GRANT
        ↓
PEP / REFERENCE-MONITOR BOUNDARY
        ↓
EXECUTOR / SANDBOX
        ↓
BOUNDED EFFECT
        ↓
INDEPENDENT OBSERVATION
        ↓
RECONCILIATION
        ↓
RECEIPT / VERIFIED STATE
        ↓
NEXT DELTA
```

Model może generować propozycję. Nie może sam nadać jej statusu autoryzowanego działania.

---

## 4. Reference Monitor i complete mediation

Docelowo każdy consequential effect powinien przechodzić przez niepomijalny punkt egzekwowania polityki.

Reference Monitor / PEP powinien spełniać co najmniej następujące wymagania:

```text
1. każde działanie ma jawną tożsamość i mission binding,
2. każde działanie ma jawny scope zasobów i operacji,
3. authority pochodzi z zewnętrznego wobec executora źródła,
4. executor nie może zwiększyć własnych uprawnień,
5. policy decision jest oddzielona od wykonania,
6. grant jest ograniczony czasowo i zakresowo,
7. efekt jest obserwowany niezależnie od deklaracji executora,
8. utrata wymaganej obserwowalności ogranicza authority,
9. krytyczne działanie pozostawia rekonstruowalny receipt,
10. brak complete mediation oznacza brak prawa do twierdzenia o pełnej kontroli.
```

Samo tekstowe `allow/deny` w promptcie nie jest mechanizmem egzekwowania. Jeżeli zabronione narzędzie pozostaje technicznie osiągalne, granica authority nie jest zamknięta.

Dla mutacji repozytorium preferowany model rozdziela:

```text
candidate preparation
→ independent verification
→ exact bounded attachment
```

Executor odpowiedzialny za finalny attachment powinien mieć tylko capability potrzebną do jednego dokładnie określonego efektu, a nie ogólne uprawnienia do tworzenia plików, branchy, PR-ów, merge'y, release'ów i deployów.

---

## 5. Model authority

Authority w LION ma być **tłumione**, a nie dziedziczone przez sam fakt uczestnictwa w misji lub roju.

```text
child <= parent
executor <= mission
mission <= fleet envelope
```

Z tego wynikają reguły:

```text
verified identity != authorization
registered capability != authority
registry presence != authority
swarm membership != credential inheritance
model confidence != permission
successful prior action != future grant
```

Zwiększenie liczby agentów albo executorów nie może zwiększać per-executor authority.

Flota powinna posiadać również wspólny budżet skutków obejmujący co najmniej:

```text
concurrent writers
repositories
branches
changed paths
consequential operations
credentials / external effects
```

---

## 6. Flota, roje i executory

Flota nie jest pętlą wywołań modeli. Jest zarządzanym systemem wykonawczym.

Każdy executor powinien być związany z:

```text
immutable executor identity
mission
repository baseline
branch / path lease
authority context
sandbox / runtime binding
heartbeat / liveness
receipt chain
```

Role operacyjne powinny być rozdzielane:

```text
BUILDER
VERIFIER
OBSERVER
RECONCILER
AUTHORITY SOURCE
```

Builder nie powinien być jedynym finalnym verifierem własnego efektu.

Rejestry LION mogą reprezentować wiele **logicznych dronów, rojów i formacji**. Taki wpis nie jest dowodem istnienia równoważnej liczby niezależnych procesów, maszyn, sandboxów lub production executorów.

---

## 7. Observability-conditioned authority

Docelowa zasada brzmi:

```text
observability loss
→ trust degradation
→ authority degradation
```

W szczególności:

```text
LOSS OF REQUIRED OBSERVATION
!=
PRESERVE PREVIOUS AUTHORITY
```

Ocena authority powinna uwzględniać co najmniej:

```text
identity
mission
policy
provenance completeness
source trust
observability state
runtime integrity
requested impact
reversibility
currentness
execution history
```

Możliwe stany wykonawcze:

```text
NORMAL
→ DEGRADED
→ RESTRICTED
→ FROZEN
→ REVOKED
```

Nie każdy brak telemetrii musi zatrzymać cały system. Dla działań wysokiego wpływu brak wymaganego sygnału powinien jednak blokować wydanie nowego authority albo zatrzymywać wykonanie przed nieodwracalnym skutkiem.

---

## 8. Evidence, receipts i rekonstrukcja skutku

Receipt nie jest automatycznie prawdą o świecie. Jest artefaktem dowodowym ważnym w granicach zaufania do źródła, collectora, klucza, platformy i kompletności obserwacji.

Minimalny łańcuch rekonstrukcji powinien umożliwiać odpowiedź:

```text
kto
→ w ramach jakiej misji
→ na jakim baseline
→ na podstawie jakiego authority
→ wykonał jaką operację
→ w jakim runtime
→ jaki efekt zaobserwowano
→ czy efekt odpowiadał żądaniu
→ czy stan został poprawnie zrekonsyliowany
```

Dla efektów wysokiego wpływu należy dążyć do niezależności co najmniej pomiędzy:

```text
AUTHORITY SOURCE
EXECUTOR
OBSERVER
VERIFIER / RECONCILER
```

Jeżeli ten sam skompromitowany komponent wykonuje efekt, obserwuje go i sam potwierdza własny receipt, otrzymujemy samozgłoszony dowód, a nie niezależną weryfikację.

---

## 9. Rekonsyliacja i zamknięcie misji

Wykonanie nie kończy się w momencie zwrócenia `SUCCESS` przez executor albo CI.

LION powinien porównywać:

```text
EXPECTED EFFECT
vs
OBSERVED EFFECT
```

oraz klasyfikować rozbieżności.

Misja lub batch nie powinny zostać uznane za zamknięte, jeżeli istnieje którykolwiek z poniższych stanów:

```text
unknown active mission
unknown result
unowned branch
unresolved write lease
unreconciled effect
unresolved observer disagreement
```

Reconciliation jest domyślnie read-only. Cleanup lub korekta wymagają nowego, jawnego authority.

---

## 10. Runtime i granice zaufania

LION nie powinien zakładać jednego typu executora.

Docelowo providery wykonawcze mogą obejmować:

```text
GitHub Actions
local process runtime
container / isolated sandbox
VM / microVM
remote controlled executor
future distributed execution provider
```

Każdy provider musi jawnie deklarować swoją granicę bezpieczeństwa i to, czego **nie potrafi** udowodnić.

Obecność testowanego kontraktu sandboxa nie dowodzi automatycznie izolacji OS. Obecność workload identity record nie dowodzi automatycznie production attestation. Zielone CI nie dowodzi complete mediation dla wszystkich zewnętrznych efektów.

Docelowy runtime wysokiego zaufania powinien wspierać:

```text
workload identity
attestation
credential isolation
bounded capabilities
sandbox enforcement
heartbeat / liveness
distributed revoke / freeze
currentness checks
independent effect observation
signed or tamper-evident receipts
```

---

## 11. F009 jako aktualna ścieżka dowodowa, nie uniwersalna gwarancja

Kod F009 rozwija konkretną ścieżkę runtime evidence:

```text
pre-runtime authority bootstrap
→ pinned authority / provider inputs
→ runtime admission
→ currentness check
→ bounded sandbox effect
→ independent observer
→ reconciliation
→ receipt
```

Ta implementacja jest istotnym krokiem w kierunku architektury docelowej, ale nie wolno z niej automatycznie wyprowadzać twierdzenia, że każdy efekt w LION jest już objęty production-grade Reference Monitorem.

Własność musi być udowodniona dla konkretnej ścieżki wykonawczej i konkretnego environmentu.

---

## 12. Graph state jako projekcja, nie źródło władzy

LION może utrzymywać graf relacji pomiędzy obiektami systemu, na przykład:

```text
Entity
Repository
Artifact
Source
Observation
Evidence
Claim
Hypothesis
Agent
Mission
Swarm
Executor
Capability
Policy
Authority
Decision
Execution
Outcome
Memory
```

oraz relacje:

```text
observed_from
derived_from
supports
contradicts
generated_by
consumed_by
executed_by
authorized_by
blocked_by
depends_on
changed
caused
correlated_with
supersedes
validated_by
```

Graf służy do korelacji, nawigacji i rekonstrukcji. Nie powinien sam mintować authority ani zamieniać korelacji w przyczynowość.

Stan grafu jest projekcją. Jeżeli konfliktuje z live GitHub, bieżącym authority source albo runtime evidence, należy ponownie zaobserwować stan zamiast bronić projekcji.

---

## 13. Federacja providerów

LION może integrować inne repozytoria i systemy, ale nie powinien zakładać ich roli wyłącznie na podstawie nazwy lub historycznej koncepcji.

Każdy provider powinien wejść do systemu przez jawny adapter określający:

```text
capabilities
input/output contract
provenance
trust class
authority requirements
effect surface
failure modes
version / digest
observability
```

Repozytoria takie jak `glitchlab`, `swarm`, `sbom`, `chunk-chunk`, `HA2D`, `writeups` i inne mogą pełnić wyspecjalizowane role w szerszym ekosystemie, ale ich dokładna rola pozostaje własnością konkretnej, zweryfikowanej integracji — nie samej architektury deklaratywnej.

---

## 14. Model awarii

Architektura musi zakładać awarie i zachowania przeciwnicze co najmniej w klasach:

```text
duplicate executor / mission / lease / branch owner
path overlap
stale baseline
lost heartbeat
forged or stale attestation
revoked executor / mission
dependency cycle
scheduler starvation
late result
result after cancellation
control-plane restart
authority-store restart
partial network partition
sandbox death
observer death
verifier death
reconciliation disagreement
telemetry loss
credential leakage
provider drift
```

Każda taka sytuacja powinna:

```text
FAIL CLOSED
albo
ENTER AN EXPLICIT DEGRADED STATE
```

Nigdy nie powinna po cichu zwiększać authority.

---

## 15. Co jest targetem, a co nie jest jeszcze udowodnione

Architektura docelowa obejmuje między innymi:

```text
complete mediation consequential effects
capability-reduced execution
real executor provisioning
OS / VM sandbox enforcement
workload attestation
credential isolation
persistent heartbeat
runtime currentness
distributed revocation
independent effect observation
reconciliation and closure
fleet-wide effect budgets
```

Sama obecność tych pojęć w kodzie lub dokumentacji nie oznacza production proof.

Do czasu osobnej obserwacji nie należy zakładać między innymi:

```text
production PKI
production-grade sandboxing dla każdej ścieżki
pełnej distributed revocation
pełnej credential isolation
100 niezależnych production executorów
pełnej atestacji zewnętrznego modelu AI
pełnej obserwowalności wszystkich external effects
```

---

## 16. Kryteria architektoniczne

Architekturę można uznać za zbliżoną do celu dopiero wtedy, gdy powtarzalnie spełnia co najmniej następujące własności:

```text
HIGH-IMPACT EFFECT
→ zawsze przechodzi przez właściwy PEP

EFFECT
→ ma wiarygodny mission/action/executor binding

OBSERVABILITY DEGRADES
→ authority nie rośnie i odpowiednio maleje

EXECUTOR
→ nie może mintować własnego authority

BUILDER
→ nie jest jedynym źródłem finalnej weryfikacji

FLEET SCALE INCREASES
→ per-executor authority nie rośnie

REPOSITORY / RUNTIME EFFECT
→ może zostać niezależnie zaobserwowany i zrekonsyliowany

PROJECTION CONFLICTS WITH LIVE STATE
→ live state wygrywa

UNKNOWN / STALE / CONFLICTED STATE
→ re-observe albo fail closed
```

---

## 17. Zasada projektowa

Rdzeń LION można sprowadzić do czterech reguł:

```text
szeroka eksploracja
+ wąska, jawna authority
+ deterministyczne bramki skutku
+ niezależna obserwacja i rekonsyliacja
```

Celem nie jest agent, który może zrobić wszystko.

Celem jest system, w którym **inteligencja może być rozproszona, adaptacyjna i probabilistyczna, ale możliwość powodowania realnych skutków pozostaje ograniczona, obserwowalna, odwoływalna i możliwa do niezależnej rekonstrukcji**.
