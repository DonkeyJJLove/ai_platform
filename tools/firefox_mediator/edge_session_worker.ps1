param(
  [string]$Ipc = "\\wsl.localhost\LION-AUTH-LAB\var\lib\sentinelx\uploads\lion-mission-control-v3\firefox-mediator-ipc",
  [string]$ProjectHomeUrl = "https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project",
  [string]$ProjectTitle = "LION_EVOLUSION",
  [string]$ConversationTitlePrefix = "LION SaaS",
  [int]$IntervalMs = 2500,
  [int]$MinSendIntervalSeconds = 45,
  [int]$JitterMinSeconds = 0,
  [int]$JitterMaxSeconds = 135,
  [int]$RateLimitCooldownSeconds = 900,
  [switch]$Once
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms

$Transport = 'CHATGPT_FIREFOX_PROJECT_MEDIATED'
$MediatorId = 'LION_EDGE_MINIMIZED_SESSION_MEDIATOR_R1'
$ProfileNeedle = 'C:/Users/d2j3/AppData/Local/LION/saas-background-profile-r1'
$Inbox = Join-Path $Ipc 'inbox'
$Outbox = Join-Path $Ipc 'outbox'
$Journal = Join-Path $Ipc 'journal'
$Receipts = Join-Path $Ipc 'receipts'
$MissionThreads = Join-Path $Ipc 'mission-threads'
$ThreadPolicy = 'ONE_CHAT_PER_MISSION_WITH_TERMINAL_ROLLOVER'
$SendControl = Join-Path $Ipc 'send-control.json'
foreach($d in @($Ipc,$Inbox,$Outbox,$Journal,$Receipts,$MissionThreads)){ New-Item -ItemType Directory -Force -Path $d | Out-Null }

function Write-AtomicJson([string]$Path,[object]$Value){
  $tmp = "$Path.tmp"
  $json=$Value | ConvertTo-Json -Depth 12
  for($attempt=1;$attempt -le 3;$attempt++){
    try {
      [System.IO.File]::WriteAllText($tmp,$json,(New-Object System.Text.UTF8Encoding($false)))
      Move-Item -Force $tmp $Path
      return
    } catch {
      if($attempt -ge 3){throw}
      Start-Sleep -Milliseconds (100*$attempt)
    }
  }
}

function Read-Json([string]$Path){
  if(-not (Test-Path $Path)){ return $null }
  try { return Get-Content -Raw -Encoding UTF8 $Path | ConvertFrom-Json } catch { return $null }
}

function Write-Status([string]$State,[hashtable]$Extra=@{}){
  $v=[ordered]@{
    mediator_id=$MediatorId
    transport=$Transport
    state=$State
    project_title=$ProjectTitle
    chat_title='MISSION_SCOPED_THREAD'
    browser='Microsoft Edge / dedicated minimized authenticated session'
    authority_effect='NONE'
    observed_at=(Get-Date).ToUniversalTime().ToString('o')
  }
  foreach($k in $Extra.Keys){$v[$k]=$Extra[$k]}
  Write-AtomicJson (Join-Path $Ipc 'mediator-status.json') $v
}

function Normalize-Url([string]$Url){
  if([string]::IsNullOrWhiteSpace($Url)){return ''}
  return ((([string]$Url) -replace '^https?://','').Split('?')[0]).TrimEnd('/')
}

function Get-FirefoxProcess([int]$ProcessId){
  try { return Get-CimInstance Win32_Process -Filter ("ProcessId="+$ProcessId) -ErrorAction Stop } catch { return $null }
}

function Test-InteractiveFirefoxWindow([System.Windows.Automation.AutomationElement]$Window){
  if(-not $Window -or $Window.Current.ClassName -notlike 'Chrome_WidgetWin*' -or $Window.Current.ProcessId -le 0){return $false}
  $p=Get-FirefoxProcess ([int]$Window.Current.ProcessId)
  if(-not $p -or [string]$p.Name -ne 'msedge.exe'){return $false}
  $cmd=(([string]$p.CommandLine) -replace '\\','/')
  if($cmd -notlike "*$ProfileNeedle*"){return $false}
  if($cmd -match '(?i)--headless'){return $false}
  return $true
}

function Get-FirefoxRoots {
  $desktop=[System.Windows.Automation.AutomationElement]::RootElement
  $wins=$desktop.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
  $out=@()
  for($i=0;$i -lt $wins.Count;$i++){
    $w=$wins.Item($i)
    if(Test-InteractiveFirefoxWindow $w){ $out += $w }
  }
  return $out
}

function Get-All([System.Windows.Automation.AutomationElement]$Root){
  return ,$Root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
}

function Ensure-Minimized([System.Windows.Automation.AutomationElement]$Window){
  if(-not $Window){return $false}
  $wp=$null
  if(-not $Window.TryGetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern,[ref]$wp)){return $false}
  try {$wp.SetWindowVisualState([System.Windows.Automation.WindowVisualState]::Minimized)} catch {return $false}
  Start-Sleep -Milliseconds 100
  return ($wp.Current.WindowVisualState -eq [System.Windows.Automation.WindowVisualState]::Minimized)
}

function Get-Url([System.Windows.Automation.AutomationElementCollection]$All){
  for($i=0;$i -lt $All.Count;$i++){
    $e=$All.Item($i)
    if($e.Current.AutomationId -eq 'view_1021'){
      $vp=$null
      if($e.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$vp)){ return [string]$vp.Current.Value }
    }
  }
  return $null
}

function Find-Prompt([System.Windows.Automation.AutomationElementCollection]$All){
  for($i=0;$i -lt $All.Count;$i++){
    $e=$All.Item($i)
    if($e.Current.AutomationId -eq 'prompt-textarea' -and $e.Current.ControlType -eq [System.Windows.Automation.ControlType]::Edit){ return $e }
  }
  return $null
}

function Get-DocumentElementText([System.Windows.Automation.AutomationElement]$Document){
  if(-not $Document){return ''}
  $tp=$null
  if($Document.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern,[ref]$tp)){
    try { return [string]$tp.DocumentRange.GetText(-1) } catch { return '' }
  }
  return ''
}

function Find-VisibleProjectDocument([System.Windows.Automation.AutomationElement]$Window){
  try {$all=Get-All $Window} catch {return $null}
  for($i=0;$i -lt $all.Count;$i++){
    $doc=$all.Item($i)
    if($doc.Current.ControlType -ne [System.Windows.Automation.ControlType]::Document){continue}
    $name=[string]$doc.Current.Name
    if($name -notlike "*$ProjectTitle*"){continue}
    try {$docAll=Get-All $doc} catch {continue}
    $prompt=Find-Prompt $docAll
    if($prompt){return [pscustomobject]@{Window=$Window;Root=$doc;All=$docAll;Prompt=$prompt;DocumentName=$name}}
  }
  return $null
}

function Find-ProjectTargetWindow {
  $target=Normalize-Url $ProjectHomeUrl
  foreach($window in @(Get-FirefoxRoots)){
    try {$windowAll=Get-All $window} catch {continue}
    $url=Get-Url $windowAll
    if((Normalize-Url $url) -eq $target){return [pscustomobject]@{Window=$window;Url=$url}}
  }
  return $null
}

