[CmdletBinding()]
param(
 [switch]$InspectOnly,
 [switch]$ValidateOnly,
 [string]$LionRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

if(-not $LionRoot){
 if(-not $env:LOCALAPPDATA){throw 'LION_OPERATOR_LOCALAPPDATA_REQUIRED'}
 $LionRoot=Join-Path $env:LOCALAPPDATA 'LION'
}
$Root=[IO.Path]::GetFullPath($LionRoot)
if(-not (Test-Path -LiteralPath $Root -PathType Container)){throw 'LION_OPERATOR_ROOT_UNAVAILABLE'}
$Pointer=Join-Path $Root 'operator\current-release.json'
if(-not (Test-Path -LiteralPath $Pointer -PathType Leaf)){throw 'LION_CURRENT_RELEASE_NOT_SELECTED'}
$config=Get-Content -LiteralPath $Pointer -Raw -Encoding UTF8|ConvertFrom-Json
function Need($ok,[string]$errorText){
 if(-not $ok){throw ('LION_CURRENT_RELEASE_'+$errorText)}
}
function ResolveBound([string]$relative,[string]$kind){
 Need ($relative -and ($relative -match '^[A-Za-z0-9 _./\\-]{3,260}$') -and ($relative -notmatch '(^|[\\/])\.\.?([\\/]|$)') -and (-not [IO.Path]::IsPathRooted($relative))) ($kind+'_UNSAFE_PATH')
 $full=[IO.Path]::GetFullPath((Join-Path $Root $relative))
 Need ($full.StartsWith($Root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) ($kind+'_ESCAPES_ROOT')
 Need (Test-Path -LiteralPath $full -PathType Leaf) ($kind+'_MISSING')
 $part=Get-Item -LiteralPath $full -Force
 Need (-not ($part.Attributes -band [IO.FileAttributes]::ReparsePoint)) ($kind+'_REPARSE_DENIED')
 return $full
}
function Sha256([string]$name){return (Get-FileHash -LiteralPath $name -Algorithm SHA256).Hash.ToLowerInvariant()}
Need ($config.schema -ceq 'lion.desktop.operator-current-release/v1') 'SCHEMA_MISMATCH'
Need (((($config.PSObject.Properties.Name | Sort-Object) -join ',') -ceq 'entrypoint_relative_path,entrypoint_sha256,generation,launcher_relative_path,launcher_sha256,manifest_relative_path,manifest_sha256,release_id,repository,schema,source_head,source_tree')) 'UNRECOGNIZED_POINTER_FIELDS'
Need ($config.generation -is [int] -and $config.generation -ge 1) 'GENERATION_REQUIRED'
Need ($config.repository -ceq 'DonkeyJJLove/ai_platform') 'REPOSITORY_MISMATCH'
Need ($config.source_head -cmatch '^[0-9a-f]{40}$' -and $config.source_tree -cmatch '^[0-9a-f]{40}$') 'SOURCE_PIN_REQUIRED'
Need ($config.release_id -cmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{3,100}$') 'RELEASE_ID_REQUIRED'
foreach($key in @('launcher_sha256','manifest_sha256','entrypoint_sha256')){
 Need ($config.$key -cmatch '^[0-9a-f]{64}$') ('DIGEST_REQUIRED_'+$key)
}
Need ($config.launcher_relative_path -match '^(?:staging|operator[\\/]releases)[\\/]') 'LAUNCHER_LOCATION_INVALID'
Need ($config.manifest_relative_path -match '^(?:staging|operator[\\/]releases)[\\/]') 'MANIFEST_LOCATION_INVALID'
Need ($config.entrypoint_relative_path -match '^desktop[\\/]release-[A-Za-z0-9_.-]+[\\/]browser_broker[\\/]src[\\/]main\.cjs$') 'ENTRYPOINT_LOCATION_INVALID'
$target=ResolveBound $config.launcher_relative_path 'LAUNCHER'
$manifest=ResolveBound $config.manifest_relative_path 'MANIFEST'
$entry=ResolveBound $config.entrypoint_relative_path 'ENTRYPOINT'
Need ((Sha256 $target) -ceq $config.launcher_sha256) 'LAUNCHER_DIGEST_MISMATCH'
Need ((Sha256 $manifest) -ceq $config.manifest_sha256) 'MANIFEST_DIGEST_MISMATCH'
Need ((Sha256 $entry) -ceq $config.entrypoint_sha256) 'ENTRYPOINT_DIGEST_MISMATCH'
$sourceManifest=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
Need ($sourceManifest.local_head -ceq $config.source_head -and
      $sourceManifest.git_tree -ceq $config.source_tree -and
      $sourceManifest.file_count -is [int] -and
      $sourceManifest.file_count -ge 1 -and
      $sourceManifest.file_count -le 10000) 'SOURCE_MANIFEST_MISMATCH'
Write-Output ('RELEASE_SELECTED='+$config.release_id)
Write-Output ('SOURCE_HEAD='+$config.source_head)
Write-Output ('GENERATION='+$config.generation)
Write-Output ('ENTRYPOINT_SHA256='+$config.entrypoint_sha256)
if($InspectOnly){Write-Output 'RESULT=ROUTER_INSPECT_PASS_NO_LAUNCH';return}
$pre=@(& $target -ValidateOnly)
$exitCode=$LASTEXITCODE
Need ($exitCode -eq 0 -and [bool](@($pre|Where-Object {$_ -match '^RESULT=PASS_LION_DESKTOP_'}).Count)) 'PRELAUNCH_VALIDATION_FAILED'
if($ValidateOnly){Write-Output 'RESULT=ROUTER_VALIDATE_PASS';return}
# User explicitly launched the selected release. No fallback to an older build.
& $target
if($LASTEXITCODE -ne 0){throw 'LION_CURRENT_RELEASE_SELECTED_LAUNCH_FAILED'}
Write-Output 'RESULT=ROUTER_SELECTED_RELEASE_LAUNCHED'
