# LION RAG 1.5 — FAILURE RECOVERY AND OBSERVABILITY

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Niepewny efekt nie jest zaproszeniem do retry

Rozróżniaj brak wysłania, nieznany wynik wysłania, dostarczenie, wykonanie, zapis artefaktu, receipt, ACK, obserwację i uzgodniony completion. Utrata ACK po zapisie bajtów może pozostawić wykonany efekt bez potwierdzenia. Sam unikalny command_id nie dowodzi exactly-once. Najpierw odtwórz stan z istniejących inbox/outbox/ledger i miejsca artefaktu.

Wyczerpany budżet, anulowanie, stale lease/fence, restart workera, stara generacja odpowiedzi, błędny digest oraz niedostępność modelu muszą mieć oddzielne warunki odrzucenia. Wynik wraca do właściwej próby i kontekstu. Odpowiedź starego providera nie może domknąć nowej misji.

## Obserwowalność jest zależnością wykonania

Wskaż, kto obserwuje postcondition, jaki odczyt je potwierdza i jak długo dowód jest ważny. Utrata obserwatora degraduje gotowość zależnego efektu; nie „naprawia” jej heartbeat workera. Wartości latencji, CPU/RAM, liczby agentów i czasu recovery z dokumentów rozwojowych są wymaganiami lub przykładami, dopóki nie zostały pomierzone.

Cztery nazwane hosty SentinelX nie są dowodem czterech niezależnych domen awarii. Odczytany wspólny boot_id wymaga interpretacji topologii; nie stwierdza sam wszystkich relacji izolacji. Logical, administrative i physical independence raportuj osobno.

## Warunki próby odbiorczej

Celowo sprawdź restart po stworzeniu artefaktu i przed ACK, duplikat odpowiedzi, reorder, spóźniony wynik, podmianę bytes, brak admission, utratę transportu SaaS, wygasły binding i anulowanie. Akceptowalne jest poprawne odtworzenie lub jawne zatrzymanie zależnego działania; nieakceptowalne: drugi efekt, osierocony rezultat, cudza rozmowa lub fałszywe COMPLETE.

Recovery projektuj wraz z implementacją, nie dopisuj go po zielonym scenariuszu happy path. Nie kasuj starego worktree ani bazy, aby ukryć konflikt. Granice cofnięcia muszą mówić, co jest odwracalne, a co wymaga kompensacji i zachowania historii.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:browser_broker/src/canonical-conversation-consumer.cjs`
- `DonkeyJJLove/ai_platform:docs/HOSTS_AND_LABS.md`
- `Prior HOST_OBSERVATIONS.json`
- `Prior authoring prompt K12/TEST4`