function Find-ProjectHome {
  $target=Normalize-Url $ProjectHomeUrl
  $projectPrefix=($target -replace '/project$','')
  foreach($window in @(Get-FirefoxRoots)){
    try {$windowAll=Get-All $window} catch {continue}
    $url=Get-Url $windowAll
    $norm=Normalize-Url $url
    $isProjectSurface=($norm -eq $target -or $norm -like "$projectPrefix/c/*")
    if(-not $isProjectSurface){continue}
    $doc=Find-VisibleProjectDocument $window
    if(-not $doc){continue}
    $doc | Add-Member -NotePropertyName Url -NotePropertyValue $url -Force
    $doc | Add-Member -NotePropertyName Surface -NotePropertyValue ($(if($norm -eq $target){'PROJECT_HOME'}else{'PROJECT_CONVERSATION'})) -Force
    return $doc
  }
  return $null
}

function Refresh-Readiness {
  $projectHome=Ensure-ProjectHome
  if($projectHome){
    if(-not (Ensure-Minimized $projectHome.Window)){Write-Status 'DEGRADED' @{reason='EDGE_MINIMIZE_FAILED';project_verified=$false};return $false}
    Write-Status 'READY' @{current_url=$projectHome.Url;document_name=$projectHome.DocumentName;session_mode='DEDICATED_MINIMIZED_EDGE';window_state='MINIMIZED';visible_window_count=0;project_verified=$true;chat_verified=$true;project_home_verified=$true;new_thread_policy=$ThreadPolicy}
    return $true
  }
  Write-Status 'PROJECT_BINDING_REQUIRED' @{reason='PROJECT_SURFACE_NOT_VERIFIED';project_home_url=$ProjectHomeUrl;new_thread_policy=$ThreadPolicy;project_verified=$false}
  return $false
}

function Ensure-ProjectHome {
  $deadline=(Get-Date).AddSeconds(30)
  while((Get-Date) -lt $deadline){
    $projectHome=Find-ProjectHome
    if($projectHome){
      if(-not (Ensure-Minimized $projectHome.Window)){Write-Status 'DEGRADED' @{reason='EDGE_MINIMIZE_FAILED';project_verified=$false};return $null}
      Write-Status 'READY' @{current_url=$projectHome.Url;document_name=$projectHome.DocumentName;session_mode='DEDICATED_MINIMIZED_EDGE';window_state='MINIMIZED';visible_window_count=0;project_verified=$true;chat_verified=$true;project_home_verified=$true;new_thread_policy=$ThreadPolicy}
      return $projectHome
    }
    Start-Sleep -Milliseconds 500
  }
  Write-Status 'PROJECT_BINDING_REQUIRED' @{reason='DEDICATED_EDGE_PROJECT_SURFACE_NOT_READY';project_home_url=$ProjectHomeUrl;new_thread_policy=$ThreadPolicy;project_verified=$false}
  return $null
}

function Navigate-ToUrl([System.Windows.Automation.AutomationElement]$Window,[string]$Url){
  if($Url -match '^chatgpt\.com/'){ $Url='https://'+$Url }
  $all=Get-All $Window
  $bar=$null
  for($i=0;$i -lt $all.Count;$i++){
    $e=$all.Item($i)
    if($e.Current.AutomationId -eq 'view_1021'){$bar=$e;break}
  }
  if(-not $bar){throw 'URLBAR_NOT_FOUND'}
  $vp=$null
  if(-not $bar.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$vp)){throw 'URLBAR_VALUE_PATTERN_REQUIRED'}
  $vp.SetValue($Url);$bar.SetFocus();[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
}

function Ensure-Conversation([string]$Url){
  $target=Normalize-Url $Url
  if([string]::IsNullOrWhiteSpace($target) -or $target -notmatch '/c/'){return $null}
  foreach($window in @(Get-FirefoxRoots)){
    try {$windowAll=Get-All $window} catch {continue}
    $current=Get-Url $windowAll
    if((Normalize-Url $current) -ne $target){continue}
    try {$all=Get-All $window} catch {continue}
    for($i=0;$i -lt $all.Count;$i++){
      $doc=$all.Item($i)
      if($doc.Current.ControlType -ne [System.Windows.Automation.ControlType]::Document){continue}
      try {$docAll=Get-All $doc} catch {continue}
      $prompt=Find-Prompt $docAll
      if($prompt){
        $result=[pscustomobject]@{Window=$window;Root=$doc;All=$docAll;Prompt=$prompt;DocumentName=([string]$doc.Current.Name)}
        $result | Add-Member -NotePropertyName Url -NotePropertyValue $current -Force
        return $result
      }
    }
  }
  return $null
}

function Get-ProjectChatSnapshot([System.Windows.Automation.AutomationElement]$Window){
  $names=New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::Ordinal)
  try {$all=Get-All $Window} catch {return $names}
  for($i=0;$i -lt $all.Count;$i++){
    $e=$all.Item($i)
    if($e.Current.ControlType -ne [System.Windows.Automation.ControlType]::Hyperlink){continue}
    $n=[string]$e.Current.Name
    if($n -like "*, czat w projekcie $ProjectTitle*" -or $n -like "*, chat in project $ProjectTitle*"){[void]$names.Add($n)}
  }
  return $names
}

function Set-Prompt([System.Windows.Automation.AutomationElement]$Prompt,[string]$Text){
  $vp=$null
  if(-not $Prompt.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$vp)){throw 'PROMPT_VALUE_PATTERN_REQUIRED'}
  $expected=$Text.TrimEnd("`r","`n")
  for($attempt=0;$attempt -lt 3;$attempt++){
    $vp.SetValue($Text)
    for($probe=0;$probe -lt 10;$probe++){
      Start-Sleep -Milliseconds 100
      $actual=([string]$vp.Current.Value).TrimEnd("`r","`n")
      if($actual -eq $expected){
        Start-Sleep -Milliseconds 400
        $final=([string]$vp.Current.Value).TrimEnd("`r","`n")
        if($final -eq $expected){return}
      }
    }
  }
  throw 'PROMPT_VALUE_READBACK_MISMATCH'
}

function Send-Prompt([System.Windows.Automation.AutomationElement]$Prompt,[System.Windows.Automation.AutomationElementCollection]$All){
  for($i=0;$i -lt $All.Count;$i++){
    $e=$All.Item($i)
    if($e.Current.ControlType -ne [System.Windows.Automation.ControlType]::Button){continue}
    $n=[string]$e.Current.Name
    if($e.Current.AutomationId -eq 'composer-submit-button' -or $n -match '^(W.*lij|Send)( .*)?$'){
      $ip=$null
      if($e.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$ip)){$ip.Invoke();return}
    }
  }
  throw 'PROMPT_SUBMIT_BUTTON_REQUIRED'
}

function Generation-InProgress([System.Windows.Automation.AutomationElementCollection]$All){
  for($i=0;$i -lt $All.Count;$i++){
    $e=$All.Item($i)
    if($e.Current.ControlType -ne [System.Windows.Automation.ControlType]::Button){continue}
    if($e.Current.AutomationId -ne 'composer-submit-button'){continue}
    $n=[string]$e.Current.Name
    if($n -match '^(Przer.*odpow|Stop)'){return $true}
  }
  return $false
}

