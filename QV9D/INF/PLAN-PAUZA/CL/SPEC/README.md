# Plan–Pauza – Planowanie vs wykonanie (architektura klasyczna)

Rejestr **Plan–Pauza‡** reguluje stosunek czasu przeznaczonego na planowanie do czasu przeznaczonego na wykonanie.  
W warstwie Informacja–Nośnik zmienia geometrię nośnika – większe okno planowania wymaga większej pojemności, mniejsze ułatwia szybką reakcję.  
W warstwie Semantyka–Ruch określa liczbę iteracji symulacji w AST/Mozaice przed podjęciem decyzji.  
W warstwie Mandat–Czas–Relacja wskazuje, czy zmiana proporcji wymaga akceptacji człowieka.

### Pola konfiguracyjne

- `plan_ratio` – udział czasu poświęcanego na planowanie (0–1).  
- `exec_ratio` – udział czasu na wykonanie; zazwyczaj `1 - plan_ratio`.  
- `window` – długość okna planowania w milisekundach lub cyklach.  

W architekturach hybrydowych `plan_ratio` może sterować liczbą iteracji QPU; w architekturze kwantowej dodatkowo ogranicza głębokość obwodu.