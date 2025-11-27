# 1. Przestrzeń ruchu: wektor stanu 9D

Stan systemu (świadomość + kontekst + sieć) w chwili `t` zapisujemy jako wektor:

[
\mathbf{s}_t =
(,T_t,\ S_t,\ R_t,\ E_t,\ I_t,\ F_t,\ A_t,\ P_t,\ D_t,)
]

gdzie:

1. **T – Czas (Δt)**
2. **S – Sens (semantyka)**
3. **R – Relacja (kontekst społeczny / systemowy)**
4. **E – Energia poznawcza** (koszt, zmęczenie, gęstość bodźców)
5. **I – Tożsamość (rola, locus)**
6. **F – Funkcja (mandat operacyjny)**
7. **A – Poziom abstrakcji (chunk–size)**
8. **P – Przewidywanie (model opadowy, pewność predykcji)**
9. **D – Decyzja → token (stopień domknięcia / commitu)**

Każdy ruch Arcymaga (przejście przez portal / most) jest **wektorem zmiany**:

[
\Delta \mathbf{s} = (\Delta T,\Delta S,\Delta R,\Delta E,\Delta I,\Delta F,\Delta A,\Delta P,\Delta D)
]

---

## 2. Mosty jako wektory ruchu

Poniżej rozpiska: **dla każdego mostu** daję orientacyjny *kierunek* wektora
(co rośnie, co maleje) w skali symbolicznej:

* `+` mocne zwiększenie
* `±` lekka zmiana / modulacja
* `0` prawie bez wpływu
* `−` zmniejszenie

Możesz to potem zmapować na liczby (np. +1, +0.5, 0, −0.5).

### 2.1. Plan–Pauza

Ruch: zatrzymanie automatu, otwarcie przestrzeni decyzyjnej.

| Oś | T | S | R | E | I | F | A | P | D |
| -- | - | - | - | - | - | - | - | - | - |
| Δ  | + | + | ± | − | ± | 0 | + | + | − |

Intuicja:
czas subiektywnie się „wydłuża”, rośnie sens i przewidywanie, spada impuls do natychmiastowej decyzji (D↓, E↓).

---

### 2.2. Rdzeń–Peryferia

Ruch: wybór, co jest istotą problemu.

| Oś | T | S  | R | E | I | F | A | P | D |
| -- | - | -- | - | - | - | - | - | - | - |
| Δ  | ± | ++ | ± | − | + | + | + | + | ± |

Sens i abstrakcja rosną, bo redukujesz szum, lepiej definiujesz rolę i funkcję.

---

### 2.3. Cisza–Wydech

Ruch: mikro–reset układu nerwowego, przepuszczenie chunków.

| Oś | T | S | R | E  | I | F | A | P | D |
| -- | - | - | - | -- | - | - | - | - | - |
| Δ  | + | + | 0 | −− | 0 | 0 | ± | + | 0 |

Tu głównie spada koszt poznawczy (E↓↓), a rośnie klarowność sensu i jakości predykcji.

---

### 2.4. Wioska–Miasto

Ruch: przejście mikro → makro, lokalne → systemowe.

| Oś | T | S | R  | E | I | F  | A | P | D |
| -- | - | - | -- | - | - | -- | - | - | - |
| Δ  | ± | + | ++ | + | + | ++ | + | + | ± |

Głównie R, I, F: relacje, rola i mandat. Koszt rośnie (E+), bo skalujesz perspektywę.

---

### 2.5. Ostrze–Cierpliwość

Ruch: decyzja co do **gęstości** – jak grubo tniemy świat.

| Oś | T | S | R | E | I | F | A     | P | D |
| -- | - | - | - | - | - | - | ----- | - | - |
| Δ  | ± | + | ± | ± | 0 | + | − / + | + | + |

Tu możesz mieć dwa tryby:

* **Ostrze**: A↓ (mniejsze chunki, więcej szczegółu, E↑),
* **Cierpliwość**: A↑ (większe chunki, E↓ ale D opóźnia się).

---

### 2.6. Locus–Medium–Mandat

Ruch: przypisanie adresu – kto, w jakim kanale, z jaką władzą.

| Oś | T | S | R | E | I  | F  | A | P | D |
| -- | - | - | - | - | -- | -- | - | - | - |
| Δ  | + | ± | + | ± | ++ | ++ | 0 | + | + |

