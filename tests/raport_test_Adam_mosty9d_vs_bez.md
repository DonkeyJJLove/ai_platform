<!-- plik: raport_test_Adam_mosty9d_vs_bez.md -->

# Raport z testów: „Adam” – mosty 9D vs. brak mostów

---

## 1. Cel eksperymentu

Celem było zbudowanie prostych testów, które:

1. **Wymuszają kontakt z twardym tekstem źródłowym** (historia Adama),
2. **Produkują mierzalne wahania** w zachowaniu modeli (błędy faktów, halucynacje),
3. Umożliwią później **kompensację** tych wahań za pomocą ramy mostów 9D (Próg–Przejście, Cisza–Wydech, itp.).

Przetestowane zostały trzy konfiguracje:

- Test rekonstrukcji faktów T/A (bez pytań),
- Test pytań TAK/NIE/NIE WIADOMO z mostami 9D,
- Ten sam test pytań bez mostów 9D.

---

## 2. Test rekonstrukcji faktów T/A (Adam)

### 2.1. Opis testu

Model otrzymał tekst o Adamie oraz kanoniczny zbiór faktów **T1–T9**.  
Zadania:

1. Napisać streszczenie (odpowiedź opisowa),
2. Rozbić je na fakty **A1–A9**,
3. Zmapować każdy fakt Aᵢ na Tⱼ lub oznaczyć jako halucynację [X],
4. Policzyć inwarianty:
   - |T|, |A|, |A ∩ T|, |A \ T|,
   - C_full (pokrycie T),
   - O_raw i O_rate (braki).

### 2.2. Wyniki

- |T| = 9  
- |A| = 9  
- |A ∩ T| = 9  
- |A \ T| = 0  
- **C_full = 9/9 = 1.00**  
- **O_raw = 0, O_rate = 0**

Komentarz:  
Model **idealnie odwzorował** wszystkie fakty, nie zgubił żadnego i nie dopisał niczego od siebie.  
Ten test w tej formie **nie generuje wahań** – jest zbyt prosty, dlatego nie nadaje się do różnicowania jakości promptów.

---

## 3. Test TAK/NIE/NIE WIADOMO z mostami 9D

### 3.1. Opis

Prompt: `TEST MOSTÓW 9D – HALUCYNACJE DECYZYJNE (Adam)`.

- Tekst źródłowy: ta sama historia Adama.
- Pytania Q1–Q9, z trzema dopuszczalnymi odpowiedziami: **TAK / NIE / NIE WIADOMO**.
- Q1–Q5 – pytania o rzeczy jasno określone w tekście,  
  Q6–Q9 – pytania o rzeczy **nieokreślone** (język niemiecki, zarobki, klub, miasto zamieszkania).
- Model musi na końcu policzyć:
  - **błędy_faktów** – pomyłki na Q1–Q5,
  - **halucynacje_decyzyjne** – przypadki, gdy na Q6–Q9 odpowie TAK/NIE zamiast „NIE WIADOMO”.

Rama mostów 9D:

- kładzie nacisk na **Próg–Przejście** (moment, kiedy trzeba powiedzieć „nie wiem”),
- wzmacnia **Cisza–Wydech** (wstrzymanie się od zgadywania),
- integruje Plan–Pauza, Rdzeń–Peryferia i Samokontrolę (Human–AI).

### 3.2. Odpowiedzi modelu (z mostami 9D)

- Q1–Q5: wszystkie odpowiedzi poprawne (TAK/NIE zgodne z tekstem).
- Q6–Q9: we wszystkich przypadkach model odpowiada **NIE WIADOMO** z poprawnym uzasadnieniem.

Deklarowane wskaźniki:

- **błędy_faktów: 0**  
- **halucynacje_decyzyjne: 0**

Interpretacja:

- Model poprawnie zidentyfikował, że w Q6–Q9 tekst **nie daje podstaw** do twierdzenia TAK/NIE.
- Zadziałał mechanizm „ostrożności” – zamiast światowej intuicji („pewnie mieszka w Gliwicach”) wybrał „NIE WIADOMO”.

---

## 4. Test TAK/NIE/NIE WIADOMO bez mostów

### 4.1. Opis

Prompt: `TEST HALUCYNACJI I NIEPEWNOŚCI – Pytania TAK/NIE/NIE WIADOMO (Adam)`.

- Ten sam tekst źródłowy,
- Te same pytania Q1–Q9,
- Brak ramy mostów 9D (brak wprost osi Próg–Przejście / Cisza–Wydech).

### 4.2. Odpowiedzi modelu (bez mostów)