function Extract-LastAssistantFromElements([System.Windows.Automation.AutomationElementCollection]$All){
  $marker=-1
  for($i=0;$i -lt $All.Count;$i++){
    $e=$All.Item($i)
    if($e.Current.ControlType -ne [System.Windows.Automation.ControlType]::Text){continue}
    $n=[string]$e.Current.Name
    if($n -match '^ChatGPT pow' -or $n -match '^ChatGPT said:'){$marker=$i}
  }
  if($marker -lt 0){return ''}
  $parts=New-Object System.Collections.Generic.List[string]
  for($i=$marker+1;$i -lt $All.Count;$i++){
    $e=$All.Item($i)
    if($e.Current.ControlType -ne [System.Windows.Automation.ControlType]::Text){continue}
    $n=([string]$e.Current.Name).Trim()
    if(-not $n){continue}
    if($n -match '^Powiedzia' -or $n -match '^You said:' -or $n -match '^ChatGPT mo' -or $n -match '^Czatuj z ChatGPT' -or $n -match '^Zapytaj ChatGPT'){break}
    $parts.Add($n)
  }
  return (($parts.ToArray() -join "`n").Trim())
}

function Find-ConversationLink([System.Windows.Automation.AutomationElement]$Window,[string]$Question,[System.Collections.Generic.HashSet[string]]$Before=$null){
  try {$all=Get-All $Window} catch {return $null}
  $needle=(($Question -replace '\s+',' ').Trim())
  if($needle.Length -gt 120){$needle=$needle.Substring(0,120)}
  $fallback=$null
  for($i=0;$i -lt $all.Count;$i++){
    $e=$all.Item($i)
    if($e.Current.ControlType -ne [System.Windows.Automation.ControlType]::Hyperlink -or $e.Current.IsOffscreen){continue}
    $n=([string]$e.Current.Name).Trim()
    if(-not $n){continue}
    $isProject=($n -like "*, czat w projekcie $ProjectTitle*" -or $n -like "*, chat in project $ProjectTitle*" -or $n.IndexOf($ProjectTitle,[System.StringComparison]::OrdinalIgnoreCase) -ge 0)
    $matchesQuestion=($needle -and $n.IndexOf($needle,[System.StringComparison]::OrdinalIgnoreCase) -ge 0)
    $isNew=($Before -and -not $Before.Contains($n))
    if($matchesQuestion){return $e}
    if($isProject -and $isNew -and -not $fallback){$fallback=$e}
  }
  return $fallback
}

function Open-ConversationLink([System.Windows.Automation.AutomationElement]$Link){
  if(-not $Link){return $false}
  $ip=$null
  if($Link.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$ip)){$ip.Invoke();return $true}
  try{$Link.SetFocus();[System.Windows.Forms.SendKeys]::SendWait('{ENTER}');return $true}catch{return $false}
}

function Wait-NewConversation([System.Windows.Automation.AutomationElement]$Window,[string]$OldUrl,[string]$Question,[System.Collections.Generic.HashSet[string]]$Before=$null){
  $old=Normalize-Url $OldUrl
  $deadline=(Get-Date).AddSeconds(45)
  $linkOpened=$false
  while((Get-Date) -lt $deadline){
    Start-Sleep -Milliseconds 400
    try {$windowAll=Get-All $Window;$url=Get-Url $windowAll} catch {continue}
    $norm=Normalize-Url $url
    if($norm -ne $old -and $norm -match '/c/'){
      $doc=Find-VisibleProjectDocument $Window
      if($doc){$doc | Add-Member -NotePropertyName Url -NotePropertyValue $url -Force;return $doc}
    }
    if(-not $linkOpened){
      $link=Find-ConversationLink $Window $Question $Before
      if($link){$linkOpened=Open-ConversationLink $link}
    }
  }
  throw 'NEW_CONVERSATION_RECOVERY_TIMEOUT'
}

function New-ConversationTitle([string]$Question,[string]$RequestId){
  $q=($Question -replace '\s+',' ').Trim()
  $q=$q -replace '^(Na SaaS:|SaaS:)\s*',''
  if($q -match '^Reply exactly'){ $topic='Mediator Test' }
  else {
    $topic=($q -replace '[^\p{L}\p{Nd} _.-]',' ').Trim()
    $topic=($topic -replace '\s+',' ')
    if([string]::IsNullOrWhiteSpace($topic)){$topic='Supervisor'}
    if($topic.Length -gt 42){$topic=$topic.Substring(0,42).Trim()}
  }
  $tail=($RequestId -replace '^saas-','')
  if($tail.Length -gt 8){$tail=$tail.Substring(0,8)}
  return "$ConversationTitlePrefix - $topic - $($tail.ToUpperInvariant())"
}

function Rename-ConversationFromProjectHome([System.Windows.Automation.AutomationElement]$Window,[string]$Question,[string]$Title){
  $deadline=(Get-Date).AddSeconds(20);$item=$null;$options=$null
  while((Get-Date) -lt $deadline -and -not $options){
    Start-Sleep -Milliseconds 500
    try {$all=Get-All $Window} catch {continue}
    for($i=0;$i -lt $all.Count;$i++){
      $e=$all.Item($i)
      if($e.Current.ControlType -ne [System.Windows.Automation.ControlType]::ListItem -or $e.Current.IsOffscreen){continue}
      $n=[string]$e.Current.Name
      if($n.IndexOf($Question,[System.StringComparison]::OrdinalIgnoreCase) -lt 0){continue}
      $desc=$e.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
      for($j=0;$j -lt $desc.Count;$j++){
        $d=$desc.Item($j)
        if($d.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and ([string]$d.Current.AutomationId) -like 'radix-*'){$item=$e;$options=$d;break}
      }
      if($options){break}
    }
  }
  if(-not $options){return [pscustomobject]@{state='AUTO_TITLE_ONLY';title=$null;reason='PROJECT_HOME_CONVERSATION_NOT_IDENTIFIED'}}
  $itemRect=$item.Current.BoundingRectangle
  $options.SetFocus();[System.Windows.Forms.SendKeys]::SendWait('{ENTER}');Start-Sleep -Milliseconds 900
  $all=Get-All $Window;$menu=@()
  for($i=0;$i -lt $all.Count;$i++){
    $e=$all.Item($i)
    if(-not $e.Current.IsOffscreen -and $e.Current.ControlType -eq [System.Windows.Automation.ControlType]::MenuItem){
      $r=$e.Current.BoundingRectangle
      if($r.Left -gt ($itemRect.Left-50)){$menu += [pscustomobject]@{Element=$e;Top=$r.Top}}
    }
  }
  $menu=$menu|Sort-Object Top
  if($menu.Count -lt 2){[System.Windows.Forms.SendKeys]::SendWait('{ESC}');return [pscustomobject]@{state='AUTO_TITLE_ONLY';title=$null;reason='RENAME_MENU_NOT_IDENTIFIED'}}
  $menu[1].Element.SetFocus();[System.Windows.Forms.SendKeys]::SendWait('{ENTER}');Start-Sleep -Milliseconds 900
  $all=Get-All $Window;$edit=$null
  for($i=0;$i -lt $all.Count;$i++){
    $e=$all.Item($i);$n=[string]$e.Current.Name
    if(-not $e.Current.IsOffscreen -and $e.Current.ControlType -eq [System.Windows.Automation.ControlType]::Edit -and $e.Current.AutomationId -ne 'prompt-textarea' -and ($n -match 'Tytul|Tytu|Title')){$edit=$e;break}
  }
  if(-not $edit){[System.Windows.Forms.SendKeys]::SendWait('{ESC}');return [pscustomobject]@{state='AUTO_TITLE_ONLY';title=$null;reason='TITLE_EDIT_NOT_IDENTIFIED'}}
  $vp=$null
  if(-not $edit.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$vp)){[System.Windows.Forms.SendKeys]::SendWait('{ESC}');return [pscustomobject]@{state='AUTO_TITLE_ONLY';title=$null;reason='TITLE_EDIT_VALUE_PATTERN_MISSING'}}
  $vp.SetValue($Title);$edit.SetFocus();[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
  $verify=(Get-Date).AddSeconds(10)
  while((Get-Date) -lt $verify){
    Start-Sleep -Milliseconds 500
    try {$all=Get-All $Window} catch {continue}
    for($i=0;$i -lt $all.Count;$i++){
      $e=$all.Item($i);$n=[string]$e.Current.Name
      if($e.Current.ControlType -eq [System.Windows.Automation.ControlType]::ListItem -and $n.IndexOf($Title,[System.StringComparison]::OrdinalIgnoreCase) -ge 0){return [pscustomobject]@{state='RENAMED';title=$Title;reason=$null}}
    }
  }
  return [pscustomobject]@{state='RENAME_UNVERIFIED';title=$Title;reason='TITLE_READBACK_TIMEOUT'}
}



