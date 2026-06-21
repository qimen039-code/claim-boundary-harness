param(
  [string]$TaskText = "",
  [string]$ClaimText = "",
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

$recommendedModes = @()
if ($combined -match '(?i)github|github\.com|repo|repository|open source|release|changelog|issue|license') {
  $recommendedModes += "github_open_source_repository_search"
}
if ($combined -match '(?i)official|authority|policy|law|price|product|institution|current|latest|version|release|CEO|president') {
  $recommendedModes += "official_authority_source_search"
}
if ($combined -match '(?i)compare|comparison|ecosystem|community|trend|tutorial') {
  $recommendedModes += "general_web_cross_check"
}
if ($combined -match '(?i)mechanism|external architecture|architecture comparison|learn from|source-grounded|external mechanism|avoid closed-door') {
  $recommendedModes += "source_grounded_learning_intake"
}

$needs = $matchedTriggers.Count -gt 0
if ($needs -and $recommendedModes.Count -eq 0) {
  $recommendedModes += "general_web_cross_check"
}
if (-not $needs) {
  $recommendedModes = @()
}
$result = [ordered]@{
  ts = (Get-Date).ToString("o")
  phase = "external_research_gate"
  status = "pass"
  needs_external_research = $needs
  matched_triggers = @($matchedTriggers | Select-Object -Unique)
  negated_triggers = @($negatedTriggers | Select-Object -Unique)
  recommended_search_modes = @($recommendedModes | Select-Object -Unique)
  learning_classification_labels = @($policy.search_and_learning_decision_matrix.classification_labels)
  rule = "deterministic string/date/version/url trigger plus search-mode routing; no extra LLM judgment"
}

$json = $result | ConvertTo-Json -Depth 20
if ($OutputPath) {
  $dir = Split-Path -Parent $OutputPath
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
}
$json
