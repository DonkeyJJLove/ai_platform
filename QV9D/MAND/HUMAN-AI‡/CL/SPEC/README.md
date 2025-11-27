# Human–AI – Tryb dialogu (architektura klasyczna)

Rejestr **Human–AI‡** określa zasady komunikacji pomiędzy człowiekiem a systemem.  
Ustala tryb prezentacji informacji (`mode`), limit zmian, które AI może zaproponować bez dodatkowej zgody, oraz warunki wymagające bezpośredniego zatwierdzenia przez człowieka.  
Wersja klasyczna dotyczy interfejsu tekstowego (HUD) oraz sposobu prezentacji wyników.

### Pola konfiguracyjne

- `mode` – sposób prezentacji informacji: `explained` (pełne wyjaśnienia), `concise` (zwięzłe informacje), `raw` (surowe dane).  
- `proposal_limit` – maksymalny zakres zmian, które AI może zaproponować bez zgody człowieka.  
- `require_confirmation` – czy każda zmiana wymaga zatwierdzenia (`true`/`false`).