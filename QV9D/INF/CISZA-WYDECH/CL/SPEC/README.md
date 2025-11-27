# Cisza–Wydech – Rejestr resetu (architektura klasyczna)

Cisza–Wydech steruje rytmem „oddechu” systemu.  
Parametr ten określa, jak często agent wykonuje pełny reset – czyszczenie cache, ponowną ewaluację, odszumienie wejścia i odrzucenie zbyt małych fluktuacji.  
W warstwie **Informacja–Nośnik** Cisza–Wydech definiuje, które bity i znaki w ogóle dopuszczamy do Latarni, aby utrzymać wysoką gęstość informacji.  
W warstwie **Semantyka–Ruch** określa częstotliwość re-evaluacji priorytetów i kosztów, aby nie reagować histerycznie na pojedynczą zmianę.  
W warstwie **Mandat–Czas–Relacja** wskazuje, kto może zmienić tryb oddechu i kiedy następuje commit nowej wartości.

### Pola konfiguracyjne

- `frequency` – okres oddechu, np. `30s` oznacza, że co 30 s wykonywany jest miękki reset.  
- `mode` – tryb resetu (`soft_reset` czyści bufory i re-evaluuje priorytety, `hard_reset` resetuje również plan w AST/Mozaice).  
- `threshold` – próg odszumienia; fluktuacje poniżej tego progu są ignorowane.

### Architektury

- **CL** (klasyczna) – czyszczenie buforów i odświeżanie struktur AST.  
- **HYB** (hybrydowa) – dodatkowo reset lokalnych kafelków w mozaice i odtworzenie mostów 9D.  
- **Q** (kwantowa) – przygotowanie rejestru kubitów w stan bazowy, amortyzacja dekoherencji i reset obwodów pomiarowych.