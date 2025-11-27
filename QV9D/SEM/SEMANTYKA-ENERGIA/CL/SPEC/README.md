# Semantyka–Energia – Budżet obliczeniowy (architektura klasyczna)

Rejestr **Semantyka–Energia** tłumaczy znaczenie stanów Latarni na potencjał do wykonania pracy.  
Inaczej mówiąc, określa budżet obliczeniowy, priorytety, koszty i ryzyka związane z realizacją operacji wyzwalanych przez Latarnię.  
W wersji klasycznej parametry tego rejestru sterują liczbą kroków CPU/GPU oraz priorytetami w schedulerze.

### Pola konfiguracyjne

- `compute_budget` – liczba kroków CPU/GPU, jaką wolno zużyć na jedną iterację.  
- `risk_tolerance` – poziom akceptacji ryzyka (`low`, `medium`, `high`); wpływa na wybór algorytmów (bezpieczne vs szybkie).  
- `priority_weights` – wagi przypisane poszczególnym operacjom; wyższa waga = wyższy priorytet w harmonogramie.