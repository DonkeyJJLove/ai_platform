<#
  Scan-9D.ps1 – skaner woluminu QV9D
  - czyta /SEM/WIOSKA-MIASTO/HYB/STATE/LAT_GLX_PROJECT_MOSAIC.tree.json
  - jeśli plik nie istnieje, tworzy szkielet z 9 Wrotami
  - skanuje katalog root w poszukiwaniu repo (git / .glx)
  - dla każdego repo zakłada węzeł z MOSTem i wagą 9D
  - dopisuje wpis do QV9D_rejestr_generacji.md

  ŹRÓDŁO PRAWDY wag 9D = weights_9D w tree.json
#>

param(
    [string]$RootPath
)

if (-not $RootPath) {
    $RootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
}

Write-Host "=== QV9D: skan woluminu 9D ==="
Write-Host "Root: $RootPath"
Write-Host ""

# --- narzędzie pomocnicze: bezpieczne dokładanie właściwości --------------

function Ensure-NoteProperty {
    param(
        [Parameter(Mandatory=$true)] [object]$Object,
        [Parameter(Mandatory=$true)] [string]$Name,
        [Parameter(Mandatory=$true)] $Default
    )

    if (-not ($Object.PSObject.Properties.Name -contains $Name)) {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Default -Force
    }
}

# --- ścieżki kluczowych artefaktów ----------------------------------------

$semDir   = Join-Path $RootPath "SEM\WIOSKA-MIASTO\HYB\STATE"
$treePath = Join-Path $semDir  "LAT_GLX_PROJECT_MOSAIC.tree.json"
$logPath  = Join-Path $RootPath "QV9D_rejestr_generacji.md"

New-Item -ItemType Directory -Force -Path $semDir | Out-Null

# --- 1. Wczytanie lub stworzenie LAT_GLX_PROJECT_MOSAIC.tree.json ---------

if (Test-Path $treePath) {
    $treeJson = Get-Content $treePath -Raw
    $tree     = $treeJson | ConvertFrom-Json
    # jeśli ktoś kiedyś zrobił z tego tablicę, bierzemy pierwszy element
    if ($tree -is [System.Array]) {
        $tree = $tree[0]
    }
    Write-Host "Załadowano istniejący LAT_GLX_PROJECT_MOSAIC.tree.json"
} else {
    Write-Host "Brak LAT_GLX_PROJECT_MOSAIC.tree.json – tworzę szkielet"

    $tree = [PSCustomObject]@{}
}

# dopilnuj podstawowej struktury
Ensure-NoteProperty $tree 'version'      '1.0'
Ensure-NoteProperty $tree 'generated_by' 'Scan-9D.ps1'
Ensure-NoteProperty $tree 'root'         ([PSCustomObject]@{
    id    = 'GLX_PROJECT'
    kind  = 'project'
    label = 'GLX + chunk-chunk + glitchlab + swarm + HA2D + hipotezy_nadawcze_LLM'
})
Ensure-NoteProperty $tree 'nodes'   @()
Ensure-NoteProperty $tree 'edges'   @()
Ensure-NoteProperty $tree 'metrics' ([PSCustomObject]@{})

Ensure-NoteProperty $tree.metrics 'last_scan' ([PSCustomObject]@{
    repos_found  = 0
    dirs_scanned = 0
    timestamp    = ''
})

# 9 Wrót – jeśli nie ma, tworzymy domyślne, ale jeśli są, NIE ruszamy
if (-not ($tree.PSObject.Properties.Name -contains 'weights_9D')) {
    $tree | Add-Member -NotePropertyName 'weights_9D' -NotePropertyValue @(
        @{ id = "CISZA-WYDECH";        k_base = 1.0 }
        @{ id = "PLAN-PAUZA";          k_base = 1.0 }
        @{ id = "RDZEN-PERYFERIA";     k_base = 1.0 }
        @{ id = "WIOSKA-MIASTO";       k_base = 1.0 }
        @{ id = "OSTRZE-CIERPLIWOSC";  k_base = 1.0 }
        @{ id = "LOCUS-MEDIUM-MANDAT"; k_base = 1.0 }
        @{ id = "HUMAN-AI‡";           k_base = 1.0 }
        @{ id = "PROG-PRZEJSCIE";      k_base = 1.0 }
        @{ id = "SEMANTYKA-ENERGIA";   k_base = 1.0 }
    ) -Force
}

