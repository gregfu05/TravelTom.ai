param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [string]$AccessToken,

    [string]$Email,

    [string]$Password
)

$root = $BaseUrl.TrimEnd("/")

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

    if (-not $ResolvedEmail) {
        return $null
    }

    $payload = @{
        email = $ResolvedEmail
        password = $ResolvedPassword
    } | ConvertTo-Json -Depth 4

    try {
        $signupResponse = Invoke-RestMethod `
            -Method Post `
            -Uri "$root/api/v1/auth/signup" `
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
        -Uri "$root/api/v1/auth/login" `
        -ContentType "application/json" `
        -Body $payload
    return [string]$loginResponse.access_token
}

$healthUrl = "$root/api/v1/health"
$response = Invoke-RestMethod -Method Get -Uri $healthUrl

if ($response.status -ne "ok") {
    throw "Health check failed for $healthUrl"
}

$effectiveEmail = $Email
if (-not $effectiveEmail -and -not $AccessToken) {
    $effectiveEmail = "smoke-api+$([guid]::NewGuid().ToString('N').Substring(0, 8))@example.com"
}
$effectivePassword = $Password
if (-not $effectivePassword) {
    $effectivePassword = $env:TRAVELTOM_SMOKE_PASSWORD
}
if (-not $effectivePassword -and -not $AccessToken) {
    $effectivePassword = New-SmokePassword
}
$token = Get-AccessToken `
    -ExistingToken $AccessToken `
    -ResolvedEmail $effectiveEmail `
    -ResolvedPassword $effectivePassword

$recommendationUrl = "$root/api/v1/recommendations/query"
$recommendationPayload = @{
    session_id = "smoke-session"
    query = "hotel in Rome"
    constraints = @{
        destination = "Rome"
    }
    filters = @{
        item_type = "hotel"
    }
    max_results = 3
    ranking_version = "heuristic-v1"
} | ConvertTo-Json -Depth 6

$recommendationResponse = Invoke-RestMethod `
    -Method Post `
    -Uri $recommendationUrl `
    -Headers (New-AuthHeaders -Token $token) `
    -ContentType "application/json" `
    -Body $recommendationPayload

if (-not $recommendationResponse.ranking_version) {
    throw "Recommendation smoke check returned no ranking_version: $recommendationUrl"
}

if ($null -eq $recommendationResponse.results) {
    throw "Recommendation smoke check returned no results array: $recommendationUrl"
}

Write-Host "API smoke checks passed: $healthUrl, $recommendationUrl"
