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

$refineSession = New-SessionId "smoke-refine"
$null = Invoke-ChatTurn `
    -SessionId $refineSession `
    -Message "Hotels in Santa Barbara from 2026-05-10 to 2026-05-20 under 2000 USD" `
    -Token $token
$refine = Invoke-ChatTurn `
    -SessionId $refineSession `
    -Message "show me more" `
    -Token $token
Assert-True `
    ($refine.Body.state.constraints.destination -eq "Santa Barbara") `
    "Show-me-more follow-up did not preserve the previous destination"
Assert-True `
    ($refine.Body.state.conversation.last_recommendation_item_type -eq "hotel") `
    "Show-me-more follow-up did not preserve hotel context"
Assert-True `
    ($refine.Body.state.conversation.last_requested_slots.Count -eq 0) `
    "Show-me-more follow-up should not re-open required slot collection"
Assert-ContainsAny `
    -Value ([string]$refine.Body.state.conversation.last_recommendation_query) `
    -Needles @("show me more hotel", "show me more hotels") `
    -Context "Show-me-more follow-up did not carry the prior hotel query context"
Assert-True `
    ($refine.Body.state.conversation.last_search_outcome -in @("results", "no_new_results", "empty_results")) `
    "Show-me-more follow-up returned an unexpected search outcome"
if ($refine.Body.state.conversation.last_search_outcome -eq "empty_results") {
    Assert-ContainsAny `
        -Value $refine.Body.assistant_message `
        -Needles @("did not find grounded matches", "adjusting your budget", "changing the travel dates") `
        -Context "Show-me-more follow-up did not explain the continued empty-results state"
} elseif ($refine.Body.recommendations.Count -eq 0) {
    Assert-ContainsAny `
        -Value $refine.Body.assistant_message `
        -Needles @("do not have new grounded options") `
        -Context "Show-me-more duplicate follow-up did not explain the lack of new results"
} else {
    Assert-ContainsAny `
        -Value $refine.Body.assistant_message `
        -Needles @("top pick", "top picks", "i found") `
        -Context "Show-me-more follow-up did not return grounded recommendation copy"
}
if ($Provider -ne "disabled") {
    Assert-HeaderEquals `
        -Headers $refine.Headers `
        -Name "X-TravelTom-Planner-Used" `
        -Expected "true" `
        -Context "Show-me-more follow-up did not use the planner"
}

$searchType = Invoke-ChatTurn `
    -SessionId (New-SessionId "smoke-search-type") `
    -Message "I am going to Lisbon next weekend" `
    -Token $token
Assert-ContainsAny `
    -Value $searchType.Body.assistant_message `
    -Needles @("hotel, a restaurant, or an activity", "hotel, restaurant, or activity") `
    -Context "Generic trip setup did not ask for recommendation type"
Assert-True `
    ($searchType.Body.state.conversation.last_clarification_kind -eq "search_type") `
    "Generic trip setup did not transition into search_type clarification"
Assert-True `
    ($searchType.Body.state.conversation.last_requested_slots.Count -eq 0) `
    "Generic trip setup should not keep a pending core slot once destination and dates are known"

$transcriptSession = New-SessionId "smoke-transcript"
$null = Invoke-ChatTurn `
    -SessionId $transcriptSession `
    -Message "I want to go to Milan" `
    -Token $token
$transcriptDates = Invoke-ChatTurn `
    -SessionId $transcriptSession `
    -Message "from the 20th to the 25th of April" `
    -Token $token
Assert-True `
    ($transcriptDates.Body.state.constraints.destination -eq "Milan") `
    "Shared-month date reply overwrote the destination"
Assert-True `
    ($null -ne $transcriptDates.Body.state.constraints.dates) `
    "Shared-month date reply did not persist dates"
$transcriptHotel = Invoke-ChatTurn `
    -SessionId $transcriptSession `
    -Message "Hotel" `
    -Token $token
Assert-True `
    ($transcriptHotel.Body.state.constraints.destination -eq "Milan") `
    "Hotel follow-up did not preserve Milan as the destination"
Assert-True `
    ($transcriptHotel.Body.state.conversation.last_requested_slots.Count -eq 0) `
    "Hotel follow-up should not block on budget after dates are known"
Assert-True `
    ($null -ne $transcriptHotel.Body.recommendations) `
    "Hotel follow-up did not return a recommendations array"

$madridSession = New-SessionId "smoke-madrid"
$null = Invoke-ChatTurn `
    -SessionId $madridSession `
    -Message "I want to go to Milan" `
    -Token $token
