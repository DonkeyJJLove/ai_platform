param(
    # Katalog główny woluminu QV9D (domyślnie katalog, z którego uruchamiasz skrypt)
    [string]$Root = $PSScriptRoot,
    [string]$GitHubUser = "DonkeyJJLove"
)

Write-Host "=== QV9D: aktualizacja struktury woluminu 9D ==="
Write-Host "Root:" $Root
Write-Host ""

# --- 1. Uzupełnienie struktury INF / SEM / MAND ---

$layers        = @("INF", "SEM", "MAND")
$architectures = @("CL", "HYB", "Q")
$kinds         = @("SPEC", "STATE", "METRICS", "RITUAL", "CI")

foreach ($layer in $layers) {
    $layerPath = Join-Path $Root $layer
    if (-not (Test-Path $layerPath)) {
        Write-Warning "Warstwa $layer nie istnieje (pomijam)."
        continue
    }

    Write-Host "Warstwa:" $layer

    # Każdy podkatalog warstwy traktujemy jako MOST (CISZA-WYDECH, WIOSKA-MIASTO, itd.)
    Get-ChildItem -Path $layerPath -Directory | ForEach-Object {
        $mostDir  = $_.FullName
        $mostName = $_.Name
        Write-Host "  Most:" $mostName

        foreach ($arch in $architectures) {
            $archPath = Join-Path $mostDir $arch
            if (-not (Test-Path $archPath)) {
                Write-Host "    + Tworzę architekturę:" $arch
                New-Item -ItemType Directory -Path $archPath -Force | Out-Null
            }

            foreach ($kind in $kinds) {
                $kindPath = Join-Path $archPath $kind
                if (-not (Test-Path $kindPath)) {
                    Write-Host "      + Tworzę typ artefaktu:" $kind
                    New-Item -ItemType Directory -Path $kindPath -Force | Out-Null
                }
            }
        }
    }

    Write-Host ""
}

# --- 2. Mozaika repozytoriów: LAT_GLX_PROJECT_MOSAIC ---

$mosaicDir = Join-Path $Root "SEM\WIOSKA-MIASTO\HYB\STATE"
if (-not (Test-Path $mosaicDir)) {
    Write-Host "Tworzę katalog mozaiki:" $mosaicDir
    New-Item -ItemType Directory -Path $mosaicDir -Force | Out-Null
}

$mosaicPath = Join-Path $mosaicDir "LAT_GLX_PROJECT_MOSAIC.tree.json"

# Ręcznie zdefiniowana lista repo jako elementów ZION–KRÓLESTWO–NIEBIESKIE
$repos = @(
    @{
        name   = "chunk-chunk"
        url    = "https://github.com/$GitHubUser/chunk-chunk"
        role   = "Rdzeń protokołu kompresji 9D (procesy, mosty, pipeline)."
        layer  = "SEM/WIOSKA-MIASTO"
        zion   = "KRÓLESTWO-NIEBIESKIE: rdzeń protokołu."
    },
    @{
        name   = "glitchlab"
        url    = "https://github.com/$GitHubUser/glitchlab"
        role   = "Laboratorium anomalii, glitche, eksperymenty na strukturach 9D."
        layer  = "SEM/WIOSKA-MIASTO"
        zion   = "KRÓLESTWO-NIEBIESKIE: strefa eksperymentu."
    },
    @{
        name   = "swarm"
        url    = "https://github.com/$GitHubUser/swarm"
        role   = "Rój / federacja agentów i mikro-podmiotów, dystrybucja pracy."
        layer  = "SEM/WIOSKA-MIASTO"
        zion   = "KRÓLESTWO-NIEBIESKIE: warstwa rojowa."
    },
    @{
        name   = "HA2D"
        url    = "https://github.com/$GitHubUser/HA2D"
        role   = "Interfejs Human–AI, płaszczyzny 2D/9D, rytuały komunikacji."
        layer  = "MAND/HUMAN-AI‡"
        zion   = "KRÓLESTWO-NIEBIESKIE: brama Human–AI."
    },
    @{
        name   = "hipotezy_nadawcze_LLM"
        url    = "https://github.com/$GitHubUser/hipotezy_nadawcze_LLM"
        role   = "Hipotezy nadawcze, meta-język, analiza sposobów emisji treści przez LLM."
        layer  = "SEM/SEMANTYKA-ENERGIA"
        zion   = "KRÓLESTWO-NIEBIESKIE: warstwa doktryny."
    },
    @{
        name   = "writeups"
        url    = "https://github.com/$GitHubUser/writeups"
        role   = "Narracje, raporty, opisy eksperymentów; spójnik między kodem a światem."
        layer  = "MAND/LOCUS-MEDIUM-MANDAT"
        zion   = "KRÓLESTWO-NIEBIESKIE: kronika i ewangelia projektu."
    }
)

$mosaic = @{
    volume      = "QV9D"
    latarnia_id = "LAT_GLX_PROJECT_MOSAIC"
    description = "Mozaika repozytoriów GitHub użytkownika jako elementów woluminu 9D w koncepcji ZION–KRÓLESTWO–NIEBIESKIE."
    owner       = $GitHubUser
    updated     = (Get-Date).ToString("o")
    repos       = $repos
}

Write-Host "Zapisuję mozaikę repozytoriów do:"
Write-Host "  $mosaicPath"
$mosaic | ConvertTo-Json -Depth 5 | Set-Content -Path $mosaicPath -Encoding UTF8

# --- 3. Opcjonalny rejestr generacji (nagłówek) ---

$registerPath = Join-Path $Root "QV9D_rejestr_generacji.md"
if (-not (Test-Path $registerPath)) {
    Write-Host "Tworzę szkielet QV9D_rejestr_generacji.md"
@"
# REJESTR GENERACJI PROJEKTU QV9D

Ten plik jest nagłówkiem rejestru generacji 9D.
Pełna treść jest utrzymywana w artefaktach:
- SEM/WIOSKA-MIASTO/HYB/STATE/LAT_GLX_PROJECT_MOSAIC.tree.json
- warstwach INF / SEM / MAND (SPEC, STATE, METRICS, RITUAL, CI).

Mosty (w szeregu):
Plan–Pauza Rdzeń–Peryferia Cisza–Wydech Wioska–Miasto Ostrze–Cierpliwość Locus–Medium–Mandat Human–AI‡ Próg–Przejście Semantyka–Energia
"@ | Set-Content -Path $registerPath -Encoding UTF8
}

Write-Host ""
Write-Host "=== QV9D: gotowe. Wolumin 9D i mozaika repo zostały zaktualizowane. ==="