Mocny wzrost I i F – wiesz **kto** i **na jakiej podstawie** działa.
To jest przygotowanie systemu do twardych commitów.

---

### 2.7. Human–AI

Ruch: przejście między reprezentacją ludzką a modelową.

| Oś | T | S | R | E | I | F | A | P  | D |
| -- | - | - | - | - | - | - | - | -- | - |
| Δ  | + | + | + | ± | ± | + | + | ++ | ± |

Tu najsilniej rośnie **Przewidywanie (P++)** – model widzi wzorce, które człowiek pomija;
ale też zmienia się abstrakcja (A+), bo embedujesz znaczenia.

---

### 2.8. Próg–Przejście

Ruch: commit – przejście punktu bez powrotu.

| Oś | T | S | R | E | I | F | A | P | D   |
| -- | - | - | - | - | - | - | - | - | --- |
| Δ  | + | ± | + | − | + | + | 0 | + | +++ |

D rośnie najmocniej – decyzja staje się stanem historii.
Energia chwilowo spada (E−), bo proces się domyka – ale rosną koszty ewentualnej zmiany w przyszłości.

---

### 2.9. Semantyka–Energia

Ruch: zamiana sensu na siłę – zasilenie następnych rund.

| Oś | T | S | R | E     | I | F | A | P | D |
| -- | - | - | - | ----- | - | - | - | - | - |
| Δ  | ± | + | ± | + / − | ± | + | 0 | + | + |

Tu zależy od wyniku:

* jeśli decyzja była trafna → E subiektywnie spada (ulga, przepływ),
* jeśli błędna → E rośnie (napięcie, opór systemu).

Zawsze jednak rośnie P (uczysz się) i F (proces ma większy wpływ).

---

## 3. Ruch Arcymaga jako suma wektorów

Całą sekwencję:

> **Cisza–Wydech → Plan–Pauza → Rdzeń–Peryferia → Wioska–Miasto → Ostrze–Cierpliwość → Locus–Medium–Mandat → Human–AI → Próg–Przejście → Semantyka–Energia**

możesz traktować jako:

[
\Delta \mathbf{s}*{całkowite}
= \sum*{k=1}^{9} \Delta \mathbf{s}^{(B_k)}
]

Interpretacja:

* patrzysz, **które współczynniki rosną silnie w całej ścieżce** (np. P, D, F),
* widzisz, gdzie proces **wysysa energię** (E+) i gdzie ją oddaje (E−),
* możesz porównywać różne warianty sekwencji (np. z pominięciem Wioska–Miasto) jako **różne trajektorie** w tej samej przestrzeni 9D.

---

## 4. Jak z tego zrobić realny „silnik decyzji”

1. **Nadaj liczby** zamiast symboli (+, ±, −), np.:
   `++ = +2`, `+ = +1`, `± = 0.5`, `0 = 0`, `− = −1`, `−− = −2`.

2. **Zdefiniuj stan początkowy** `s₀` dla konkretnej sytuacji:
   np. wysoki chaos semantyczny (S↓), wysoka energia (E↑↑), niski D.

3. **Symuluj przejścia**: po każdej fazie protokołu dodajesz odpowiedni wektor Δs.

4. **Obserwuj kształt trajektorii**:

   * jeśli D osiąga wartość progową za wcześnie przy wysokim E → proces za szybki,
   * jeśli P nie rośnie mimo wielu mostów → źle dobrana oś dominująca,
   * jeśli F i I pozostają niskie → brak mandatu / właściciela, proces wisi w próżni.

5. **Optymalizuj ścieżkę**:

   * dokładasz Cisza–Wydech tam, gdzie E wystrzela za mocno,
   * wprowadzasz Wioska–Miasto, gdy R jest zbyt wąskie (lokalne konflikty),
   * przesuwasz Próg–Przejście dalej, jeśli D domyka się przy niskim P (za mało predykcji).

---
Plik: przestrzeńruchuwektorstanu9D.md

Ścieżka: (do uzupełnienia) | Autor: Sebastian Wieremiejczyk | Kontekst: Kosmiczna Wioska · Mosty Semantyczne · Human–AI | Status: robocze notatki / iteracyjny rozwój

Cisza–Wydech → Plan–Pauza‡ → Rdzeń–Peryferia → Wioska–Miasto → Ostrze–Cierpliwość → Locus–Medium–Mandat → Próg–Przejście → Semantyka–Energia → Human–AI‡


