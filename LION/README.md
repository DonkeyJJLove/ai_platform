# LION — operacyjna warstwa wiedzy

`/LION/` jest kanoniczną powierzchnią nawigacji i koordynacji dla ewolucyjnej architektury oraz operacji rojowych. **Nie jest źródłem authority wykonawczego.**

Każdy wątek/dron rozpoczyna tutaj, a przed działaniem wykonuje aktualne obserwacje stanu.

## Orientacja

1. Przeczytaj `catalog.json` i protokoły.
2. Przeczytaj mapy targetu, implementacji i ewolucji.
3. Przeczytaj rejestry misji, dronów, kanałów i zależności.
4. Ponownie zaobserwuj bieżący stan GitHub oraz autorytatywne rejestry wskazane w katalogu.
5. Oznacz projekcje nieaktualne lub skonfliktowane przed ich użyciem.
6. Przeczytaj kanał roboczy dla bieżącej misji/drona/roju.
7. Kontynuuj wyłącznie w granicach authority przyznanego osobnym mechanizmem.

## Pierwszeństwo źródeł prawdy

Dla dynamicznego stanu repozytorium aktualne obserwacje GitHub mają pierwszeństwo przed zapisanymi projekcjami `/LION/`. Tożsamość i lifecycle agenta pochodzą z Agent Registry. Własność branchy względem misji pochodzi z Branch Ownership Registry. Architektura normatywna pochodzi z dokumentów architektonicznych wskazanych przez katalog. Historia czatu jest wyłącznie kontekstem i nigdy nie stanowi stanu kanonicznego.

## Model operacyjny

`TARGET -> OBSERVE -> GAP -> MISSION -> DRONE/SWARM -> BUILD -> VERIFY -> INTEGRATE -> OBSERVE -> RECONCILE -> UPDATE PROJECTIONS -> NEXT GAP`

Komunikacja między wątkami korzysta z adresowalnych GitHub Issues i komentarzy zarejestrowanych w `ops/channel-registry.json`. Dron publikuje ustrukturyzowane wiadomości do docelowego kanału roboczego; nigdy nie zakłada dostępu do innej sesji czatu.

## Bezpieczeństwo

Sama obecność wpisu w rejestrze lub katalogu nie przyznaje credentials, dostępu do runtime, authority do merge, release ani deploymentu. Stan nieznany, nieaktualny lub skonfliktowany musi zostać ponownie zaobserwowany albo doprowadzić do fail-closed przed wykonaniem działania powodującego skutki.
