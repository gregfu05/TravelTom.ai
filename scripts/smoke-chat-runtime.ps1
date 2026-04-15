param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [ValidateSet("disabled", "ollama", "openai")]
    [string]$Provider = "disabled"
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

function New-SessionId {
    param([string]$Prefix)

    return "$Prefix-$([guid]::NewGuid().ToString('N'))"
}

function Invoke-ChatTurn {
    param(
        [string]$SessionId,
        [string]$Message
    )

    $payload = @{
        session_id = $SessionId
        message_id = [guid]::NewGuid().ToString("N")
        message = $Message
    } | ConvertTo-Json -Depth 6

    return Invoke-RestMethod `
        -Method Post `
        -Uri "$root/api/v1/chat" `
        -ContentType "application/json" `
        -Body $payload
}

$health = Invoke-RestMethod -Method Get -Uri "$root/api/v1/health"
Assert-True ($health.status -eq "ok") "Health check failed for $root/api/v1/health"

$greeting = Invoke-ChatTurn -SessionId (New-SessionId "smoke-greeting") -Message "Hello Tom"
Assert-ContainsAny `
    -Value $greeting.assistant_message `
    -Needles @("hi, i'm tom", "tell me where you want to go") `
    -Context "Greeting flow did not return the expected opening copy"

$slotGate = Invoke-ChatTurn -SessionId (New-SessionId "smoke-slot") -Message "show me hotels"
Assert-ContainsAny `
    -Value $slotGate.assistant_message `
    -Needles @("city", "destination") `
    -Context "Hotel slot-gating did not ask for a destination"
Assert-True `
    ($slotGate.state.conversation.last_recommendation_item_type -eq "hotel") `
    "Hotel slot-gating did not retain item_type=hotel"
Assert-True `
    ($slotGate.state.conversation.last_requested_slots.Count -eq 1 -and `
        $slotGate.state.conversation.last_requested_slots[0] -eq "destination") `
    "Hotel slot-gating did not keep destination as the pending slot"

$complete = Invoke-ChatTurn `
    -SessionId (New-SessionId "smoke-complete") `
    -Message "Hotels in Santa Barbara from 2026-05-10 to 2026-05-20 under 2000 USD"
Assert-True `
    ($complete.state.constraints.destination -eq "Santa Barbara") `
    "Complete request did not persist destination"
Assert-True `
    ($null -ne $complete.state.constraints.dates) `
    "Complete request did not persist dates"
Assert-True `
    ($null -ne $complete.state.constraints.budget) `
    "Complete request did not persist budget"
Assert-True `
    ($complete.state.conversation.last_requested_slots.Count -eq 0) `
    "Complete request still left required slots unresolved"

$preferenceSession = New-SessionId "smoke-preferences"
$null = Invoke-ChatTurn -SessionId $preferenceSession -Message "I like nightlife and food"
$followUp = Invoke-ChatTurn -SessionId $preferenceSession -Message "show me options"
$carriedQuery = [string]$followUp.state.conversation.last_recommendation_query
Assert-ContainsAny `
    -Value $followUp.assistant_message `
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

$repairSession = New-SessionId "smoke-repair"
$null = Invoke-ChatTurn -SessionId $repairSession -Message "Activities in Santa Barbara"
$repair = Invoke-ChatTurn -SessionId $repairSession -Message "not restaurants, more like sightseeing"
Assert-ContainsAny `
    -Value $repair.assistant_message `
    -Needles @("not assume restaurants") `
    -Context "Repair turn did not stay in clarification mode"

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

$recommendation = Invoke-RestMethod `
    -Method Post `
    -Uri "$root/api/v1/recommendations/query" `
    -ContentType "application/json" `
    -Body $recommendationPayload

Assert-True `
    ($recommendation.ranking_version -eq "heuristic-v1") `
    "Recommendation smoke check returned an unexpected ranking_version"
Assert-True `
    ($null -ne $recommendation.results) `
    "Recommendation smoke check returned no results array"

Write-Host "Chat runtime smoke passed for provider mode '$Provider': $root"
Write-Host "Review API logs for provider_stage_succeeded/provider_stage_failed/provider_stage_skipped to confirm planner/composer usage."
