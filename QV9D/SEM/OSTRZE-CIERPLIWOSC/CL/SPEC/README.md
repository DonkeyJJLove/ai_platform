# Ostrze–Cierpliwość – Agresja zmian (architektura klasyczna)

Rejestr **Ostrze–Cierpliwość** równoważy szybkość reakcji systemu (ostrze) i magazynowanie historii stanów (cierpliwość).  
Ostrze decyduje o tym, jak duży krok robimy w optymalizatorze (np. zmiana parametrów, odcięcie procesu), a cierpliwość – ile poprzednich stanów uwzględniamy przed reakcją, aby uniknąć histerycznych ruchów.  
Równowaga ta jest kluczowa dla stabilności systemu i jakości przewidywań.

### Pola konfiguracyjne

- `step_size` – wielkość kroku optymalizatora; większa wartość = szybsze, ale bardziej ryzykowne zmiany.  
- `memory` – liczba poprzednich stanów uwzględnianych przy podejmowaniu decyzji.  
- `hysteresis` – współczynnik tłumienia małych fluktuacji; im wyższy, tym system wolniej reaguje na drobne sygnały.