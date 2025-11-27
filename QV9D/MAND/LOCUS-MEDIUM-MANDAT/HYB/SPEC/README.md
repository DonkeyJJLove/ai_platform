# Locus–Medium–Mandat – Zakotwiczenie stanu (architektura hybrydowa)

W hybrydzie rejestr **Locus–Medium–Mandat** rozszerza się o pojęcie lokalnych i globalnych repozytoriów oraz o synchronizację między nimi.  
`location` może wskazywać zarówno lokalny plik `.glx` w projekcie, jak i centralny Postgres (`glx_config`).  
`medium` uwzględnia mozaikę (np. zapis kafelków w pliku) oraz strumienie zdarzeń na busie.  
`authoritative` może przyjmować wartość `committee`, co oznacza, że zmiana musi zostać zaakceptowana przez kilka węzłów.