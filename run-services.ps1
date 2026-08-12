<#
.SYNOPSIS
  Run microservices locally using Python & Uvicorn (without Docker).
.DESCRIPTION
  Launches Gateway and Microservices as background jobs.
#>

param(
    [string]$Action = "start"  # "start" or "stop"
)

$base = $PSScriptRoot

if ($Action -eq "stop") {
    Write-Host "Stopping all running uvicorn processes..." -ForegroundColor Yellow
    Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
    Write-Host "All services stopped." -ForegroundColor Green
    exit
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  🚀 Starting AI Career Hub Microservices (Local Python)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$services = @(
    @{ Name = "Auth Service";         Dir = "$base\services\auth-service";         Port = 8001 },
    @{ Name = "Catalog Service";      Dir = "$base\services\catalog-service";      Port = 8002 },
    @{ Name = "Learning Service";     Dir = "$base\services\learning-service";     Port = 8003 },
    @{ Name = "Interview Service";    Dir = "$base\services\interview-service";    Port = 8004 },
    @{ Name = "Progress Service";     Dir = "$base\services\progress-service";     Port = 8005 },
    @{ Name = "Notification Service"; Dir = "$base\services\notification-service"; Port = 8006 },
    @{ Name = "Dashboard BFF";        Dir = "$base\services\dashboard-bff";        Port = 8007 },
    @{ Name = "API Gateway";          Dir = "$base\gateway";                       Port = 8000 }
)

foreach ($svc in $services) {
    Write-Host "  -> Starting $($svc.Name) on http://localhost:$($svc.Port)..." -ForegroundColor Green
    Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "Set-Location '$($svc.Dir)'; python -m uvicorn app.main:app --host 0.0.0.0 --port $($svc.Port) --reload"
}

Write-Host "`nAll 8 services launched as background jobs." -ForegroundColor Cyan
Write-Host "API Gateway is active at: http://localhost:8000" -ForegroundColor Yellow
Write-Host "To stop all services run: .\run-services.ps1 -Action stop`n" -ForegroundColor Gray
