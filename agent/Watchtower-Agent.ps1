$ErrorActionPreference = "Stop"
$PSDefaultParameterValues[
    "Invoke-RestMethod:TimeoutSec"
] = 30
$agentMutex = New-Object System.Threading.Mutex(
    $false,
    "Global\WatchtowerSecurityAgent"
)

try {
    $hasAgentLock = $agentMutex.WaitOne(
        0,
        $false
    )
}
catch [System.Threading.AbandonedMutexException] {
    $hasAgentLock = $true
}

if (-not $hasAgentLock) {
    Write-Host "Another Watchtower Agent run is already active."
    exit 0
}

$logDirectory = Join-Path $PSScriptRoot "logs"
$transcriptStarted = $false

try {
    if (-not (Test-Path $logDirectory)) {
        New-Item `
            -Path $logDirectory `
            -ItemType Directory `
            -Force |
        Out-Null
    }

    $logFileName = (
        "watchtower-agent-{0}.log" -f
        (Get-Date).ToString("yyyy-MM-dd")
    )

    $logPath = Join-Path $logDirectory $logFileName

    Start-Transcript `
        -Path $logPath `
        -Append |
    Out-Null

    $transcriptStarted = $true

    Get-ChildItem `
        -Path $logDirectory `
        -Filter "watchtower-agent-*.log" `
        -File |
    Where-Object {
        $_.LastWriteTime -lt (Get-Date).AddDays(-14)
    } |
    Remove-Item -Force
}
catch {
    Write-Warning "Agent logging could not be started."
    Write-Warning $_.Exception.Message
}

$configPath = Join-Path $PSScriptRoot "agent-config.json"

if (-not (Test-Path $configPath)) {
    throw "Agent configuration file was not found: $configPath"
}

$config = Get-Content $configPath -Raw | ConvertFrom-Json
$apiHeaders = @{
    "X-Watchtower-API-Key" = $config.api_key
}

$queueDirectory = Join-Path $PSScriptRoot "queue"
$maximumQueuedEvents = 10000

if (-not (Test-Path $queueDirectory)) {
    New-Item `
        -Path $queueDirectory `
        -ItemType Directory `
        -Force |
    Out-Null
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
    Write-Host (
        "Continuing in offline queue mode."
    ) -ForegroundColor Yellow
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
Write-Host "Collecting device telemetry..." -ForegroundColor Cyan

try {
    $osInfo = Get-CimInstance Win32_OperatingSystem
    $processorInfo = Get-CimInstance Win32_Processor

    $systemDrive = Get-CimInstance Win32_LogicalDisk `
        -Filter "DeviceID='$($env:SystemDrive)'"

    $cpuPercent = (
        $processorInfo |
        Measure-Object -Property LoadPercentage -Average
    ).Average

    $memoryUsed = (
        $osInfo.TotalVisibleMemorySize -
        $osInfo.FreePhysicalMemory
    )

    $memoryPercent = (
        $memoryUsed /
        $osInfo.TotalVisibleMemorySize
    ) * 100

    $diskTotalGb = $systemDrive.Size / 1GB
    $diskFreeGb = $systemDrive.FreeSpace / 1GB

    $uptimeSeconds = (
        New-TimeSpan `
            -Start $osInfo.LastBootUpTime `
            -End (Get-Date)
    ).TotalSeconds

    $telemetryData = @{
        cpu_percent = [math]::Round(
            [double]$cpuPercent,
            2
        )
        memory_percent = [math]::Round(
            [double]$memoryPercent,
            2
        )
        disk_total_gb = [math]::Round(
            [double]$diskTotalGb,
            2
        )
        disk_free_gb = [math]::Round(
            [double]$diskFreeGb,
            2
        )
        uptime_seconds = [long]$uptimeSeconds
    }

    $telemetryJson = $telemetryData | ConvertTo-Json

    $telemetryUrl = (
        "$($config.api_base_url)/devices/" +
        "$($config.device_id)/telemetry"
    )

    $telemetryResponse = Invoke-RestMethod `
        -Uri $telemetryUrl `
        -Method Post `
        -Headers $apiHeaders `
        -ContentType "application/json" `
        -Body $telemetryJson

    Write-Host "Device telemetry sent successfully." -ForegroundColor Green
    Write-Host "CPU: $($telemetryResponse.cpu_percent)%"
    Write-Host "Memory: $($telemetryResponse.memory_percent)%"
    Write-Host "Disk free: $($telemetryResponse.disk_free_gb) GB"
}
catch {
    Write-Host "Unable to send device telemetry." -ForegroundColor Red
    Write-Host $_.Exception.Message
}

Write-Host ""
Write-Host "Checking queued security events..." -ForegroundColor Cyan

$queuedEventsSent = 0
$retryEventsUrl = "$($config.api_base_url)/events/"

$queuedEventFiles = @(
    Get-ChildItem `
        -Path $queueDirectory `
        -Filter "*.json" `
        -File |
    Sort-Object CreationTime |
    Select-Object -First 100
)

foreach ($queuedEventFile in $queuedEventFiles) {
    try {
        $queuedEventJson = Get-Content `
            -Path $queuedEventFile.FullName `
            -Raw

        Invoke-RestMethod `
            -Uri $retryEventsUrl `
            -Method Post `
            -Headers $apiHeaders `
            -ContentType "application/json" `
            -Body $queuedEventJson |
        Out-Null

        Remove-Item `
            -Path $queuedEventFile.FullName `
            -Force

        $queuedEventsSent++
    }
    catch {
        Write-Host (
            "Queued event retry failed. " +
            "It will remain queued."
        ) -ForegroundColor Yellow

        Write-Host $_.Exception.Message
        break
    }
}

Write-Host "Queued events sent: $queuedEventsSent"
Write-Host "Events still queued: $(
    (
        Get-ChildItem `
            -Path $queueDirectory `
            -Filter '*.json' `
            -File
    ).Count
)"

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
        $sendErrorMessage = $_.Exception.Message

        try {
            $queuedEventCount = @(
                Get-ChildItem `
                    -Path $queueDirectory `
                    -Filter "*.json" `
                    -File
            ).Count

            if (
                $queuedEventCount -ge
                $maximumQueuedEvents
            ) {
                throw (
                    "The local event queue has reached " +
                    "$maximumQueuedEvents events."
                )
            }
            $queueFileName = (
                "event-{0}-{1}.json" -f
                $securityEvent.RecordId,
                [guid]::NewGuid().ToString("N")
            )

            $queueFilePath = Join-Path `
                $queueDirectory `
                $queueFileName

            $eventJson |
                Set-Content `
                    -Path $queueFilePath `
                    -Encoding UTF8

            Write-Host (
                "Event ID $($securityEvent.Id) was queued."
            ) -ForegroundColor Yellow
            if (
                $securityEvent.RecordId -gt
                $highestSuccessfulRecordId
            ) {
                $highestSuccessfulRecordId = (
                    $securityEvent.RecordId
                )
            }
        }
        catch {
            Write-Host (
                "Unable to save the failed event locally."
            ) -ForegroundColor Red

            Write-Host $_.Exception.Message
        }

        Write-Host (
            "Failed to send Event ID $($securityEvent.Id)."
        ) -ForegroundColor Red

        Write-Host $sendErrorMessage
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

