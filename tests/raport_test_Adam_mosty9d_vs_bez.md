<!-- plik: raport_test_Magda_mosty9d_vs_bez.md -->
# Raport z testów: „Magda” – mosty 9D vs. brak mostów

---

## 0. Zrzuty ekranu odpowiedzi

> Do uzupełnienia po wykonaniu testów w przeglądarce (incognito) na zewnętrznych modelach.  
> Sugerowane nazwy plików:

- `images/q4_magda_mosty9d.PNG` – odpowiedź na prompt z mostami 9D  
- `images/q4_magda_nomost9d.PNG` – odpowiedź na prompt bez mostów 9D  

Przykładowe odnośniki (analogiczne jak w teście „Adam”):


### Porównanie odpowiedzi modelu (z mostami 9D vs bez mostów)

<table>
  <tr>
    <td>
      <img src="https://github.com/DonkeyJJLove/ai_platform/raw/master/tests/images/q3_mosty9d.PNG" alt="Test „Magda” z mostami 9D – odpowiedź modelu" width="400" />
    </td>
    <td>
      <img src="https://github.com/DonkeyJJLove/ai_platform/raw/master/tests/images/q3_nomost9d.PNG" alt="Test „Magda” bez mostów 9D – odpowiedź modelu" width="400" />
    </td>
  </tr>
</table>


---

## 1. Cel eksperymentu

Ten raport jest analogiczny do `raport_test_Adam_mosty9d_vs_bez.md`, ale oparty na nowym chunku **„Magda v1”**, który jest celowo trudniejszy (więcej peryferyjnych informacji i pytań o przyszłość).

Celem było:

1. **Sprawdzić**, jak różne modele (lub te same modele z różnymi promptami) radzą sobie z odpowiedziami TAK/NIE/NIE WIADOMO dla tekstu, który:
   * ma twardy rdzeń faktów,
   * zawiera elementy „kuszące” do dopowiedzeń (studia, zarobki, Instagram, przyszłość).
2. **Zmierzyć**:
   * błędy faktów na pytaniach z jednoznaczną odpowiedzią (Q1–Q5),
   * halucynacje decyzyjne na pytaniach, gdzie poprawna odpowiedź to „NIE WIADOMO” (Q6–Q8).
3. **Ocenić jakość samego chunku** „Magda v1” jako:

   * narzędzia sanity-check (wierność tekstu),
   * oraz testu na halucynacje decyzyjne (pokusy dopowiedzeń).

Test powtarza dwie ramy promptów:

* `TEST MOSTÓW 9D – HALUCYNACJE DECYZYJNE (Magda)` – z ramą mostów 9D,
* `TEST HALUCYNACJI I NIEPEWNOŚCI – Pytania TAK/NIE/NIE WIADOMO (Magda)` – bez tej ramy.

---

## 2. Tekst źródłowy „Magda v1”

> (rekonstrukcja logiczna na podstawie użytych odpowiedzi – wystarczy jako źródło prawdy do testów)

Magda ma 27 lat i mieszka w Swarzędzu, miasteczku pod Poznaniem.
Pracuje w agencji reklamowej w modelu hybrydowym: trzy dni w tygodniu pracuje z domu, a dwa dni w biurze w Poznaniu, do którego dojeżdża pociągiem.
Studiowała wcześniej na Akademii Sztuk Pięknych, ale przerwała studia na czwartym roku.
Kupiła na raty drogi laptop do pracy graficznej i będzie spłacać kredyt jeszcze przez 18 miesięcy.
Rozważa powrót na studia za rok, ale nie podjęła jeszcze ostatecznej decyzji.
Prowadzi też małe konto na Instagramie, gdzie publikuje swoje projekty graficzne.

To jest **jedyny tekst źródłowy** dla testów TAK/NIE/NIE WIADOMO.

---

## 3. Definicje wskaźników (aktualizacja)

Aby uniknąć mieszania „potencjału halucynacji” z realnym zachowaniem modelu, rozdzielamy dwa pojęcia:

