# Locus–Medium–Mandat – Zakotwiczenie stanu (architektura klasyczna)

Rejestr **Locus–Medium–Mandat** określa, gdzie Latarnię przechowujemy i kto ma prawo ją modyfikować.  
Wersja klasyczna opisuje lokalizację (np. plik YAML, tablica w bazie), medium (HUD, konsola, plik w repozytorium) oraz mandat (człowiek, AI czy hybryda).  
Wskazuje również mechanizm podpisu i wersjonowania – od `git commit` po własne rytuały operacyjne.

### Pola konfiguracyjne

- `location` – ścieżka lub identyfikator miejsca przechowywania (`file`, `db`, `hud`).  
- `medium` – format/medium nośnika (`yaml`, `json`, `bin`, `ui`).  
- `authoritative` – kto ma mandat do wprowadzania zmian (`human`, `ai`, `hybrid`).  
- `signature_required` – czy zmiana wymaga podpisu kryptograficznego (`true`/`false`).