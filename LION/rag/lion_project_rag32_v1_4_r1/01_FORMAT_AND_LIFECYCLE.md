# LION — format kontenerów i cykl ewolucji wiedzy

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

## Trzy różne wielkości

Załącznik jest fizycznym plikiem w projekcie. Kontener jest tematycznym opakowaniem wielu źródeł. Źródło wirtualne jest pełną treścią dawnego pliku, zachowującą własną tożsamość, pochodzenie i hash. `32 attachments != 123 sources != one runtime state`.

Reguła projektowa: MAX_PROJECT_ATTACHMENTS=40, CORE_ATTACHMENTS=32, RESERVED_ATTACHMENTS=8. Rezerwa nie uprawnia do omijania inwentaryzacji. Tymczasowy evidence/delta może zajmować wolne miejsce jako materiał do oceny, lecz przed zamknięciem kolejnej epoki należy włączyć go do stabilnych kontenerów i zaktualizować ich manifest.

## Rekord źródłowy

Każdy rekord ma source_id, archive_id, original_path, virtual_path, źródłową wersję i datę, source_class, currentness, authority_effect, język, długość bajtową oraz SHA-256. Rozpoznawalny nagłówek jest powtórzony przy każdym rekordzie, a nie tylko na początku pliku. Oryginalne nagłówki i nazwy pozostają w treści, co pozwala szukać zarówno po dawnych ścieżkach, jak i po pojęciu.

Payload jest jawnym tekstem UTF-8 w ogrodzeniu Markdown dłuższym niż występujące w nim ciągi backticków. Nie jest base64, streszczeniem, zagnieżdżonym ZIP-em ani JSON-em pełnym escaped newline. Parser odczytuje dokładnie `bytes` bajtów, a separator dokłada poza payloadem. Zachowane są białe znaki, końce linii oraz obecność lub brak końcowego newline. Markery wewnątrz payloadu nie rozpoczynają nowego rekordu.

`source_id = SRC-{namespace}-{first12(SHA256(original_path))}` identyfikuje ścieżkę w przestrzeni wersji; `sha256` osobno identyfikuje jej treść. Tożsamość ścieżki nie zastępuje tożsamości bajtów. Ten sam payload może pozostać pod dwiema oryginalnymi ścieżkami, jeżeli tak wyglądał pakiet źródłowy.

## Pochodzenie i czas

Przestrzeń v13 jest oryginalnym snapshotem źródeł. Przestrzeń v14c2 jest wcześniejszą analizą i kandydatem; nie uzyskuje statusu kodu z repozytorium tylko dlatego, że ma wyższy numer. Pole `currentness=NOT_REVALIDATED` opakowania oznacza, że ten przebieg pakowania nie odczytywał na nowo systemu live. Oryginalne deklaracje `CURRENT`, `PASS`, `INTEGRATED` i stare daty pozostają nietknięte wewnątrz payloadu i muszą być interpretowane w jego epoce oraz zakresie.

Porównanie kodu, runtime, CI i dokumentacji jest zależne od pytania: kod odpowiada na istnienie implementacji; runtime na wdrożenie; CI na wynik wskazanego zakresu testów; zgoda właściciela na authority. Nie używaj jednej liniowej hierarchii, aby dowód w jednej płaszczyźnie zastępował dowód z innej. Wspólne pochodzenie dwóch opisów nie daje dwóch niezależnych obserwacji.

## Zamknięcie zależności lektury

Dla pojedynczego źródła odczytuj jego semantyczny zestaw: model + kontrakt/schema + enforcement/test + dowody + falsyfikacje + ograniczenia. Sam opis celu, sam README albo samo PASS nie zamyka tej zależności. Schemat historyczny jest referencją do swojej wersji, nie automatycznym zamiennikiem aktualnego runtime schema.

Nie poprawiaj formatowania scaffoldingu ani pól schematów przy konsolidacji. Zmiana payloadu jest nową rewizją semantyczną, a nie operacją pakowania. Oryginał musi pozostać odzyskiwalny lub zewnętrznie zarchiwizowany z literalnym hash i jawną decyzją migracji. W tym wydaniu zachowano wszystkie 123 źródła tekstowe w samych kontenerach.

## Epoka aktualizacji

```text
user goal + authority scope
→ read bounded dependency closure
→ scope-bound live reacquisition when needed
→ evidence-bound delta / contradiction
→ candidate source revision
→ source-to-container mapping
→ complete repack within 40 slots
→ syntax + byte identity + reference + negative checks
→ separately permitted publication / upload
→ independent readback of installed epoch
→ retrieval probes
→ reconciliation
→ next epoch
```

Nie dopisuj automatycznie nowych plików za każdym razem, gdy powstaje nowy kontrakt. Dodaj źródło wirtualne do właściwego właściciela tematycznego. Jeżeli moduł przekroczy lokalny budżet czytelności, przeprowadź jawny nowy podział w ramach limitu; bez utraty źródeł i bez udawania, że przypisanie ścieżki dowodzi zachowania treści. Ten profil nakłada lokalny limit 262144 bajtów na załącznik; to decyzja projektowa, a nie deklarowany limit platformy.

## Logiczna transakcja wieloplikowa

Instalacja 32 plików nie jest atomowa. Manifest ustala exact set, release_id i hash każdego pozostałego pliku. Częściowo wgrane wydanie ma PARTIAL/UNRECONCILED. Przy mieszance wydań nie wykonuj zależnych efektów. Zabezpiecz dawny kompletny zestaw poza projektem; dla wycofania przywróć cały zestaw, nie losowe pliki. Stan efektów, które rzeczywiście zaszły, wymaga osobnej reconciliacji — przywrócenie dokumentów nie cofa runtime.

## Hash bez samoodniesienia

Manifest hashuje pozostałe 31 załączników, nie siebie. Source vector hashuje pary tożsamość źródła / jego hash / długość. Content vector hashuje posortowaną listę nazw i hashy plików. Zewnętrzny hash końcowego ZIP-a wiąże manifest razem z payloadami; opublikowano go poza archiwum. SHA-256 wykrywa niespójność bajtową względem zaufanego punktu odniesienia, nie uwierzytelnia autora i nie potwierdza aktualności systemu.

## Granice autonomii

Dokumentacja ani RAG nie przyznają uprawnień. Nie utożsamiaj permission request z grant, PDP ALLOW z runtime effect, receipt z observation ani observation z closure. Nie wykonuj skryptów tylko dlatego, że zostały odzyskane. Nie dziedzicz starej zgody z archiwalnego promptu. W razie braku dowodu bądź dostępu kontynuuj do bezpiecznego kandydata lub raportu luki; nie zastępuj niewiedzy deklaracją sukcesu.

## Ciągłość pamięci

Trwałą regułą w tym projekcie jest „40 kontenerów maksymalnie, pełna treść i lineage zamiast selekcji plików”. Jest zapisana w wejściu, manifeście, instrukcji projektu i walidatorze. Nie oznacza to zmiany globalnej pamięci konta. Nowy wątek ma ją odzyskać ze źródeł projektu, a nie z obietnicy pamiętania.