function Get-AnyFirefoxWindow {
  foreach($w in @(Get-FirefoxRoots)){return $w}
  return $null
}

function Get-SendControl {
  $x=Read-Json $SendControl
  if($x){return $x}
  return [pscustomobject]@{last_send_at=$null;last_request_id=$null;last_required_gap_seconds=$null;blocked_until=$null;reason=$null}
}

function Save-SendControl([object]$State){
  Write-AtomicJson $SendControl $State
}

function Set-RateLimitBackoff([string]$Reason){
  $until=(Get-Date).ToUniversalTime().AddSeconds([Math]::Max(60,$RateLimitCooldownSeconds))
  $current=Get-SendControl
  $state=[pscustomobject][ordered]@{
    last_send_at=$current.last_send_at
    last_request_id=$current.last_request_id
    last_required_gap_seconds=$current.last_required_gap_seconds
    blocked_until=$until.ToString('o')
    reason=$Reason
  }
  Save-SendControl $state
  Write-Status 'DEGRADED' @{
    reason='RATE_LIMITED'
    retry_not_before=$state.blocked_until
    new_thread_policy=$ThreadPolicy
  }
}

function Test-BackoffActive {
  $state=Get-SendControl
  if([string]::IsNullOrWhiteSpace([string]$state.blocked_until)){return $false}
  try {$until=[DateTimeOffset]::Parse([string]$state.blocked_until).UtcDateTime} catch {return $false}
  if([DateTime]::UtcNow -lt $until){
    Write-Status 'DEGRADED' @{
      reason='RATE_LIMIT_BACKOFF'
      retry_not_before=$state.blocked_until
      new_thread_policy=$ThreadPolicy
    }
    return $true
  }
  $state.blocked_until=$null;$state.reason=$null
  Save-SendControl $state
  return $false
}

function Get-DeterministicJitterSeconds([string]$Seed){
  $min=[Math]::Max(0,$JitterMinSeconds)
  $max=[Math]::Max($min,$JitterMaxSeconds)
  if($max -le $min){return $min}
  $digest=Get-Sha256Text $Seed
  $bucket=[Convert]::ToUInt32($digest.Substring(0,8),16)
  return $min+([int]($bucket % (($max-$min)+1)))
}

function Get-RequiredSendGapSeconds([object]$Work){
  $seed=(Get-MissionKey $Work)+'|'+([string]$Work.request_id)+'|'+([string]$Work.question_digest)
  return [Math]::Max(1,$MinSendIntervalSeconds)+(Get-DeterministicJitterSeconds $seed)
}

function Test-PreviousReceiptReady([object]$Work){
  $state=Get-MissionState $Work
  $previous=[string]$state.last_completed_request_id
  if([string]::IsNullOrWhiteSpace($previous)){return $true}
  $receipt=Read-Json (Join-Path $Receipts "$previous.json")
  if(-not $receipt){return $false}
  if([string]$receipt.status -eq 'RESPONDED'){
    return (-not [string]::IsNullOrWhiteSpace([string]$receipt.receipt_digest))
  }
  if(([string]$receipt.status -in @('SUPERSEDED','CANCELLED')) -and $receipt.terminal_without_response -eq $true){return $true}
  return $false
}

function Wait-SendBudget([object]$Work){
  if(-not (Test-PreviousReceiptReady $Work)){throw 'PREVIOUS_RECEIPT_REQUIRED'}
  $state=Get-SendControl
  if(-not [string]::IsNullOrWhiteSpace([string]$state.last_send_at)){
    try {$last=[DateTimeOffset]::Parse([string]$state.last_send_at).UtcDateTime} catch {$last=$null}
    if($last){
      $required=Get-RequiredSendGapSeconds $Work
      $remaining=$required-([DateTime]::UtcNow-$last).TotalSeconds
      if($remaining -gt 0){Start-Sleep -Milliseconds ([int][Math]::Ceiling($remaining*1000))}
    }
  }
}

function Note-Send([object]$Work){
  $state=Get-SendControl
  if(-not $state.PSObject.Properties['last_request_id']){
    $state | Add-Member -NotePropertyName last_request_id -NotePropertyValue $null
  }
  if(-not $state.PSObject.Properties['last_required_gap_seconds']){
    $state | Add-Member -NotePropertyName last_required_gap_seconds -NotePropertyValue $null
  }
  $state.last_send_at=(Get-Date).ToUniversalTime().ToString('o')
  $state.last_request_id=[string]$Work.request_id
  $state.last_required_gap_seconds=Get-RequiredSendGapSeconds $Work
  Save-SendControl $state
}

function Test-RateLimitInDocument([System.Windows.Automation.AutomationElement]$Root){
  if(-not $Root){return $false}
  $text=Get-DocumentElementText $Root
  if([string]::IsNullOrWhiteSpace($text)){return $false}
  return (
    $text -match 'Zbyt wiele' -or
    $text -match 'Za .*wysy.*' -or
    $text -match 'Too many requests' -or
    $text -match 'temporarily limited'
  )
}

function Get-WindowText([System.Windows.Automation.AutomationElement]$Window){
  if(-not $Window){return ''}
  try {$all=Get-All $Window} catch {return ''}
  $parts=New-Object System.Collections.Generic.List[string]
  for($i=0;$i -lt $all.Count;$i++){
    $e=$all.Item($i)
    if($e.Current.ControlType -eq [System.Windows.Automation.ControlType]::Text){
      $n=([string]$e.Current.Name).Trim()
      if($n){$parts.Add($n)}
    }
  }
  return (($parts.ToArray() -join "`n").Trim())
}

function Test-WindowRateLimit([System.Windows.Automation.AutomationElement]$Window){
  $text=Get-WindowText $Window
  if([string]::IsNullOrWhiteSpace($text)){return $false}
  return (
    $text -match 'Zbyt wiele' -or
    $text -match 'Za .*wysy.*' -or
    $text -match 'Too many requests' -or
    $text -match 'temporarily limited'
  )
}

function Get-WindowUrl([System.Windows.Automation.AutomationElement]$Window){
  if(-not $Window){return ''}
  try {$all=Get-All $Window; return [string](Get-Url $all)} catch {return ''}
}

function Get-ExplicitTerminalReason([System.Windows.Automation.AutomationElement]$Window){
  $text=Get-WindowText $Window
  if([string]::IsNullOrWhiteSpace($text)){return $null}
  if($text -match 'maximum.*conversation.*length' -or $text -match 'conversation.*maximum.*length'){return 'CONVERSATION_MAX_LENGTH'}
  if($text -match 'conversation.*too long' -or $text -match 'chat.*too long'){return 'CONVERSATION_TOO_LONG'}
  if($text -match 'start a new chat' -and $text -match 'limit|length|reached'){return 'TERMINAL_START_NEW_CHAT'}
  if($text -match 'Conversation not found'){return 'CONVERSATION_NOT_FOUND'}
  return $null
}

