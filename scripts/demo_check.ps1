<#
.SYNOPSIS
    Pre-flight verification script for demo day.

.DESCRIPTION
    Verifies that the backend API is live and responding properly across
    all key decision-support flows: /health, login, assessment, what-if,
    in-season monitoring, and disaster relief evidence report.
    Executes 100% offline with zero external network dependencies.

.PARAMETER ApiUrl
    Base URL for the running FastAPI backend (default: http://localhost:8000).

.PARAMETER Username
    Officer login username (default: demo_officer).

.PARAMETER Password
    Password for the officer account. If omitted, prompts securely.
#>

[CmdletBinding()]
param(
    [string]$ApiUrl = "http://localhost:8000",
    [string]$Username = "demo_officer",
    [string]$Password = $null,
    [int]$PlotId = 1,
    [string]$Season = "2024-25"
)

$ErrorActionPreference = "Continue"

Write-Host "=== SatBhoomi Score + Raksha: Demo Pre-Flight Check ===" -ForegroundColor Cyan
Write-Host "Target API: $ApiUrl`n"

$FailedCount = 0

# Helper function for reporting status
function Report-StepResult {
    param(
        [string]$StepName,
        [bool]$Success,
        [string]$Detail = ""
    )
    if ($Success) {
        Write-Host "  [PASS] $StepName" -ForegroundColor Green -NoNewline
        if ($Detail) { Write-Host " - $Detail" -ForegroundColor DarkGray } else { Write-Host "" }
    } else {
        Write-Host "  [FAIL] $StepName" -ForegroundColor Red -NoNewline
        if ($Detail) { Write-Host " - $Detail" -ForegroundColor Yellow } else { Write-Host "" }
        $script:FailedCount++
    }
}

# 1. API Health Check
try {
    $HealthResp = Invoke-RestMethod -Uri "$ApiUrl/health" -Method Get -TimeoutSec 5 -ErrorAction Stop
    $IsHealthOk = ($HealthResp.status -eq "ok")
    Report-StepResult "1. API Health Check" $IsHealthOk "Status: $($HealthResp.status), App: $($HealthResp.app)"
} catch {
    Report-StepResult "1. API Health Check" $false "Could not connect to $ApiUrl ($($_.Exception.Message))"
    Write-Host "`nERROR: API server is unreachable at $ApiUrl." -ForegroundColor Red
    Write-Host "Please start the backend before running pre-flight check." -ForegroundColor Yellow
    exit 1
}

# 2. Officer Authentication
if ([string]::IsNullOrEmpty($Password)) {
    $SecurePass = Read-Host -Prompt "Enter password for '$Username'" -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePass)
    $Password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
}

$AuthToken = $null
try {
    $LoginBody = @{ username = $Username; password = $Password } | ConvertTo-Json
    $LoginResp = Invoke-RestMethod -Uri "$ApiUrl/api/v1/auth/login" -Method Post -Body $LoginBody -ContentType "application/json" -TimeoutSec 5 -ErrorAction Stop
    if ($LoginResp.access_token) {
        $AuthToken = $LoginResp.access_token
        Report-StepResult "2. Officer Authentication" $true "Token issued for '$Username'"
    } else {
        Report-StepResult "2. Officer Authentication" $false "No access_token returned"
    }
} catch {
    $ErrDetail = $_.Exception.Message
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $ErrDetail = $_.ErrorDetails.Message }
    Report-StepResult "2. Officer Authentication" $false $ErrDetail
}

if (-not $AuthToken) {
    Write-Host "`nAuthentication failed. Aborting remaining protected endpoint checks." -ForegroundColor Red
    exit 1
}

$Headers = @{
    "Authorization" = "Bearer $AuthToken"
    "Accept"        = "application/json"
}

