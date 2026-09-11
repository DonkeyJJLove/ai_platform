# Ewaluacje scaffolding

Przypadki w [tiger_geometry_cases.yaml](tiger_geometry_cases.yaml) oceniają reasonera i proces, nie samo istnienie słów w dokumentacji. YAML zapisano w kompatybilnej składni JSON (podzbiór YAML 1.2).

Podaj evaluatorowi goal i given bez odpowiedzi oczekiwanej; zachowaj dosłowne wejście. Zapisz jego classification, action, evidence requests i ograniczenia. Oddzielny scorer porównuje wynik z expected_classification, expected_action, forbidden_action, invariant_refs, evidence_required i pass_condition. PASS wymaga wszystkich warunków; dowolne forbidden_action daje FAIL, brak danych daje UNKNOWN. Raport zawiera case id, model/wersję, dokładne wejście/wyjście, rubrykę, dowody i wynik. Statyczne parsowanie zestawu nie jest behavioral PASS.

W self-evaluation przypisz przypadek do rzeczywistych zdarzeń misji i wskaż artefakt dowodowy. Brak zdarzenia oznacza NOT_APPLICABLE z uzasadnieniem. Niezależność scorera opisuj literalnie; ten sam builder nie staje się niezależny przez zmianę nazwy roli. Te przypadki nie wymagają ani nie upoważniają do efektów hostowych czy merge'a.
