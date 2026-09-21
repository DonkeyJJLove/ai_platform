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
$LionElectron = Join-Path $LionAppRoot 'node_modules\electron\dist\electron.exe'
Push-Location $LionAppRoot
try {
    if (-not (Test-Path -LiteralPath $LionElectron)) {
        Write-Host 'Instalowanie przypietych zaleznosci brokera. To moze potrwac kilka minut.'
        & $LionNpm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'Instalacja zaleznosci nie powiodla sie. Nie uruchomiono brokera.' }
    }
    $env:LION_BROWSER_DATA = Join-Path $env:LOCALAPPDATA 'LION\r19-browser-broker'
    Write-Host ('Profil: ' + $env:LION_BROWSER_DATA)
    Write-Host 'Otwieram panel i sesje SaaS. Kolejka startuje zatrzymana; brak automatycznych zapytan.'
    Write-Host 'Zaloguj sie w widoku SaaS. Menu LION > Stan / diagnostyka pokazuje wynik.'
    Write-Host 'Zamkniecie okna zatrzymuje ten komponent. Nie zmieniam uslug ani autostartu.'
    Start-Process -FilePath $LionElectron -ArgumentList '.' -WorkingDirectory $LionAppRoot | Out-Null
} finally { Pop-Location }
