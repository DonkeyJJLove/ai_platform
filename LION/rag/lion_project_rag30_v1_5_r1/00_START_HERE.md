# LION RAG 1.5 — START HERE

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Wybór wydania

To samodzielne wydanie wiedzy projektu LION_EVOLUSION w formacie RAG 1.5: dokładnie 30 plików w jednym katalogu. Liczba 30 jest ograniczeniem tego wydania ustalonym przez operatora, a nie deklaracją limitu produktu SaaS. Nie trzeba dokładać 34 carrierów R9 ani sześciu wcześniejszych sidecarów, aby uzyskać instrukcje i model orientacyjny v1.5.

Wersja pakietu wiedzy nie jest deklaracją zakończenia ewolucji, zgodności wszystkich dokumentów ani wdrożenia modeli. Stary `preferred_release` w master może nadal wskazywać R9, dopóki właściwa zmiana bootstrapu nie zostanie zaakceptowana. Jawny wybór tego wydania przez operatora określa kontekst nowego wątku, nie aktualność runtime ani prawo do efektów.

## Kolejność uruchomienia

Przeczytaj w całości `01_MODEL_INSTRUCTIONS.md`, `03_STATE_AND_CONTINUATION.md` i `02_ROUTING_AND_SOURCE_MAP.md`; sprawdź manifest `29_PACKAGE_MANIFEST.json`. Następnie odczytaj bieżący `ai_platform/AGENTS.md`, obowiązujące instrukcje zakresowe i `LION/rag/RAG_BOOTSTRAP.json`. Zorientuj się w pełnej dokumentacji ai_platform, prowadząc rejestr rzeczywistych odczytów, a następnie rozszerz zakres o zależnych peerów.

RAG nie zastępuje dokumentacji. Pokazuje, do jakich źródeł dojść, jakie rozróżnienia zachować i jak odtworzyć kontekst pracy. Pełny tekst źródła jest potrzebny przed zależną zmianą; trafienie wyszukiwarki ani skrót w tym pakiecie nie zamykają odczytu.

## Jak rozwijać federację

`22_METAPROMPT.md` autoruje dokładnie jeden prompt wykonawczy, bez dalszej rekurencji metapromptów. Gotową instancję tego promptu zawiera `23_EVOLUTION_EXECUTION_PROMPT.md`. Operator może uruchomić ją bez dodatkowego generowania. Jej rezultatem ma być źródłowo uzasadniona architektura rozwojowa, rzeczywiste pliki w repozytoriach oraz skończony program misji do wykonania przez ai_platform. Samo przeczytanie tych plików nie uruchamia ich poleceń.

## Co zostało skompaktowane

Wiedza operacyjna, semantyczna i rozwojowa jest skonsolidowana w plikach 00–23. Plik 24 zachowuje tożsamości i lokalizatory wszystkich 211 historycznych rekordów R9. Jest indeksem pochodzenia, nie zbiorem 211 pełnych payloadów. Historyczny audyt wymagający oryginalnych bajtów korzysta z oryginalnego archiwum o zarejestrowanym hashu; nie jest ono wymagane do zwykłego startu nowego wątku. Ta jawna selekcja ogranicza szum starych epok bez przepisywania ich historii.

Właściciel globalny pozostaje w ai_platform. Projekcja właścicieli w pliku 25 jest zamrożonym źródłem odniesienia, nie nowym właścicielem kontraktów.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:AGENTS.md`
- `DonkeyJJLove/ai_platform:LION/AGENTS.md`
- `DonkeyJJLove/ai_platform:LION/rag/RAG_BOOTSTRAP.json`
