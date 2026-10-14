[CmdletBinding()]
param(
 [ValidateSet('Inspect','Install')][string]$Mode='Inspect',
 [string]$LionRoot,
 [string]$DesktopPath,
 [string]$Approval=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not $LionRoot){
 if(-not $env:LOCALAPPDATA){throw 'LION_LOCALAPPDATA_REQUIRED'}
 $LionRoot=Join-Path $env:LOCALAPPDATA 'LION'
}
if(-not $DesktopPath){$DesktopPath=[Environment]::GetFolderPath('Desktop')}
$Root=[IO.Path]::GetFullPath($LionRoot)
$Source=Split-Path -Parent $MyInvocation.MyCommand.Path
$Operator=Join-Path $Root 'operator'
$Shortcut=if($DesktopPath){Join-Path $DesktopPath 'LION - panel i SaaS.lnk'}else{''}
$Files=@(
 @('Start-LION-Current.ps1','Start-LION-Current.ps1'),
 @('Start-LION.vbs','Start-LION.vbs')
)
$Candidate=Join-Path $Source 'PR454_CURRENT_RELEASE_EXAMPLE.json'
function Need($value,[string]$why){
 if(-not $value){throw ('LION_STABLE_SHORTCUT_'+$why)}
}
function Sha([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
Need (Test-Path -LiteralPath $Candidate -PathType Leaf) 'SOURCE_POINTER_MISSING'
Need (Test-Path -LiteralPath $Root -PathType Container) 'LION_ROOT_MISSING'
Need ($Shortcut -and (Test-Path -LiteralPath $Shortcut -PathType Leaf)) 'DESKTOP_SHORTCUT_NOT_FOUND'
$srcPointer=Get-Content -LiteralPath $Candidate -Raw -Encoding UTF8|ConvertFrom-Json
Need ($srcPointer.schema -ceq 'lion.desktop.operator-current-release/v1') 'BAD_SOURCE_POINTER_SCHEMA'
Need ($srcPointer.repository -ceq 'DonkeyJJLove/ai_platform') 'BAD_SOURCE_REPOSITORY'
$Witness=New-Object -ComObject WScript.Shell
$Old=$Witness.CreateShortcut($Shortcut)
$OldTarget=[string]$Old.TargetPath
$OldArgs=[string]$Old.Arguments
$ExpectedVbs=Join-Path $Operator 'Start-LION.vbs'
$LegacyVbs=Join-Path $Root 'staging\Start-LION-Current-R24.vbs'
Need ($OldTarget.EndsWith('\wscript.exe',[StringComparison]::OrdinalIgnoreCase)) 'UNKNOWN_SHORTCUT_TARGET'
$AlreadyStable=$OldArgs.Contains($ExpectedVbs)
Need ($AlreadyStable -or $OldArgs.Contains($LegacyVbs)) 'UNKNOWN_SHORTCUT_ARGUMENTS'
foreach($pair in $Files){
 Need (Test-Path -LiteralPath (Join-Path $Source $pair[0]) -PathType Leaf) 'ROUTER_SOURCE_MISSING'
}
$targetLauncher=Join-Path $Root $srcPointer.launcher_relative_path
$targetManifest=Join-Path $Root $srcPointer.manifest_relative_path
$targetApp=Join-Path $Root $srcPointer.entrypoint_relative_path
foreach($pair in @(
 @($targetLauncher,$srcPointer.launcher_sha256),
 @($targetManifest,$srcPointer.manifest_sha256),
 @($targetApp,$srcPointer.entrypoint_sha256)
)){
 Need (Test-Path -LiteralPath $pair[0] -PathType Leaf) 'EXACT_RELEASE_NOT_INSTALLED'
 Need ((Sha $pair[0]) -ceq [string]$pair[1]) 'INSTALLED_RELEASE_DIGEST_MISMATCH'
}
$Current=Join-Path $Operator 'current-release.json'
$Existing='ABSENT'
if(Test-Path -LiteralPath $Current -PathType Leaf){
 if((Sha $Current) -ne (Sha $Candidate)){throw 'LION_STABLE_SHORTCUT_CURRENT_RELEASE_EXISTS_DIFFERENT_PROMOTION_REQUIRED'}
 $Existing='IDENTICAL'
}
if($Mode -eq 'Inspect'){
 Write-Output 'RESULT=LION_STABLE_SHORTCUT_INSPECT_ONLY'
 Write-Output ('SOURCE_HEAD='+$srcPointer.source_head)
 Write-Output ('RELEASE_ID='+$srcPointer.release_id)
 Write-Output ('CURRENT_POINTER='+$Existing)
 Write-Output ('SHORTCUT_TARGET_KIND='+$(if($AlreadyStable){'STABLE'}else{'LEGACY'}))
 Write-Output 'FILES_CHANGED=NONE'
 return
}
# This is an explicit user-initiated write to their own Desktop and app data.
Need ($Approval -ceq 'INSTALL_LION_STABLE_ROUTER_PR454_00be49a1') 'EXACT_OPERATOR_APPROVAL_REQUIRED'
$who=[Security.Principal.WindowsIdentity]::GetCurrent()
Need ($who.IsSystem -eq $false -and $who.Name -notmatch '(?i)SYSTEM$') 'REAL_DESKTOP_OWNER_REQUIRED'
Need (([IO.Path]::GetFullPath($Root)).StartsWith([IO.Path]::GetFullPath($env:LOCALAPPDATA),[StringComparison]::OrdinalIgnoreCase)) 'LOCALAPPDATA_OWNER_MISMATCH'
if(-not (Test-Path -LiteralPath $Operator -PathType Container)){
 New-Item -ItemType Directory -Path $Operator -ErrorAction Stop|Out-Null
}
foreach($pair in $Files){
 $from=Join-Path $Source $pair[0];$to=Join-Path $Operator $pair[1]
 if(Test-Path -LiteralPath $to -PathType Leaf){
  Need ((Sha $to) -eq (Sha $from)) 'ROUTER_INSTALLED_BYTES_DIFFER'
 }else{
  Copy-Item -LiteralPath $from -Destination $to -ErrorAction Stop
  Need ((Sha $to) -eq (Sha $from)) 'ROUTER_COPY_UNKNOWN'
 }
}
if($Existing -eq 'ABSENT'){
 $tmp=Join-Path $Operator ('current-release.'+[guid]::NewGuid().ToString('N')+'.new')
 [IO.File]::WriteAllBytes($tmp,[IO.File]::ReadAllBytes($Candidate))
 [IO.File]::Move($tmp,$Current)
 Need ((Sha $Current) -eq (Sha $Candidate)) 'CURRENT_SELECTOR_UNKNOWN'
}
# Never rewrite if the stable shortcut is already installed.
if(-not $AlreadyStable){
 $Backups=Join-Path $Operator 'shortcut-backups'
 if(-not (Test-Path -LiteralPath $Backups)){New-Item -ItemType Directory -Path $Backups|Out-Null}
 $backup=Join-Path $Backups ('LION_original_'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'_'+[guid]::NewGuid().ToString('N')+'.lnk')
 Copy-Item -LiteralPath $Shortcut -Destination $backup -ErrorAction Stop
 Need ((Sha $Shortcut) -eq (Sha $backup)) 'SHORTCUT_BACKUP_UNKNOWN'
 $new=Join-Path $DesktopPath ('LION_pending_'+[guid]::NewGuid().ToString('N')+'.lnk')
 $link=$Witness.CreateShortcut($new)
 $link.TargetPath=$Old.TargetPath
 $link.Arguments='"'+$ExpectedVbs+'"'
 $link.WorkingDirectory=$Operator
 $link.IconLocation=$Old.IconLocation
 $link.Save()
 $proof=$Witness.CreateShortcut($new)
 Need ($proof.Arguments.Contains($ExpectedVbs)) 'PENDING_SHORTCUT_NOT_BOUND'
 [IO.File]::Replace($new,$Shortcut,$null)
}
$live=$Witness.CreateShortcut($Shortcut)
Need ($live.Arguments.Contains($ExpectedVbs)) 'DESKTOP_SHORTCUT_EFFECT_UNKNOWN_READBACK_REQUIRED'
Write-Output 'RESULT=LION_STABLE_SHORTCUT_ACTIVATED'
Write-Output ('RELEASE_ID='+$srcPointer.release_id)
Write-Output ('CURRENT_RELEASE_POINTER='+$Current)
Write-Output ('SHORTCUT='+$Shortcut)
Write-Output 'OLD_RELEASE_AND_PROFILE_PRESERVED=TRUE'
Write-Output 'SAAS_SEND=NONE'