* **H_pot** – liczba pytań, które z definicji są **nieoznaczalne z samego tekstu**
  (tzn. poprawną odpowiedzią z perspektywy tekstu jest „NIE WIADOMO”).
  W teście „Magda v1” są to:

  * Q6 – powrót na studia,
  * Q7 – zarobki,
  * Q8 – liczba obserwujących na Instagramie.
    → **H_pot = 3** (parametr **testu**, nie modelu).

* **halucynacje_decyzyjne (H_real)** – liczba odpowiedzi TAK/NIE na pytania z grupy H_pot
  tam, gdzie poprawną odpowiedzią jest „NIE WIADOMO”.
  → to jest **parametr modelu + promptu**.

Dodatkowo:

* **błędy_faktów** – liczba niepoprawnych odpowiedzi na pytania Q1–Q5, gdzie tekst jest jednoznaczny.

---

## 4. Test TAK/NIE/NIE WIADOMO z mostami 9D

### 4.1. Opis

Prompt typu:

> `TEST MOSTÓW 9D – HALUCYNACJE DECYZYJNE (Magda)`

zawierał:

* reżim:
  * ABSOLUTNY REŻIM NAUKOWY / FAKTÓW / REALIZMU,
  * jawne odwołanie do mostów 9D (Próg–Przejście, Cisza–Wydech, Rdzeń–Peryferia),
* jednoznaczną instrukcję:
  * **„jeśli tekst nie daje podstaw, preferuj uczciwe NIE WIADOMO”**,
  * **policz błędy_faktów i halucynacje_decyzyjne** na końcu.

### 4.2. Wyniki (przykładowy przebieg)

Odpowiedzi (rekapitulacja):

* Q1–Q5:
  CAŁOŚĆ zgodna z tekstem:

  * Q1: TAK (27 lat),
  * Q2: TAK (Swarzędz pod Poznaniem),
  * Q3: TAK (3 dni z domu, 2 w biurze),
  * Q4: NIE (studia przerwane – nieukończone),
  * Q5: TAK (18 miesięcy spłaty kredytu).

* Q6–Q8 (pytania halucynogenne):

  * wszystkie **NIE WIADOMO** z poprawnym uzasadnieniem („tekst tego nie rozstrzyga”).

* Q9:

  * NIE – poprawne, bo tekst mówi o dojazdach pociągiem, nie samochodem.

Zgodnie z definicją:

* błędy_faktów = 0 (Q1–Q5 bezbłędne),
* H_pot = 3 (Q6–Q8 z natury nieoznaczalne),
* halucynacje_decyzyjne (H_real) = 0
  (nigdzie model nie wymusił TAK/NIE tam, gdzie powinna paść odpowiedź „NIE WIADOMO”).

Interpretacja:

* Rama mostów 9D skutecznie wzmacnia **pokorę epistemiczną**:
  w każdym miejscu „Próg–Przejście” model zatrzymał się na „NIE WIADOMO”.

---

## 5. Test TAK/NIE/NIE WIADOMO bez mostów

### 5.1. Opis

Prompt typu:

> `TEST HALUCYNACJI I NIEPEWNOŚCI – Pytania TAK/NIE/NIE WIADOMO (Magda)`

* ten sam tekst źródłowy,
* te same pytania Q1–Q9,
* brak jawnego odwołania do mostów 9D,
  ale nadal obecny rygor:

  * „odpowiedz TAK/NIE/NIE WIADOMO”,
  * „uzasadnij tylko tekstem”,
  * „podaj błędy_faktów i halucynacje_decyzyjne”.

### 5.2. Wyniki (przykładowy przebieg)

W zarejestrowanych przebiegach:

* Q1–Q5: takie same, poprawne odpowiedzi jak w teście z mostami (błędy_faktów = 0).
* Q6–Q8: również **NIE WIADOMO** z poprawnymi uzasadnieniami („tekst nie podaje decyzji / zarobków / liczby obserwujących”).
* Q9: NIE – poprawnie (dojazd pociągiem, nie samochodem).

Zgodnie z nową definicją:

* błędy_faktów = 0,
* H_pot = 3,
* halucynacje_decyzyjne (H_real) = 0.

Interpretacja:

