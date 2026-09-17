param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('ON','OFF','STATUS')]
    [string]$Action,
    [string]$Runtime = 'C:\Users\d2j3\Documents\Codex\2026-09-13\r10-r2-unified\runtime',
    [string]$Node = 'C:\Program Files\nodejs\node.exe'
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$App=Join-Path $Runtime 'firefox-mediator-app'
$Script=Join-Path $App 'mediator.js'
$StatusUrl='http://127.0.0.1:8790/status'
function Listener8790 { Get-NetTCPConnection -State Listen -LocalPort 8790 -ErrorAction SilentlyContinue | Select-Object -First 1 }
function ManagerProcess {
    $l=Listener8790
    if(-not $l){return $null}
    $p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$l.OwningProcess) -ErrorAction SilentlyContinue
    if(-not $p -or $p.Name -ne 'node.exe' -or -not $p.CommandLine -or $p.CommandLine -notmatch 'firefox-mediator-app' -or $p.CommandLine -notmatch 'mediator\.js'){throw 'PORT_8790_FOREIGN_PROCESS'}
    return $p
}
function ReadStatus {
    try { Invoke-RestMethod -Uri $StatusUrl -TimeoutSec 3 }
    catch { $null }
}
if($Action -eq 'STATUS'){
    $p=ManagerProcess;$s=ReadStatus
    [ordered]@{manager_running=[bool]$p;pid=if($p){[int]$p.ProcessId}else{$null};state=if($s){[string]$s.state}else{'ABSENT'};relay_active=if($s){[string]$s.state -notin @('DISABLED','STOPPED')}else{$false};authority_effect='OPERATOR_EXPLICIT_LEGACY_FALLBACK'} | ConvertTo-Json -Compress
    exit 0
}
if($Action -eq 'ON'){
    $existing=ManagerProcess
    if($existing){$s=ReadStatus;if($s -and $s.state -ne 'DISABLED'){throw 'LEGACY_BROWSER_MANAGER_NOT_DISABLED_AT_ENABLE'};Write-Output ('LEGACY_BROWSER_MANAGER_ALREADY_ON pid='+$existing.ProcessId);exit 0}
    if(-not (Test-Path -LiteralPath $Node) -or -not (Test-Path -LiteralPath $Script)){throw 'LEGACY_BROWSER_ARTIFACT_MISSING'}
    $stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
    $out=Join-Path $Runtime ('legacy-browser-manager-'+$stamp+'.out.log');$err=Join-Path $Runtime ('legacy-browser-manager-'+$stamp+'.err.log')
    $p=Start-Process -FilePath $Node -ArgumentList @($Script) -WorkingDirectory $App -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
    $deadline=(Get-Date).AddSeconds(30)
    do{Start-Sleep -Milliseconds 250;$s=ReadStatus;if($s -and $s.state -eq 'DISABLED'){Write-Output ('LEGACY_BROWSER_MANAGER_ON pid='+$p.Id+' relay=DISABLED');exit 0}}while((Get-Date)-lt$deadline)
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    throw 'LEGACY_BROWSER_MANAGER_START_TIMEOUT'
}
if($Action -eq 'OFF'){
    $p=ManagerProcess
    if(-not $p){Write-Output 'LEGACY_BROWSER_MANAGER_OFF already_absent=true';exit 0}
    try{Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8790/control/relay/off' -ContentType 'application/json' -Body '{}' -TimeoutSec 3 | Out-Null}catch{}
    Stop-Process -Id $p.ProcessId -Force
    $deadline=(Get-Date).AddSeconds(10);do{if(-not(Listener8790)){Write-Output ('LEGACY_BROWSER_MANAGER_OFF pid='+$p.ProcessId);exit 0};Start-Sleep -Milliseconds 200}while((Get-Date)-lt$deadline)
    throw 'LEGACY_BROWSER_MANAGER_STOP_TIMEOUT'
}