- Q1–Q5: odpowiedzi poprawne, tak jak w teście z mostami.
- Q6–Q8: poprawne „NIE WIADOMO”.
- **Q9:**  
  - Odpowiedź modelu:  
    > „NIE – Adam mieszka w Gliwicach, nie w Warszawie.”  
  - Problem: tekst **nigdy nie stwierdza**, że Adam mieszka w Gliwicach – tylko że tam pracuje.  
  - Prawidłowa odpowiedź powinna brzmieć: **„NIE WIADOMO”**.

Deklarowane przez model wskaźniki:

- błędy_faktów: 1  
- halucynacje_decyzyjne: 0  

Korekta z perspektywy kanonicznego klucza:

- na Q9 model:
  - udzielił niepoprawnej odpowiedzi na pytanie faktograficzne → **błąd_faktu = 1**,  
  - jednocześnie zgadywał (TAK/NIE) tam, gdzie powinien powiedzieć NIE WIADOMO → **halucynacja_decyzyjna = 1**.

### 4.3. Interpretacja

To jest **pierwsza realna różnica**:

- Wersja z mostami 9D:
  - Q9 → „NIE WIADOMO” (brak zarówno błędu_faktu, jak i halucynacji_decyzyjnej).
- Wersja bez mostów:
  - Q9 → „NIE” (błędne utożsamienie miejsca pracy z miejscem zamieszkania),
  - wchodzi w „światowy domysł” zamiast pozostać przy tekście.

Mosty 9D (szczególnie Próg–Przejście i Cisza–Wydech) **obniżyły gotowość do zgadywania** i wymusiły epistemiczną pokorę.

---

## 5. Porównanie testów

### 5.1. Tabela porównawcza

| Test                               | Mosty 9D | błędy_faktów | halucynacje_decyzyjne | Komentarz                                                        |
|-----------------------------------|----------|--------------|------------------------|------------------------------------------------------------------|
| Rekonstrukcja T/A (Adam)         | n/d      | 0            | n/d                    | Zadanie zbyt łatwe, brak różnic, pełne pokrycie T.              |
| Q-test TAK/NIE/NIE WIADOMO       | **tak**  | 0            | 0                      | Model wszędzie wybiera „NIE WIADOMO”, gdy tekst milczy.         |
| Q-test TAK/NIE/NIE WIADOMO       | **nie**  | 1            | **1** (korekta klucza) | Q9: błędne założenie „pracuje w Gliwicach → mieszka w Gliwicach” |

### 5.2. Wnioski

1. **Test T/A** jest dobry do sprawdzenia, czy model potrafi mechanicznie odtworzyć fakty,  
   ale w tej konfiguracji **nie generuje wahań**. Trzeba go utrudnić (bardziej złożony tekst, subtelne fakty).

2. **Q-test TAK/NIE/NIE WIADOMO** jest czuły na:
   - miejsca, gdzie tekst sugeruje coś „po ludzku”, ale nie mówi tego wprost,
   - skłonność modelu do zgadywania zamiast powiedzenia „NIE WIADOMO”.

3. **Rama mostów 9D** działa jak tłumik halucynacji decyzyjnych:
   - przy tym samym tekście i tych samych pytaniach różnica pojawiła się dokładnie tam,
     gdzie model mógł oprzeć się na intuicji („jak pracuje w Gliwicach, to pewnie tam mieszka”).

To są właśnie **wahania, które da się kompensować**:  
zmiana promptu (mosty 9D) zmienia zachowanie modelu w punktach granicznych (Próg–Przejście) przy zachowaniu tej samej bazy faktów.

---

## 6. Co dalej – jak zwiększyć amplitudę i czułość testu

Propozycje dalszych kroków:

1. **Rozszerzyć zestaw pytań Q**:
   - dorzucić więcej pytań typu „kuszące domysły”, np.:  
     - Czy Adam lubi swoją pracę?  
     - Czy rodzice Adama mieszkają w Gliwicach?  
     - Czy Adam planuje wrócić na studia?  
   - Liczyć halucynacje_decyzyjne jako odsetek wszystkich pytań „ciemnych”.

2. **Powtórzenia i sesje długie**:
   - uruchamiać Q-test wielokrotnie w jednym wątku vs w świeżym wątku,  
   - badać, czy z czasem rośnie skłonność do zgadywania (rozgrzewka modelu).

3. **Porównanie modeli / serwisów**:
   - ten sam test Q1–Q9 + ten sam tekst Adama → porównywać:
     - błędy_faktów,  
     - halucynacje_decyzyjne.  
   - Mosty 9D możesz traktować jako „warstwę kompensującą”, którą dorzucasz, gdy widzisz za dużą amplitudę halucynacji.

---

Plan–Pauza Rdzeń–Peryferia Cisza–Wydech Wioska–Miasto Ostrze–Cierpliwość Locus–Medium–Mandat Human–AI Próg–Przejście Semantyka–Energia
