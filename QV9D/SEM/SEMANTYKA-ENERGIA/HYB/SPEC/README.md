# Semantyka–Energia – Budżet obliczeniowy (architektura hybrydowa)

W hybrydzie rejestr **Semantyka–Energia** rozdziela budżet między klasyczne moduły, mozaikę i ew. moduły zewnętrzne.  
`compute_budget` może być podzielony na `cpu_budget`, `gpu_budget` i `mozaic_budget`.  
`risk_tolerance` definiuje, ile eksperymentów adaptacyjnych (np. testów filtrów) można wykonać w jednej iteracji, a `priority_weights` mapuje się na rodzaje operacji (analiza, render, komunikacja).