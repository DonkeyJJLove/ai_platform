# R9 Authorization Lifecycle — continuation state

R8/R9 hybrid repair został scalony przez PR #335. Post-merge projekt otworzył oddzielny lokalny successor wyłącznie dla doprecyzowania lifecycle autoryzacji. Ta faza nie dziedziczy prawa publikacji nowego successor HEAD z wcześniejszego LPCL.

Canonical rule: wygenerowanie LPCL materializuje authority intent/scope, ale `LPCL_GENERATION_NE_AUTHORITY`; dopiero jawne uruchomienie dokładnego LPCL przez użytkownika jest external activation event. Aktywacja wiąże tylko zapisane identities, currentness i effect classes. Każdy nowy successor identity poza tym bindingiem wymaga nowego LPCL i nowego user launch.

Discovery ma prowadzić do `LION/architecture/v1_4/AUTHORIZATION_LIFECYCLE_CONTRACT.json` z root `AGENTS.md`, skill `lion-evolution`, Codex README/integration i Tool Authority Map. RAG successor musi umożliwiać odzyskanie tej reguły bez pamięci czatu.

Publikacja tej lokalnej fazy jest następną authority boundary i wymaga nowego exact LPCL po ustaleniu finalnego HEAD/TREE/scan/truth/RAG identity.
