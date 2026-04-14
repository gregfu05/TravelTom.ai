param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl
)

$routes = @("/", "/planner", "/why-traveltom", "/how-it-works", "/login", "/signup")

foreach ($route in $routes) {
    $url = "$($BaseUrl.TrimEnd('/'))$route"
    $response = Invoke-WebRequest -Method Get -Uri $url
    if ($response.StatusCode -ne 200) {
        throw "Web smoke check failed for $url"
    }
    if (-not ($response.Content -match "TravelTom")) {
        throw "Web smoke check did not find expected TravelTom marker for $url"
    }
}

Write-Host "Web smoke checks passed: $($routes -join ', ')"
