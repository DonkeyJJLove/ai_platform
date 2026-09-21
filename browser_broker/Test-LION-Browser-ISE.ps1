# Otworz w Windows PowerShell ISE i nacisnij F5. Tylko odczyt stanu.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
$LionProfile = Join-Path $env:LOCALAPPDATA 'LION\r19-browser-broker'
$LionControlFile = Join-Path $LionProfile 'control.key'
$LionReportFile = Join-Path $LionProfile 'diagnostic-r19-live.json'
if (-not (Test-Path -LiteralPath $LionControlFile -PathType Leaf)) {
    throw 'Brak profilu uruchomionego brokera. Uruchom Start-LION-Browser-ISE.ps1.'
}
$LionControl = (Get-Content -LiteralPath $LionControlFile -Raw).Trim()
$LionHeaders = @{ Authorization = 'Bearer ' + $LionControl }
try {
    $LionStatus = Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8793/v1/status' -Headers $LionHeaders -TimeoutSec 10
    $LionJson = $LionStatus | ConvertTo-Json -Depth 12
    [System.IO.File]::WriteAllText($LionReportFile, $LionJson, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host $LionJson
    Write-Host ('Raport bez wartosci kluczy: ' + $LionReportFile)
} catch {
    Write-Host 'Nie odczytano stanu uruchomionego brokera na porcie 8793.'
    throw 'Sprawdz, czy okno LION Broker pozostaje otwarte. Nie wznowiono kolejki.'
} finally {
    $LionHeaders.Clear()
    Remove-Variable LionControl -ErrorAction SilentlyContinue
}
