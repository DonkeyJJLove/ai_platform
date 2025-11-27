# Cisza–Wydech – Rejestr resetu (architektura kwantowa)

W architekturze kwantowej rejestr Cisza–Wydech ma podwójną rolę.  
Po pierwsze określa częstotliwość czyszczenia klasycznych buforów i ponownej interpretacji stanów w AST.  
Po drugie – steruje przygotowaniem rejestru kubitów w stan bazowy oraz resetowaniem obwodów, aby zmniejszyć dekoherencję.  
Parametr `threshold` może w tej architekturze odnosić się również do tolerancji szumu (błędów pomiaru), a `mode` przyjmuje wartości `soft_reset`, `hard_reset` oraz `q_reset`.

### Pola konfiguracyjne

Patrz plik w katalogu `CL`; wszystkie pola (`frequency`, `mode`, `threshold`) obowiązują, z dodatkowymi wartościami dla trybu `q_reset`.