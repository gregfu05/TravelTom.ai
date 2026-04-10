param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl
)

$routes = @("/", "/planner", "/why-traveltom", "/how-it-works")

foreach ($route in $routes) {
    $url = "$($BaseUrl.TrimEnd('/'))$route"
    $response = Invoke-WebRequest -Method Get -Uri $url
    if ($response.StatusCode -ne 200) {
        throw "Web smoke check failed for $url"
    }
}

Write-Host "Web smoke checks passed: $($routes -join ', ')"