function Open-BoundConversationAny([string]$Url){
  $existing=Ensure-Conversation $Url
  if($existing){return $existing}
  $window=Get-AnyFirefoxWindow
  if(-not $window){return $null}
  Navigate-ToUrl $window $Url
  $deadline=(Get-Date).AddSeconds(20)
  while((Get-Date) -lt $deadline){
    Start-Sleep -Milliseconds 500
    $conversation=Ensure-Conversation $Url
    if($conversation){return $conversation}
  }
  return $null
}

function Get-Sha256Text([string]$Text){
  $sha=[System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes=[System.Text.Encoding]::UTF8.GetBytes([string]$Text)
    return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
  } finally {$sha.Dispose()}
}

function Get-MissionKey([object]$Work){
  $mission=[string]$Work.mission_id
  if(-not [string]::IsNullOrWhiteSpace($mission)){return "mission:$mission"}
  $scopeType=[string]$Work.scope_type;$scopeId=[string]$Work.scope_id
  if(-not [string]::IsNullOrWhiteSpace($scopeType) -and -not [string]::IsNullOrWhiteSpace($scopeId)){return "scope:${scopeType}:${scopeId}"}
  $thread=[string]$Work.thread_id
  if(-not [string]::IsNullOrWhiteSpace($thread)){return "lion-thread:$thread"}
  return "request:$([string]$Work.request_id)"
}

function Get-MissionStatePath([object]$Work){
  $key=Get-MissionKey $Work
  $digest=Get-Sha256Text $key
  return Join-Path $MissionThreads "$digest.json"
}

function New-MissionState([object]$Work){
  return [pscustomobject][ordered]@{
    schema='lion.firefox-mediator.mission-thread/v3'
    thread_policy=$ThreadPolicy
    mission_key=(Get-MissionKey $Work)
    mission_id=([string]$Work.mission_id)
    lion_thread_id=([string]$Work.thread_id)
    generation=0
    active_conversation_url=$null
    state='UNBOUND'
    total_turn_count=0
    last_completed_request_id=$null
    last_completed_at=$null
    created_at=(Get-Date).ToUniversalTime().ToString('o')
    updated_at=(Get-Date).ToUniversalTime().ToString('o')
    threads=@()
  }
}

function Get-MissionState([object]$Work){
  $x=Read-Json (Get-MissionStatePath $Work)
  if($x){return $x}
  return New-MissionState $Work
}

function Save-MissionState([object]$Work,[object]$State){
  $State.updated_at=(Get-Date).ToUniversalTime().ToString('o')
  Write-AtomicJson (Get-MissionStatePath $Work) $State
}

function Bind-MissionConversation([object]$Work,[string]$Url,[string]$Reason){
  $state=Get-MissionState $Work
  if(-not [string]::IsNullOrWhiteSpace([string]$state.active_conversation_url) -and (Normalize-Url ([string]$state.active_conversation_url)) -eq (Normalize-Url $Url)){
    return $state
  }
  $state.generation=[int]$state.generation+1
  $state.active_conversation_url=$Url
  $state.state='ACTIVE'
  $entry=[pscustomobject][ordered]@{
    generation=[int]$state.generation
    conversation_url=$Url
    state='ACTIVE'
    open_reason=$Reason
    turn_count=0
    created_at=(Get-Date).ToUniversalTime().ToString('o')
    updated_at=(Get-Date).ToUniversalTime().ToString('o')
    closed_at=$null
    close_reason=$null
  }
  $state.threads=@($state.threads)+@($entry)
  Save-MissionState $Work $state
  return $state
}

function Close-MissionConversation([object]$Work,[string]$Reason){
  $state=Get-MissionState $Work
  $gen=[int]$state.generation
  foreach($t in @($state.threads)){
    if([int]$t.generation -eq $gen -and [string]$t.state -eq 'ACTIVE'){
      $t.state='CLOSED'
      $t.close_reason=$Reason
      $t.closed_at=(Get-Date).ToUniversalTime().ToString('o')
      $t.updated_at=$t.closed_at
    }
  }
  $state.active_conversation_url=$null
  $state.state='ROLLOVER_REQUIRED'
  Save-MissionState $Work $state
  return $state
}

function Note-MissionTurn([object]$Work){
  $state=Get-MissionState $Work
  if([string]$state.last_completed_request_id -eq [string]$Work.request_id){return $state}
  $state.total_turn_count=[int]$state.total_turn_count+1
  $state.last_completed_request_id=[string]$Work.request_id
  $state.last_completed_at=(Get-Date).ToUniversalTime().ToString('o')
  $gen=[int]$state.generation
  foreach($t in @($state.threads)){
    if([int]$t.generation -eq $gen -and [string]$t.state -eq 'ACTIVE'){
      $t.turn_count=[int]$t.turn_count+1
      $t.updated_at=(Get-Date).ToUniversalTime().ToString('o')
    }
  }
  Save-MissionState $Work $state
  return $state
}

function Note-MissionTurnByKey([string]$MissionKey,[string]$RequestId){
  if([string]::IsNullOrWhiteSpace($MissionKey) -or [string]::IsNullOrWhiteSpace($RequestId)){return $null}
  $path=Join-Path $MissionThreads "$((Get-Sha256Text $MissionKey)).json"
  $state=Read-Json $path
  if(-not $state){return $null}
  if([string]$state.last_completed_request_id -eq $RequestId){return $state}
  $state.total_turn_count=[int]$state.total_turn_count+1
  $state.last_completed_request_id=$RequestId
  $state.last_completed_at=(Get-Date).ToUniversalTime().ToString('o')
  $gen=[int]$state.generation
  foreach($t in @($state.threads)){
    if([int]$t.generation -eq $gen -and [string]$t.state -eq 'ACTIVE'){
      $t.turn_count=[int]$t.turn_count+1
      $t.updated_at=(Get-Date).ToUniversalTime().ToString('o')
    }
  }
  $state.updated_at=(Get-Date).ToUniversalTime().ToString('o')
  Write-AtomicJson $path $state
  return $state
}

function Reconcile-TerminalJournals {
  foreach($file in @(Get-ChildItem -File -Filter '*.json' $Journal)){
    $j=Read-Json $file.FullName
    if(-not $j -or [string]$j.state -ne 'SEND_CONFIRMED'){continue}
    $rid=[string]$j.request_id
    if([string]::IsNullOrWhiteSpace($rid)){continue}
    $receipt=Read-Json (Join-Path $Receipts "$rid.json")
    if(-not $receipt -or [string]$receipt.status -ne 'RESPONDED' -or [string]::IsNullOrWhiteSpace([string]$receipt.receipt_digest)){continue}
    $state=Note-MissionTurnByKey ([string]$j.mission_key) $rid
    $value=[ordered]@{}
    foreach($p in $j.PSObject.Properties){$value[$p.Name]=$p.Value}
    $value.state='RECEIPT_CONFIRMED'
    $value.receipt_digest=[string]$receipt.receipt_digest
    $value.response_source='BROKER_RECEIPT'
    $value.updated_at=(Get-Date).ToUniversalTime().ToString('o')
    Write-AtomicJson $file.FullName $value
  }
}

