# Próg–Przejście – Warunek commitu (architektura klasyczna)

Rejestr **Próg–Przejście** określa, kiedy nowy stan Latarni staje się obowiązujący.  
Zmiana stanu w systemie to przejście przez próg: stary wzór przestaje obowiązywać, a nowy staje się normą.  
Parametry tego rejestru ustalają minimalny spadek funkcji celu (`deltaJ_threshold`), liczbę iteracji potwierdzających spadek (`confirm_iterations`) oraz to, czy możliwy jest rollback.

### Pola konfiguracyjne

- `deltaJ_threshold` – minimalny spadek funkcji celu wymagany do zaakceptowania zmiany.  
- `confirm_iterations` – liczba kolejnych iteracji, w których zmiana musi utrzymać się poniżej progu.  
- `rollback_enabled` – czy można przywrócić poprzedni stan (`true`/`false`).