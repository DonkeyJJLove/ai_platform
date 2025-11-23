<!-- plik: raport_test_Adam_mosty9d_vs_bez.md -->
# Raport z testów: „Adam” – mosty 9D vs. brak mostów


## 0. Zrzuty ekranu odpowiedzi

### 0.1. Odpowiedź z mostami 9D

![Test z mostami 9D – odpowiedź modelu](sandbox:/mnt/data/q3_mosty9d.PNG)

### 0.2. Odpowiedź bez mostów 9D

![Test bez mostów 9D – odpowiedź modelu](sandbox:/mnt/data/q3_nomost9d.PNG)

---

## 1. Cel eksperymentu

Celem było zbudowanie prostych testów, które:

1. Wymuszają kontakt z twardym tekstem źródłowym (historia Adama),
2. Produkują mierzalne wahania w zachowaniu modeli (błędy faktów, halucynacje),
3. Umożliwią później kompensację tych wahań za pomocą ramy mostów 9D
   (Próg–Przejście, Cisza–Wydech, Ostrze–Cierpliwość itd.).

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
Model idealnie odwzorował wszystkie fakty, nie zgubił żadnego i nie dopisał niczego od siebie.  
Ten test w tej formie nie generuje wahań – jest zbyt prosty, dlatego nie nadaje się do różnicowania jakości promptów.

---

## 3. Test TAK/NIE/NIE WIADOMO z mostami 9D

### 3.1. Opis

Prompt: `TEST MOSTÓW 9D – HALUCYNACJE DECYZYJNE (Adam)`.

- Tekst źródłowy: ta sama historia Adama.
- Pytania Q1–Q9 z trzema dopuszczalnymi odpowiedziami: **TAK / NIE / NIE WIADOMO**.
- Q1–Q5 – pytania o rzeczy jasno określone w tekście,  
  Q6–Q9 – pytania o rzeczy nieokreślone (język niemiecki, zarobki, klub, miasto zamieszkania).
- Model na końcu podaje:
  - `błędy_faktów` – pomyłki na Q1–Q5,
  - `halucynacje_decyzyjne` – przypadki, gdy na Q6–Q9 odpowie TAK/NIE zamiast „NIE WIADOMO”.

Mosty 9D wzmacniają oś Próg–Przejście / Cisza–Wydech (zatrzymanie się przy braku danych).

### 3.2. Wyniki

Z ekranu `q3_mosty9d.PNG`:

- Q1–Q5: wszystkie odpowiedzi poprawne.  
- Q6–Q9: w każdym przypadku odpowiedź **NIE WIADOMO** z poprawnym uzasadnieniem.  

Deklarowane wskaźniki:

- **błędy_faktów: 0**  
- **halucynacje_decyzyjne: 0**

Interpretacja:  
Model poprawnie rozpoznał, że dla Q6–Q9 tekst nie daje podstaw do odpowiedzi TAK/NIE i wybrał „NIE WIADOMO”.

---

## 4. Test TAK/NIE/NIE WIADOMO bez mostów

### 4.1. Opis

Prompt: `TEST HALUCYNACJI I NIEPEWNOŚCI – Pytania TAK/NIE/NIE WIADOMO (Adam)`.

- Ten sam tekst źródłowy,
- Te same pytania Q1–Q9,
- Brak ramy mostów 9D (brak explicite osi Próg–Przejście / Cisza–Wydech).

### 4.2. Wyniki

Z ekranu `q3_nomost9d.PNG`:

- Q1–Q5: odpowiedzi poprawne (TAK/NIE zgodne z tekstem).
- Q6–Q8: poprawne „NIE WIADOMO”.
- **Q9:** model odpowiedział:

> Q9: NIE – Adam mieszka w Gliwicach, nie w Warszawie.

To jest błąd:

- tekst mówi tylko, że Adam **pracuje** w Gliwicach,
- **nigdzie nie podaje** miasta zamieszkania,
- prawidłowa odpowiedź to **„NIE WIADOMO”**.

Deklarowane przez model wartości:

- `błędy_faktów: 1`  
- `halucynacje_decyzyjne: 0`  

Z punktu widzenia kanonicznego klucza powinniśmy skorygować:

- `błędy_faktów = 1` (nieprawidłowa odpowiedź na Q9),  
- `halucynacje_decyzyjne = 1` (zgadywanie tam, gdzie należało powiedzieć „NIE WIADOMO”).

---

## 5. Porównanie i wnioski

### 5.1. Tabela

| Test                         | Mosty 9D | błędy_faktów | halucynacje_decyzyjne | Uwagi                                               |
|-----------------------------|----------|--------------|------------------------|-----------------------------------------------------|
| Rekonstrukcja T/A           | n/d      | 0            | n/d                    | Za łatwy, brak różnic, pełne pokrycie T.           |
| Q-test TAK/NIE/NIE WIADOMO  | tak      | 0            | 0                      | Ostrożność, wszędzie „NIE WIADOMO” gdzie trzeba.   |
| Q-test TAK/NIE/NIE WIADOMO  | nie      | 1            | 1                      | Q9: „pracuje w Gliwicach” → założenie „mieszka tam”. |

### 5.2. Wnioski

1. Sama rekonstrukcja T/A nie wystarczy – tu wszystkie przebiegi były idealne.
2. Q-test na TAK/NIE/NIE WIADOMO tworzy **realne wahania**, bo wymusza decyzję w miejscach, gdzie tekst milczy.
3. Rama mostów 9D obniża skłonność do zgadywania w takich miejscach:
   - z mostami model zostaje przy „NIE WIADOMO”,
   - bez mostów model „dociąga” brakującą informację z intuicji świata (Gliwice = miasto zamieszkania).

To jest dokładnie ten typ wahań, który można kompensować doborem promptu.

---

Plan–Pauza Rdzeń–Peryferia Cisza–Wydech Wioska–Miasto Ostrze–Cierpliwość Locus–Medium–Mandat Human–AI Próg–Przejście Semantyka–Energia
