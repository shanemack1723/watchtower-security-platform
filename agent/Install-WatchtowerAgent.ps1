$ErrorActionPreference = "Stop"

$taskName = "Watchtower Security Agent"
$agentScript = Join-Path $PSScriptRoot "Watchtower-Agent.ps1"

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal(
    $currentIdentity
)

$isAdministrator = $currentPrincipal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

if (-not $isAdministrator) {
    throw "Run this installer from PowerShell as an administrator."
}

if (-not (Test-Path $agentScript)) {
    throw "Watchtower agent script was not found: $agentScript"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$agentScript`""

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 2)

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

$taskPrincipal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $taskPrincipal `
    -Description "Collects Windows security events and sends Watchtower heartbeats." `
    -Force |
Out-Null

Start-ScheduledTask -TaskName $taskName

Write-Host "Watchtower agent installed successfully." -ForegroundColor Green
Write-Host "Task name: $taskName"
Write-Host "Run interval: Every 2 minutes"
Write-Host "Account: SYSTEM"