$null = Invoke-ChatTurn `
    -SessionId $madridSession `
    -Message "20th of April to 25th of April" `
    -Token $token
$madrid = Invoke-ChatTurn `
    -SessionId $madridSession `
    -Message "Provide top 5 hotels in Madrid" `
    -Token $token
Assert-True `
    ($madrid.Body.state.constraints.destination -eq "Madrid") `
    "Madrid hotel request did not update destination"
Assert-True `
    ($null -ne $madrid.Body.state.constraints.dates) `
    "Madrid hotel request did not retain carried dates"
Assert-True `
    ($madrid.Body.state.conversation.last_requested_slots.Count -eq 0) `
    "Madrid hotel request should not re-block on budget"

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

$emptySession = New-SessionId "smoke-empty"
$empty = Invoke-ChatTurn `
    -SessionId $emptySession `
    -Message "Hotels in Atlantis from 2026-05-10 to 2026-05-20" `
    -Token $token
Assert-True `
    ($empty.Body.state.constraints.destination -eq "Atlantis") `
    "Empty-results setup did not persist the requested destination"
Assert-True `
    ($empty.Body.recommendations.Count -eq 0) `
    "Empty-results setup unexpectedly returned recommendations"
Assert-True `
    ($empty.Body.state.conversation.last_search_outcome -eq "empty_results") `
    "Empty-results setup did not mark the search outcome as empty_results"
Assert-True `
    ($empty.Body.state.conversation.last_clarification_kind -eq "refine_preference") `
    "Empty-results setup did not switch into refine_preference clarification"
Assert-ContainsAny `
    -Value $empty.Body.assistant_message `
    -Needles @("did not find grounded matches", "did not find grounded hotel matches") `
    -Context "Empty-results setup did not explain that grounded matches were unavailable"

$emptyFollowUp = Invoke-ChatTurn `
    -SessionId $emptySession `
    -Message "Anything works" `
    -Token $token
Assert-True `
    ($emptyFollowUp.Body.state.conversation.last_search_outcome -eq "empty_results") `
    "Vague reply after empty results should keep the session in empty_results state"
Assert-True `
    ($emptyFollowUp.Body.state.conversation.last_clarification_kind -eq "refine_preference") `
    "Vague reply after empty results should remain in refine_preference clarification"
Assert-True `
    ($emptyFollowUp.Body.state.conversation.last_recommendation_item_type -eq "hotel") `
    "Vague reply after empty results should preserve the hotel recommendation context"
Assert-ContainsAny `
    -Value $emptyFollowUp.Body.assistant_message `
    -Needles @("still do not have grounded hotel matches", "try widening the budget", "trying a nearby area") `
    -Context "Vague reply after empty results did not provide stronger refinement guidance"
if ($Provider -ne "disabled") {
    Assert-HeaderEquals `
        -Headers $emptyFollowUp.Headers `
        -Name "X-TravelTom-Planner-Used" `
        -Expected "true" `
        -Context "Vague empty-results follow-up did not use the planner"
}

$unsupported = Invoke-ChatTurn `
    -SessionId (New-SessionId "smoke-unsupported") `
    -Message "Find me flights from Paris to Lisbon next weekend" `
    -Token $token
Assert-ContainsAny `
    -Value $unsupported.Body.assistant_message `
    -Needles @("flights are not supported", "can't assist with flight") `
    -Context "Unsupported flight flow did not refuse the request clearly"
Assert-True `
    ($null -eq $unsupported.Body.state.constraints.destination) `
    "Unsupported flight flow should not persist destination into planner state"
Assert-True `
    ($null -eq $unsupported.Body.state.constraints.dates) `
    "Unsupported flight flow should not persist dates into planner state"

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
    (-not [string]::IsNullOrWhiteSpace([string]$recommendation.Body.ranking_version)) `
    "Recommendation smoke check returned no ranking_version"
Assert-True `
    ($null -ne $recommendation.Body.results) `
    "Recommendation smoke check returned no results array"

Write-Host "Chat runtime smoke passed for provider mode '$Provider': $root"
Write-Host "Planner/composer usage was validated through response headers."
