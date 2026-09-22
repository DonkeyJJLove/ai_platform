# Uruchamianie: otworz ten plik w Windows PowerShell ISE i nacisnij F5.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
$LionAppRoot = $PSScriptRoot
if (-not $LionAppRoot) { throw 'Zapisz i otworz skrypt z katalogu browser_broker w repozytorium.' }
$LionPackage = Join-Path $LionAppRoot 'package.json'
if (-not (Test-Path -LiteralPath $LionPackage)) { throw 'Brak package.json. Wymagany jest pelny katalog browser_broker.' }
$LionNode = (Get-Command node.exe -ErrorAction Stop).Source
$LionNpm = (Get-Command npm.cmd -ErrorAction Stop).Source
$LionVersion = & $LionNode -p 'process.versions.node'
if ($LASTEXITCODE -ne 0 -or [version]$LionVersion -lt [version]'22.13.0') { throw 'Wymagany Node.js >= 22.13.0.' }
$LionExpected = Get-Content -LiteralPath $LionPackage -Raw | ConvertFrom-Json
$LionElectronRoot = Join-Path $LionAppRoot 'node_modules\electron'
$LionElectron = Join-Path $LionElectronRoot 'dist\electron.exe'
$LionInstaller = Join-Path $LionElectronRoot 'install.js'
$LionNeedDependencies = $false
foreach ($LionDependency in @('electron', 'express')) {
    $LionInstalledManifest = Join-Path $LionAppRoot ('node_modules\' + $LionDependency + '\package.json')
    if (-not (Test-Path -LiteralPath $LionInstalledManifest -PathType Leaf)) {
        $LionNeedDependencies = $true
    } else {
        $LionInstalled = Get-Content -LiteralPath $LionInstalledManifest -Raw | ConvertFrom-Json
        if ($LionInstalled.version -ne $LionExpected.dependencies.$LionDependency) { $LionNeedDependencies = $true }
    }
}
if (-not (Test-Path -LiteralPath $LionInstaller -PathType Leaf)) { $LionNeedDependencies = $true }
Push-Location $LionAppRoot
try {
    if ($LionNeedDependencies) {
        Write-Host 'Instalowanie przypietych zaleznosci brokera. To moze potrwac kilka minut.'
        # W ISE stderr moze byc NativeCommandError; wynik ocenia kod wyjscia.
        $LionSavedPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $LionNpm ci --no-audit --no-fund
            $LionDependencyExitCode = $LASTEXITCODE
        } finally { $ErrorActionPreference = $LionSavedPreference }
        if ($LionDependencyExitCode -ne 0) { throw ('Instalacja npm nie powiodla sie, exit=' + $LionDependencyExitCode + '. Nie uruchomiono brokera.') }
    }
    if (-not (Test-Path -LiteralPath $LionInstaller -PathType Leaf)) { throw ('Brak instalatora Electron: ' + $LionInstaller) }
    # Electron 44 pobiera binaria oddzielnie od npm ci. Oficjalny instalator jest idempotentny.
    Write-Host ('Sprawdzanie / pobieranie Electron ' + $LionExpected.dependencies.electron + '. Pierwsze pobranie moze potrwac kilka minut.')
    $LionSavedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $LionNode $LionInstaller
        $LionBinaryExitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $LionSavedPreference }
    if ($LionBinaryExitCode -ne 0) { throw ('Instalator Electron zakonczyl sie bledem, exit=' + $LionBinaryExitCode + '. Szczegoly sa powyzej. Nie uruchomiono brokera.') }
    if (-not (Test-Path -LiteralPath $LionElectron -PathType Leaf)) { throw ('Instalator nie utworzyl pliku dla Windows: ' + $LionElectron + '. Sprawdz ustawienia platformy / katalogu Electron i wynik pobierania powyzej.') }
    $LionDistVersionPath = Join-Path $LionElectronRoot 'dist\version'
    if (-not (Test-Path -LiteralPath $LionDistVersionPath -PathType Leaf)) { throw 'Brak pliku wersji Electron. Nie uruchomiono brokera.' }
    $LionDistVersion = (Get-Content -LiteralPath $LionDistVersionPath -Raw).Trim().TrimStart('v')
    if ($LionDistVersion -ne $LionExpected.dependencies.electron) { throw 'Wersja binarna Electron nie zgadza sie z przypietym pakietem. Nie uruchomiono brokera.' }
    Write-Host ('Zweryfikowano plik: ' + $LionElectron)
    $env:LION_BROWSER_DATA = Join-Path $env:LOCALAPPDATA 'LION\r19-browser-broker'
    Write-Host ('Profil: ' + $env:LION_BROWSER_DATA)
    Write-Host 'Zaloguj sie w widoku SaaS. Menu LION > Stan / diagnostyka pokazuje wynik.'
    Write-Host 'Zamkniecie okna zatrzymuje ten komponent. Nie zmieniam uslug ani autostartu.'
    $LionProcess = Start-Process -FilePath $LionElectron -ArgumentList '.' -WorkingDirectory $LionAppRoot -PassThru
    Write-Host ('Uruchomiono proces Electron, PID=' + $LionProcess.Id + '. Kolejka startuje zatrzymana.')
} finally { Pop-Location }
