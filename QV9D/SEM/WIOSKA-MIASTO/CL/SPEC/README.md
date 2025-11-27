# Wioska–Miasto – Skala społeczna (architektura klasyczna)

Rejestr **Wioska–Miasto** definiuje zasięg, w jakim Latarni steruje procesami.  
W trybie `local` latarnia dotyczy jednej wioski (np. jednego zespołu, jednego modułu); w trybie `global` wpływa na wiele miast – federację systemów lub całą sieć usług.  
Zmiana skali nie zmienia języka ani alfabetu, ale zmienia sposób agregacji wyników i priorytetów.

### Pola konfiguracyjne

- `scope` – `local` lub `global`; decyduje o zasięgu działania.  
- `aggregation` – metoda łączenia wyników (`mean`, `max`, `consensus`).  
- `fanout_limit` – maksymalna liczba odbiorników sygnału, do których latarnia rozgłasza zmiany.