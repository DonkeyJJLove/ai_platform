# LION RAG 1.5 — FEDERATION AND DEPENDENCIES

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Role lokalne i globalne

ai_platform: EnterpriseControlPlane, AgentFoundry, SwarmPlanner, FederationRegistry, AuthorityPolicyEngine i ProcessContractIntegration. Ma rozwijać zdolność budowania kolejnych rozwiązań i misji, nie tylko przechowywać statyczny opis wszystkich peerów. Własność architektury nie nadaje lokalnemu modelowi ani koordynatorowi prawa do dowolnego wykonania.

swarm: execution mesh, telemetria i workload runtime; powiązanie z ai_platform przez rzeczywisty kontrakt, identity oraz admission. Repozytorium nie jest synonimem technologii Docker Swarm. chunk-chunk: semantyka procesu, HMK-9D i routing/kompresja kontekstu. glitchlab: analiza delty, anomalii i niezmienników. HA2D: pamięć, stan poznawczy, snapshoty i ich pochodzenie.

hipotezy_nadawcze_LLM: hipotezy, eksperymenty i falsyfikatory. mosaic_lab_pro.py: headless projekcje grafu i analiza struktury, przy zachowaniu odrębności od GUI. sbom: AID, tożsamość i pochodzenie rzeczywistych bajtów artefaktu. SymulacjaKaskadySieciowej: wyniki symulacji wraz z seedem, założeniami i ModelRiskStatement. writeups: korpus badań, dowodów i publikacji, w tym wyniki negatywne, nie globalny rejestr bieżącego runtime.

## Jak czytać zależność

Każda relacja musi określać producenta, konsumenta, typ danych lub kontrakt, dokładną wersję, klasę dowodu oraz warunek unieważnienia. DECLARES_ROLE jest słabsze i innego rodzaju niż CALLS_PROVIDER; CONTRACT_COMPATIBLE nie znaczy LIVE_INTEROPERABLE. Dwie etykiety global_owner i depends_on nie tworzą jeszcze funkcjonalnego roundtripu.

Rozwój federacji nie oznacza dziesięciu kopii globalnej dokumentacji. Peery publikują własne wejścia, wyjścia, ograniczenia i testy. Globalny owner importuje ich kontrakty i wskazuje związany source vector. Nie wszystkie repozytoria muszą uczestniczyć w każdej misji; każde musi mieć jednak własny uzasadniony kierunek ewolucji w programie całej federacji.

## Dwa przekroje integracyjne

Przekrój strukturalny wiąże semantykę procesu, deltę Git, rzeczywistą analizę glitchlab, projekcję mosaic, tożsamość artefaktu oraz konsumenta ai_platform. Przekrój dowodowy wiąże hipotezę, żądanie i wynik symulacji, ryzyko modelowe, AID, korpus i snapshot HA2D. Ich wykonanie wymaga faktycznych call sites oraz bajtów wyników. Osobno sprawdza się runtime roundtrip swarm. Nie zastępuj tych przekrojów liczbą dowolnych unit testów.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:cyber_lion/registry/repositories.json`
- `Peer cyber-lion.repository.json at vector 26`
- `Prior FEDERATION_ROLE_PROJECTION.json`
