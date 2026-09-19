param(
    [switch]$Once,
    [string]$Repo = 'C:\Users\d2j3\Documents\Codex\2026-09-14\files-pasted-by-the-user-role\work\lion-r2-panel-runtime',
    [string]$Runtime = 'C:\Users\d2j3\Documents\Codex\2026-09-13\r10-r2-unified\runtime',
    [string]$Python = 'C:\Users\d2j3\AppData\Roaming\uv\python\cpython-3.13-windows-x86_64-none\python.exe',
    [string]$ModelRoot = 'C:\Users\d2j3\Documents\Codex\2026-09-10\napraw\outputs\moon-native',
    [string]$OperatorPanelProxyKey = 'C:\Users\d2j3\AppData\Local\LION\secrets\operator-panel-proxy.key',
    [string]$OperatorPairingKey = 'C:\Users\d2j3\AppData\Local\LION\secrets\operator-pairing.key'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$MatRuntime = Join-Path $Runtime 'mat12'
$ThreadDb = Join-Path $Runtime 'threads\lion-local-model.db'
$ModelExe = Join-Path $ModelRoot 'runtime\llama-b10809-vulkan\llama-server.exe'
$ModelFile = Join-Path $ModelRoot 'models\gpt-oss-20b-MXFP4.gguf'
$ExpectedModelSha = '27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901'
$ModelUrl = 'http://127.0.0.1:8772'
$MissionControlUrl = 'http://127.0.0.1:8766'
$OperatorControlUrl = 'http://127.0.0.1:8767'
$PanelUrl = 'http://127.0.0.1:8780'
$SupervisorLog = Join-Path $Runtime 'lion-control-plane-supervisor.log'
$SupervisorState = Join-Path $Runtime 'lion-control-plane-supervisor-state.json'
$Git = 'C:\Program Files\Git\cmd\git.exe'
$script:ModelHashVerified = $false

function Write-Log([string]$Message) {
    $line = ([DateTime]::UtcNow.ToString('o') + ' ' + $Message)
    Add-Content -LiteralPath $SupervisorLog -Value $line -Encoding utf8
}
function Listener([int]$Port) {
    return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
}
function Process-For-Port([int]$Port) {
    $n = Listener $Port
    if (-not $n) { return $null }
    return Get-CimInstance Win32_Process -Filter ('ProcessId=' + $n.OwningProcess)
}
function Wait-Http([string]$Url,[int]$Seconds=30) {
    $deadline=(Get-Date).AddSeconds($Seconds)
    do {
        try {
            $r=Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($r.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $false
}
function Test-OperatorControl {
    try {
        $r=Invoke-WebRequest -UseBasicParsing -Uri ($OperatorControlUrl + '/v1/participants') -TimeoutSec 5
        return $r.StatusCode -eq 200
    } catch {
        try {
            # An unauthenticated 403 is the expected healthy fail-closed surface.
            return [int]$_.Exception.Response.StatusCode -eq 403
        } catch {
            return $false
        }
    }
}
function Assert-RepoClean {
    if (-not (Test-Path -LiteralPath $Repo)) { throw 'PANEL_REPO_MISSING' }
    $status = @(& $Git -C $Repo status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw 'PANEL_REPO_GIT_FAILED' }
    if ($status.Count -ne 0) { throw 'PANEL_REPO_DIRTY_FAIL_CLOSED' }
    $head = (& $Git -C $Repo rev-parse HEAD).Trim()
    $tree = (& $Git -C $Repo rev-parse 'HEAD^{tree}').Trim()
    return @{head=$head;tree=$tree}
}
function Ensure-Model {
    $p=Process-For-Port 8772
    if ($p) {
        if ([IO.Path]::GetFullPath($p.ExecutablePath) -ne [IO.Path]::GetFullPath($ModelExe)) { throw 'PORT_8772_FOREIGN_PROCESS' }
        try { $null=Invoke-RestMethod -Uri ($ModelUrl + '/v1/models') -TimeoutSec 5 } catch { throw 'MODEL_8772_UNHEALTHY' }
        return [int]$p.ProcessId
    }
    if (-not (Test-Path -LiteralPath $ModelExe) -or -not (Test-Path -LiteralPath $ModelFile)) { throw 'MODEL_ARTIFACT_MISSING' }
    if (-not $script:ModelHashVerified) {
        $sha=(Get-FileHash -LiteralPath $ModelFile -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($sha -ne $ExpectedModelSha) { throw 'MODEL_SHA_MISMATCH' }
        $script:ModelHashVerified=$true
    }
    $stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
    $out=Join-Path $ModelRoot ('model-server-supervised-' + $stamp + '.stdout.log')
    $err=Join-Path $ModelRoot ('model-server-supervised-' + $stamp + '.stderr.log')
    $args=@('-m',('"'+$ModelFile+'"'),'--host','127.0.0.1','--port','8772','--device','Vulkan0','-ngl','99','-c','4096','-np','1','-n','384','--jinja','--reasoning-budget','0')
    $proc=Start-Process -FilePath $ModelExe -ArgumentList $args -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
    Write-Log ('MODEL_START pid=' + $proc.Id)
    if (-not (Wait-Http ($ModelUrl + '/v1/models') 75)) { throw 'MODEL_START_TIMEOUT' }
    return [int]$proc.Id
}
function Current-MatProcesses {
    $rows=@{}
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine -match 'lion_material_drone_worker\.py' -and $_.CommandLine -match [regex]::Escape($Repo) } | ForEach-Object {
        $m=[regex]::Match($_.CommandLine,'--drone-id\s+(MAT\d{2})')
        if($m.Success){$rows[$m.Groups[1].Value]=[int]$_.ProcessId}
    }
    return $rows
}
function Ensure-MatFleet {
    $rows=Current-MatProcesses
    if ($rows.Count -ne 12) {
        1..12 | ForEach-Object {
            $id=('MAT{0:D2}' -f $_)
            if (-not $rows.ContainsKey($id)) {
                Remove-Item -LiteralPath (Join-Path $MatRuntime ('health\'+$id+'.json')) -Force -ErrorAction SilentlyContinue
                Remove-Item -LiteralPath (Join-Path $MatRuntime ('pids\'+$id+'.pid')) -Force -ErrorAction SilentlyContinue
            }
        }
        $fleet=Join-Path $Repo 'tools\lion_material_fleet.py'
        $worker=Join-Path $Repo 'tools\lion_material_drone_worker.py'
        $raw=& $Python $fleet start --runtime-dir $MatRuntime --repo $Repo --worker $worker
        if ($LASTEXITCODE -ne 0) { throw 'MAT_FLEET_START_FAILED' }
        Write-Log ('MAT_START ' + ($raw -join ' '))
    }
    $fleet=Join-Path $Repo 'tools\lion_material_fleet.py'
    $raw=& $Python $fleet status --runtime-dir $MatRuntime
    if ($LASTEXITCODE -ne 0) { throw 'MAT_FLEET_STATUS_FAILED' }
    $status=($raw -join "`n") | ConvertFrom-Json
    if ([int]$status.healthy -ne 12 -or [int]$status.count -ne 12) { throw ('MAT_FLEET_NOT_READY healthy='+$status.healthy+' count='+$status.count) }
    return 12
}
function Ensure-MissionControl {
    if (Listener 8766) { return $true }
    try {
        $wsl='C:\Windows\System32\wsl.exe'
        & $wsl -d 'LION-AUTH-LAB' --exec /bin/true | Out-Null
        $deadline=(Get-Date).AddSeconds(45)
        do {
            Start-Sleep -Milliseconds 500
            if (Listener 8766) { Write-Log 'MISSION_CONTROL_8766_READY_AFTER_WSL_BOOT'; return $true }
        } while ((Get-Date) -lt $deadline)
    } catch { Write-Log ('WARN MISSION_CONTROL_BOOT ' + $_.Exception.Message) }
    Write-Log 'WARN MISSION_CONTROL_8766_DOWN'
    return $false
}
function Ensure-Panel([hashtable]$RepoIdentity) {
    if (-not (Test-OperatorControl)) { throw 'OPERATOR_CONTROL_8767_UNAVAILABLE' }
    $p=Process-For-Port 8780
    if ($p) {
        if ([IO.Path]::GetFullPath($p.ExecutablePath) -ne [IO.Path]::GetFullPath($Python)) { throw 'PORT_8780_FOREIGN_PROCESS' }
        if ($p.CommandLine -notmatch 'lion_local_intelligence_runtime\.py' -or $p.CommandLine -notmatch [regex]::Escape($Repo)) { throw 'PORT_8780_WRONG_RUNTIME' }
        if ($p.CommandLine -notmatch '--operator-panel-proxy-key-file' -or $p.CommandLine -notmatch [regex]::Escape($OperatorPanelProxyKey)) { throw 'PORT_8780_OPERATOR_BINDING_MISSING' }
        if ($p.CommandLine -notmatch '--operator-pairing-key-file' -or $p.CommandLine -notmatch [regex]::Escape($OperatorPairingKey)) { throw 'PORT_8780_OPERATOR_PAIRING_BINDING_MISSING' }
        if (-not (Wait-Http ($PanelUrl + '/') 5)) { throw 'PANEL_8780_UNHEALTHY' }
        return [int]$p.ProcessId
    }
    if (-not (Test-Path -LiteralPath $OperatorPanelProxyKey)) { throw 'OPERATOR_PANEL_PROXY_KEY_MISSING' }
    if (-not (Test-Path -LiteralPath $OperatorPairingKey)) { throw 'OPERATOR_PAIRING_KEY_MISSING' }
    $stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
    $out=Join-Path $Runtime ('supervised8780-' + $stamp + '.out.log')
    $err=Join-Path $Runtime ('supervised8780-' + $stamp + '.err.log')
    $args=@((Join-Path $Repo 'tools\lion_local_intelligence_runtime.py'),'--repo',$Repo,'--model',$ModelUrl,'--model-sha',$ExpectedModelSha,'--port','8780','--material-runtime-dir',$MatRuntime,'--thread-db',$ThreadDb,'--mission-control-url',$MissionControlUrl,'--operator-control-url',$OperatorControlUrl,'--operator-panel-proxy-key-file',$OperatorPanelProxyKey,'--operator-pairing-key-file',$OperatorPairingKey)
    $proc=Start-Process -FilePath $Python -ArgumentList $args -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
    Write-Log ('PANEL_START pid=' + $proc.Id + ' head=' + $RepoIdentity.head + ' operator_control=8767')
    if (-not (Wait-Http ($PanelUrl + '/') 30)) { throw 'PANEL_START_TIMEOUT' }
    return [int]$proc.Id
}
function Observe-OptionalFirefoxTransport {
    $p=Process-For-Port 8790
    if (-not $p) { return $false }
    if ($p.Name -eq 'node.exe' -and $p.CommandLine -and $p.CommandLine -match 'firefox-mediator-app' -and $p.CommandLine -match 'mediator\.js') {
        return $true
    }
    Write-Log ('WARN PORT_8790_PRESENT_BUT_NOT_LION_MEDIATOR pid=' + $p.ProcessId)
    return $false
}
function Write-State([hashtable]$RepoIdentity,[int]$ModelPid,[int]$PanelPid,[int]$MatHealthy,[bool]$FirefoxTransportActive) {
    $mc=[bool](Listener 8766)
    $operatorControl=[bool](Test-OperatorControl)
    $state=[ordered]@{
        observed_at=[DateTime]::UtcNow.ToString('o')
        status='READY'
        repo_head=$RepoIdentity.head
        repo_tree=$RepoIdentity.tree
        model_pid=$ModelPid
        panel_pid=$PanelPid
        mat_healthy=$MatHealthy
        mission_control_8766=$mc
        operator_control_8767=$operatorControl
        model_8772=$true
        panel_8780=$true
        legacy_browser_8790=$false
        browser_relay_active=$FirefoxTransportActive
        optional_model_transport_8790=$FirefoxTransportActive
        message_transport='LION_OPERATOR_MESSAGES'
        control_transport='SENTINELX_OPERATOR_CONTROL'
        panel_channel='LION_BUS'
        authority_effect='LOCAL_RUNTIME_SUPERVISION'
    }
    $tmp=$SupervisorState+'.tmp'
    $state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $tmp -Encoding utf8
    Move-Item -LiteralPath $tmp -Destination $SupervisorState -Force
}
function One-Pass {
    $repoIdentity=Assert-RepoClean
    $firefoxTransportActive=Observe-OptionalFirefoxTransport
    $modelPid=Ensure-Model
    $mat=Ensure-MatFleet
    $null=Ensure-MissionControl
    if (-not (Test-OperatorControl)) { throw 'OPERATOR_CONTROL_8767_UNAVAILABLE' }
    $panelPid=Ensure-Panel $repoIdentity
    Write-State $repoIdentity $modelPid $panelPid $mat $firefoxTransportActive
    $firefoxState=if($firefoxTransportActive){'OPTIONAL_ACTIVE'}else{'ABSENT'}
    Write-Log ('READY model=' + $modelPid + ' panel=' + $panelPid + ' bus=LION_OPERATOR_MESSAGES operator8767=READY browser8790=' + $firefoxState + ' mat=12 head=' + $repoIdentity.head)
}

if ($Once) {
    One-Pass
    Get-Content -LiteralPath $SupervisorState
    exit 0
}
Write-Log 'SUPERVISOR_START'
while ($true) {
    try { One-Pass }
    catch { Write-Log ('ERROR ' + $_.Exception.Message) }
    Start-Sleep -Seconds 15
}
