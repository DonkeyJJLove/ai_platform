# QV9D_rejestr_generacji.md  
**Procesowy rejestr projektu GLX / chunk-chunk / glitchlab / swarm / HA2D / hipotezy_nadawcze_LLM**

---

## 1. Cel rejestru

Ten plik jest **czytelną dla człowieka stopką do LAT_GLX_PROJECT_MOSAIC.tree.json**.  
Rejestr służy do:

- śledzenia, **jak zmienia się struktura mozaiki repozytoriów w czasie**,  
- zapisywania decyzji o tym, **które zmiany wymagają aktualizacji dokumentacji / rytuałów**,  
- łączenia logiki AST↔mozaika z realnymi commitami i tagami w poszczególnych repozytoriach.

Źródłem prawdy o strukturze jest plik:

`SEM/WIOSKA-MIASTO/HYB/STATE/LAT_GLX_PROJECT_MOSAIC.tree.json`.

---

## 2. Warstwy 9D powiązane z rejestrem

- **INF / RDZEN-PERYFERIA / HYB**  
  Mapuje węzły mozaiki na realne repozytoria, kontenery i ścieżki (GitHub, ZIP, wolumeny).  
- **SEM / WIOSKA-MIASTO / HYB**  
  Definiuje drzewo procesowe projektu – węzły (repo, moduły) i ich relacje.  
- **MAND / LOCUS-MEDIUM-MANDAT / HYB**  
  Określa, kto ma mandat do zmiany węzłów i jakie rytuały (testy, review, CI) obowiązują.

Ten rejestr opisuje głównie warstwę **SEM**, ale zawsze w odniesieniu do INF i MAND.

---

## 3. Aktualny stan mozaiki projektu

> Fragment streszczający `LAT_GLX_PROJECT_MOSAIC.tree.json`  
> (ten akapit może być generowany automatycznie przez Scan-9D.ps1)

- Repozytorium główne: **GLX_PROJECT**  
- Rdzeń języka i mostów 9D: **chunk-chunk**  
- Rdzeń GUI i operacji mozaiki: **glitchlab**  
- Warstwa orkiestracji: **swarm**  
- Warstwa analizy i metryk: **HA2D**  
- Warstwa teorii kanału i hipotez nadawczych LLM: **hipotezy_nadawcze_LLM**

Każde z tych repozytoriów jest powiązane z dominującym mostem 9D  
(PLAN–PAUZA, WIOSKA–MIASTO, SEMANTYKA–ENERGIA, HUMAN–AI‡ itd.),  
co odzwierciedla jego rolę w architekturze.

---

## 4. Historia generacji / skanów

Tabela jest append-only – każdy wywołany `Update-QV9D.ps1` lub `Scan-9D.ps1` dopisuje jedną linię:

| Data / czas (UTC+1)     | Narzędzie       | Zmiany w mozaice                | Decyzja dokumentacyjna |
|-------------------------|-----------------|----------------------------------|------------------------|
| 2025-11-22 19:15        | Update-QV9D     | Inicjalizacja QV9D, brak zmian logicznych | NO-OP                  |
| 2025-11-22 19:20        | Scan-9D         | Wykryto 5 repo (chunk, glitch, swarm, HA2D, hipotezy) | AUTO-DOC (ten wpis)    |
| ...                     | ...             | ...                              | ...                    |

Kolumna **Decyzja dokumentacyjna** powinna używać prostego słownika:

- **NO-OP** – zmiana techniczna (np. usunięcie `__pycache__`), nie wymaga modyfikacji opisu AST↔mozaika. :contentReference[oaicite:3]{index=3}  
- **AUTO-DOC** – skrypt sam odświeżył opis (np. nowe repo), wystarczy ten rejestr.  
- **MANUAL-DOC** – wymagana ręczna aktualizacja dokumentów wyższego poziomu (np. `Mozaikowe Drzewo AST – matematyka...`), bo doszło do zmiany koncepcji lub wprowadzenia Φ / Ψ w kodzie.

---

## 5. Powiązania z dokumentacją koncepcyjną

Ten rejestr jest niższą warstwą względem dokumentu:

- **„Mozaikowe Drzewo AST – matematyka, formalizm i praktyka dla AgentaAI”** – opisuje meta-język AST↔mozaika dla Glitchlab i AgentaAI. :contentReference[oaicite:4]{index=4}  

Zasada:

- jeśli commit **nie zmienia** żadnego z inwariantów AST↔mozaika ani nie dodaje nowych klas węzłów / polityk, wystarczy odnotować go jako **NO-OP** lub **AUTO-DOC**;  
- jeśli commit dodaje realną implementację Φ / Ψ, nowych metryk per-tile, nowych polityk – wpis w tym rejestrze powinien mieć decyzję **MANUAL-DOC** i wskazanie, który fragment dokumentu koncepcyjnego wymaga aktualizacji (sekcja, rozdział).

---

## 6. Plan dalszy (dla Agenta / HUD)

Na tej podstawie możesz w kolejnym kroku:

- podpiąć HUD tak, by z `LAT_GLX_PROJECT_MOSAIC.tree.json` rysował **„mapę wioski-miasta”** repo (kafelki z ikonami jak na Twoich grafikach),  
- pozwolić Agentowi AI korzystać z tego JSON-a jako **AST-u na poziomie projektu**: każde repo to kafelek, a każda zmiana w repo to potencjalna zmiana w mozaice.

To domyka klamrę: repozytoria stają się **mozaiką 9D**, a `Scan-9D.ps1` i `Update-QV9D.ps1` to **operatory Φ** na poziomie infrastruktury.

---

### Mosty (w szeregu, na dole)

Plan–Pauza Rdzeń–Peryferia Cisza–Wydech Wioska–Miasto Ostrze–Cierpliwość Locus–Medium–Mandat Human–AI‡ Próg–Przejście Semantyka–Energia
| 2025-11-22 21:59:19 | Scan-9D.ps1 | 1 | 1101 | AUTO-DOC | skan struktury repo |
| 2025-11-22 21:59:40 | Scan-9D.ps1 | 1 | 1101 | AUTO-DOC | skan struktury repo |
| 2025-11-22 22:21:58 | Scan-9D.ps1 | 1 | 1101 | AUTO-DOC | skan struktury repo |