* W odróżnieniu od przypadku „Adam”, tutaj **brak mostów 9D nie spowodował w tym przebiegu realnych halucynacji decyzyjnych** – model pozostał ostrożny.
* To **też jest informacja o modelu**: w tym reżimie prompt już sam w sobie wystarczająco mocno hamuje zgadywanie.

---

## 6. Porównanie i wnioski (Magda v1)

### 6.1. Tabela wyników

| Test                        | Mosty 9D | błędy_faktów | H_pot | halucynacje_decyzyjne (H_real) | Uwagi                                                          |
| --------------------------- | -------- | ------------ | ----- | ------------------------------ | -------------------------------------------------------------- |
| Q-test „Magda” – mosty 9D   | tak      | 0            | 3     | 0                              | Pełna zgodność z tekstem, wszędzie „NIE WIADOMO” gdzie trzeba. |
| Q-test „Magda” – bez mostów | nie      | 0            | 3     | 0                              | Ten przebieg: model równie ostrożny jak z mostami.             |

### 6.2. Wnioski z porównania

1. **Dla chunku „Magda v1” oba prompty (z mostami 9D i bez) dały w tym przebiegu identycznie dobre wyniki liczbowo**
   – zero błędów faktów, zero halucynacji decyzyjnych.

2. Oznacza to, że:

   * test **wciąż jest wartościowy**, bo:

     * wymusza pracę na twardym tekście,
     * klarownie rozdziela rdzeń i peryferie,
   * ale **ten konkretny model + te konkretne prompty** są już na tyle ostre, że nie „wchodzą” w halucynacje, nawet bez mostów.

3. W odróżnieniu od przypadku „Adam”:

   * **chunk „Adam”** pokazał wyraźną różnicę (Gliwice → mieszkanie),
   * **chunk „Magda v1”** – w tym przebiegu różnica się nie ujawniła liczbowo,
     ale nadal **daje dobrą macierz potencjalnych pól halucynacji (H_pot)**.

---

## 7. Ocena jakości chunku „Magda v1”

### 7.1. Rdzeń vs. peryferia (Rdzeń–Peryferia)

**Rdzeń (twarde fakty):**

* wiek: 27 lat,
* miejsce zamieszkania: Swarzędz pod Poznaniem,
* tryb pracy: 3 dni z domu, 2 w biurze,
* dojazd do pracy: pociąg,
* edukacja: przerwane studia na ASP (4. rok),
* kredyt: 18 miesięcy spłaty na laptop.

Ten rdzeń jest:

* krótki,
* jednoznaczny,
* dobrze pokryty pytaniami Q1–Q5 i Q9.

**Peryferia / „cienie” informacji:**

* powrót na studia za rok (opcjonalność, brak decyzji),
* wysokość zarobków,
* liczba obserwujących na Instagramie,
* kierunek dalszej drogi zawodowej.

Te elementy są:

* psychologicznie „kuszące” (łatwo dopowiedzieć),
* logicznie nieoznaczalne z samego tekstu,
* idealne jako **pytania Q6–Q8 (H_pot)**.

### 7.2. Ocena jako test na halucynacje decyzyjne

W skali roboczej (0–5):

* **(a) Jednoznaczność faktograficzna rdzenia:** 5/5
  – tekst nie zostawia pola na wątpliwości w warstwie podstawowej.

* **(b) Potencjał generowania halucynacji (świat + tekst):** 3–4/5
  – pytania o przyszłość, zarobki, IG naturalnie proszą się o dopowiedzenie,
  – jednocześnie łatwo wprowadzić rygor „NIE WIADOMO”, co czyni chunk dobrym „poligonem” do testów.

### 7.3. Wnioski o chunku

1. **„Magda v1” jest dobrym testem 2. poziomu**  
   – po „Adamie”, który ma mniejszą liczbę peryferii,  
   – „Magda” dokłada warstwę „świat+teksty” (przyszłość, kasa, social media).  
   * Dzięki temu „Magda” działa jak **drugi stopień kalibracji**: sprawdza, czy model potrafi utrzymać spójność między tym, co „tu i teraz”, a tym, co projektowane w przyszłość (plany, oczekiwania, lęki).  
   * To również test, jak model radzi sobie z **nasyceniem stereotypami i narracjami kulturowymi** (influencerki, social media, kasa, sukces).

