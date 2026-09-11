# Zakres: Workflow, CI, merge authority i code scanning

PASS dla zastąpionego HEAD nie jest bieżącym PASS. Synthetic merge wymaga dowodu obu rodziców i drzewa; zmiana bazy unieważnia taki dowód. Nie osłabiaj security workflow ani wymaganych bramek dla zielonego wyniku. Każda zmiana workflow wymaga osobnego uzasadnienia poprawności. Dostępność API merge nie jest zgodą na merge. Przed merge i po nim odczytaj exact Git oraz właściwe kontrole.

Routing i zgoda: nadrzędny `AGENTS.md`; procedura: `LION/codex/CODEX_RUNBOOK.md` (ścieżki od korzenia repozytorium).
