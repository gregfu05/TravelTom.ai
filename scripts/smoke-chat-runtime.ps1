param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [ValidateSet("disabled", "ollama", "openai")]
    [string]$Provider = "disabled",

    [string]$AccessToken,

    [string]$Email,

    [string]$Password
)

$root = $BaseUrl.TrimEnd("/")

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-ContainsAny {
    param(
        [string]$Value,
        [string[]]$Needles,
        [string]$Context
    )

    $normalized = $Value.ToLowerInvariant()
    foreach ($needle in $Needles) {
        if ($normalized.Contains($needle.ToLowerInvariant())) {
            return
        }
    }

    throw "$Context. Actual: $Value"
}

function Assert-HeaderEquals {
    param(
        $Headers,
        [string]$Name,
        [string]$Expected,
        [string]$Context
    )

    $actual = [string]$Headers[$Name]
    if ($actual -ne $Expected) {
        throw "$Context. Expected '$Expected', actual '$actual'"
    }
}

function New-SessionId {
    param([string]$Prefix)

    return "$Prefix-$([guid]::NewGuid().ToString('N'))"
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
    }
    if ($Body) {
        $requestParams["ContentType"] = "application/json"
        $requestParams["Body"] = $Body
    }
    $requestParams["UseBasicParsing"] = $true

    $response = Invoke-WebRequest @requestParams
    return @{
        Body = ($response.Content | ConvertFrom-Json)
        Headers = $response.Headers
        StatusCode = [int]$response.StatusCode
    }
}

function Invoke-ChatTurn {
    param(
        [string]$SessionId,
        [string]$Message,
        [string]$Token
    )

    $payload = @{
        session_id = $SessionId
        message_id = [guid]::NewGuid().ToString("N")
        message = $Message
    } | ConvertTo-Json -Depth 6

    return Invoke-JsonRequest `
        -Method Post `
        -Uri "$root/api/v1/chat" `
        -Headers (New-AuthHeaders -Token $Token) `
        -Body $payload
}

$health = Invoke-RestMethod -Method Get -Uri "$root/api/v1/health"
Assert-True ($health.status -eq "ok") "Health check failed for $root/api/v1/health"

$effectiveEmail = $Email
if (-not $effectiveEmail -and -not $AccessToken) {
    $effectiveEmail = "smoke+$([guid]::NewGuid().ToString('N').Substring(0, 8))@example.com"
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

$greeting = Invoke-ChatTurn `
    -SessionId (New-SessionId "smoke-greeting") `
    -Message "Hello Tom" `
    -Token $token
Assert-ContainsAny `
    -Value $greeting.Body.assistant_message `
    -Needles @("hi, i'm tom", "tell me where you want to go") `
    -Context "Greeting flow did not return the expected opening copy"
Assert-HeaderEquals `
    -Headers $greeting.Headers `
    -Name "X-TravelTom-Planner-Status" `
    -Expected "skipped_fast_path" `
    -Context "Greeting flow should stay on the deterministic fast path"
Assert-HeaderEquals `
    -Headers $greeting.Headers `
    -Name "X-TravelTom-Composer-Status" `
    -Expected "skipped_fast_path" `
    -Context "Greeting flow should not hit the response composer"

$slotGate = Invoke-ChatTurn `
    -SessionId (New-SessionId "smoke-slot") `
    -Message "show me hotels" `
    -Token $token
Assert-ContainsAny `
    -Value $slotGate.Body.assistant_message `
    -Needles @("city", "destination") `
    -Context "Hotel slot-gating did not ask for a destination"
Assert-True `
    ($slotGate.Body.state.conversation.last_recommendation_item_type -eq "hotel") `
    "Hotel slot-gating did not retain item_type=hotel"
Assert-True `
    ($slotGate.Body.state.conversation.last_requested_slots.Count -eq 1 -and `
        $slotGate.Body.state.conversation.last_requested_slots[0] -eq "destination") `
    "Hotel slot-gating did not keep destination as the pending slot"
if ($Provider -ne "disabled") {
    Assert-HeaderEquals `
        -Headers $slotGate.Headers `
        -Name "X-TravelTom-Planner-Used" `
        -Expected "true" `
        -Context "Slot-gating turn did not use the planner"
}

$complete = Invoke-ChatTurn `
    -SessionId (New-SessionId "smoke-complete") `
    -Message "Hotels in Santa Barbara from 2026-05-10 to 2026-05-20 under 2000 USD" `
    -Token $token
