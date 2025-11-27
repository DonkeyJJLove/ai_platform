# Rdzeń–Peryferia – Priorytety obszarów (architektura klasyczna)

Rejestr **Rdzeń–Peryferia** odpowiada za podział matrycy Latarni na część rdzeniową – nośnik najważniejszego sensu – oraz część peryferyjną, która służy jako rama, kontekst i redundancja.  
Decyzja o wielkości rdzenia wpływa na gęstość informacyjną i możliwość wykrywania błędów (większa redundancja = mniejsza gęstość).  
W architekturze klasycznej parametry te sterują przydziałem zasobów CPU/GPU do obliczeń na rdzeniu i peryferiach.

### Pola konfiguracyjne

- `core_size` – procent komórek należących do rdzenia (0–1).  
- `periphery_size` – procent komórek należących do peryferii; zwykle `1 - core_size`.  
- `redundancy` – liczba kopii rdzenia utrzymywanych w pamięci do celów kontroli błędów.  
- `layout` – ewentualny kształt rdzenia (kwadratowy, okrągły, nieregularny).