function Open-BoundConversation([System.Windows.Automation.AutomationElement]$Window,[string]$Url){
  $existing=Ensure-Conversation $Url
  if($existing){return $existing}
  Navigate-ToUrl $Window $Url
  $deadline=(Get-Date).AddSeconds(20)
  while((Get-Date) -lt $deadline){
    Start-Sleep -Milliseconds 400
    $conversation=Ensure-Conversation $Url
    if($conversation){return $conversation}
  }
  return $null
}

function Get-QuestionOccurrenceCount([System.Windows.Automation.AutomationElement]$Root,[string]$Question){
  if(-not $Root -or [string]::IsNullOrWhiteSpace($Question)){return 0}
  $text=Get-DocumentElementText $Root
  if([string]::IsNullOrWhiteSpace($text)){return 0}
  $needle=($Question -replace '\s+',' ').Trim()
  $hay=($text -replace '\s+',' ')
  if([string]::IsNullOrWhiteSpace($needle)){return 0}
  return [regex]::Matches($hay,[regex]::Escape($needle),[System.Text.RegularExpressions.RegexOptions]::IgnoreCase).Count
}

function Set-SendUnknown([string]$JournalPath,[object]$Journal,[string]$Reason){
  $value=[ordered]@{}
  foreach($p in $Journal.PSObject.Properties){$value[$p.Name]=$p.Value}
  $value.state='SEND_UNKNOWN'
  $value.unknown_reason=$Reason
  $value.updated_at=(Get-Date).ToUniversalTime().ToString('o')
  Write-AtomicJson $JournalPath $value
  Write-Status 'DEGRADED' @{
    reason='SEND_UNKNOWN_RECONCILE_REQUIRED'
    request_id=$value.request_id
    unknown_reason=$Reason
    retry_policy='RECONCILE_FIRST_NO_BLIND_RETRY'
    new_thread_policy=$ThreadPolicy
  }
}

