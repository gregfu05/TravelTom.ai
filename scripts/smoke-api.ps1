param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl
)

$healthUrl = "$($BaseUrl.TrimEnd('/'))/api/v1/health"
$response = Invoke-RestMethod -Method Get -Uri $healthUrl

if ($response.status -ne "ok") {
    throw "Health check failed for $healthUrl"
}

$recommendationUrl = "$($BaseUrl.TrimEnd('/'))/api/v1/recommendations/query"
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
    -ContentType "application/json" `
    -Body $recommendationPayload

if (-not $recommendationResponse.ranking_version) {
    throw "Recommendation smoke check returned no ranking_version: $recommendationUrl"
}

if ($null -eq $recommendationResponse.results) {
    throw "Recommendation smoke check returned no results array: $recommendationUrl"
}

Write-Host "API smoke checks passed: $healthUrl, $recommendationUrl"
