param(
    [string]$RootPath
)

if (-not $RootPath) {
    $RootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
}

Write-Host "=== QV9D: inicjalizacja LAT_GLX_PROJECT_MOSAIC.tree.json ==="
Write-Host "Root: $RootPath"
Write-Host ""

$semDir   = Join-Path $RootPath "SEM\WIOSKA-MIASTO\HYB\STATE"
$treePath = Join-Path $semDir  "LAT_GLX_PROJECT_MOSAIC.tree.json"

New-Item -ItemType Directory -Force -Path $semDir | Out-Null

# backup jeśli plik już istnieje
if (Test-Path $treePath) {
    $stamp   = Get-Date -Format "yyyyMMdd_HHmmss"
    $backup  = "$treePath.bak.$stamp"
    Copy-Item $treePath $backup
    Write-Host "Istniejący plik zachowany jako: $backup"
}

$weights_9D = @(
    @{ id = "PLAN-PAUZA";          k_base = 1.00; axis = "czas";        role = "okno planowania i zatrzymania akcji";        description = "Jak często i jak głęboko wolno zmieniać strukturę projektu." }
    @{ id = "RDZEN-PERYFERIA";     k_base = 1.20; axis = "topologia";   role = "separacja jądra od eksperymentów";           description = "Rozróżnienie rdzenia systemu od peryferii eksperymentalnych." }
    @{ id = "CISZA-WYDECH";        k_base = 0.90; axis = "szum/sygnal"; role = "filtr hałasu i nadkomentarza";               description = "Steruje kompresją logów i artefaktów." }
    @{ id = "WIOSKA-MIASTO";       k_base = 1.30; axis = "skala";       role = "federacja lokalne ↔ globalne";              description = "Jak ważna jest skalowalna federacja instancji." }
    @{ id = "OSTRZE-CIERPLIWOSC";  k_base = 1.40; axis = "ryzyko";      role = "balans refaktoryzacja ↔ stabilność";        description = "Preferencja dla rzadkich, ale precyzyjnych cięć." }
    @{ id = "LOCUS-MEDIUM-MANDAT"; k_base = 1.50; axis = "wladza";      role = "rozmieszczenie mandatów";                   description = "Waga poprawnie zdefiniowanych ról i rytuałów CI/CD." }
    @{ id = "HUMAN-AI‡";           k_base = 1.60; axis = "interfejs";   role = "spojnosc Human–AI";                         description = "Jak ważna jest czytelność zarówno dla człowieka, jak i AgentaAI." }
    @{ id = "PROG-PRZEJSCIE";      k_base = 1.10; axis = "stany";       role = "progi faz projektu";                        description = "Poprawne przejścia między stanami artefaktów." }
    @{ id = "SEMANTYKA-ENERGIA";   k_base = 1.25; axis = "znaczenie";   role = "gestosc semantyczna / koszt";              description = "Premiowanie rozwiązań o wysokiej gęstości znaczenia." }
)

$tree = [PSCustomObject]@{
    version      = "1.0"
    generated_by = "Init-LAT-GLX_PROJECT_MOSAIC.ps1"
    root         = [PSCustomObject]@{
        id    = "GLX_PROJECT"
        kind  = "project"
        label = "GLX + chunk-chunk + glitchlab + swarm + HA2D + hipotezy_nadawcze_LLM"
    }
    weights_9D   = $weights_9D
    nodes        = @()
    edges        = @()
    metrics      = [PSCustomObject]@{
        last_scan = [PSCustomObject]@{
            repos_found  = 0
            dirs_scanned = 0
            timestamp    = ""
        }
    }
    generated_at = "TO_BE_SET_BY_Scan-9D"
}

$tree | ConvertTo-Json -Depth 10 | Out-File -FilePath $treePath -Encoding UTF8

Write-Host "Zapisano LAT_GLX_PROJECT_MOSAIC.tree.json:"
Write-Host "  $treePath"
Write-Host "=== QV9D: inicjalizacja zakończona ==="
