param(
  [string]$TaskText = "",
  [string]$Cwd = (Get-Location).Path,
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$policyPath = Join-Path $PSScriptRoot "embedded_harness_policy.json"
$policy = Get-Content -LiteralPath $policyPath -Raw | ConvertFrom-Json

function ConvertTo-Array($value) {
  if ($null -eq $value) {
    return @()
  }
  if ($value -is [System.Array]) {
    return @($value)
  }
  return @($value)
}

function ConvertTo-TriggerList($value) {
  $items = @()
  if ($null -eq $value) {
    return @()
  }
  if ($value -is [System.Array]) {
    foreach ($entry in $value) {
      $items += ConvertTo-TriggerList $entry
    }
    return @($items)
  }
  if (($value -isnot [string]) -and $value.PSObject.Properties.Count -gt 0) {
    foreach ($prop in $value.PSObject.Properties) {
      $items += ConvertTo-TriggerList $prop.Value
    }
    return @($items)
  }
  return @([string]$value)
}

function Get-ObjectPropertyValue($object, [string]$name) {
  if ($null -eq $object) {
    return $null
  }
  $prop = $object.PSObject.Properties[$name]
  if ($null -eq $prop) {
    return $null
  }
  return $prop.Value
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

function Get-TriggerMatchSet($triggers) {
  $matched = @()
  $negated = @()
  foreach ($trigger in (ConvertTo-TriggerList $triggers)) {
    $text = [string]$trigger
    if ([string]::IsNullOrWhiteSpace($text)) {
      continue
    }
    $regex = New-TriggerRegex $text
    $hits = [regex]::Matches($TaskText, $regex)
    foreach ($hit in $hits) {
      if (Test-NegatedMatch -source $TaskText -index $hit.Index) {
        $negated += $text
      } else {
        $matched += $text
      }
    }
  }
  return [pscustomobject]@{
    positive = @($matched | Select-Object -Unique)
    negated = @($negated | Select-Object -Unique)
  }
}

function Get-MatchedTriggers($triggers) {
  return @((Get-TriggerMatchSet $triggers).positive)
}

function Get-ProjectLane([string]$path) {
  $normalized = $path.ToLowerInvariant()
  foreach ($prop in $policy.project_lanes.PSObject.Properties) {
    foreach ($root in $prop.Value) {
      if ($normalized.StartsWith($root.ToLowerInvariant())) {
        return $prop.Name
      }
    }
  }
  return "PROJECTLESS"
}

$projectLane = Get-ProjectLane $Cwd
$risk = "R0"
$approval = @()
$requiredGates = @("microkernel")
$requiredSkills = @()
$triggeredRisks = @()
$matchedRiskTriggers = [ordered]@{}
$negatedRiskTriggers = [ordered]@{}
$fallbackModelJudgmentRecommended = $false
$classificationConfidence = "high"
$riskRules = $policy.risk_trigger_rules
if ($null -eq $riskRules) {
  $riskRules = $policy.risk_keyword_rules
}

foreach ($riskName in (ConvertTo-Array $policy.risk_order_high_to_low)) {
  $triggers = Get-ObjectPropertyValue $riskRules ([string]$riskName)
  $matchSet = Get-TriggerMatchSet $triggers
  $matched = @($matchSet.positive)
  if ($matchSet.negated.Count -gt 0) {
    $negatedRiskTriggers[[string]$riskName] = @($matchSet.negated)
  }
  if ($matched.Count -gt 0) {
    $triggeredRisks += [string]$riskName
    $matchedRiskTriggers[[string]$riskName] = @($matched)

    $gates = Get-ObjectPropertyValue $policy.risk_gate_rules ([string]$riskName)
    foreach ($gate in (ConvertTo-Array $gates)) {
      $requiredGates += [string]$gate
    }

    $approvalRules = Get-ObjectPropertyValue $policy.risk_approval_rules ([string]$riskName)
    foreach ($approvalRule in (ConvertTo-Array $approvalRules)) {
      $approval += [string]$approvalRule
    }
  }
}

foreach ($riskName in (ConvertTo-Array $policy.risk_order_high_to_low)) {
  if ($triggeredRisks -contains [string]$riskName) {
    $risk = [string]$riskName
    break
  }
}

if ($triggeredRisks.Count -eq 0) {
  $fallbackMatched = Get-MatchedTriggers $policy.fallback_boundary_triggers
  if ($fallbackMatched.Count -gt 0) {
    $fallbackModelJudgmentRecommended = $true
    $classificationConfidence = "low"
    $requiredGates += "model_boundary_review_gate"
    $matchedRiskTriggers["fallback_boundary"] = @($fallbackMatched)
  }
}

if ($projectLane -ne "PROJECTLESS") {
  $requiredGates += "memory_isolation_gate"
  $requiredGates += "project_agents_gate"
}

if ((Get-MatchedTriggers $policy.skill_matrix_triggers).Count -gt 0) {
  $requiredSkills += "troubleshooting-skill-matrix"
}

if ($projectLane -ne "PROJECTLESS") {
  $requiredSkills += "$projectLane project AGENTS/router"
}

$externalResearchMatchSet = Get-TriggerMatchSet $policy.external_research_triggers
$needsExternalResearch = @($externalResearchMatchSet.positive).Count -gt 0
if ($needsExternalResearch) {
  $matchedRiskTriggers["external_research"] = @($externalResearchMatchSet.positive)
}
if ($externalResearchMatchSet.negated.Count -gt 0) {
  $negatedRiskTriggers["external_research"] = @($externalResearchMatchSet.negated)
}

$result = [ordered]@{
  ts = (Get-Date).ToString("o")
  phase = "intake_router"
  status = "pass"
  cwd = $Cwd
  project_lane = $projectLane
  risk_level = $risk
  triggered_risks = @($triggeredRisks | Select-Object -Unique)
  matched_risk_triggers = $matchedRiskTriggers
  negated_risk_triggers = $negatedRiskTriggers
  classification_confidence = $classificationConfidence
  required_gates = @($requiredGates | Select-Object -Unique)
  required_skills = @($requiredSkills | Select-Object -Unique)
  needs_external_research = $needsExternalResearch
  approval_required = @($approval | Select-Object -Unique)
  fallback_model_judgment_used = $false
  fallback_model_judgment_recommended = $fallbackModelJudgmentRecommended
  enforcement_boundary = $policy.gate_enforcement_boundary
}

$json = $result | ConvertTo-Json -Depth 20
if ($OutputPath) {
  $dir = Split-Path -Parent $OutputPath
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
}
$json



