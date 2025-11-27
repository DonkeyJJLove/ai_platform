# Semantyka–Energia – Budżet obliczeniowy (architektura kwantowa)

W architekturze kwantowej rejestr **Semantyka–Energia** łączy budżet klasyczny z parametrami obwodu kwantowego.  
Oprócz `compute_budget` (kroki CPU/GPU) definiuje się dodatkowe pola:

- `qpu_qubits` – maksymalna liczba kubitów używanych w obwodzie.  
- `qpu_depth` – maksymalna głębokość obwodu (liczba warstw bram).  
- `error_tolerance` – dopuszczalny poziom błędu (np. 1e-2).

Parametr `risk_tolerance` przekłada się na dopuszczalną liczbę prób na QPU i wybór algorytmów (VQE, QAOA, itp.).