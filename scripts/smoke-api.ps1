param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl
)

$healthUrl = "$($BaseUrl.TrimEnd('/'))/api/v1/health"
$response = Invoke-RestMethod -Method Get -Uri $healthUrl

if ($response.status -ne "ok") {
    throw "Health check failed for $healthUrl"
}

Write-Host "API smoke check passed: $healthUrl"
