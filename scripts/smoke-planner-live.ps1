param(
    [string]$ApiBaseUrl = "http://localhost:8000",

    [string]$WebBaseUrl = "http://127.0.0.1:4173",

    [ValidateSet("enabled", "disabled")]
    [string]$AuthMode = "enabled",

    [ValidateSet("disabled", "ollama")]
    [string]$Provider = "disabled",

    [string]$AccessToken,

    [string]$Email,

    [string]$Password
)

$ErrorActionPreference = "Stop"

$apiRoot = $ApiBaseUrl.TrimEnd("/")
$repoRoot = Split-Path -Parent $PSScriptRoot
$webRoot = Join-Path $repoRoot "apps\web"

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function New-SmokePassword {
    return "$([guid]::NewGuid().ToString('N'))!1"
}

function New-AuthHeaders {
    param([string]$Token)

    if (-not $Token) {
        return @{}
    }

    return @{ Authorization = "Bearer $Token" }
}

function Get-AccessToken {
    param(
        [string]$ExistingToken,
        [string]$ResolvedEmail,
        [string]$ResolvedPassword
    )

    if ($ExistingToken) {
        return $ExistingToken
    }

    if (-not $ResolvedEmail -or $AuthMode -eq "disabled") {
        return $null
    }

    $payload = @{
        email = $ResolvedEmail
        password = $ResolvedPassword
    } | ConvertTo-Json -Depth 4

    try {
        $signupResponse = Invoke-RestMethod `
            -Method Post `
            -Uri "$apiRoot/api/v1/auth/signup" `
            -ContentType "application/json" `
            -Body $payload
        return [string]$signupResponse.access_token
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        if ($statusCode -ne 409) {
            throw
        }
    }

    $loginResponse = Invoke-RestMethod `
        -Method Post `
        -Uri "$apiRoot/api/v1/auth/login" `
        -ContentType "application/json" `
        -Body $payload
    return [string]$loginResponse.access_token
}

function Invoke-JsonRequest {
    param(
        [string]$Method,
        [string]$Uri,
        [hashtable]$Headers,
        [string]$Body = ""
    )

    $requestParams = @{
        Method = $Method
        Uri = $Uri
        Headers = $Headers
        UseBasicParsing = $true
    }
    if ($Body) {
        $requestParams["ContentType"] = "application/json"
        $requestParams["Body"] = $Body
    }

    $response = Invoke-WebRequest @requestParams
    return @{
        Body = ($response.Content | ConvertFrom-Json)
        Headers = $response.Headers
        StatusCode = [int]$response.StatusCode
    }
}

$health = Invoke-RestMethod -Method Get -Uri "$apiRoot/api/v1/health"
Assert-True ($health.status -eq "ok") "Health check failed for $apiRoot/api/v1/health"

$effectiveEmail = $Email
if (-not $effectiveEmail -and -not $AccessToken -and $AuthMode -eq "enabled") {
    $effectiveEmail = "planner-live+$([guid]::NewGuid().ToString('N').Substring(0, 8))@example.com"
}
$effectivePassword = $Password
if (-not $effectivePassword) {
    $effectivePassword = $env:TRAVELTOM_SMOKE_PASSWORD
}
if (-not $effectivePassword -and -not $AccessToken -and $AuthMode -eq "enabled") {
    $effectivePassword = New-SmokePassword
}

$token = Get-AccessToken `
    -ExistingToken $AccessToken `
    -ResolvedEmail $effectiveEmail `
    -ResolvedPassword $effectivePassword

$candidateDestinations = @("Santa Barbara", "Rome", "Paris", "Lisbon", "Milan", "Madrid", "London")
$verifiedDestination = $null

foreach ($destination in $candidateDestinations) {
    $recommendationPayload = @{
        session_id = "planner-live-readiness"
        query = "hotel in $destination"
        constraints = @{
            destination = $destination
        }
        filters = @{
            item_type = "hotel"
        }
        max_results = 3
        ranking_version = "heuristic-v1"
    } | ConvertTo-Json -Depth 6

    $recommendation = Invoke-JsonRequest `
        -Method Post `
        -Uri "$apiRoot/api/v1/recommendations/query" `
        -Headers (New-AuthHeaders -Token $token) `
        -Body $recommendationPayload

    Assert-True `
        ($null -ne $recommendation.Body.results) `
        "Catalog readiness check returned no results array."

    if ($recommendation.Body.results.Count -gt 0) {
        $verifiedDestination = $destination
        break
    }
}

Assert-True `
    (-not [string]::IsNullOrWhiteSpace($verifiedDestination)) `
    "Catalog readiness check found no hotel seed rows for: $($candidateDestinations -join ', ')."

$env:LIVE_PLANNER = "1"
$env:LIVE_PLANNER_AUTH_MODE = $AuthMode
$env:LIVE_PLANNER_EMAIL = $effectiveEmail
$env:LIVE_PLANNER_PASSWORD = $effectivePassword
$env:LIVE_PLANNER_PROVIDER = $Provider
$env:LIVE_PLANNER_PROMPT = "Hotels in $verifiedDestination from 2026-05-10 to 2026-05-20 under 2000 USD"
$env:PLAYWRIGHT_BASE_URL = $WebBaseUrl
$env:VITE_API_PROXY_TARGET = $apiRoot

Write-Host "Running live planner UI verification against $apiRoot via $WebBaseUrl in provider mode '$Provider'."
Write-Host "Verified seeded hotel destination: $verifiedDestination"
Push-Location $webRoot
try {
    npm run test:e2e -- planner-live.spec.ts
    if ($LASTEXITCODE -ne 0) {
        throw "Live planner Playwright verification failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
