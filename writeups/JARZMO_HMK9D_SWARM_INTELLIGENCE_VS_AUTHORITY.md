# Jarzmo i HMK-9D: rozdzielenie inteligencji roju od prawa do działania

## Status dokumentu

Ten write-up opisuje architektoniczną relację między warstwą komunikacji i wspólnego stanu roju, mechanizmami Fleet/Mission/Lease oraz deterministyczną granicą wykonawczą Jarzma. Dokument ma charakter architektoniczno-badawczy: rozdziela intencję i poznanie od authority oraz wskazuje, które własności wymagają twardego enforcementu runtime, a nie wyłącznie semantyki komunikacji.

Opisany kierunek zagrożenia trafia dokładnie w granicę, dla której powstała koncepcja Jarzma. Problemem nie jest już wyłącznie to, że model może wygenerować złośliwy kod. Problem zaczyna się wtedy, gdy **model, agent, pamięć, narzędzia, credentiale i inni agenci tworzą jedną ciągłą ścieżkę od informacji do realnego skutku**. W takim świecie filtrowanie promptu jest zabezpieczeniem zbyt wysoko w stosie. Jarzmo przenosi kontrolę na dół — pomiędzy probabilistyczną inteligencję a rzeczywistość. Agent może uznać, że należy wykraść token, uruchomić skaner, zmienić plik, połączyć się z hostem albo przekazać zadanie innemu agentowi, ale z samego faktu powstania takiego zamiaru **nie wynika możliwość wykonania**. To jest centralna zasada JARZMO-MESH: `PERCEPTION ≠ AUTHORITY`, `INFERENCE ≠ EXECUTION`, `CONFIDENCE ≠ PERMISSION`.

Technicznie ścieżka jest odwrócona względem typowego agenta:

```text
AI / AGENT
    ↓
ACTION PROPOSAL
    ↓
JARZMO
    ↓
POLICY + CURRENT AUTHORITY
    ↓
CAPABILITY
    ↓
LOCAL PEP / REFERENCE MONITOR
    ↓
BOUNDED EXECUTION
    ↓
OBSERVED EFFECT
    ↓
EXECUTION RECEIPT
```

To bezpośrednio mityguje klasę problemów widocznych w kampaniach AI-Driven. Agent nie powinien posiadać trwałych credentiali; dostaje krótkotrwałą capability ograniczoną do konkretnego `run_id`, `action_id`, operacji i zasobu. Nie otrzymuje dowolnego shella tylko dlatego, że potrafi używać shella. Dostęp sieciowy może być domyślnie `DENY`, filesystem ograniczony, proces osadzony w osobnym cgroup/namespace, wywołania systemowe ograniczone przez seccomp i LSM, a wyjście do zewnętrznych API przepuszczane przez semantyczną bramę. Jeżeli model zostanie przejęty przez prompt injection albo sam model okaże się złośliwy, **kompromitacja cognition nie powinna oznaczać kompromitacji deterministic enforcement**. Jarzmo rozwija tę granicę jako Observability-Conditioned Reference Monitor z complete mediation, runtime assurance i execution attestation.

Najważniejszą odpowiedzią na problem agentów tworzących własne kanały komunikacji jest natomiast to, że w JARZMO-MESH **komunikacja także jest efektem podlegającym polityce**. Agent-to-agent traffic nie może omijać lokalnego `Mesh Communication Gate`; fakt, że A może rozmawiać z B, nie oznacza, że A może delegować B swoje uprawnienia. Obserwacje, requesty, głosy, decyzje i receipty powinny być przypisane do konkretnej tożsamości, czasu i źródła. Dzięki temu „HOST-B też to widział” przestaje być narracją modelu, a staje się twierdzeniem możliwym do związania z konkretnym uczestnikiem i evidence. W późniejszym modelu LION zasada zostaje zaostrzona przez `child ≤ parent`, `executor ≤ mission`, `mission ≤ fleet envelope`: zwiększenie liczby agentów nie zwiększa authority pojedynczego agenta ani nie tworzy authority przez samą komunikację.

Szczególnie istotna jest **negative authority**. Jeżeli przeciwnik próbuje zgasić telemetrykę, zmanipulować stan, odizolować observera albo wymusić nieobserwowalną ścieżkę, system nie interpretuje utraty widoczności jako „braku alarmu”. Interpretacja jest przeciwna:

```text
OBSERVABILITY ↓
        ⇒
POSSIBLE AUTHORITY ↓

OBSERVABILITY = 0
        ⇒
NEW HIGH-IMPACT AUTHORITY = 0
```

Jarzmo może wtedy przejść `ACTIVE → RESTRICTED → OBSERVE_ONLY → QUARANTINED`, zamrozić wykonanie, odebrać credentiale lub zabić cały procesowy podgraf działania. To zasadnicza różnica względem klasycznego systemu telemetrycznego: telemetryka nie służy wyłącznie do postmortem. **Jest warunkiem utrzymywania autonomii.**

## 9D: zanim pojawiło się Jarzmo wykonawcze, potrzebny był wspólny język roju

