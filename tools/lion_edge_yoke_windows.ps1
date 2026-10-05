[CmdletBinding()]
param(
    [ValidateSet('Prepare','Test','Demo','Init','Watch','State','R24Pilot')][string]$Action = 'Test',
    [string]$PythonExe = '',
    [string]$YokeHome = "$env:LOCALAPPDATA\LION\EdgeYokeR6\MOON",
    [string]$Output = '',
    [string]$DockerExe = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe',
    [switch]$InstallDependencies,
    [switch]$LocalModel
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Invoke-LionNative {
    param([scriptblock]$Command, [string]$Failure)
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Command
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($code -ne 0) { throw "$Failure (exit $code)" }
}
$Repo = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Repo '.venv-edge-yoke\Scripts\python.exe'
if ($Action -eq 'Prepare') {
    if (-not $PythonExe) { $PythonExe = 'python' }
    Invoke-LionNative { & $PythonExe -c 'import sys; assert sys.version_info >= (3, 12), sys.version; print(sys.executable)' } 'Python 3.12+ required; provide -PythonExe with an actual executable path.'
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        Invoke-LionNative { & $PythonExe -m venv (Join-Path $Repo '.venv-edge-yoke') } 'Could not create component venv. Existing project .venv was not changed.'
    }
    if ($InstallDependencies) {
        Invoke-LionNative { & $VenvPython -m pip install -r (Join-Path $Repo 'requirements\edge-yoke.txt') } 'Dependency installation failed.'
    }
    Invoke-LionNative { & $VenvPython -c 'import psutil,cryptography; print("Dependencies available")' } 'Use reviewed offline wheels or the explicit -InstallDependencies option.'
    Write-Host "Prepared repository component interpreter: $VenvPython"
    return
}
if (-not $PythonExe) { $PythonExe = $VenvPython }
if (-not (Test-Path -LiteralPath $PythonExe)) { throw 'Run Prepare first or supply an existing -PythonExe.' }
Push-Location $Repo
try {
    if ($Action -eq 'Test') {
        Invoke-LionNative { & $PythonExe -B -m unittest discover -s cyber_lion/tests -p 'test_edge_*.py' -v } 'Tests failed; do not continue.'
        Write-Host 'Windows qualification: six Linux/R5 storage integration cases are explicitly skipped, not counted as Windows PASS. Run them in Ubuntu/Docker before live integration.'
        return
    }
    $Entry = Join-Path $Repo 'tools\lion_edge_yoke.py'
    switch ($Action) {
        'Init'  { $Arguments = @($Entry,'init','--home',$YokeHome,'--host-id','MOON') }
        'Watch' { $Arguments = @($Entry,'watch','--home',$YokeHome) }
        'State' { $Arguments = @($Entry,'state','--home',$YokeHome) }
        'Demo' {
            if (-not $Output) { $Output = Join-Path $env:LOCALAPPDATA ("LION\EdgeR6Runs\native-" + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')) }
            $Arguments = @($Entry,'demo','--host-id','MOON','--output',$Output)
            if ($LocalModel) { $Arguments += @('--model-endpoint','http://127.0.0.1:8772') }
        }
        'R24Pilot' {
            if (-not $Output) { $Output = Join-Path $env:LOCALAPPDATA ("LION\EdgeR6Runs\r24-" + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')) }
            $Arguments = @($Entry,'r24-pilot','--home',$YokeHome,'--docker-exe',$DockerExe,'--output',$Output)
            if ($LocalModel) { $Arguments += '--local-model' }
        }
    }
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $PythonExe -B @Arguments
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($code -ne 0 -and $code -ne 130) { throw "Operation rejected/failed ($code). Preserve output; do not retry an unknown effect blindly." }
    if ($Output) { Write-Host "Readback: $Output\PILOT_RECEIPT.json" }
} finally { Pop-Location }
