param(
  [string]$Ipc = "\\wsl.localhost\LION-AUTH-LAB\var\lib\sentinelx\uploads\lion-mission-control-v3\firefox-mediator-ipc",
  [string]$ProjectHomeUrl = "https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project",
  [string]$ProjectTitle = "LION_EVOLUSION",
  [string]$ConversationTitlePrefix = "LION SaaS",
  [int]$IntervalMs = 700,
  [switch]$Once
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms

$Transport = 'CHATGPT_FIREFOX_PROJECT_MEDIATED'
$MediatorId = 'LION_FIREFOX_OPEN_SESSION_MEDIATOR_R2'
$Firefox = 'C:\Program Files\Firefox Developer Edition\firefox.exe'
$Inbox = Join-Path $Ipc 'inbox'
$Outbox = Join-Path $Ipc 'outbox'
$Journal = Join-Path $Ipc 'journal'
$Receipts = Join-Path $Ipc 'receipts'
foreach($d in @($Ipc,$Inbox,$Outbox,$Journal,$Receipts)){ New-Item -ItemType Directory -Force -Path $d | Out-Null }

function Write-AtomicJson([string]$Path,[object]$Value){
  $tmp = "$Path.tmp"
  $json=$Value | ConvertTo-Json -Depth 12
  [System.IO.File]::WriteAllText($tmp,$json,(New-Object System.Text.UTF8Encoding($false)))
  Move-Item -Force $tmp $Path
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
    chat_title='NEW_THREAD_PER_REQUEST'
    browser='Firefox Developer Edition / existing authenticated session'
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

function Get-FirefoxRoots {
  $desktop=[System.Windows.Automation.AutomationElement]::RootElement
  $wins=$desktop.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
  $out=@()
  for($i=0;$i -lt $wins.Count;$i++){
    $w=$wins.Item($i)
    if($w.Current.ClassName -eq 'MozillaWindowClass' -and $w.Current.ProcessId -gt 0){ $out += $w }
  }
  return $out
}

function Get-All([System.Windows.Automation.AutomationElement]$Root){
  return ,$Root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
}

function Get-Url([System.Windows.Automation.AutomationElementCollection]$All){
  for($i=0;$i -lt $All.Count;$i++){
    $e=$All.Item($i)
    if($e.Current.AutomationId -eq 'urlbar-input'){
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
    if($doc.Current.ControlType -ne [System.Windows.Automation.ControlType]::Document -or $doc.Current.IsOffscreen){continue}
    $name=[string]$doc.Current.Name
    if($name -notlike "*$ProjectTitle*"){continue}
    try {$docAll=Get-All $doc} catch {continue}
    $prompt=Find-Prompt $docAll
    if($prompt){return [pscustomobject]@{Window=$Window;Root=$doc;All=$docAll;Prompt=$prompt;DocumentName=$name}}
  }
  return $null
}

function Find-ProjectHome {
  $target=Normalize-Url $ProjectHomeUrl
  foreach($window in @(Get-FirefoxRoots)){
    try {$windowAll=Get-All $window} catch {continue}
    $url=Get-Url $windowAll
    if((Normalize-Url $url) -ne $target){continue}
    $doc=Find-VisibleProjectDocument $window
    if(-not $doc){continue}
    $doc | Add-Member -NotePropertyName Url -NotePropertyValue $url -Force
    return $doc
  }
  return $null
}

function Ensure-ProjectHome {
  $projectHome=Find-ProjectHome
  if(-not $projectHome){
    if(-not (Test-Path $Firefox)){throw 'FIREFOX_EXECUTABLE_NOT_FOUND'}
    Start-Process -FilePath $Firefox -ArgumentList @('-new-window',$ProjectHomeUrl) | Out-Null
    $deadline=(Get-Date).AddSeconds(20)
    while((Get-Date) -lt $deadline){
      Start-Sleep -Milliseconds 500
      $projectHome=Find-ProjectHome
      if($projectHome){break}
    }
  }
  if(-not $projectHome){
    Write-Status 'PROJECT_BINDING_REQUIRED' @{project_home_url=$ProjectHomeUrl;new_thread_policy='PER_REQUEST';project_verified=$false}
    return $null
  }
  Write-Status 'READY' @{current_url=$projectHome.Url;document_name=$projectHome.DocumentName;session_mode='EXISTING_AUTHENTICATED_FIREFOX';project_verified=$true;chat_verified=$true;project_home_verified=$true;new_thread_policy='PER_REQUEST'}
  return $projectHome
}

function Navigate-ToUrl([System.Windows.Automation.AutomationElement]$Window,[string]$Url){
  $all=Get-All $Window
  $bar=$null
  for($i=0;$i -lt $all.Count;$i++){
    $e=$all.Item($i)
    if($e.Current.AutomationId -eq 'urlbar-input'){$bar=$e;break}
  }
  if(-not $bar){throw 'URLBAR_NOT_FOUND'}
  $vp=$null
  if(-not $bar.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$vp)){throw 'URLBAR_VALUE_PATTERN_REQUIRED'}
  $vp.SetValue($Url);$bar.SetFocus();[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
}

function Ensure-Conversation([string]$Url){
  $target=Normalize-Url $Url
  foreach($window in @(Get-FirefoxRoots)){
    try {$windowAll=Get-All $window} catch {continue}
    $current=Get-Url $windowAll
    if((Normalize-Url $current) -ne $target){continue}
    $doc=Find-VisibleProjectDocument $window
    if($doc){$doc | Add-Member -NotePropertyName Url -NotePropertyValue $current -Force;return $doc}
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

function Process-One {
  $file=Get-ChildItem -File -Filter '*.json' $Inbox | Sort-Object Name | Select-Object -First 1
  if(-not $file){$null=Ensure-ProjectHome;return}
  $work=Read-Json $file.FullName
  if(-not $work -or $work.transport -ne $Transport -or [string]::IsNullOrWhiteSpace([string]$work.question)){return}
  $rid=[string]$work.request_id;$jpath=Join-Path $Journal "$rid.json";$j=Read-Json $jpath
  if($j -and $j.state -eq 'OUTBOX_WRITTEN'){return}
  $conversation=$null;$plannedTitle=New-ConversationTitle ([string]$work.question) $rid
  if($j -and $j.conversation_url){
    $conversation=Ensure-Conversation ([string]$j.conversation_url)
    if(-not $conversation){throw 'RECOVERY_CONVERSATION_NOT_OPEN'}
  } elseif($j -and $j.state -in @('SEND_TRIGGERED','USER_MESSAGE_OBSERVED','ASSISTANT_MESSAGE_OBSERVED')){
    $projectHome=Ensure-ProjectHome
    if(-not $projectHome){return}
    $conversation=Wait-NewConversation $projectHome.Window $projectHome.Url ([string]$work.question) $null
    Write-AtomicJson $jpath ([ordered]@{request_id=$rid;state='CONVERSATION_BOUND';claim_generation=$work.claim_generation;conversation_url=$conversation.Url;planned_title=$plannedTitle;recovered_after_send=$true;updated_at=(Get-Date).ToUniversalTime().ToString('o')})
  } else {
    $projectHome=Ensure-ProjectHome
    if(-not $projectHome){return}
    $beforeChats=Get-ProjectChatSnapshot $projectHome.Window
    Write-AtomicJson $jpath ([ordered]@{request_id=$rid;state='PROJECT_HOME_BOUND';claim_generation=$work.claim_generation;planned_title=$plannedTitle;updated_at=(Get-Date).ToUniversalTime().ToString('o')})
    Set-Prompt $projectHome.Prompt ([string]$work.question)
    Start-Sleep -Milliseconds 250
    $docAll=Get-All $projectHome.Root;$prompt=Find-Prompt $docAll
    Send-Prompt $prompt $docAll
    Write-AtomicJson $jpath ([ordered]@{request_id=$rid;state='SEND_TRIGGERED';claim_generation=$work.claim_generation;planned_title=$plannedTitle;updated_at=(Get-Date).ToUniversalTime().ToString('o')})
    $conversation=Wait-NewConversation $projectHome.Window $projectHome.Url ([string]$work.question) $beforeChats
    Write-AtomicJson $jpath ([ordered]@{request_id=$rid;state='CONVERSATION_BOUND';claim_generation=$work.claim_generation;conversation_url=$conversation.Url;planned_title=$plannedTitle;updated_at=(Get-Date).ToUniversalTime().ToString('o')})
  }
  $deadline=(Get-Date).AddMinutes(3);$answer='';$stable='';$stableAt=$null
  while((Get-Date) -lt $deadline){
    Start-Sleep -Milliseconds 700
    try {$docAll=Get-All $conversation.Root} catch {continue}
    if(Generation-InProgress $docAll){$stable='';$stableAt=$null;continue}
    $candidate=Extract-LastAssistantFromElements $docAll
    if([string]::IsNullOrWhiteSpace($candidate)){continue}
    if($candidate -match '^(My.li|Mysli|Thinking|Working|Generating|Analyzing|Analiz.*|Rozum.*|Przetwarz.*)\s*[.]*$'){$stable='';$stableAt=$null;continue}
    if($candidate -eq $stable){
      if(-not $stableAt){$stableAt=Get-Date}
      if(((Get-Date)-$stableAt).TotalSeconds -ge 3){$answer=$candidate;break}
    } else {$stable=$candidate;$stableAt=Get-Date}
  }
  if([string]::IsNullOrWhiteSpace($answer)){throw 'ASSISTANT_RESPONSE_TIMEOUT'}
  Write-AtomicJson $jpath ([ordered]@{request_id=$rid;state='ASSISTANT_MESSAGE_OBSERVED';claim_generation=$work.claim_generation;conversation_url=$conversation.Url;planned_title=$plannedTitle;updated_at=(Get-Date).ToUniversalTime().ToString('o')})
  $rename=[pscustomobject]@{state='NOT_ATTEMPTED';title=$null;reason=$null}
  try {
    Navigate-ToUrl $conversation.Window $ProjectHomeUrl
    $projectHomeAfter=$null;$homeDeadline=(Get-Date).AddSeconds(20)
    while((Get-Date) -lt $homeDeadline -and -not $projectHomeAfter){Start-Sleep -Milliseconds 500;$projectHomeAfter=Find-ProjectHome}
    if($projectHomeAfter){$rename=Rename-ConversationFromProjectHome $projectHomeAfter.Window ([string]$work.question) $plannedTitle}
    else {$rename=[pscustomobject]@{state='RENAME_FAILED';title=$null;reason='PROJECT_HOME_RETURN_TIMEOUT'}}
  } catch {$rename=[pscustomobject]@{state='RENAME_FAILED';title=$null;reason=$_.Exception.Message}}
  Write-AtomicJson (Join-Path $Outbox "$rid.json") ([ordered]@{
    request_id=$rid
    claim_generation=$work.claim_generation
    answer=$answer
    model_identity='ChatGPT UI / existing authenticated Firefox / LION_EVOLUSION'
    transport=$Transport
    authority_effect='NONE'
    conversation_url=$conversation.Url
    conversation_title=$rename.title
    conversation_title_state=$rename.state
    conversation_title_reason=$rename.reason
    new_thread_per_request=$true
  })
  Write-AtomicJson $jpath ([ordered]@{request_id=$rid;state='OUTBOX_WRITTEN';claim_generation=$work.claim_generation;conversation_url=$conversation.Url;conversation_title=$rename.title;conversation_title_state=$rename.state;updated_at=(Get-Date).ToUniversalTime().ToString('o')})
}

while($true){
  try { Process-One } catch { Write-Status 'DEGRADED' @{reason=$_.Exception.Message;new_thread_policy='PER_REQUEST'} }
  if($Once){break}
  Start-Sleep -Milliseconds ([Math]::Max(250,$IntervalMs))
}
