$ErrorActionPreference='Stop'
Set-StrictMode -Version 2
$Desktop=[Environment]::GetFolderPath('Desktop')
$Installer=Join-Path $Desktop 'Repair-LION-R20-ISE.ps1'
$Root=Join-Path $env:LOCALAPPDATA 'LION'
$Broker=Join-Path $Root 'browser_broker'
$Profile=Join-Path $Root 'r19-browser-broker'
$FinalBackup=Join-Path $Root 'backups\r20-panel-saas\final'
$Node='C:\Program Files\nodejs\node.exe'
$PanelRoot='C:\Users\d2j3\Documents\Codex\2026-09-14\files-pasted-by-the-user-role\work\lion-r2-panel-runtime\node_panel'
$RelayState='C:\Users\d2j3\Documents\Codex\2026-09-13\r10-r2-unified\runtime\node-secure-mcp-relay'

if(-not (Test-Path -LiteralPath $Installer)){throw 'R20 installer missing'}
if(-not (Test-Path -LiteralPath (Join-Path $FinalBackup 'browser.cjs.pre-send-fix'))){throw 'R20 final backup missing'}

# Roll back installer-owned browser sources/config/credential first.
& $Installer -Rollback

# Stop only broker-owned Electron before restoring the later browser adapter delta.
$electron=[IO.Path]::GetFullPath((Join-Path $Broker 'node_modules\electron\dist\electron.exe'))
$owned=@()
foreach($p in (Get-CimInstance Win32_Process -Filter "Name='electron.exe'" -ErrorAction SilentlyContinue)){
  $exe=[string]$p.ExecutablePath
  $cmd=[string]$p.CommandLine
  if(($exe -and ([IO.Path]::GetFullPath($exe)-eq $electron)) -or ($cmd -and $cmd.IndexOf($Broker,[StringComparison]::OrdinalIgnoreCase)-ge 0)){$owned += [int]$p.ProcessId}
}
foreach($processId in ($owned|Sort-Object -Unique)){Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue}

Copy-Item -LiteralPath (Join-Path $FinalBackup 'browser.cjs.pre-send-fix') -Destination (Join-Path $Broker 'src\browser.cjs') -Force
Remove-Item -LiteralPath (Join-Path $Broker 'test\browser.test.cjs') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $Profile 'thread-scope.json') -Force -ErrorAction SilentlyContinue

# Restore the pre-R20 active Node secure-MCP producer.
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match 'node_panel\\src\\secure-mcp-relay\.js' } | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Copy-Item -LiteralPath (Join-Path $FinalBackup 'secure-mcp-relay.js.pre-r20') -Destination (Join-Path $PanelRoot 'src\secure-mcp-relay.js') -Force
Copy-Item -LiteralPath (Join-Path $FinalBackup 'relay.test.js.pre-r20') -Destination (Join-Path $PanelRoot 'test\relay.test.js') -Force

# Restore the pre-R20 WSL turn-ingress source and service.
& wsl.exe -d Ubuntu-24.04 -u root -- sh -lc 'test -f /opt/lion/lion-turn-ingress-node-r2/server.mjs.r20-backup && cp /opt/lion/lion-turn-ingress-node-r2/server.mjs.r20-backup /opt/lion/lion-turn-ingress-node-r2/server.mjs && chown root:root /opt/lion/lion-turn-ingress-node-r2/server.mjs && chmod 0644 /opt/lion/lion-turn-ingress-node-r2/server.mjs && systemctl restart lion-turn-ingress-node-r2.service'
if($LASTEXITCODE -ne 0){throw 'WSL ingress rollback failed'}

# Start the restored Node relay with the same bounded runtime arguments.
$relayScript=Join-Path $PanelRoot 'src\secure-mcp-relay.js'
$argLine=(
 '"' + $relayScript + '"' +
 ' --broker "http://127.0.0.1:8766"' +
 ' --ingress "http://127.0.0.1:8791"' +
 ' --tunnel "http://127.0.0.1:8792"' +
 ' --mediator-key-file "' + (Join-Path $RelayState 'saas-mediator.dpapi') + '"' +
 ' --ingress-token-file "' + (Join-Path $RelayState 'secure-mcp-ingress.dpapi') + '"' +
 ' --state-dir "' + $RelayState + '"' +
 ' --legacy-turn-map "' + (Join-Path $RelayState 'legacy-turn-map.json') + '"' +
 ' --interval-ms "1000"'
)
$relay=Start-Process -FilePath $Node -ArgumentList $argLine -WorkingDirectory $PanelRoot -WindowStyle Hidden -PassThru

# Start restored browser broker. It starts STOPPED by design.
& (Join-Path $Broker 'Start-LION-Browser-ISE.ps1')
Write-Output ('R20_FINAL_ROLLBACK=PASS relay_pid='+$relay.Id)
