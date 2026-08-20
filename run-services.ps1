<#
.SYNOPSIS
  Run microservices locally using Python & Uvicorn.
.DESCRIPTION
  Launches Gateway and Microservices as minimized background windows so they don't clutter your screen.

  Usage:
    .\run-services.ps1              # Start all services
    .\run-services.ps1 -Action stop   # Stop all services
    .\run-services.ps1 -Action status # Check running services
#>

param(
    [ValidateSet("start", "stop", "status")]
    [string]$Action = "start"
)

$base = $PSScriptRoot

$services = @(
    @{ Name = "Auth Service";         Dir = (Join-Path $base "services\auth-service");         Port = 8001 },
    @{ Name = "Catalog Service";      Dir = (Join-Path $base "services\catalog-service");      Port = 8002 },
    @{ Name = "Learning Service";     Dir = (Join-Path $base "services\learning-service");     Port = 8003 },
    @{ Name = "Interview Service";    Dir = (Join-Path $base "services\interview-service");    Port = 8004 },
    @{ Name = "Progress Service";     Dir = (Join-Path $base "services\progress-service");     Port = 8005 },
    @{ Name = "Notification Service"; Dir = (Join-Path $base "services\notification-service"); Port = 8006 },
    @{ Name = "Dashboard BFF";        Dir = (Join-Path $base "services\dashboard-bff");        Port = 8007 },
    @{ Name = "API Gateway";          Dir = (Join-Path $base "gateway");                       Port = 8000 }
)

function Test-PortInUse {
    param([int]$Port)
    $lines = netstat -ano 2>$null | Select-String ":$Port\s" | Select-String "LISTENING"
    return ($null -ne $lines)
}

function Get-PortPids {
    param([int]$Port)
    $lines = netstat -ano 2>$null | Select-String ":$Port\s" | Select-String "LISTENING"
    if (-not $lines) { return @() }
    $procIds = $lines | ForEach-Object {
        ($_.ToString() -replace '\s+', ' ').Trim().Split(' ')[-1]
    } | Sort-Object -Unique
    return $procIds
}

# == STOP ================================================================== #
if ($Action -eq "stop") {
    Write-Host ""
    Write-Host "  Stopping all microservices..." -ForegroundColor Yellow

    foreach ($svc in $services) {
        $port = $svc.Port
        $procIds = Get-PortPids -Port $port
        if ($procIds.Count -gt 0) {
            foreach ($procId in $procIds) {
                try {
                    Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
                } catch { }
            }
            Write-Host "    [x] $($svc.Name) (port $port) stopped" -ForegroundColor Red
        } else {
            Write-Host "    [-] $($svc.Name) (port $port) was not running" -ForegroundColor DarkGray
        }
    }
    Write-Host ""
    Write-Host "  All microservices stopped." -ForegroundColor Green
    Write-Host ""
    exit
}

# == STATUS ================================================================ #
if ($Action -eq "status") {
    Write-Host ""
    Write-Host "  Service Status:" -ForegroundColor Cyan
    Write-Host "  =================================================" -ForegroundColor DarkGray

    foreach ($svc in $services) {
        $port = $svc.Port
        if (Test-PortInUse -Port $port) {
            Write-Host "    [RUNNING]  $($svc.Name) -> http://localhost:$port" -ForegroundColor Green
        } else {
            Write-Host "    [STOPPED]  $($svc.Name) -> port $port" -ForegroundColor Red
        }
    }
    Write-Host ""
    exit
}

# == START ================================================================= #

Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Cyan
Write-Host "    AI Career Hub Microservices (Local Python)                 " -ForegroundColor Cyan
Write-Host "  ============================================================" -ForegroundColor Cyan
Write-Host ""

foreach ($svc in $services) {
    $port = $svc.Port
    $dir  = $svc.Dir

    if (Test-PortInUse -Port $port) {
        Write-Host "    [SKIP] $($svc.Name) - port $port already in use" -ForegroundColor Yellow
        continue
    }

    # Start PowerShell process minimized so it doesn't interrupt the user
    Start-Process powershell.exe `
        -WindowStyle Minimized `
        -WorkingDirectory $dir `
        -ArgumentList "-NoExit", "-Command", "python -m uvicorn app.main:app --host 0.0.0.0 --port $port"

    Write-Host "    [OK]  $($svc.Name) -> http://localhost:$port" -ForegroundColor Green
}

Write-Host ""
Write-Host "  All 8 services launched in minimized background windows." -ForegroundColor Cyan
Write-Host "  API Gateway : http://localhost:8000" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Commands:" -ForegroundColor DarkGray
Write-Host "    .\run-services.ps1 -Action status   # Check running services" -ForegroundColor DarkGray
Write-Host "    .\run-services.ps1 -Action stop     # Stop all services" -ForegroundColor DarkGray
Write-Host ""
