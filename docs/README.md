# LION — dokumentacja operacyjna i zgodności

Ten katalog grupuje dokumenty opisujące bieżące granice środowisk wykonawczych, laboratoriów, production-entry oraz zależności/licencje.

## Środowiska, hosty i laboratoria

- [`HOSTS_AND_LABS.md`](HOSTS_AND_LABS.md) — skonsolidowany inwentarz hostów, WSL/environment lifecycle, physical control domains, zewnętrznych runnerów i laboratoriów/repozytoriów ekosystemu.
- [`architecture/production-entry/README.md`](architecture/production-entry/README.md) — deterministyczny rendering current lab world, macierz evidence i production-entry dossier.
- [`../cyber_lion/REPOSITORY_INVENTORY.md`](../cyber_lion/REPOSITORY_INVENTORY.md) — szczegółowy historyczny inwentarz capability repozytoriów.
- [`../cyber_lion/registry/repositories.json`](../cyber_lion/registry/repositories.json) — machine-readable registry repozytoriów/labów.

## Open source i supply-chain

- [`../OPEN_SOURCE_LICENSES.md`](../OPEN_SOURCE_LICENSES.md) — status licencji first-party labów oraz bezpośrednio wykrytych komponentów/toolingu OSS.
- [`../cyber_lion/adapters/sbom.py`](../cyber_lion/adapters/sbom.py) — adapter SBOM/provenance.

## Zasada źródła prawdy

Dokumentacja jest projekcją stanu, nie authority. Przy konflikcie z live GitHub / current CI / exact Git state należy preferować świeższy dowód i zarejestrować drift. W szczególności dokument `HOSTS_AND_LABS.md` nie może być użyty do uzasadnienia production authority bez ponownej obserwacji currentness, host/runtime identity, observability i policy state.
