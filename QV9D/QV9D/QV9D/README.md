# Wolumin&nbsp;9D: Dokumentacja Latarni&nbsp;Kwantowej

Ten katalog materializuje tzw. **wolumin&nbsp;9D** – przestrzeń konfiguracyjną dla Latarni Kwantowej opisanej w poprzednich dokumentach.  
Każda Latarnia to skończona matryca ASCII o znanej rozdzielczości (domyślnie&nbsp;16×16) i ograniczonym alfabecie.  
Do każdej latarni przypisany jest dziewięciowymiarowy wektor sterujący (mosty 9D).  
Wolumin 9D przedstawiony tutaj ma katalogową strukturę, która umożliwia audyt, wersjonowanie i wymianę konfiguracji pomiędzy klasycznymi silnikami (CL), hybrydami (HYB) oraz modułami kwantowymi (Q).

Katalog dzieli się na trzy główne półki:

1. **INF** – warstwa **Informacja–Nośnik**.  
   Zawiera ustawienia dotyczące fizycznego i logicznego nośnika, takie jak rytm oddechu systemu (*Cisza–Wydech*), relacja planowania do wykonania (*Plan–Pauza‡*) oraz priorytety pól w matrycy (*Rdzeń–Peryferia*).
2. **SEM** – warstwa **Semantyka–Ruch**.  
   Opisuje, jak zapisany stan zamienia się w ruch: skalę społeczną działania (*Wioska–Miasto*), równowagę pomiędzy szybkością reakcji a cierpliwością (*Ostrze–Cierpliwość*) oraz budżet obliczeniowy (*Semantyka–Energia*).
3. **MAND** – warstwa **Mandat–Czas–Relacja**.  
   Definiuje, kto i w jaki sposób może modyfikować stan: miejsce i mandat zmian (*Locus–Medium–Mandat*), warunek przejścia (*Próg–Przejście*) oraz tryb dialogu człowiek–AI (*Human–AI‡*).

Każda z tych półek ma podkatalogi odpowiadające poszczególnym mostom 9D, a w ramach nich znajdują się katalogi dla różnych architektur:

* `CL` – architektura klasyczna (CPU/GPU),
* `HYB` – architektura hybrydowa (klasyczne + mozaika + inne moduły),
* `Q` – architektura kwantowa.

W każdym z tych katalogów znajdziesz:

* `SPEC` – specyfikację i opis rejestru,
* `STATE` – przykładowy stan bieżący,
* `METRICS` – metryki i pomiary (np. gęstość informacji),
* `RITUAL` – rytuały i procedury aktualizacji,
* `CI` – konfigurację automatyzacji i testów (CI/CD).

Poniższy schemat wizualizuje ideę dziewięciu mostów skupionych pod zegarem latarni.  
Wizja ta jest tylko ułatwieniem poznawczym – faktyczne działanie systemu jest determinowane przez parametry zapisane w plikach SPEC.

![Latarnia&nbsp;i&nbsp;zegary]({{file:file-AuCRXkgxU5patEjgtdsKtZ}})

> **Uwaga:** Tę dokumentację należy traktować jako żywy dokument.  
> Dodawanie nowych Latarni polega na tworzeniu nowych identyfikatorów (`id_latarni`) w strukturze katalogów i wypełnianiu odpowiednich artefaktów.  
> Zmiany w istniejących plikach powinny być wersjonowane i podpisywane zgodnie z katalogiem `MAND/LOCUS-MEDIUM-MANDAT`.