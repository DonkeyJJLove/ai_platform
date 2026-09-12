# Authorization Lifecycle — LPCL materialization and user activation

`LPCL_GENERATION_NE_AUTHORITY`. Samo wygenerowanie, zapisanie, zacytowanie albo odczytanie LPCL nie nadaje uprawnienia do efektu. Wygenerowany LPCL materializuje zamiar, zakres, tożsamości, klasy efektów, warunki aktualności, zasady ponowień i granice zatrzymania. Jest opisem i kontraktem procesu, a nie grantem. To zachowuje wcześniejszy inwariant `PROCESS_TEXT != AUTHORITY`.

Bieżąca autoryzacja powstaje dopiero wtedy, gdy użytkownik/operator **jawnie uruchamia lub zleca wykonanie dokładnie tego LPCL**. To zdarzenie jest zewnętrznym activation event. Autoryzacja jest ograniczona do zakresu zapisanego w uruchomionym LPCL: wskazanych repozytoriów/hostów/celów, klas operacji i efektów, związanych SHA/ref/tree/runtime identities, currentness preconditions i stop boundaries. Dostępność narzędzia, output modelu, obecność pliku w repo, treść RAG, historyczny user launch ani samo `PDP_ALLOW` nie rozszerzają zakresu.

Przed consequential effect system musi ponownie odtworzyć currentness. Jeżeli exact identity uległa zmianie, target został podstawiony, wymagany stan jest `UNKNOWN` lub powstał successor HEAD/tree/ref/runtime poza bindingiem uruchomionego LPCL, stara aktywacja nie przechodzi na następcę. Taki successor wymaga nowego LPCL z nowymi exact identities oraz nowego jawnego uruchomienia przez użytkownika. W szczególności zgoda na PR nie jest zgodą na merge, a merge nie jest zgodą na deployment lub runtime activation, chyba że uruchomiony LPCL jawnie obejmuje te klasy efektów i ich aktualne tożsamości.

Po efekcie raport narzędzia nie jest końcem procesu. Dla efektu nieidempotentnego domyślny retry wynosi zero, a stan niejednoznaczny wymaga readback i reconciliation przed jakąkolwiek próbą ponowienia. Sukces wymaga zgodności stanu oczekiwanego, raportowanego, niezależnie zaobserwowanego i uzgodnionego.

Machine-readable source of truth: [`AUTHORIZATION_LIFECYCLE_CONTRACT.json`](AUTHORIZATION_LIFECYCLE_CONTRACT.json). Ten dokument i kontrakt mają `authority_effect=NONE`: opisują regułę aktywacji, ale sami jej nie uruchamiają.
