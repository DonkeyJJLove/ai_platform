Option Explicit
Dim shell, appData, powershell, launcher, command, rc
Set shell = CreateObject("WScript.Shell")
appData = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
If Len(appData) = 0 Or InStr(appData, "%") <> 0 Then WScript.Quit 2
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"
launcher = appData & "\LION\operator\Start-LION-Current.ps1"
command = Chr(34) & powershell & Chr(34) & " -NoProfile -WindowStyle Hidden -File " & Chr(34) & launcher & Chr(34)
rc = shell.Run(command, 0, True)
If rc <> 0 Then
 MsgBox "LION nie uruchomil wybranego wydania. Uruchom Start-LION-Current.ps1 -InspectOnly w PowerShell.", 48, "LION Desktop"
End If
