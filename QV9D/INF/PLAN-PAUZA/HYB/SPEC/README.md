# Plan–Pauza – Planowanie vs wykonanie (architektura hybrydowa)

W wersji hybrydowej rejestr Plan–Pauza określa, jak dzielić czas między symulację w AST/Mozaice a uruchomienia zewnętrznych komponentów (np. interpretacji obrazu, integracji).  
`plan_ratio` wskazuje, ile iteracji planera hybrydowego wykonujemy, zanim skierujemy ruch do modułu wykonawczego.  
`window` ogranicza liczbę kafelków mozaiki analizowanych w jednym przebiegu.  
Zmiana tych parametrów wymaga odświeżenia konfiguracji w katalogu `MAND/PLAN-PAUZA`.