HMK-9D rozwiązuje inną połowę tego samego problemu. Jarzmo odpowiada na pytanie **„czy wolno to zrobić?”**, natomiast 9D zapewnia wspólną reprezentację **„co się właśnie dzieje, gdzie jestem w procesie i jak moje przejście odnosi się do przejść innych uczestników?”**. `chunk-chunk` formalizuje działanie jako trajektorię stanów:

```text
s₀ → Δ₀ → s₁ → Δ₁ → s₂ → ... → skutek
```

Każdy krok może być opisany przez lokalne własności, reprezentację `[x9D]`, energię/koszt przejścia, progi i mosty; do opisu przejścia włączane są także tożsamość, mandat, przewidywanie i decyzja. W ten sposób agent nie powinien przekazywać drugiemu całej swojej „głowy”. Może przekazać **skompresowany stan, różnicę i pozycję w trajektorii**, czyli informację potrzebną do koordynacji.

To jest mechanizm przeciwdziałający bezmyślnemu powielaniu pracy przez rój. Jeżeli agent A zakomunikował już:

```text
MISSION = M
OBJECT = X
STATE = s17
DELTA = reconnaissance_completed
NEXT_GAP = credential_lineage
ROLE = observer
```

to agent B nie musi ponownie wykonywać reconnaissance tylko dlatego, że dostał ten sam ogólny prompt. Może odczytać istniejącą deltę, zająć brakujący fragment przestrzeni problemu albo wejść w rolę verifiera. Wspólną inteligencję tworzy więc nie `A ↔ B ↔ C` jako swobodny chat, lecz **koordynacja przez jawny stan, różnice, role i artefakty**. W obecnym LION tę zasadę rozwija kanoniczny protokół komunikacji roju: wiadomości posiadają identyfikator, nadawcę, target, kontekst misji, correlation id, evidence refs i requested action; dozwolone typy obejmują m.in. `DEPENDENCY`, `HANDOFF`, `BLOCKER`, `EVIDENCE`, `REQUEST`, `STATUS` i `RECONCILIATION`, przy czym sam komunikat nie nadaje authority.

Jest tu jednak ważne rozróżnienie historyczno-techniczne. **HMK-9D sam w sobie nie jest dowodem twardej ochrony przed dublowaniem tasków.** Formalizm wspólnego stanu i komunikacji nie zastępuje runtime'owej własności pracy. Twarda gwarancja „dwóch executorów nie obejmuje nieświadomie tego samego efektu” wymaga dodatkowo mechanizmów takich jak immutable executor identity, mission binding, lease, heartbeat, zakres repo/path oraz receipt chain. W późniejszej polityce floty LION executor jest wiązany z misją, baseline'em, branch/path lease'em, sandboxem i łańcuchem receiptów, a duplicate executor/mission/lease owner należy do jawnego failure modelu i musi failować closed albo wejść w explicit degraded state.

Dlatego pełna odpowiedź architektury wygląda nie jak jedno zabezpieczenie, lecz jak **trzy sprzężone warstwy**:

```text
HMK-9D / SHARED STATE
„co już wiemy, co już zrobiono,
gdzie jest różnica i kto zajmuje jaki fragment problemu”
                ↓
FLEET / MISSION / LEASE
„kto jest właścicielem konkretnej pracy
i jaki zakres może aktualnie wykonywać”
                ↓
JARZMO / PEP
„czy ten konkretny skutek jest teraz dozwolony”
                ↓
REAL EFFECT + RECEIPT
```

To jest zasadnicza odpowiedź na normalizację ofensywnego AI. **Nie próbujemy sprawić, żeby wszystkie agenty były posłuszne. Projektujemy system tak, aby mogły być inteligentne, omylne, skompromitowane, komunikować się i dynamicznie organizować — ale żeby żadna z tych własności sama nie tworzyła prawa do konsekwencji.** Rój może zwiększać swoją przestrzeń poznawczą. Jarzmo nie pozwala, aby z tego automatycznie rosła przestrzeń władzy.

## Relacja do aktualnego protokołu LION

Aktualny `LION/protocols/SWARM_COMMUNICATION.md` materializuje część tej ewolucji: adresy `mission:`, `drone:`, `swarm:` i `group:` są rozwiązywane przez registry; nierozwiązany adres failuje closed; canonical envelope wiąże kontekst misji i evidence; replay, ambiguity, stale head, niepoprawny artifact lub `UNKNOWN` prowadzą do `DENY`. Najważniejsza reguła pozostaje niezmienna: **komunikacja nigdy nie rozszerza authority**.

W rezultacie 9D/shared-state, Fleet ownership i Jarzmo nie są konkurencyjnymi rozwiązaniami. Są kolejnymi granicami tego samego systemu: semantyka mówi, jaki fragment rzeczywistości został rozpoznany; Fleet ustala własność pracy; Jarzmo rozstrzyga dopuszczalność skutku; observer i receipt pozwalają następnie stwierdzić, co rzeczywiście zaszło.