# mapa: MOST -> k_base
$weightMap = @{}
foreach ($w in $tree.weights_9D) {
    $weightMap[$w.id] = [double]$w.k_base
}

# --- 2. Skan katalogu root w poszukiwaniu repo ----------------------------

Write-Host ""
Write-Host "Skanuję katalog w poszukiwaniu repozytoriów..."

$knownRepos = @{
    "chunk-chunk"           = @{ role = "protocol_core";     most = "SEMANTYKA-ENERGIA" }
    "glitchlab"             = @{ role = "image_mosaic_gui";  most = "HUMAN-AI‡" }
    "swarm"                 = @{ role = "orchestrator";      most = "WIOSKA-MIASTO" }
    "HA2D"                  = @{ role = "analysis_engine";   most = "OSTRZE-CIERPLIWOSC" }
    "hipotezy_nadawcze_LLM" = @{ role = "theory_spec";       most = "PLAN-PAUZA" }
}

$dirsScanned = 0
$repoNodes   = @()

Get-ChildItem -Path $RootPath -Directory -Recurse |
    Where-Object {
        $dirsScanned++
        (Test-Path (Join-Path $_.FullName ".git")) -or
        (Test-Path (Join-Path $_.FullName ".glx"))
    } |
    ForEach-Object {
        $name = Split-Path $_.FullName -Leaf

        if ($name -eq "QV9D") { return }

        $repoInfo = $knownRepos[$name]
        if (-not $repoInfo) {
            $repoInfo = @{ role = "unknown"; most = "RDZEN-PERYFERIA" }
        }

        $most   = $repoInfo.most
        $role   = $repoInfo.role
        $weight = if ($weightMap.ContainsKey($most)) { $weightMap[$most] } else { 1.0 }

        $node = [PSCustomObject]@{
            id    = "REPO_$name"
            kind  = "repo"
            label = $name
            role  = $role
            path  = (Resolve-Path $_.FullName).Path
            most  = $most
            weight_9D = @{
                base = $weight
            }
        }

        $repoNodes += $node

        Write-Host ("  - znaleziono repo: {0} (MOST={1}, k={2})" -f $name, $most, $weight)
    }

# --- 3. Aktualizacja węzłów i metryk --------------------------------------

$tree.nodes = @($repoNodes)

$tree.metrics.last_scan.repos_found  = $repoNodes.Count
$tree.metrics.last_scan.dirs_scanned = $dirsScanned
$tree.metrics.last_scan.timestamp    = (Get-Date).ToString("o")

$tree | Add-Member -NotePropertyName 'generated_at' -NotePropertyValue (Get-Date).ToString("o") -Force

# --- 4. Zapis tree.json ----------------------------------------------------

$tree | ConvertTo-Json -Depth 10 | Out-File -FilePath $treePath -Encoding UTF8

Write-Host ""
Write-Host "Zapisuję mozaikę repozytoriów do:"
Write-Host "  $treePath"

# --- 5. Rejestr generacji --------------------------------------------------

if (-not (Test-Path $logPath)) {
    @"
# QV9D_rejestr_generacji.md
Rejestr generacji / skanów woluminu 9D (GLX / chunk-chunk / glitchlab / swarm / HA2D / hipotezy_nadawcze_LLM)

| Data / czas (UTC+1) | Narzędzie  | Repos | Dirs | Decyzja dokumentacyjna | Komentarz |
|---------------------|-----------|-------|------|------------------------|-----------|
"@ | Out-File -FilePath $logPath -Encoding UTF8
}

$now = Get-Date
$line = "| {0} | Scan-9D.ps1 | {1} | {2} | AUTO-DOC | skan struktury repo |" -f `
    $now.ToString("yyyy-MM-dd HH:mm:ss"), `
    $repoNodes.Count, `
    $dirsScanned

Add-Content -Path $logPath -Value $line

Write-Host "Zaktualizowano QV9D_rejestr_generacji.md"
Write-Host ""
Write-Host "=== QV9D: skan zakończony. ==="