function Process-One {
  $file=Get-ChildItem -File -Filter '*.json' $Inbox | Sort-Object Name | Select-Object -First 1
  if(-not $file){return}
  if(Test-BackoffActive){return}

  $work=Read-Json $file.FullName
  if(-not $work -or $work.transport -ne $Transport -or [string]::IsNullOrWhiteSpace([string]$work.question)){return}

  $rid=[string]$work.request_id
  $jpath=Join-Path $Journal "$rid.json"
  $j=Read-Json $jpath
  if($j -and $j.state -in @('OUTBOX_WRITTEN','RECEIPT_CONFIRMED')){return}

  $missionKey=Get-MissionKey $work
  $missionState=Get-MissionState $work
  $conversation=$null
  $createdNew=$false
  $rolloverReason=$null
  $beforeAssistantDigest=''

  if($j -and $j.state -eq 'SEND_UNKNOWN'){
    $reason=[string]$j.unknown_reason;if([string]::IsNullOrWhiteSpace($reason)){$reason='PERSISTED_UNKNOWN_SEND_EFFECT'}
    Set-SendUnknown $jpath $j $reason
    return
  }
  if($j -and $j.state -eq 'INTENT_DURABLE'){
    # No external send can occur before SEND_ATTEMPT is durably recorded.
    # Re-entering normal preparation is therefore safe.
    $j=$null
  }
  if($j -and $j.state -eq 'SEND_ATTEMPT'){
    $beforeAssistantDigest=[string]$j.before_assistant_digest
    if(-not [string]::IsNullOrWhiteSpace([string]$j.conversation_url)){
      $conversation=Open-BoundConversationAny ([string]$j.conversation_url)
      if(-not $conversation){
        Set-SendUnknown $jpath $j 'ATTEMPT_CONVERSATION_NOT_OPEN'
        return
      }
      $currentCount=Get-QuestionOccurrenceCount $conversation.Root ([string]$work.question)
      if($currentCount -le [int]$j.before_question_count){
        Set-SendUnknown $jpath $j 'ATTEMPT_EFFECT_NOT_PROVABLE_IN_BOUND_CONVERSATION'
        return
      }
      $confirmed=[ordered]@{}
      foreach($p in $j.PSObject.Properties){$confirmed[$p.Name]=$p.Value}
      $confirmed.state='SEND_CONFIRMED';$confirmed.conversation_url=$conversation.Url
      $confirmed.updated_at=(Get-Date).ToUniversalTime().ToString('o')
      Write-AtomicJson $jpath $confirmed
      Note-Send $work
      $j=Read-Json $jpath
    } else {
      $projectHome=Ensure-ProjectHome
      if(-not $projectHome){
        Set-SendUnknown $jpath $j 'ATTEMPT_PROJECT_HOME_NOT_OPEN'
        return
      }
      try {$conversation=Wait-NewConversation $projectHome.Window $projectHome.Url ([string]$work.question) $null}
      catch {
        Set-SendUnknown $jpath $j 'ATTEMPT_NEW_CONVERSATION_NOT_PROVABLE'
        return
      }
      $missionState=Bind-MissionConversation $work $conversation.Url 'RECOVERED_AFTER_SEND_ATTEMPT'
      $confirmed=[ordered]@{}
      foreach($p in $j.PSObject.Properties){$confirmed[$p.Name]=$p.Value}
      $confirmed.state='SEND_CONFIRMED';$confirmed.conversation_url=$conversation.Url
      $confirmed.generation=$missionState.generation;$confirmed.recovered_after_send=$true
      $confirmed.updated_at=(Get-Date).ToUniversalTime().ToString('o')
      Write-AtomicJson $jpath $confirmed
      Note-Send $work
      $j=Read-Json $jpath
    }
  }
  if($j -and $j.state -in @('SEND_CONFIRMED','RESPONSE_RECONCILED')){
    $beforeAssistantDigest=[string]$j.before_assistant_digest
    if(-not [string]::IsNullOrWhiteSpace([string]$j.conversation_url)){
      $conversation=Open-BoundConversationAny ([string]$j.conversation_url)
      if(-not $conversation){throw 'RECOVERY_CONVERSATION_NOT_OPEN'}
    } else {
      $projectHome=Ensure-ProjectHome
      if(-not $projectHome){return}
      try {$conversation=Wait-NewConversation $projectHome.Window $projectHome.Url ([string]$work.question) $null}
      catch {
        Set-SendUnknown $jpath $j 'CONFIRMED_SEND_CONVERSATION_NOT_RECOVERABLE'
        return
      }
      $missionState=Bind-MissionConversation $work $conversation.Url 'RECOVERED_AFTER_CONFIRMED_SEND'
      $updated=[ordered]@{}
      foreach($p in $j.PSObject.Properties){$updated[$p.Name]=$p.Value}
      $updated.conversation_url=$conversation.Url;$updated.generation=$missionState.generation
      $updated.updated_at=(Get-Date).ToUniversalTime().ToString('o')
      Write-AtomicJson $jpath $updated
      $j=Read-Json $jpath
    }
  }
  elseif($j -and $j.state -eq 'CONVERSATION_BOUND' -and $j.conversation_url){
    $conversation=Open-BoundConversationAny ([string]$j.conversation_url)
    if(-not $conversation){throw 'RECOVERY_CONVERSATION_NOT_OPEN'}
    $beforeAssistantDigest=[string]$j.before_assistant_digest
    if(Test-RateLimitInDocument $conversation.Root){
      Set-RateLimitBackoff 'BOUND_CONVERSATION_RATE_LIMIT'
      return
    }
    Wait-SendBudget $work
    $beforeQuestionCount=Get-QuestionOccurrenceCount $conversation.Root ([string]$work.question)
    Write-AtomicJson $jpath ([ordered]@{
      request_id=$rid;state='INTENT_DURABLE';claim_generation=$work.claim_generation
      mission_key=$missionKey;mission_id=$work.mission_id
      conversation_url=$conversation.Url;generation=$missionState.generation
      before_assistant_digest=$beforeAssistantDigest;before_question_count=$beforeQuestionCount
      question_digest=$work.question_digest;reused_conversation=$true
      updated_at=(Get-Date).ToUniversalTime().ToString('o')
    })
    Set-Prompt $conversation.Prompt ([string]$work.question)
    Start-Sleep -Milliseconds 250
    $docAll=Get-All $conversation.Root;$prompt=Find-Prompt $docAll
    Write-AtomicJson $jpath ([ordered]@{
      request_id=$rid;state='SEND_ATTEMPT';claim_generation=$work.claim_generation
      mission_key=$missionKey;mission_id=$work.mission_id
      conversation_url=$conversation.Url;generation=$missionState.generation
      before_assistant_digest=$beforeAssistantDigest;before_question_count=$beforeQuestionCount
      question_digest=$work.question_digest;reused_conversation=$true
      updated_at=(Get-Date).ToUniversalTime().ToString('o')
    })
    Send-Prompt $prompt $docAll
    Write-AtomicJson $jpath ([ordered]@{
      request_id=$rid;state='SEND_CONFIRMED';claim_generation=$work.claim_generation
      mission_key=$missionKey;mission_id=$work.mission_id
      conversation_url=$conversation.Url;generation=$missionState.generation
      before_assistant_digest=$beforeAssistantDigest;before_question_count=$beforeQuestionCount
      question_digest=$work.question_digest;reused_conversation=$true
      updated_at=(Get-Date).ToUniversalTime().ToString('o')
    })
    Note-Send $work
    $j=Read-Json $jpath
  }
  elseif($j -and $j.conversation_url){
    $conversation=Open-BoundConversationAny ([string]$j.conversation_url)
    if(-not $conversation){throw 'RECOVERY_CONVERSATION_NOT_OPEN'}
    $beforeAssistantDigest=[string]$j.before_assistant_digest
  }
  else {
    $projectHome=$null
    $activeUrl=[string]$missionState.active_conversation_url
    if(-not [string]::IsNullOrWhiteSpace($activeUrl)){
      $conversation=Open-BoundConversationAny $activeUrl
      if(-not $conversation){
        $window=Get-AnyFirefoxWindow
        $terminalReason=Get-ExplicitTerminalReason $window
        if($terminalReason){
          $null=Close-MissionConversation $work $terminalReason
          $missionState=Get-MissionState $work
          $rolloverReason=$terminalReason
        } else {
          if(Test-WindowRateLimit $window){
            Set-RateLimitBackoff 'BOUND_CHAT_RATE_LIMIT_TRANSIENT'
          } else {
            $currentUrl=Get-WindowUrl $window
            Write-Status 'DEGRADED' @{
              reason='BOUND_CHAT_TRANSIENT_UNAVAILABLE_NO_ROLLOVER'
              expected_url=$activeUrl
              current_url=$currentUrl
              new_thread_policy=$ThreadPolicy
            }
          }
          return
        }
      }
    }

    if($conversation){
      $docAll=Get-All $conversation.Root
      $beforeAssistant=Extract-LastAssistantFromElements $docAll
      if(-not [string]::IsNullOrWhiteSpace($beforeAssistant)){$beforeAssistantDigest=Get-Sha256Text $beforeAssistant}
      Write-AtomicJson $jpath ([ordered]@{
        request_id=$rid;state='CONVERSATION_BOUND';claim_generation=$work.claim_generation
        mission_key=$missionKey;mission_id=$work.mission_id
        conversation_url=$conversation.Url;generation=$missionState.generation
        before_assistant_digest=$beforeAssistantDigest
        reused_conversation=$true;updated_at=(Get-Date).ToUniversalTime().ToString('o')
      })
      if(Test-RateLimitInDocument $conversation.Root){
        Set-RateLimitBackoff 'BOUND_CONVERSATION_RATE_LIMIT'
        return
      }
      Wait-SendBudget $work
      $beforeQuestionCount=Get-QuestionOccurrenceCount $conversation.Root ([string]$work.question)
      Write-AtomicJson $jpath ([ordered]@{
        request_id=$rid;state='INTENT_DURABLE';claim_generation=$work.claim_generation
        mission_key=$missionKey;mission_id=$work.mission_id
        conversation_url=$conversation.Url;generation=$missionState.generation
        before_assistant_digest=$beforeAssistantDigest;before_question_count=$beforeQuestionCount
        question_digest=$work.question_digest;reused_conversation=$true
        updated_at=(Get-Date).ToUniversalTime().ToString('o')
      })
      Set-Prompt $conversation.Prompt ([string]$work.question)
      Start-Sleep -Milliseconds 250
      $docAll=Get-All $conversation.Root;$prompt=Find-Prompt $docAll
      Write-AtomicJson $jpath ([ordered]@{
        request_id=$rid;state='SEND_ATTEMPT';claim_generation=$work.claim_generation
        mission_key=$missionKey;mission_id=$work.mission_id
        conversation_url=$conversation.Url;generation=$missionState.generation
        before_assistant_digest=$beforeAssistantDigest;before_question_count=$beforeQuestionCount
        question_digest=$work.question_digest;reused_conversation=$true
        updated_at=(Get-Date).ToUniversalTime().ToString('o')
      })
      Send-Prompt $prompt $docAll
      Write-AtomicJson $jpath ([ordered]@{
        request_id=$rid;state='SEND_CONFIRMED';claim_generation=$work.claim_generation
        mission_key=$missionKey;mission_id=$work.mission_id
        conversation_url=$conversation.Url;generation=$missionState.generation
        before_assistant_digest=$beforeAssistantDigest;before_question_count=$beforeQuestionCount
        question_digest=$work.question_digest;reused_conversation=$true
        updated_at=(Get-Date).ToUniversalTime().ToString('o')
      })
      Note-Send $work
    }
    else {
      $projectHome=Ensure-ProjectHome
      if(-not $projectHome){return}
      if(Test-RateLimitInDocument $projectHome.Root){
        Set-RateLimitBackoff 'PROJECT_HOME_RATE_LIMIT'
        return
      }
      $beforeChats=Get-ProjectChatSnapshot $projectHome.Window
      Write-AtomicJson $jpath ([ordered]@{
        request_id=$rid;state='PROJECT_HOME_BOUND';claim_generation=$work.claim_generation
        mission_key=$missionKey;mission_id=$work.mission_id
        rollover_reason=$rolloverReason;updated_at=(Get-Date).ToUniversalTime().ToString('o')
      })
      Wait-SendBudget $work
      $beforeQuestionCount=Get-QuestionOccurrenceCount $projectHome.Root ([string]$work.question)
      Write-AtomicJson $jpath ([ordered]@{
        request_id=$rid;state='INTENT_DURABLE';claim_generation=$work.claim_generation
        mission_key=$missionKey;mission_id=$work.mission_id
        project_home_url=$projectHome.Url;rollover_reason=$rolloverReason
        before_assistant_digest='';before_question_count=$beforeQuestionCount
        question_digest=$work.question_digest;reused_conversation=$false
        updated_at=(Get-Date).ToUniversalTime().ToString('o')
      })
      Set-Prompt $projectHome.Prompt ([string]$work.question)
      Start-Sleep -Milliseconds 250
      $docAll=Get-All $projectHome.Root;$prompt=Find-Prompt $docAll
      Write-AtomicJson $jpath ([ordered]@{
        request_id=$rid;state='SEND_ATTEMPT';claim_generation=$work.claim_generation
        mission_key=$missionKey;mission_id=$work.mission_id
        project_home_url=$projectHome.Url;rollover_reason=$rolloverReason
        before_assistant_digest='';before_question_count=$beforeQuestionCount
        question_digest=$work.question_digest;reused_conversation=$false
        updated_at=(Get-Date).ToUniversalTime().ToString('o')
      })
      Send-Prompt $prompt $docAll
      Write-AtomicJson $jpath ([ordered]@{
        request_id=$rid;state='SEND_CONFIRMED';claim_generation=$work.claim_generation
        mission_key=$missionKey;mission_id=$work.mission_id
        project_home_url=$projectHome.Url;rollover_reason=$rolloverReason
        before_assistant_digest='';before_question_count=$beforeQuestionCount
        question_digest=$work.question_digest;reused_conversation=$false
        updated_at=(Get-Date).ToUniversalTime().ToString('o')
      })
      Note-Send $work
      $conversation=Wait-NewConversation $projectHome.Window $projectHome.Url ([string]$work.question) $beforeChats
      $openReason=if($rolloverReason){$rolloverReason}else{'MISSION_FIRST_THREAD'}
      $missionState=Bind-MissionConversation $work $conversation.Url $openReason
      $createdNew=$true
      Write-AtomicJson $jpath ([ordered]@{
        request_id=$rid;state='SEND_CONFIRMED';claim_generation=$work.claim_generation
        mission_key=$missionKey;mission_id=$work.mission_id
        conversation_url=$conversation.Url;generation=$missionState.generation
        before_assistant_digest='';before_question_count=$beforeQuestionCount
        question_digest=$work.question_digest;reused_conversation=$false
        conversation_bound=$true;updated_at=(Get-Date).ToUniversalTime().ToString('o')
      })
    }
  }

  $liveJ=Read-Json $jpath
  if($liveJ -and $liveJ.before_assistant_digest){$beforeAssistantDigest=[string]$liveJ.before_assistant_digest}

  $answer=''
  if($liveJ -and $liveJ.state -eq 'RESPONSE_RECONCILED' -and -not [string]::IsNullOrWhiteSpace([string]$liveJ.response_text)){
    $answer=[string]$liveJ.response_text
  }
  $deadline=(Get-Date).AddMinutes(3)
  $stable='';$stableAt=$null
  $receiptPath=Join-Path $Receipts "$rid.json"
  while([string]::IsNullOrWhiteSpace($answer) -and (Get-Date) -lt $deadline){
    $receipt=Read-Json $receiptPath
    if($receipt -and [string]$receipt.status -eq 'RESPONDED' -and -not [string]::IsNullOrWhiteSpace([string]$receipt.receipt_digest)){
      $missionState=Note-MissionTurn $work
      Write-AtomicJson $jpath ([ordered]@{
        request_id=$rid;state='RECEIPT_CONFIRMED';claim_generation=$work.claim_generation
        mission_key=$missionKey;mission_id=$work.mission_id
        conversation_url=$conversation.Url;generation=$missionState.generation
        receipt_digest=[string]$receipt.receipt_digest
        response_source='BROKER_RECEIPT';retry_policy='RECONCILE_FIRST_NO_BLIND_RETRY'
        updated_at=(Get-Date).ToUniversalTime().ToString('o')
      })
      return
    }
    Start-Sleep -Milliseconds 700
    try {$docAll=Get-All $conversation.Root} catch {continue}
    if(Test-RateLimitInDocument $conversation.Root){
      Set-RateLimitBackoff 'RATE_LIMIT_DURING_RESPONSE'
      throw 'RATE_LIMITED_NO_RETRY'
    }
    if(Generation-InProgress $docAll){$stable='';$stableAt=$null;continue}
    $candidate=Extract-LastAssistantFromElements $docAll
    if([string]::IsNullOrWhiteSpace($candidate)){continue}
    if(-not [string]::IsNullOrWhiteSpace($beforeAssistantDigest) -and (Get-Sha256Text $candidate) -eq $beforeAssistantDigest){continue}
    if($candidate -match '^(My.li|Mysli|Thinking|Working|Generating|Analyzing|Analiz.*|Rozum.*|Przetwarz.*)\s*[.]*$'){$stable='';$stableAt=$null;continue}
    if($candidate -eq $stable){
      if(-not $stableAt){$stableAt=Get-Date}
      if(((Get-Date)-$stableAt).TotalSeconds -ge 3){$answer=$candidate;break}
    } else {$stable=$candidate;$stableAt=Get-Date}
  }
  if([string]::IsNullOrWhiteSpace($answer)){throw 'ASSISTANT_RESPONSE_TIMEOUT'}

  $missionState=Note-MissionTurn $work
  Write-AtomicJson $jpath ([ordered]@{
    request_id=$rid;state='RESPONSE_RECONCILED';claim_generation=$work.claim_generation
    mission_key=$missionKey;mission_id=$work.mission_id
    conversation_url=$conversation.Url;generation=$missionState.generation
    before_assistant_digest=$beforeAssistantDigest
    response_digest=(Get-Sha256Text $answer);response_text=$answer
    retry_policy='RECONCILE_FIRST_NO_BLIND_RETRY'
    updated_at=(Get-Date).ToUniversalTime().ToString('o')
  })

  $rename=[pscustomobject]@{
    state='AUTO_TITLE_ONLY_NO_POST_RESPONSE_NAVIGATION'
    title=$null
    reason='RATE_LIMIT_SAFE_PATH'
  }

  Write-AtomicJson (Join-Path $Outbox "$rid.json") ([ordered]@{
    request_id=$rid
    claim_generation=$work.claim_generation
    answer=$answer
    model_identity='ChatGPT UI / dedicated minimized Edge / LION_EVOLUSION'
    transport=$Transport
    authority_effect='NONE'
    project_title=$ProjectTitle
    mission_id=$work.mission_id
    mission_key=$missionKey
    conversation_url=$conversation.Url
    conversation_generation=$missionState.generation
    conversation_reused=(-not $createdNew)
    conversation_title=$rename.title
    conversation_title_state=$rename.state
    conversation_title_reason=$rename.reason
    thread_policy=$ThreadPolicy
    new_thread_per_request=$false
  })

  Write-AtomicJson $jpath ([ordered]@{
    request_id=$rid;state='OUTBOX_WRITTEN';claim_generation=$work.claim_generation
    mission_key=$missionKey;mission_id=$work.mission_id
    conversation_url=$conversation.Url;generation=$missionState.generation
    conversation_reused=(-not $createdNew)
    conversation_title=$rename.title;conversation_title_state=$rename.state
    updated_at=(Get-Date).ToUniversalTime().ToString('o')
  })
}

$LastReadinessProbe=[DateTime]::MinValue
while($true){
  try {
    if(((Get-Date)-$LastReadinessProbe).TotalSeconds -ge 10){
      $null=Refresh-Readiness
      $LastReadinessProbe=Get-Date
    }
    Reconcile-TerminalJournals
    Process-One
  } catch { Write-Status 'DEGRADED' @{reason=$_.Exception.Message;new_thread_policy=$ThreadPolicy} }
  if($Once){break}
  Start-Sleep -Milliseconds ([Math]::Max(250,$IntervalMs))
}
