<#
.SYNOPSIS
    Provisions a fresh, isolated demo database for SatBhoomi Score + Raksha.

.DESCRIPTION
    Creates a dedicated SQLite database (default: data/satbhoomi_demo.db),
    applies Alembic migrations, prompts for the demo officer credentials via
    create_user.py, and imports sample plots, pre-cutoff features, and alert replays.

    Guarantees:
    - Never touches or overwrites the configured development database.
    - Refuses to overwrite an existing demo database unless -Reset is passed.
    - Prompts for password interactively with hidden input (no default credentials).

.PARAMETER Reset
    Removes existing demo database and recreates it from scratch.

.PARAMETER DemoDbPath
    Relative or absolute path for the demo SQLite database file.
#>

[CmdletBinding()]
param(
    [switch]$Reset,
    [string]$DemoDbPath = "data/satbhoomi_demo.db",
    [string]$Username = "demo_officer",
    [string]$Name = "Demo Loan Officer",
    [string]$Role = "officer"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

# Determine configured development database path from .env or default
$DevDbPath = "data/satbhoomi.db"
if (Test-Path ".env") {
    $EnvContent = Get-Content ".env" | Where-Object { $_ -match "^DATABASE_URL=" }
    if ($EnvContent) {
        $RawUrl = ($EnvContent -split "=", 2)[1].Trim().Trim('"').Trim("'")
        if ($RawUrl -match "sqlite:///(.+)") {
            $DevDbPath = $Matches[1]
        }
    }
}

if ([System.IO.Path]::IsPathRooted($DevDbPath)) {
    $ResolvedDevDb = [System.IO.Path]::GetFullPath($DevDbPath)
} else {
    $ResolvedDevDb = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $DevDbPath))
}

if ([System.IO.Path]::IsPathRooted($DemoDbPath)) {
    $ResolvedDemoDb = [System.IO.Path]::GetFullPath($DemoDbPath)
} else {
    $ResolvedDemoDb = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $DemoDbPath))
}

# Guard 1: Never touch the development database
if ($ResolvedDemoDb.ToLower() -eq $ResolvedDevDb.ToLower()) {
    Write-Error "CRITICAL SAFETY REFUSAL: Demo database path matches the development database ($ResolvedDevDb). Demo must use a separate database."
    exit 1
}

# Guard 2: Refuse existing demo database without -Reset
if (Test-Path $ResolvedDemoDb) {
    if (-not $Reset) {
        Write-Error "Demo database '$DemoDbPath' already exists. Refusing execution to prevent accidental overwrite. Pass -Reset to recreate."
        exit 1
    }
    Write-Host "[RESET] Removing existing demo database: $DemoDbPath" -ForegroundColor Yellow
    Remove-Item -Force $ResolvedDemoDb
    if (Test-Path "$ResolvedDemoDb-wal") { Remove-Item -Force "$ResolvedDemoDb-wal" }
    if (Test-Path "$ResolvedDemoDb-shm") { Remove-Item -Force "$ResolvedDemoDb-shm" }
}

# Ensure parent directory exists
$ParentDir = [System.IO.Path]::GetDirectoryName($ResolvedDemoDb)
if (-not (Test-Path $ParentDir)) {
    New-Item -ItemType Directory -Force -Path $ParentDir | Out-Null
}

$PyExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PyExe)) {
    $PyExe = "python"
}

# Construct sqlite URL
$DemoDbUrl = "sqlite:///" + $ResolvedDemoDb.Replace("\", "/")
$env:DATABASE_URL = $DemoDbUrl
$env:ALLOW_REAL_DATA = "false"

Write-Host "=== SatBhoomi Score + Raksha: Demo Setup ===" -ForegroundColor Cyan
Write-Host "Target Demo DB: $DemoDbUrl"

# 1. Run database migrations
Write-Host "`n[1/4] Applying database migrations to demo database..." -ForegroundColor Green
& $PyExe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Error "Alembic migration failed."
    exit 1
}

# 2. Create demo officer user with hidden password prompt
Write-Host "`n[2/4] Setting up demo officer account ($Username)..." -ForegroundColor Green
Write-Host "Please enter a secure password for '$Username' (minimum 12 characters):"
& $PyExe scripts/create_user.py --username $Username --name $Name --role $Role
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create demo officer user."
    exit 1
}

# 3. Import active plots and seasonal features
Write-Host "`n[3/4] Importing active plots and feature snapshots..." -ForegroundColor Green
& $PyExe scripts/import_plots_features.py --allow-fixture
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to import plots and features."
    exit 1
}

# 4. Import historical alert replay
Write-Host "`n[4/4] Importing historical alert replay timeline..." -ForegroundColor Green
& $PyExe scripts/import_alert_replay.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to import alert replay."
    exit 1
}

Write-Host "`n========================================================" -ForegroundColor Green
Write-Host " Demo Database Provisioned Successfully!" -ForegroundColor Green
Write-Host " Database Location: $DemoDbPath" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host "`nTo start the demonstration services, open two separate terminals:"
Write-Host "`nTerminal 1 (Backend API):" -ForegroundColor Yellow
Write-Host "  `$env:DATABASE_URL = `"$DemoDbUrl`"; .venv\Scripts\uvicorn.exe satbhoomi.api.main:app --host 127.0.0.1 --port 8000"
Write-Host "`nTerminal 2 (Streamlit UI):" -ForegroundColor Yellow
Write-Host "  .venv\Scripts\streamlit.exe run src/satbhoomi/ui/app.py --server.port 8501"
Write-Host "`nPre-flight verification command:" -ForegroundColor Cyan
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/demo_check.ps1"
