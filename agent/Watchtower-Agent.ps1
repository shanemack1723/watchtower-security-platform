$ErrorActionPreference = "Stop"

$configPath = Join-Path $PSScriptRoot "agent-config.json"

if (-not (Test-Path $configPath)) {
    throw "Agent configuration file was not found: $configPath"
}

$config = Get-Content $configPath -Raw | ConvertFrom-Json
$apiHeaders = @{
    "X-Watchtower-API-Key" = $config.api_key
}

$statePath = Join-Path $PSScriptRoot "agent-state.json"
$lastRecordId = 0

if (Test-Path $statePath) {
    $state = Get-Content $statePath -Raw | ConvertFrom-Json
    $lastRecordId = [long]$state.last_record_id
}

Write-Host "Starting Watchtower Agent..." -ForegroundColor Cyan

$operatingSystem = (Get-CimInstance Win32_OperatingSystem).Caption

$networkConfiguration = Get-NetIPConfiguration |
    Where-Object {
        $_.IPv4DefaultGateway -ne $null -and
        $_.NetAdapter.Status -eq "Up"
    } |
    Select-Object -First 1

if ($networkConfiguration.IPv4Address.IPAddress) {
    $ipAddress = $networkConfiguration.IPv4Address.IPAddress
}
else {
    $ipAddress = "127.0.0.1"
}

$registrationData = @{
    device_id       = $config.device_id
    hostname        = $env:COMPUTERNAME
    operating_system = $operatingSystem
    ip_address      = $ipAddress
    agent_version   = $config.agent_version
}

$registrationJson = $registrationData | ConvertTo-Json

$registrationUrl = "$($config.api_base_url)/devices/register"

try {
    $registeredDevice = Invoke-RestMethod `
        -Uri $registrationUrl `
        -Method Post `
        -Headers $apiHeaders `
        -ContentType "application/json" `
        -Body $registrationJson

    Write-Host "Device registered successfully." -ForegroundColor Green
    Write-Host "Hostname: $($registeredDevice.hostname)"
    Write-Host "IP address: $($registeredDevice.ip_address)"
    Write-Host "Status: $($registeredDevice.status)"
}
catch {
    Write-Host "Device registration failed." -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}

Write-Host ""
Write-Host "Sending device heartbeat..." -ForegroundColor Cyan

$heartbeatUrl = "$($config.api_base_url)/devices/$($config.device_id)/heartbeat"

$heartbeatData = @{
    agent_version = $config.agent_version
}

$heartbeatJson = $heartbeatData | ConvertTo-Json

try {
    $heartbeatResponse = Invoke-RestMethod `
        -Uri $heartbeatUrl `
        -Method Post `
        -Headers $apiHeaders `
        -ContentType "application/json" `
        -Body $heartbeatJson

    Write-Host "Heartbeat sent successfully." -ForegroundColor Green
    Write-Host "Device status: $($heartbeatResponse.status)"
}
catch {
    Write-Host "Heartbeat failed." -ForegroundColor Red
    Write-Host $_.Exception.Message
}

Write-Host ""
Write-Host "Collecting Windows Security events..." -ForegroundColor Cyan

$startTime = (Get-Date).AddMinutes(
    -[int]$config.lookback_minutes
)

$eventFilter = @{
    LogName  = "Security"
    Id       = [int[]]$config.monitored_event_ids
    StartTime = $startTime
}

try {
    $securityEvents = @(
        Get-WinEvent `
    -FilterHashtable $eventFilter `
    -MaxEvents 25 `
    -ErrorAction Stop |
Where-Object {
    $_.RecordId -gt $lastRecordId
} |
Sort-Object RecordId
    )
}
catch {
    Write-Host "Unable to read the Windows Security log." -ForegroundColor Red
    Write-Host "The agent may need to be run as an administrator."
    Write-Host $_.Exception.Message
    exit 1
}

if ($securityEvents.Count -eq 0) {
    Write-Host "No monitored security events were found during the last $($config.lookback_minutes) minutes." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($securityEvents.Count) monitored events."

$eventsSent = 0
$eventsFailed = 0
$eventsUrl = "$($config.api_base_url)/events/"
$highestSuccessfulRecordId = $lastRecordId

foreach ($securityEvent in $securityEvents) {
    $eventMessage = $securityEvent.Message

    if ([string]::IsNullOrWhiteSpace($eventMessage)) {
        $eventMessage = "No Windows event message was available."
    }

    $propertyValues = @(
        $securityEvent.Properties |
        ForEach-Object {
            $_.Value
        }
    )

    $eventData = @{
        device_id       = $config.device_id
        windows_event_id = $securityEvent.Id
        record_id       = $securityEvent.RecordId
        log_name        = $securityEvent.LogName
        provider        = $securityEvent.ProviderName
        level           = if ($securityEvent.LevelDisplayName) {
            $securityEvent.LevelDisplayName
        }
        else {
            "Information"
        }
        message          = $eventMessage
        occurred_at      = $securityEvent.TimeCreated.ToUniversalTime().ToString("o")
        raw_data         = @{
            machine_name   = $securityEvent.MachineName
            task           = $securityEvent.TaskDisplayName
            keywords       = @($securityEvent.KeywordsDisplayNames)
            property_values = $propertyValues
        }
    }

    $eventJson = $eventData | ConvertTo-Json -Depth 6

    try {
    Invoke-RestMethod `
        -Uri $eventsUrl `
        -Method Post `
        -Headers $apiHeaders `
        -ContentType "application/json" `
        -Body $eventJson |
    Out-Null

    $eventsSent++

    if ($securityEvent.RecordId -gt $highestSuccessfulRecordId) {
        $highestSuccessfulRecordId = $securityEvent.RecordId
    }
}
    catch {
        $eventsFailed++

        Write-Host "Failed to send Event ID $($securityEvent.Id)." -ForegroundColor Red
        Write-Host $_.Exception.Message
    }
}

Write-Host ""
Write-Host "Security event collection complete." -ForegroundColor Green
Write-Host "Events sent: $eventsSent"
Write-Host "Events failed: $eventsFailed"

if ($highestSuccessfulRecordId -gt $lastRecordId) {
    $newState = @{
        last_record_id = $highestSuccessfulRecordId
        updated_at     = (Get-Date).ToUniversalTime().ToString("o")
    }

    $newState |
        ConvertTo-Json |
        Set-Content -Path $statePath -Encoding UTF8

    Write-Host "Agent state updated to Record ID $highestSuccessfulRecordId."
}

