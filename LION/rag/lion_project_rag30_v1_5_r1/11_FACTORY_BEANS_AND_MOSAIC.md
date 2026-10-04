# LION RAG 1.5 — FACTORY BEANS AND MOSAIC

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Zdolność do tworzenia rozwiązań jest celem, nie założeniem

Linia The Bean Factory opisuje przejście od rozpoznanej luki do potrzebnej zdolności, ponownego użycia lub specyfikacji Bean, kompozycji, Mosaic i materializacji kandydata. ai_platform ma wspierać ten obieg jako element budujący rozwiązania. Nie może być sprowadzony do panelu, który tylko wyświetla listę cudzych skryptów.

Gap wymaga odtworzonego stanu i wymagań. CapabilityNeed nie nadaje capability ani prawa jej użycia. BeanSpec, BeanCandidate i BeanInstance opisują różne etapy; CompositionContract określa zgodność części, a Mosaic może wiązać czasowe zestawienie funkcji. AutonomyBlueprint i Materializer muszą mieć określone wejście, wynik, ograniczenia i konsumenta; sama obecność słów w dokumencie nie jest działającą fabryką.

## Zachowany kierunek rozwoju

Rozwijaj reuse przed generowaniem nowego kodu. Jeżeli istniejący Bean spełnia potrzebę, oceń jego zgodność, stan i ograniczenia. Gdy potrzebna jest nowa zdolność, zbuduj źródłowo związany kandydat, jego zależności i testy. Falsyfikator powinien wykazać, kiedy kandydat nie realizuje celu; poprawiona generacja musi zachować lineage do błędu, a nie usuwać nieudanego wyniku.

Rozdziel generowanie, kompozycję, wykonanie i ewolucję samej fabryki. Możliwość zbudowania dwóch ograniczonych rodzin artefaktów nie jest dowodem dowolnej generatywności. Historyczny B0 jest ograniczonym wynikiem o własnym zakresie; Factory-of-factories pozostaje odrębnym wymaganiem badawczym, nie blokadą każdej użytecznej misji.

## Predykat użytkowy dla przyszłych misji

Ten sam mechanizm przyjmuje dwie różne, wcześniej niezakodowane jako osobne workflow potrzeby. Rozpoznaje brak, wybiera lub tworzy komponent, wytwarza nowy użyteczny kandydat, wykrywa kontrolnie wprowadzony błąd, zwraca kontrprzykład i produkuje poprawioną generację. Weryfikacja dotyczy rzeczywistych bajtów i zachowania. Zakres uogólnienia, rodzina zadań i koszty pozostają jawne.

Dopiero potem kandydat trafia do odpowiedniej ścieżki publikacji i efektów. Autonomia nie może nadać sobie prawa do wdrożenia własnego control plane. Rozwój fabryki ma kończyć się kolejną weryfikowalną zdolnością, nie tylko dodatkowym manifestem.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:cyber_lion/TARGET_ARCHITECTURE.md#bean-factory`
- `DonkeyJJLove/ai_platform:cyber_lion/contracts/capability_need.py`
- `DonkeyJJLove/ai_platform:cyber_lion/contracts/bean.py`
- `DonkeyJJLove/ai_platform:cyber_lion/contracts/bean_composition.py`
- `DonkeyJJLove/ai_platform:cyber_lion/contracts/mosaic.py`
