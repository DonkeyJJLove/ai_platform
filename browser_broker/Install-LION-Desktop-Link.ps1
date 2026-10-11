# LION native Electron desktop shortcut. Read-only preview is the default.
# Only explicit -Apply writes a .lnk in the current operator's Desktop folder.
# This does not start services, launch Electron, elevate privileges, alter
# Windows execution policy, create startup tasks or open a web browser.
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$ReplaceExisting,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9 _.-]{0,79}$')]
    [string]$ShortcutName = 'LION - LPCL Panel'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

if ($env:OS -ne 'Windows_NT') { throw 'Native Windows PowerShell is required for the desktop shortcut.' }
$LionAppRoot = $PSScriptRoot
if (-not $LionAppRoot) { throw 'Run this script from the installed browser_broker directory.' }
$LionLauncher = Join-Path $LionAppRoot 'Start-LION-Browser-ISE.ps1'
$LionManifest = Join-Path $LionAppRoot 'package.json'
$LionMain = Join-Path $LionAppRoot 'src\main.cjs'
foreach ($LionFile in @($LionLauncher,$LionManifest,$LionMain)) {
    if (-not (Test-Path -LiteralPath $LionFile -PathType Leaf)) {
        throw ('Incomplete LION Electron package: ' + $LionFile)
    }
}
$LionLauncher = (Resolve-Path -LiteralPath $LionLauncher).ProviderPath
$LionAppRoot = (Resolve-Path -LiteralPath $LionAppRoot).ProviderPath

$LionDesktop = [Environment]::GetFolderPath('DesktopDirectory')
if (-not $LionDesktop -or -not (Test-Path -LiteralPath $LionDesktop -PathType Container)) {
    throw 'Operator Desktop folder is not available.'
}
$LionLink = Join-Path $LionDesktop ($ShortcutName + '.lnk')
$LionPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $LionPowerShell -PathType Leaf)) {
    throw ('Windows PowerShell executable not available: ' + $LionPowerShell)
}
$LionArgs = '-NoLogo -NoProfile -File "' + $LionLauncher + '"'
$LionShell = New-Object -ComObject WScript.Shell
$LionExisting = Test-Path -LiteralPath $LionLink -PathType Leaf
$LionExistingCorrect = $false
if ($LionExisting) {
    $LionOld = $LionShell.CreateShortcut($LionLink)
    $LionExistingCorrect = (
        [string]::Equals($LionOld.TargetPath,$LionPowerShell,[StringComparison]::OrdinalIgnoreCase) -and
        [string]::Equals($LionOld.Arguments,$LionArgs,[StringComparison]::Ordinal) -and
        [string]::Equals($LionOld.WorkingDirectory,$LionAppRoot,[StringComparison]::OrdinalIgnoreCase)
    )
}
$LionResult = [ordered]@{
    schema = 'lion.electron-desktop-entrypoint/v1'
    shortcut = $LionLink
    launcher = $LionLauncher
    target = $LionPowerShell
    working_directory = $LionAppRoot
    existing = $LionExisting
    existing_correct = $LionExistingCorrect
    apply_requested = [bool]$Apply
    application_started = $false
    startup_task_created = $false
    browser_url_shortcut = $false
    authority_effect = 'NONE'
}
if ($Apply) {
    if ($LionExisting -and -not $LionExistingCorrect -and -not $ReplaceExisting) {
        throw 'Existing shortcut differs; inspect preview and explicitly run -Apply -ReplaceExisting to rebind.'
    }
    $LionShortcut = $LionShell.CreateShortcut($LionLink)
    $LionShortcut.TargetPath = $LionPowerShell
    $LionShortcut.Arguments = $LionArgs
    $LionShortcut.WorkingDirectory = $LionAppRoot
    $LionShortcut.Description = 'LION Electron - Mission Control left, LPCL Panel/SaaS right'
    $LionShortcut.WindowStyle = 1
    $LionShortcut.Save()

    # Independent native Windows .lnk readback; does not start Electron.
    $LionReadback = $LionShell.CreateShortcut($LionLink)
    if (
        -not [string]::Equals($LionReadback.TargetPath,$LionPowerShell,[StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals($LionReadback.Arguments,$LionArgs,[StringComparison]::Ordinal) -or
        -not [string]::Equals($LionReadback.WorkingDirectory,$LionAppRoot,[StringComparison]::OrdinalIgnoreCase)
    ) {
        throw 'Desktop shortcut readback mismatch. The application was not started.'
    }
    $LionResult['result'] = 'DESKTOP_SHORTCUT_VERIFIED'
} else {
    $LionResult['result'] = 'PREVIEW_ONLY'
}
$LionResult | ConvertTo-Json -Compress -Depth 4