Assert-True `
    ($complete.Body.state.constraints.destination -eq "Santa Barbara") `
    "Complete request did not persist destination"
Assert-True `
    ($null -ne $complete.Body.state.constraints.dates) `
    "Complete request did not persist dates"
Assert-True `
    ($null -ne $complete.Body.state.constraints.budget) `
    "Complete request did not persist budget"
Assert-True `
    ($complete.Body.state.conversation.last_requested_slots.Count -eq 0) `
    "Complete request still left required slots unresolved"
if ($Provider -ne "disabled") {
    Assert-HeaderEquals `
        -Headers $complete.Headers `
        -Name "X-TravelTom-Composer-Used" `
        -Expected "true" `
        -Context "Complete recommendation turn did not use the response composer"
}

$preferenceSession = New-SessionId "smoke-preferences"
$null = Invoke-ChatTurn `
    -SessionId $preferenceSession `
    -Message "I like nightlife and food" `
    -Token $token
$followUp = Invoke-ChatTurn `
    -SessionId $preferenceSession `
    -Message "show me options" `
    -Token $token
$carriedQuery = [string]$followUp.Body.state.conversation.last_recommendation_query
Assert-ContainsAny `
    -Value $followUp.Body.assistant_message `
    -Needles @("which destination", "what city") `
    -Context "Preference follow-up did not ask for destination"
Assert-ContainsAny `
    -Value $carriedQuery `
    -Needles @("nightlife") `
    -Context "Preference follow-up did not carry nightlife into the pending query"
Assert-ContainsAny `
    -Value $carriedQuery `
    -Needles @("food") `
    -Context "Preference follow-up did not carry food into the pending query"
if ($Provider -ne "disabled") {
    Assert-HeaderEquals `
        -Headers $followUp.Headers `
        -Name "X-TravelTom-Planner-Used" `
        -Expected "true" `
        -Context "Preference follow-up did not use the planner"
}

$repairSession = New-SessionId "smoke-repair"
$null = Invoke-ChatTurn `
    -SessionId $repairSession `
    -Message "Activities in Santa Barbara" `
    -Token $token
$repair = Invoke-ChatTurn `
    -SessionId $repairSession `
    -Message "not restaurants, more like sightseeing" `
    -Token $token
Assert-ContainsAny `
    -Value $repair.Body.assistant_message `
    -Needles @("not assume restaurants") `
    -Context "Repair turn did not stay in clarification mode"
if ($Provider -ne "disabled") {
    Assert-HeaderEquals `
        -Headers $repair.Headers `
        -Name "X-TravelTom-Planner-Used" `
        -Expected "true" `
        -Context "Repair turn did not use the planner"
}

$recommendationPayload = @{
    session_id = "smoke-query"
    query = "hotel in Santa Barbara"
    constraints = @{
        destination = "Santa Barbara"
    }
    filters = @{
        item_type = "hotel"
    }
    max_results = 3
    ranking_version = "heuristic-v1"
} | ConvertTo-Json -Depth 6

$recommendation = Invoke-JsonRequest `
    -Method Post `
    -Uri "$root/api/v1/recommendations/query" `
    -Headers (New-AuthHeaders -Token $token) `
    -Body $recommendationPayload

Assert-True `
    ($recommendation.Body.ranking_version -eq "heuristic-v1") `
    "Recommendation smoke check returned an unexpected ranking_version"
Assert-True `
    ($null -ne $recommendation.Body.results) `
    "Recommendation smoke check returned no results array"

Write-Host "Chat runtime smoke passed for provider mode '$Provider': $root"
Write-Host "Planner/composer usage was validated through response headers."
