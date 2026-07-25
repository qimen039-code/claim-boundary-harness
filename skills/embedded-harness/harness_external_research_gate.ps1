param(
  [string]$TaskText = "",
  [string]$ClaimText = "",
  [string]$AttemptJson = "",
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$policy = Get-Content -LiteralPath (Join-Path $PSScriptRoot "embedded_harness_policy.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$combined = "$TaskText`n$ClaimText"
$matchedTriggers = @()
$negatedTriggers = @()

function ConvertTo-TriggerList($value) {
  $items = @()
  if ($null -eq $value) { return @() }
  if ($value -is [System.Array]) {
    foreach ($entry in $value) { $items += ConvertTo-TriggerList $entry }
    return @($items)
  }
  if (($value -isnot [string]) -and $value.PSObject.Properties.Count -gt 0) {
    foreach ($prop in $value.PSObject.Properties) { $items += ConvertTo-TriggerList $prop.Value }
    return @($items)
  }
  return @([string]$value)
}

function Test-EnglishTrigger([string]$text) {
  return (($text -match '^[\x20-\x7E]+$') -and ($text -match '[A-Za-z0-9]'))
}

function New-TriggerRegex([string]$text) {
  $escaped = [regex]::Escape($text)
  if (Test-EnglishTrigger $text) {
    return "(?i)(?<![A-Za-z0-9_])$escaped(?![A-Za-z0-9_])"
  }
  return $escaped
}

function Test-NegatedMatch([string]$source, [int]$index) {
  $start = [Math]::Max(0, $index - 48)
  $prefix = $source.Substring($start, $index - $start)
  return ($prefix -match "(?i)(\bdo\s+not\b|\bdon't\b|\bnever\b|\bnot\b|\bno\b)[\s\w'-]{0,36}$")
}

foreach ($trigger in (ConvertTo-TriggerList $policy.external_research_triggers)) {
  if ([string]::IsNullOrWhiteSpace($trigger)) {
    continue
  }
  $regex = New-TriggerRegex ([string]$trigger)
  foreach ($hit in [regex]::Matches($combined, $regex)) {
    if (Test-NegatedMatch -source $combined -index $hit.Index) {
      $negatedTriggers += [string]$trigger
    } else {
      $matchedTriggers += [string]$trigger
    }
  }
}

$externalRetrievalContract = $policy.search_and_learning_decision_matrix.external_retrieval_contract
$explicitSearchIntentMatches = @()
foreach ($trigger in (ConvertTo-TriggerList $externalRetrievalContract.explicit_search_intent_terms)) {
  if ([string]::IsNullOrWhiteSpace($trigger)) {
    continue
  }
  $regex = New-TriggerRegex ([string]$trigger)
  foreach ($hit in [regex]::Matches($combined, $regex)) {
    if (Test-NegatedMatch -source $combined -index $hit.Index) {
      $negatedTriggers += [string]$trigger
    } else {
      $matchedTriggers += [string]$trigger
      $explicitSearchIntentMatches += [string]$trigger
    }
  }
}

$localOnlyExclusionHits = @()
foreach ($trigger in (ConvertTo-TriggerList $externalRetrievalContract.local_only_exclusion_terms)) {
  if ([string]::IsNullOrWhiteSpace($trigger)) {
    continue
  }
  $regex = New-TriggerRegex ([string]$trigger)
  if ([regex]::IsMatch($combined, $regex)) {
    $localOnlyExclusionHits += [string]$trigger
  }
}

if ($combined -match '\b20\d{2}[-/]\d{1,2}([-/]\d{1,2})?\b') {
  $matchedTriggers += "date_pattern"
}
$versionPattern = '\b(v\d+\.\d+(\.\d+)?|(?:version|release|sdk|node|python|npm|package|plugin|model)\s*:?\s*v?\d+\.\d+(\.\d+)?)\b'
if ($combined -match $versionPattern) {
  $matchedTriggers += "version_pattern"
}
if ($combined -match 'https?://|github\.com') {
  $matchedTriggers += "url_or_github_pattern"
}
$typedExternalIdentifierPattern = '(?i)\bRFC\s*-?\s*\d{3,5}\b|\bCVE-\d{4}-\d{4,}\b|\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b|\barXiv\s*:\s*\d{4}\.\d{4,5}(?:v\d+)?\b|\barXiv\s+\d{4}\.\d{4,5}(?:v\d+)?\b|\b(?:ISO(?:/IEC)?|IEC|IEEE)\s+\d+(?:[-:]\d+)*(?::\d{4})?\b|(?<![A-Za-z0-9_.-])@[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*|\b(?:PyPI|npm|Hugging\s*Face)\b'
if ([regex]::IsMatch($combined, $typedExternalIdentifierPattern)) {
  $matchedTriggers += "typed_external_identifier_pattern"
}
$currentnessPattern = '(?i)\bnow\b|\bcurrently\b|\bpresent\s+(?:role|office|holder)\b|\u73b0\u5728|\u73b0\u4efb|\u76ee\u524d'
if ([regex]::IsMatch($combined, $currentnessPattern)) {
  $matchedTriggers += "currentness_pattern"
}

$recommendedModes = @()
foreach ($mode in $policy.search_and_learning_decision_matrix.search_modes.PSObject.Properties) {
  $modeMatched = $false
  foreach ($trigger in (ConvertTo-TriggerList $mode.Value.triggers)) {
    if ([string]::IsNullOrWhiteSpace($trigger)) {
      continue
    }
    $regex = New-TriggerRegex ([string]$trigger)
    foreach ($hit in [regex]::Matches($combined, $regex)) {
      if (-not (Test-NegatedMatch -source $combined -index $hit.Index)) {
        $modeMatched = $true
        break
      }
    }
    if ($modeMatched) {
      break
    }
  }
  if ($modeMatched) {
    $recommendedModes += [string]$mode.Name
  }
}

$hasExplicitSearchIntent = $explicitSearchIntentMatches.Count -gt 0
if ($hasExplicitSearchIntent) {
  $recommendedModes += "general_web_cross_check"
}
if ([regex]::IsMatch($combined, '(?i)github\.com|\bGitHub\b|\u4ed3\u5e93|\u5f00\u6e90')) {
  $recommendedModes += "github_open_source_repository_search"
}

$needs = ($matchedTriggers.Count -gt 0) -and ($localOnlyExclusionHits.Count -eq 0)
if ($needs -and $recommendedModes.Count -eq 0) {
  $recommendedModes += "general_web_cross_check"
}
if (-not $needs) {
  $recommendedModes = @()
}
$recommendedModes = @($recommendedModes | Select-Object -Unique)

$plannerPath = Join-Path $PSScriptRoot "external_retrieval_strategy.py"
$pythonCommand = Get-Command python -ErrorAction Stop
$plannerInput = if ([string]::IsNullOrWhiteSpace($ClaimText)) { $TaskText } else { $combined.Trim() }
$taskTextBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($plannerInput))
$plannerArgs = @("-B", $plannerPath, "--task-text-base64", $taskTextBase64, "--ascii-output", "--policy-path", (Join-Path $PSScriptRoot "embedded_harness_policy.json"))
foreach ($mode in $recommendedModes) {
  $plannerArgs += @("--mode", [string]$mode)
}
if (-not [string]::IsNullOrWhiteSpace($AttemptJson)) {
  $attemptJsonBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($AttemptJson))
  $plannerArgs += @("--attempt-json-base64", $attemptJsonBase64)
}
$retrievalReceiptJson = & $pythonCommand.Source @plannerArgs
if ($LASTEXITCODE -ne 0) {
  throw "external retrieval planner failed with exit code $LASTEXITCODE"
}
$retrievalReceipt = $retrievalReceiptJson | ConvertFrom-Json

$result = [ordered]@{
  ts = (Get-Date).ToString("o")
  phase = "external_research_gate"
  status = "pass"
  needs_external_research = $needs
  matched_triggers = @($matchedTriggers | Select-Object -Unique)
  negated_triggers = @($negatedTriggers | Select-Object -Unique)
  local_only_exclusion_hits = @($localOnlyExclusionHits | Select-Object -Unique)
  recommended_search_modes = @($recommendedModes)
  learning_classification_labels = @($policy.search_and_learning_decision_matrix.classification_labels)
  external_retrieval_receipt = $retrievalReceipt
  rule = "policy-driven trigger and source-mode routing plus an anchor-preserving task-local retrieval plan; no browsing, blocking, or memory write"
}

$json = $result | ConvertTo-Json -Depth 20
if ($OutputPath) {
  $dir = Split-Path -Parent $OutputPath
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
}
$json