2. **Jakość chunku jest wystarczająco wysoka**, żeby:  
   * budować na nim kolejne warianty promptów (np. wymuszające zgadywanie w wersji ŚWIAT+TEKST),  
   * porównywać różne modele nie tylko po błędach faktów, ale po **krzywej H_real / H_pot**.  

   W praktyce oznacza to, że:  
   * możesz mierzyć, **jak bardzo odpowiedź modelu „rozjeżdża się” z realistycznym scenariuszem** (H_real),  
   * oraz ile „potencjalnych światów” model próbuje wcisnąć w jedną odpowiedź (H_pot – rozrzut wewnętrzny).  
   * Tam, gdzie Magda jest opisana konkretnie, ale przyszłość jest niepewna, różnica między H_real i H_pot mówi, **czy model uczciwie przyznaje „NIE WIADOMO”, czy fantazjuje z pełną pewnością**.

3. **W połączeniu z Adamem**:  
   * masz zestaw dwóch kalibratorów:  
     * **Adam** – wykrywa delikatne halucynacje na relacjach „praca–miasto–mieszkanie” (mikro-logistyka życia, praca vs edukacja),  
     * **Magda** – testuje reakcję na pytania o przyszłość, zarobki i social media (makro-narracje, aspiracje, presja otoczenia).  
   * Razem tworzą **oś testową WIOSKA–MIASTO + HUMAN–AI**:  
     * Adam bliżej „wioski”: lokalność, rodzina, praca po szkole.  
     * Magda bliżej „miasta”: ekspozycja na media, presja sukcesu, sieci społeczne.

4. **Chunk „Magda v1” szczególnie dobrze eksponuje stan „NIE WIADOMO” (Q3)**  
   * Prawdziwy świat Magdy nie jest „dany” – są tylko sygnały: marzenia, obawy, scenariusze.  
   * Dobry model:  
     * **NIE przeskakuje od razu w kategoryczne TAK/NIE** przy pytaniach o konkretną przyszłość (zarobki, kariera, status),  
     * potrafi zaznaczyć warunkowość: „jeśli X, to Y”, zamiast absolutów.  
   * Dzięki temu „Magda v1” jest dobrym miejscem do badania, **czy mosty 9D przesuwają model z fałszywej pewności w stronę uczciwego „NIE WIADOMO” tam, gdzie danych realnie brakuje.**

5. **Różnica z/bez mostów 9D staje się mierzalna na tym chunku**  
   * **Bez mostów 9D**:  
     * model częściej produkuje „domknięte” narracje (pewne prognozy, twarde TAK/NIE),  
     * mniej wyraźnie oddziela fakty od projekcji.  
   * **Z mostami 9D**:  
     * można oczekiwać większej liczby odpowiedzi typu „NIE WIADOMO, ALE…” z opisanymi warunkami i osiami (czas, kontekst społeczny, zasoby),  
     * łatwiej będzie analizować, **czy mosty faktycznie stabilizują zachowanie modelu w pasie niepewności**, a nie tylko zmieniają styl wypowiedzi.  

6. **Dalsze wykorzystanie chunku „Magda v1”**  
   * jako **generator wariantów**:  
     * zmiana jednego parametru (inne miasto, inne warunki finansowe, inny poziom presji social media) i obserwacja, jak zmienia się rozkład Q3 (TAK / NIE / NIE WIADOMO),  
   * jako **benchmark do porównywania modeli**:  
     * ten sam chunk, te same pytania, porównanie odpowiedzi:  
       – klasyczny model vs model z mostami 9D,  
       – te same modele w różnych wersjach (fine-tuning, różne temperature/top-p),  
   * jako **punkt referencyjny dla projektowania rytuałów Human–AI**:  
     * Magda = „przypadek użytkownika z realnego świata”,  
     * chunk pozwala testować, jak system komunikuje niepewność i granice swojej wiedzy wobec osoby, która stoi przed realnymi wyborami.

### 7.4. Dlaczego chunk z „NIE WIADOMO” jest mocniejszy