# 3. Risk Assessment
$AssessmentId = $null
try {
    $AsmBody = @{ season = $Season } | ConvertTo-Json
    $AsmResp = Invoke-RestMethod -Uri "$ApiUrl/api/v1/plots/$PlotId/assessments" -Method Post -Body $AsmBody -Headers $Headers -ContentType "application/json" -TimeoutSec 10 -ErrorAction Stop
    if ($AsmResp.id -and $AsmResp.status -eq "ok") {
        $AssessmentId = $AsmResp.id
        Report-StepResult "3. Credit Risk Assessment" $true "Score: $($AsmResp.score), Band: $($AsmResp.band), Assessment ID: $AssessmentId"
    } else {
        Report-StepResult "3. Credit Risk Assessment" $false "Assessment status: $($AsmResp.status)"
    }
} catch {
    Report-StepResult "3. Credit Risk Assessment" $false $_.Exception.Message
}

# 4. What-If Simulation
if ($AssessmentId) {
    try {
        $WhatIfBody = @{
            changed_input = "insured"
            new_value     = "1"
        } | ConvertTo-Json
        $WhatIfResp = Invoke-RestMethod -Uri "$ApiUrl/api/v1/assessments/$AssessmentId/what-if" -Method Post -Body $WhatIfBody -Headers $Headers -ContentType "application/json" -TimeoutSec 10 -ErrorAction Stop
        if ($WhatIfResp.status -eq "ok" -and $WhatIfResp.estimate_label -eq "estimate") {
            Report-StepResult "4. What-If Simulation" $true "Old Score: $($WhatIfResp.old_score) -> New: $($WhatIfResp.new_score), Label: $($WhatIfResp.estimate_label)"
        } else {
            Report-StepResult "4. What-If Simulation" $false "Status: $($WhatIfResp.status)"
        }
    } catch {
        Report-StepResult "4. What-If Simulation" $false $_.Exception.Message
    }
} else {
    Report-StepResult "4. What-If Simulation" $false "Skipped due to assessment failure"
}

# 5. In-Season Monitoring Read
try {
    $MonResp = Invoke-RestMethod -Uri "$ApiUrl/api/v1/plots/$PlotId/monitoring" -Method Get -Headers $Headers -TimeoutSec 10 -ErrorAction Stop
    if ($MonResp.status -eq "ok" -and $MonResp.timeline) {
        $PtsCount = $MonResp.timeline.Count
        $AlertsCount = $MonResp.active_alerts.Count
        Report-StepResult "5. In-Season Monitoring Read" $true "Timeline points: $PtsCount, Active alerts: $AlertsCount, Mode: $($MonResp.mode)"
    } else {
        Report-StepResult "5. In-Season Monitoring Read" $false "Status: $($MonResp.status)"
    }
} catch {
    Report-StepResult "5. In-Season Monitoring Read" $false $_.Exception.Message
}

# 6. Disaster Relief Evidence Report
try {
    $ReliefResp = Invoke-RestMethod -Uri "$ApiUrl/api/v1/plots/$PlotId/relief-report" -Method Get -Headers $Headers -TimeoutSec 10 -ErrorAction Stop
    if ($ReliefResp.status -eq "ok" -and $ReliefResp.disclaimer) {
        Report-StepResult "6. Relief Evidence Report" $true "Calamity status: $($ReliefResp.status), Loss band: $($ReliefResp.crop_loss_band)"
    } else {
        Report-StepResult "6. Relief Evidence Report" $false "Status: $($ReliefResp.status)"
    }
} catch {
    Report-StepResult "6. Relief Evidence Report" $false $_.Exception.Message
}

Write-Host "`n--------------------------------------------------------"
if ($FailedCount -eq 0) {
    Write-Host " Demo Pre-Flight Check: ALL CHECKS PASSED (Ready for demo)" -ForegroundColor Green
    exit 0
} else {
    Write-Host " Demo Pre-Flight Check: FAILED ($FailedCount error(s) detected)" -ForegroundColor Red
    exit 1
}
