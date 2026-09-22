param([switch]$Rollback)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
$TaskId = 'LION-R20-SOL-L64-W8-PANEL-SAAS-REPAIR-R1'
$Root = Join-Path $env:LOCALAPPDATA 'LION'
$Broker = Join-Path $Root 'browser_broker'
$Profile = Join-Path $Root 'r19-browser-broker'
$PatchZip = Join-Path $PSScriptRoot 'LION-R20-browser-broker-patch.zip'
$BackupRoot = Join-Path $Root 'backups\r20-panel-saas'
$SecretDir = Join-Path $Root 'secrets'
$SecretFile = Join-Path $SecretDir 'mcp-local-token'
$Pointer = Join-Path $BackupRoot 'latest.txt'
$backup = $null
$InstallMutated = $false
$Report = [ordered]@{
  schema='lion.r20.windows-installer-report/v1'; task_id=$TaskId;
  observed_at=(Get-Date).ToUniversalTime().ToString('o'); result='STARTED';
  broker=$Broker; profile=$Profile; ingress='http://127.0.0.1:8791';
  ingress_auth=$false; ingress_unauth_denied=$false; broker_started=$false;
  broker_ingress_credential_present=$false; binding_state='UNKNOWN';
  backup=$null; patch_sha256=$null; rollback_available=$false; error=$null
}
function Write-Report {
  $desktop=[Environment]::GetFolderPath('Desktop')
  $path=Join-Path $desktop ('LION-R20-install-report-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
  [IO.File]::WriteAllText($path,($Report|ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
  Write-Host ('Raport: ' + $path)
}
function Hash-File([string]$Path) {
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Stop-BrokerOwnedElectron {
  $electron = [IO.Path]::GetFullPath((Join-Path $Broker 'node_modules\electron\dist\electron.exe'))
  $owned=@()
  foreach($p in (Get-CimInstance Win32_Process -Filter "Name='electron.exe'" -ErrorAction SilentlyContinue)) {
    $exe=[string]$p.ExecutablePath
    $cmd=[string]$p.CommandLine
    if (($exe -and ([IO.Path]::GetFullPath($exe) -eq $electron)) -or ($cmd -and $cmd.IndexOf($Broker,[StringComparison]::OrdinalIgnoreCase) -ge 0)) {
      $owned += [int]$p.ProcessId
    }
  }
  foreach($processId in ($owned|Sort-Object -Unique)) { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue }
  return @($owned|Sort-Object -Unique)
}
function Restart-Broker {
  $launcher=Join-Path $Broker 'Start-LION-Browser-ISE.ps1'
  if(-not (Test-Path -LiteralPath $launcher -PathType Leaf)){throw 'Brak launchera browser_broker.'}
  & $launcher
}
try {
  New-Item -ItemType Directory -Force -Path $BackupRoot,$SecretDir,$Profile | Out-Null
  if($Rollback) {
    if(-not (Test-Path -LiteralPath $Pointer)){throw 'Brak wskaźnika backupu R20.'}
    $b=(Get-Content -LiteralPath $Pointer -Raw).Trim()
    if(-not (Test-Path -LiteralPath $b -PathType Container)){throw 'Backup R20 nie istnieje.'}
    $meta=Get-Content -LiteralPath (Join-Path $b 'backup.json') -Raw | ConvertFrom-Json
    Stop-BrokerOwnedElectron | Out-Null
    foreach($f in $meta.files) {
      $from=Join-Path $b $f.path
      $to=Join-Path $Broker $f.path
      Copy-Item -LiteralPath $from -Destination $to -Force
    }
    if($meta.services_existed) { Copy-Item -LiteralPath (Join-Path $b 'services.json') -Destination (Join-Path $Profile 'services.json') -Force }
    else { Remove-Item -LiteralPath (Join-Path $Profile 'services.json') -Force -ErrorAction SilentlyContinue }
    if($meta.secret_existed) { Copy-Item -LiteralPath (Join-Path $b 'mcp-local-token') -Destination $SecretFile -Force }
    else { Remove-Item -LiteralPath $SecretFile -Force -ErrorAction SilentlyContinue }
    Restart-Broker
    $Report.result='ROLLED_BACK'
    $Report.backup=$b
    $Report.rollback_available=$true
    Write-Report
    return
  }

  if(-not (Test-Path -LiteralPath $PatchZip -PathType Leaf)){throw 'Brak LION-R20-browser-broker-patch.zip obok instalatora.'}
  if(-not (Test-Path -LiteralPath $Broker -PathType Container)){throw 'Nie znaleziono istniejącego browser_broker.'}
  $main=Join-Path $Broker 'src\main.cjs'
  if((Hash-File $main) -ne 'bbbb5bd22e6346fb0721e37d4c2c554e29d7e076aca47435549eb6d58012cb0e'){throw 'main.cjs nie odpowiada zweryfikowanemu fix4; instalacja zatrzymana.'}
  $Report.patch_sha256=Hash-File $PatchZip

  $stage=Join-Path $env:TEMP ('lion-r20-' + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force -Path $stage | Out-Null
  Expand-Archive -LiteralPath $PatchZip -DestinationPath $stage -Force
  $manifest=Get-Content -LiteralPath (Join-Path $stage 'R20-SOURCE-MANIFEST.json') -Raw | ConvertFrom-Json
  if($manifest.task_id -ne $TaskId){throw 'Manifest TASK_ID mismatch.'}
  foreach($f in $manifest.files) {
    $candidate=Join-Path $stage $f.path
    if((Hash-File $candidate) -ne $f.new_sha256){throw ('Patch hash mismatch: '+$f.path)}
    $current=Join-Path $Broker $f.path
    $h=Hash-File $current
    if($h -ne $f.required_pre_sha256 -and $h -ne $f.new_sha256){throw ('Nieoczekiwany drift przed instalacją: '+$f.path)}
  }

  $distros=@(& wsl.exe -l -q 2>$null | ForEach-Object { (([string]$_) -replace ([char]0),'').Trim() } | Where-Object { $_ })
  $Distro=$null
  foreach($d in $distros) {
    $probe=& wsl.exe -d $d -u root -- sh -lc 'test -r /etc/lion/mcp-local-token && test -r /etc/systemd/system/lion-turn-ingress-node-r2.service && grep -q "LION_INGRESS_TOKEN_FILE=/etc/lion/mcp-local-token" /etc/systemd/system/lion-turn-ingress-node-r2.service && printf R20_OK' 2>$null
    if(((($probe|Out-String) -replace ([char]0),'').Trim()) -eq 'R20_OK'){$Distro=$d;break}
  }
  # WSL service credential is 0640 root:lion-mcp; use root only for this local read/probe. No WSL permission or secret mutation occurs.
  if(-not $Distro){throw 'Nie znaleziono distro WSL z czytelnym, istniejącym credentialem lion-turn-ingress-node-r2.'}
  $Token=(((& wsl.exe -d $Distro -u root -- cat /etc/lion/mcp-local-token 2>$null | Out-String) -replace ([char]0),'').Trim())
  if($LASTEXITCODE -ne 0 -or $Token.Length -lt 32){throw 'Nie można odczytać istniejącego credentialu ingress przez konto sentinelx.'}

  $state=Invoke-RestMethod -Uri 'http://127.0.0.1:8791/v1/state' -Headers @{'X-LION-Token'=$Token} -Method Get -TimeoutSec 5
  if($null -eq $state.seq -or [int64]$state.seq -lt 0){throw 'Ingress zwrócił nieoczekiwany schemat /v1/state.'}
  $Report.ingress_auth=$true
  try {
    Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8791/v1/state' -Method Get -TimeoutSec 5 | Out-Null
  } catch {
    try { if([int]$_.Exception.Response.StatusCode -eq 401){$Report.ingress_unauth_denied=$true} } catch {}
  }

  $stamp=(Get-Date -Format 'yyyyMMdd-HHmmss')
  $backup=Join-Path $BackupRoot $stamp
  New-Item -ItemType Directory -Force -Path $backup | Out-Null
  $bfiles=@()
  foreach($f in $manifest.files) {
    $from=Join-Path $Broker $f.path
    $to=Join-Path $backup $f.path
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $to) | Out-Null
    Copy-Item -LiteralPath $from -Destination $to -Force
    $bfiles += [ordered]@{path=[string]$f.path;sha256=Hash-File $from}
  }
  $services=Join-Path $Profile 'services.json'
  $servicesExisted=Test-Path -LiteralPath $services -PathType Leaf
  if($servicesExisted){Copy-Item -LiteralPath $services -Destination (Join-Path $backup 'services.json') -Force}
  $secretExisted=Test-Path -LiteralPath $SecretFile -PathType Leaf
  if($secretExisted){Copy-Item -LiteralPath $SecretFile -Destination (Join-Path $backup 'mcp-local-token') -Force}
  $bm=[ordered]@{schema='lion.r20.backup/v1';task_id=$TaskId;created_at=(Get-Date).ToUniversalTime().ToString('o');files=$bfiles;services_existed=$servicesExisted;secret_existed=$secretExisted}
  [IO.File]::WriteAllText((Join-Path $backup 'backup.json'),($bm|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
  Set-Content -LiteralPath $Pointer -Value $backup -Encoding UTF8
  $Report.backup=$backup
  $Report.rollback_available=$true
  $InstallMutated=$true

  $utf8=[Text.UTF8Encoding]::new($false)
  [IO.File]::WriteAllText($SecretFile,($Token+[Environment]::NewLine),$utf8)
  $acl=New-Object Security.AccessControl.FileSecurity
  $acl.SetAccessRuleProtection($true,$false)
  $me=[Security.Principal.WindowsIdentity]::GetCurrent().Name
  $acl.SetOwner((New-Object Security.Principal.NTAccount($me)))
  $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($me,'FullControl','Allow')))
  $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule('NT AUTHORITY\SYSTEM','FullControl','Allow')))
  Set-Acl -LiteralPath $SecretFile -AclObject $acl

  Stop-BrokerOwnedElectron | Out-Null
  foreach($f in $manifest.files) {
    $from=Join-Path $stage $f.path
    $to=Join-Path $Broker $f.path
    Copy-Item -LiteralPath $from -Destination $to -Force
    if((Hash-File $to) -ne $f.new_sha256){throw ('Readback hash mismatch: '+$f.path)}
  }

  $node=(Get-Command node.exe -ErrorAction Stop).Source
  $nodeRc=0
  Push-Location $Broker
  try {
    & $node --test 'test\relay.test.cjs' 'test\thread-consumer.test.cjs'
    $nodeRc=$LASTEXITCODE
  } finally { Pop-Location }
  if($nodeRc -ne 0) {
    foreach($f in $manifest.files) {
      Copy-Item -LiteralPath (Join-Path $backup $f.path) -Destination (Join-Path $Broker $f.path) -Force
    }
    Restart-Broker
    throw ('Natywne testy browser_broker nie przeszły, exit=' + $nodeRc + '. Przywrócono poprzednie pliki.')
  }
  $Report['browser_tests']='PASS'

  $svcObj=[ordered]@{}
  if($servicesExisted){
    $old=Get-Content -LiteralPath $services -Raw | ConvertFrom-Json
    foreach($prop in $old.PSObject.Properties){$svcObj[$prop.Name]=$prop.Value}
  }
  $svcObj['ingress_token_file']=$SecretFile
  $tmp=$services+'.r20.tmp'
  [IO.File]::WriteAllText($tmp,($svcObj|ConvertTo-Json -Depth 8),$utf8)
  Move-Item -LiteralPath $tmp -Destination $services -Force

  Restart-Broker
  $Report.broker_started=$true
  $control=Join-Path $Profile 'control.key'
  $deadline=(Get-Date).AddSeconds(40)
  $status=$null
  while((Get-Date) -lt $deadline) {
    if(Test-Path -LiteralPath $control){
      try {
        $ck=(Get-Content -LiteralPath $control -Raw).Trim()
        $status=Invoke-RestMethod -Uri 'http://127.0.0.1:8793/v1/status' -Headers @{Authorization=('Bearer '+$ck)} -Method Get -TimeoutSec 5
        if($status){break}
      } catch {}
    }
    Start-Sleep -Milliseconds 500
  }
  if(-not $status){throw 'Broker nie odpowiedział na uwierzytelniony /v1/status po instalacji.'}
  if($status.schema -ne 'lion.browser-broker.status/v1'){throw 'Broker status schema mismatch.'}
  if(-not $status.ingress_credential_present){throw 'Broker działa, ale nie załadował credentialu ingress.'}
  $Report.broker_ingress_credential_present=$true
  $Report.binding_state=[string]$status.relay.state
  $Report.browser_state=[string]$status.browser.state
  $Report.conversation_route=[string]$status.conversation.route
  $Report.result='BROKER_AUTH_READY_BIND_PENDING'
  Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
  Write-Report
  Write-Host 'R20: ingress auth i broker zostały zainstalowane i odczytane. Kolejka pozostaje zatrzymana; teraz można wykonać świeży bind/wątek bez wysyłania historycznych żądań.'
}
catch {
  $PrimaryError=$_.Exception.Message
  $Report.result='FAILED'
  $Report.error=$PrimaryError
  if($InstallMutated -and $backup -and (Test-Path -LiteralPath (Join-Path $backup 'backup.json'))) {
    try {
      $meta=Get-Content -LiteralPath (Join-Path $backup 'backup.json') -Raw | ConvertFrom-Json
      Stop-BrokerOwnedElectron | Out-Null
      foreach($f in $meta.files) {
        Copy-Item -LiteralPath (Join-Path $backup $f.path) -Destination (Join-Path $Broker $f.path) -Force
      }
      $services=Join-Path $Profile 'services.json'
      if($meta.services_existed) { Copy-Item -LiteralPath (Join-Path $backup 'services.json') -Destination $services -Force }
      else { Remove-Item -LiteralPath $services -Force -ErrorAction SilentlyContinue }
      if($meta.secret_existed) { Copy-Item -LiteralPath (Join-Path $backup 'mcp-local-token') -Destination $SecretFile -Force }
      else { Remove-Item -LiteralPath $SecretFile -Force -ErrorAction SilentlyContinue }
      Restart-Broker
      $Report['auto_rollback']='PASS'
    } catch {
      $Report['auto_rollback']='FAILED: '+$_.Exception.Message
    }
  }
  try { Write-Report } catch {}
  throw $PrimaryError
}
