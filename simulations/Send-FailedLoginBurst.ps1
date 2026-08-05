$ErrorActionPreference = "Stop"

$configPath = Join-Path `
    $PSScriptRoot `
    "..\agent\agent-config.json"

$config = Get-Content $configPath -Raw | ConvertFrom-Json

$eventsUrl = "$($config.api_base_url)/events/"
$deviceId = $config.device_id

$apiHeaders = @{
    "X-Watchtower-API-Key" = $config.api_key
}

$baseRecordId = (
    [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() * 10
)

Write-Host "Starting failed-login burst simulation..." -ForegroundColor Cyan

for ($attempt = 1; $attempt -le 5; $attempt++) {
    $eventData = @{
        device_id        = $deviceId
        windows_event_id = 4625
        record_id        = $baseRecordId + $attempt
        log_name         = "Security"
        provider         = "Watchtower-Simulation"
        level            = "Information"
        message          = "Simulated failed login attempt $attempt of 5."
        occurred_at      = (
            Get-Date
        ).ToUniversalTime().ToString("o")
        raw_data         = @{
            simulation      = $true
            target_user_name = "TestAdministrator"
            source_ip       = "192.168.1.200"
            attempt_number  = $attempt
        }
    }

    $eventJson = $eventData | ConvertTo-Json -Depth 5

Invoke-RestMethod `
    -Uri $eventsUrl `
    -Method Post `
    -Headers $apiHeaders `
    -ContentType "application/json" `
    -Body $eventJson |
Out-Null

    Write-Host "Sent failed-login event $attempt of 5."

    Start-Sleep -Milliseconds 300
}

Write-Host ""
Write-Host "Simulation completed." -ForegroundColor Green
Write-Host "Watchtower should generate a high-severity alert."