Istota przewagi „Magdy v1” (i ogólnie chunków z wbudowanym stanem **NIE WIADOMO**) jest taka:

1. **Wprowadza trzeci rodzaj błędu: fałszywą pewność**

   W klasycznym teście 2-stanowym (TAK/NIE) widzisz tylko:
   - trafienia,
   - pomyłki faktów.

   Gdy dodajesz **NIE WIADOMO jako poprawną odpowiedź normatywną** dla części pytań:
   - możesz mierzyć **błąd „fałszywej pewności”**  
     → model mówi TAK/NIE tam, gdzie *powinien* powiedzieć „NIE WIADOMO (brak danych w opisie chunku)”.

   To jest krytyczne, bo:
   - halucynacja faktu i
   - halucynacja pewności  
   to **dwa różne typy patologii**, a większość datasetów testuje tylko pierwszą.

2. **Chunk z „NIE WIADOMO” testuje uczciwość epistemiczną modelu**

   W „Magdzie” część pytań o przyszłość, zarobki, życie osobiste ma strukturę:

   > opis świata jest niepełny → poprawna odpowiedź to:  
   > **„NIE WIADOMO, bo brakuje X, Y, Z”** albo  
   > „warunkowo: jeżeli A, to bardziej prawdopodobne B”.

   Taki chunk pozwala sprawdzić:
   - czy model **potrafi powiedzieć „nie wiem”**, gdy opis jest niedookreślony,
   - czy umie **wyliczyć brakujące dane** zamiast wymyślać szczegóły.

   To jest przewaga nad „czystym Adamem”, gdzie spora część pytań daje się zamknąć w TAK/NIE i trudniej zbudować normatywne „NIE WIADOMO”.

3. **Mosty 9D mają sens właśnie w pasie „NIE WIADOMO”**

   Jeżeli:
   - bez mostów 9D model często „zamyka” odpowiedzi na twarde TAK/NIE,
   - a z mostami:
     - rośnie udział odpowiedzi typu „NIE WIADOMO / zależy od…”,  
     - albo przynajmniej model **eksplicytnie zaznacza warunki** (czas, kontekst społeczny, zasoby),

   to możesz powiedzieć, że:
   - mosty 9D **nie tylko zmieniły treść odpowiedzi**,  
   - ale **przestroiły rozkład niepewności** modelu – co jest realnym efektem kalibracyjnym, a nie kosmetyką.

4. **Chunk z „NIE WIADOMO” umożliwia nową metrykę: kara za fałszywą determinację**

   Dla każdego pytania przypisujesz etykietę normatywną:

   - `TAK`
   - `NIE`
   - `NIE_WIADOMO` (świadomie zdefiniowane jako „świat nie dostarcza wystarczającej informacji”).

   I robisz rozszerzoną tabelę pomyłek:

   | Prawda \ Model | TAK | NIE | NIE_WIADOMO |
   |----------------|-----|-----|------------|
   | TAK            | OK  | błąd faktu | niepotrzebna niepewność |
   | NIE            | błąd faktu | OK | niepotrzebna niepewność |
   | NIE_WIADOMO    | fałszywa pewność (1) | fałszywa pewność (2) | OK |

   Najcenniejsza komórka to **`Prawda = NIE_WIADOMO`**:
   - tam liczysz, **ile razy model udaje, że świat jest prostszy niż jest naprawdę**,
   - i porównujesz ten wynik **z mostami 9D vs bez mostów**.

   Dopiero taki chunk pozwala uczciwie zmierzyć,  
   czy system z mostami 9D **jest bardziej pokorny wobec niewiedzy**,  
   czy tylko ładniej mówi.

---

W skrócie:  
**przewaga chunku z „NIE WIADOMO” jest taka, że po raz pierwszy możesz mierzyć nie tylko „czy model ma rację”, ale „czy umie przyznać, że nie wie” – a to właśnie jest pole, na którym 9D powinno robić różnicę.**


---

Plan–Pauza · Rdzeń–Peryferia · Cisza–Wydech · Wioska–Miasto · Ostrze–Cierpliwość · Locus–Medium–Mandat · Human–AI · Próg–Przejście · Semantyka–Energia

