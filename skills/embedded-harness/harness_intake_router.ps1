param(
  [string]$TaskText = "",
  [string]$Cwd = (Get-Location).Path,
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$policyPath = Join-Path $PSScriptRoot "embedded_harness_policy.json"
$policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 | ConvertFrom-Json

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

function Normalize-PathText([string]$path) {
  if ([string]::IsNullOrWhiteSpace($path)) { return "" }
  try {
    return [System.IO.Path]::GetFullPath($path).TrimEnd('\','/')
  } catch {
    return $path.TrimEnd('\','/')
  }
}

function Add-TrailingSeparator([string]$path) {
  if ([string]::IsNullOrWhiteSpace($path)) { return "" }
  return $path.TrimEnd('\','/') + [System.IO.Path]::DirectorySeparatorChar
}

function Test-PathInsideRoot([string]$path, [string]$root) {
  $normalizedPath = Normalize-PathText $path
  $normalizedRoot = Normalize-PathText $root
  if ([string]::IsNullOrWhiteSpace($normalizedPath) -or [string]::IsNullOrWhiteSpace($normalizedRoot)) {
    return $false
  }
  if ($normalizedPath.Equals($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $true
  }
  $rootWithSeparator = Add-TrailingSeparator $normalizedRoot
  return $normalizedPath.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)
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

function Set-ObjectProperty($object, [string]$name, $value) {
  if ($null -eq $object) { return }
  if ($object.PSObject.Properties.Name -contains $name) {
    $object.$name = $value
  } else {
    $object | Add-Member -MemberType NoteProperty -Name $name -Value $value -Force
  }
}

function Merge-StringListMapProperty($target, $overlay, [string]$name) {
  if ($null -eq $target -or $null -eq $overlay) { return }
  $incoming = Get-ObjectPropertyValue $overlay $name
  if ($null -eq $incoming) { return }
  $current = Get-ObjectPropertyValue $target $name
  if ($null -eq $current) {
    $current = [pscustomobject]@{}
    Set-ObjectProperty $target $name $current
  }
  foreach ($prop in $incoming.PSObject.Properties) {
    $existing = @(ConvertTo-Array (Get-ObjectPropertyValue $current $prop.Name))
    $addition = @(ConvertTo-Array $prop.Value)
    $merged = @($existing + $addition | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -Unique)
    Set-ObjectProperty $current $prop.Name $merged
  }
}

function Import-LocalProjectLaneOverlay {
  $config = Get-ObjectPropertyValue $policy "local_project_lane_overlay"
  if (($null -ne $config) -and ((Get-ObjectPropertyValue $config "enabled") -eq $false)) {
    return
  }
  $envVar = "CBH_PROJECT_LANES_FILE"
  $configuredEnvVar = Get-ObjectPropertyValue $config "env_var"
  if (-not [string]::IsNullOrWhiteSpace([string]$configuredEnvVar)) {
    $envVar = [string]$configuredEnvVar
  }
  $defaultFilename = "embedded_harness_policy.local.json"
  $configuredFilename = Get-ObjectPropertyValue $config "default_filename"
  if (-not [string]::IsNullOrWhiteSpace([string]$configuredFilename)) {
    $defaultFilename = [string]$configuredFilename
  }
  $candidates = @()
  $envPath = [Environment]::GetEnvironmentVariable($envVar)
  if (-not [string]::IsNullOrWhiteSpace($envPath)) {
    $candidates += $envPath
  }
  $candidates += (Join-Path $PSScriptRoot $defaultFilename)
  foreach ($candidate in $candidates) {
    if ([string]::IsNullOrWhiteSpace([string]$candidate)) { continue }
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    $overlay = Get-Content -LiteralPath $candidate -Raw -Encoding UTF8 | ConvertFrom-Json
    $expectedSchema = Get-ObjectPropertyValue $config "schema"
    $actualSchema = Get-ObjectPropertyValue $overlay "schema"
    if ((-not [string]::IsNullOrWhiteSpace([string]$expectedSchema)) -and
        (-not [string]::IsNullOrWhiteSpace([string]$actualSchema)) -and
        ([string]$actualSchema -ne [string]$expectedSchema)) {
      continue
    }
    Merge-StringListMapProperty $policy $overlay "project_lanes"
    Merge-StringListMapProperty $policy $overlay "memory_roots"
    Set-ObjectProperty $policy "_local_project_lane_overlay" ([pscustomobject]@{
      loaded = $true
      path = [string]$candidate
      rule = "machine-local project lane overlay; do not publish private roots"
    })
    break
  }
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
  $start = [Math]::Max(0, $index - 256)
  $prefix = $source.Substring($start, $index - $start)
  if ($prefix -match "(?i)(\bdo\s+not\b|\bdon't\b|\bnever\b|\bnot\b|\bno\b)[\s\w'-]{0,128}$") {
    return $true
  }
  $shortStart = [Math]::Max(0, $index - 32)
  $shortPrefix = $source.Substring($shortStart, $index - $shortStart)
  return ($shortPrefix -match "(不需要|无需|不要|别|禁止|不)\s*$")
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
  foreach ($prop in $policy.project_lanes.PSObject.Properties) {
    foreach ($root in $prop.Value) {
      if (Test-PathInsideRoot $path ([string]$root)) {
        return $prop.Name
      }
    }
  }
  return "PROJECTLESS"
}

function Test-TaskContainsAny($patterns) {
  foreach ($pattern in (ConvertTo-Array $patterns)) {
    $text = [string]$pattern
    if ([string]::IsNullOrWhiteSpace($text)) {
      continue
    }
    if ([regex]::IsMatch($TaskText, [regex]::Escape($text), [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
      return $true
    }
  }
  return $false
}

function Get-TaskMatchedTerms($patterns) {
  $terms = @()
  foreach ($pattern in (ConvertTo-Array $patterns)) {
    $text = [string]$pattern
    if ([string]::IsNullOrWhiteSpace($text)) {
      continue
    }
    if ([regex]::IsMatch($TaskText, [regex]::Escape($text), [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
      $terms += $text
    }
  }
  return @($terms | Select-Object -Unique)
}

function Get-SourceMatchedTerms([string]$source, $terms) {
  $hits = @()
  foreach ($term in (ConvertTo-TriggerList $terms)) {
    $text = [string]$term
    if ([string]::IsNullOrWhiteSpace($text)) {
      continue
    }
    $regex = New-TriggerRegex $text
    if ([regex]::IsMatch($source, $regex)) {
      $hits += $text
    }
  }
  return @($hits | Select-Object -Unique)
}

function Get-TermIntersection($leftTerms, $rightTerms) {
  $right = @{}
  foreach ($term in (ConvertTo-TriggerList $rightTerms)) {
    $key = ([string]$term).ToLowerInvariant()
    if (-not [string]::IsNullOrWhiteSpace($key)) {
      $right[$key] = $true
    }
  }
  $hits = @()
  foreach ($term in (ConvertTo-TriggerList $leftTerms)) {
    $text = [string]$term
    if ($right.ContainsKey($text.ToLowerInvariant())) {
      $hits += $text
    }
  }
  return @($hits | Select-Object -Unique)
}

function Get-R5ContextDecision {
  param(
    [string]$SourceText,
    [object[]]$PositiveTermsInput = @(),
    [object[]]$NegatedTermsInput = @()
  )
  $candidateTerms = @($positiveTermsInput | Select-Object -Unique)
  $negatedTerms = @($negatedTermsInput | Select-Object -Unique)
  if ($candidateTerms.Count -eq 0) {
    return [pscustomobject]@{
      decision = "none"
      action_surface = "none"
      promote_to_risk = $false
      candidate_terms = @()
      negated_terms = @($negatedTerms)
      reason = "no_R5_candidate"
    }
  }

  $contextRules = $policy.r5_context_decision_rules
  $directActionHits = Get-SourceMatchedTerms -source $sourceText -terms $contextRules.direct_action_terms
  $explicitActionPhraseHits = Get-SourceMatchedTerms -source $sourceText -terms (Get-ObjectPropertyValue $contextRules "explicit_action_phrases")
  $explicitActionNegationHits = Get-SourceMatchedTerms -source $sourceText -terms (Get-ObjectPropertyValue $contextRules "explicit_action_negation_phrases")
  $actionContextHits = Get-SourceMatchedTerms -source $sourceText -terms $contextRules.action_context_terms
  $documentationContextHits = Get-SourceMatchedTerms -source $sourceText -terms $contextRules.documentation_context_terms
  $nonActionContextHits = Get-SourceMatchedTerms -source $sourceText -terms $contextRules.non_action_context_terms
  $contextRequiredCandidateHits = Get-TermIntersection -leftTerms $candidateTerms -rightTerms $contextRules.context_required_candidate_terms
  $alwaysActionCandidateHits = Get-TermIntersection -leftTerms $candidateTerms -rightTerms $contextRules.always_action_candidate_terms

  if (($explicitActionPhraseHits.Count -gt 0) -and ($explicitActionNegationHits.Count -eq 0)) {
    return [pscustomobject]@{
      decision = "requires_confirmation"
      action_surface = "actionable_R5"
      promote_to_risk = $true
      candidate_terms = @($candidateTerms)
      negated_terms = @($negatedTerms)
      reason = "explicit_action_phrase_detected"
    }
  }

  if (($directActionHits.Count -gt 0) -or (($alwaysActionCandidateHits.Count -gt 0) -and ($documentationContextHits.Count -eq 0)) -or (($contextRequiredCandidateHits.Count -gt 0) -and ($actionContextHits.Count -gt 0) -and ($nonActionContextHits.Count -eq 0))) {
    return [pscustomobject]@{
      decision = "requires_confirmation"
      action_surface = "actionable_R5"
      promote_to_risk = $true
      candidate_terms = @($candidateTerms)
      negated_terms = @($negatedTerms)
      reason = "action_context_detected"
    }
  }

  if (($documentationContextHits.Count -gt 0) -or ($nonActionContextHits.Count -gt 0)) {
    return [pscustomobject]@{
      decision = "contextual_review"
      action_surface = "documentation_or_discussion"
      promote_to_risk = $false
      candidate_terms = @($candidateTerms)
      negated_terms = @($negatedTerms)
      reason = "R5_terms_are_context_not_action"
    }
  }

  return [pscustomobject]@{
    decision = "contextual_review"
    action_surface = "ambiguous_R5_candidate"
    promote_to_risk = $false
    candidate_terms = @($candidateTerms)
    negated_terms = @($negatedTerms)
    reason = "R5_candidate_needs_context_review"
  }
}

function Get-R3ContextDecision {
  param(
    [string]$SourceText,
    [object[]]$PositiveTermsInput = @(),
    [object[]]$NegatedTermsInput = @()
  )
  $candidateTerms = @($PositiveTermsInput | Select-Object -Unique)
  $negatedTerms = @($NegatedTermsInput | Select-Object -Unique)
  if ($candidateTerms.Count -eq 0) {
    return [pscustomobject]@{
      decision = "none"
      action_surface = "none"
      promote_to_risk = $false
      candidate_terms = @()
      negated_terms = @($negatedTerms)
      diagnostic_terms = @()
      reason = "no_R3_candidate"
    }
  }

  $contextRules = Get-ObjectPropertyValue $policy "r3_context_decision_rules"
  if ($null -eq $contextRules) {
    $contextRules = [pscustomobject]@{
      diagnostic_intent_terms = @("read-only", "inspect", "check", "detect", "只读", "检查", "核查", "检测")
      explicit_mutation_phrases = @("please update", "please modify", "please fix", "update config", "modify config", "请更新", "请修改", "请修复", "更新配置", "修改配置")
      strong_mutation_terms = @("implement", "fix", "patch", "edit", "sync", "实现", "修复", "补丁", "落地", "同步")
    }
  }

  $diagnosticHits = Get-SourceMatchedTerms -source $SourceText -terms $contextRules.diagnostic_intent_terms
  $explicitMutationMatchSet = Get-TriggerMatchSet $contextRules.explicit_mutation_phrases
  $explicitMutationHits = @($explicitMutationMatchSet.positive)
  $strongMutationHits = Get-TermIntersection -leftTerms $candidateTerms -rightTerms $contextRules.strong_mutation_terms

  if (($diagnosticHits.Count -gt 0) -and ($explicitMutationHits.Count -eq 0) -and ($strongMutationHits.Count -eq 0)) {
    return [pscustomobject]@{
      decision = "contextual_read_only"
      action_surface = "read_only_diagnostic"
      promote_to_risk = $false
      candidate_terms = @($candidateTerms)
      negated_terms = @($negatedTerms)
      diagnostic_terms = @($diagnosticHits)
      reason = "R3_terms_are_diagnostic_context_not_mutation"
    }
  }

  return [pscustomobject]@{
    decision = "change_context"
    action_surface = "actionable_R3"
    promote_to_risk = $true
    candidate_terms = @($candidateTerms)
    negated_terms = @($negatedTerms)
    diagnostic_terms = @($diagnosticHits)
    reason = if ($explicitMutationHits.Count -gt 0) { "explicit_mutation_phrase_detected" } elseif ($strongMutationHits.Count -gt 0) { "strong_mutation_term_detected" } else { "R3_candidate_without_read_only_context" }
  }
}

function Get-TargetSurface {
  $rules = $policy.router_decision_contract.target_surface_trigger_rules
  if ($null -ne $rules) {
    foreach ($name in @("git_action", "tool_call", "adapter", "public_docs", "conversation_ledger", "conversation_memory", "private_rule", "local_harness", "skill_matrix", "project_memory")) {
      $triggers = Get-ObjectPropertyValue $rules $name
      if ((Get-MatchedTriggers $triggers).Count -gt 0) {
        return $name
      }
    }
  }
  if (Test-TaskContainsAny @("git commit", "git push", "commit", "push")) { return "git_action" }
  if (Test-TaskContainsAny @("tool proxy", "tool call", "shell_command", "command")) { return "tool_call" }
  if (Test-TaskContainsAny @("WorkBuddy", "Claude Code", "adapter", "client update")) { return "adapter" }
  if (Test-TaskContainsAny @("public", "README", "GitHub", "open source", "repo", "repository", "whiteboard")) { return "public_docs" }
  if (Test-TaskContainsAny @("conversation ledger", "session ledger", "raw session", "raw session JSONL", "evidence_refs", "time_anchors", "segments.jsonl", "turns.jsonl", "sessions.jsonl", "对话账本", "会话账本", "原始对话日志", "证据指针", "时间锚点")) { return "conversation_ledger" }
  if (Test-TaskContainsAny @("internal", "private", "local maintainer", "local-only")) { return "private_rule" }
  if (Test-TaskContainsAny @("memory", "history", "_META_INDEX", "capsule", "ERR-", "SOL-")) { return "project_memory" }
  if (Test-TaskContainsAny @("skill", "semantic anchor", "skill matrix")) { return "skill_matrix" }
  if (Test-TaskContainsAny @("harness", "AGENTS", "policy", "route", "routing", "dynamic evaluation", "decision layer", "governance layer")) { return "local_harness" }
  return "current_chat"
}

function Get-SkillAuditDecision {
  $contract = $policy.router_decision_contract.skill_audit_contract
  if ($null -eq $contract) { return [pscustomobject]@{ profile = "none"; signals = @() } }
  $subjectHits = Get-MatchedTriggers $contract.subject_triggers
  $intentHits = Get-MatchedTriggers $contract.audit_intent_triggers
  $safetyHits = Get-MatchedTriggers $contract.safety_triggers
  $redundancyHits = Get-MatchedTriggers $contract.redundancy_triggers
  $profile = "none"
  if (($subjectHits.Count -gt 0) -and ($intentHits.Count -gt 0)) {
    if (($safetyHits.Count -gt 0) -and ($redundancyHits.Count -gt 0)) { $profile = "safety_and_redundancy_audit" }
    elseif ($safetyHits.Count -gt 0) { $profile = "safety_audit" }
    elseif ($redundancyHits.Count -gt 0) { $profile = "redundancy_audit" }
  }
  return [pscustomobject]@{
    profile = $profile
    signals = @(@($subjectHits) + @($intentHits) + @($safetyHits) + @($redundancyHits) | Select-Object -Unique)
  }
}

function Get-FirstPrinciplesDecision([string]$riskLevel, [string]$surface) {
  $contract = $policy.router_decision_contract.first_principles_contract
  if ($null -eq $contract) { return [pscustomobject]@{ profile = "none"; signals = @() } }
  $fullHits = Get-MatchedTriggers $contract.full_design_triggers
  $constraintHits = Get-MatchedTriggers $contract.constraint_gate_triggers
  $noneHits = Get-MatchedTriggers $contract.none_triggers
  $profile = "none"
  if ($fullHits.Count -gt 0) { $profile = "full_design" }
  elseif ($noneHits.Count -gt 0) { $profile = "none" }
  elseif (($constraintHits.Count -gt 0) -or ($riskLevel -eq "R5") -or ($surface -in @($contract.high_impact_target_surfaces))) { $profile = "constraint_gate" }
  elseif ($riskLevel -in @($contract.micro_constraint_risks)) { $profile = "micro_constraints" }
  return [pscustomobject]@{
    profile = $profile
    signals = @(@($fullHits) + @($constraintHits) + @($noneHits) | Select-Object -Unique)
  }
}

function Get-Audience([string]$lane) {
  $rules = $policy.router_decision_contract.audience_trigger_rules
  if ($null -ne $rules) {
    foreach ($name in @("public_user", "local_maintainer")) {
      $triggers = Get-ObjectPropertyValue $rules $name
      if ((Get-MatchedTriggers $triggers).Count -gt 0) {
        return $name
      }
    }
  }
  if (Test-TaskContainsAny @("public", "README", "GitHub", "open source", "repo", "repository", "whiteboard")) { return "public_user" }
  if (Test-TaskContainsAny @("internal", "private", "local maintainer", "local-only")) { return "local_maintainer" }
  if ($lane -ne "PROJECTLESS") { return "project_operator" }
  return "current_chat"
}

function Find-ActiveConversationMemoryLane([string]$path) {
  try {
    $current = (Resolve-Path -LiteralPath $path).Path
  } catch {
    $current = $path
  }
  for ($depth = 0; $depth -lt 5; $depth++) {
    if ([string]::IsNullOrWhiteSpace($current)) {
      break
    }
    $root = Join-Path $current "local-conversation-memory"
    if (Test-Path -LiteralPath $root) {
      foreach ($lane in Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue) {
        $metaPath = Join-Path $lane.FullName "_META_INDEX.md"
        $indexPath = Join-Path $lane.FullName "index.json"
        if ((Test-Path -LiteralPath $metaPath) -or (Test-Path -LiteralPath $indexPath)) {
          $metaText = ""
          $indexText = ""
          if (Test-Path -LiteralPath $metaPath) {
            $metaText = Get-Content -LiteralPath $metaPath -Raw -Encoding UTF8
          }
          if (Test-Path -LiteralPath $indexPath) {
            $indexText = Get-Content -LiteralPath $indexPath -Raw -Encoding UTF8
          }
          $combined = "$metaText`n$indexText"
          if (($combined -match "(?im)(?:lane_state|status)[`"']?\s*[:=]\s*[`"']?active") -or ($combined -match "single_conversation_project_shaped_lane")) {
            return $lane.FullName
          }
        }
      }
    }
    $parent = Split-Path -Parent $current
    if (($parent -eq $current) -or [string]::IsNullOrWhiteSpace($parent)) {
      break
    }
    $current = $parent
  }
  return ""
}

Import-LocalProjectLaneOverlay

$projectLane = Get-ProjectLane $Cwd
$activeConversationMemoryLanePath = Find-ActiveConversationMemoryLane $Cwd
$hasActiveConversationMemoryLane = -not [string]::IsNullOrWhiteSpace($activeConversationMemoryLanePath)
$risk = "R0"
$approval = @()
$requiredGates = @("microkernel")
$requiredSkills = @()
$triggeredRisks = @()
$matchedRiskTriggers = [ordered]@{}
$negatedRiskTriggers = [ordered]@{}
$riskCandidates = [ordered]@{}
$risk_context_decisions = [ordered]@{}
$diagnosticR1FallbackHits = @()
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
  if ([string]$riskName -eq "R5") {
    $r5DecisionArgs = @{
      SourceText = [string]$TaskText
      PositiveTermsInput = @($matched)
      NegatedTermsInput = @($matchSet.negated)
    }
    $r5Decision = Get-R5ContextDecision @r5DecisionArgs
    if ($matched.Count -gt 0) {
      $riskCandidates["R5"] = @($matched)
      $risk_context_decisions["R5"] = $r5Decision
      if (-not $r5Decision.promote_to_risk) {
        if ($r5Decision.action_surface -eq "ambiguous_R5_candidate") {
          $classificationConfidence = "low"
          $requiredGates += "risk_context_review_gate"
        }
        continue
      }
    }
  }
  if ([string]$riskName -eq "R3") {
    $r3DecisionArgs = @{
      SourceText = [string]$TaskText
      PositiveTermsInput = @($matched)
      NegatedTermsInput = @($matchSet.negated)
    }
    $r3Decision = Get-R3ContextDecision @r3DecisionArgs
    if ($matched.Count -gt 0) {
      $riskCandidates["R3"] = @($matched)
      $risk_context_decisions["R3"] = $r3Decision
      if (-not $r3Decision.promote_to_risk) {
        $diagnosticR1FallbackHits += @($r3Decision.diagnostic_terms)
        continue
      }
    }
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

if ($diagnosticR1FallbackHits.Count -gt 0) {
  $triggeredRisks += "R1"
  $existingR1Hits = @()
  if ($matchedRiskTriggers.Contains("R1")) {
    $existingR1Hits = @($matchedRiskTriggers["R1"])
  }
  $matchedRiskTriggers["R1"] = @($existingR1Hits + $diagnosticR1FallbackHits | Select-Object -Unique)
  foreach ($gate in (ConvertTo-Array (Get-ObjectPropertyValue $policy.risk_gate_rules "R1"))) {
    $requiredGates += [string]$gate
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
  $fallbackShortTextMaxChars = 30
  $fallbackLongTextMinChars = 100
  if ($null -ne $policy.router_decision_contract.fallback_short_text_max_chars) {
    $fallbackShortTextMaxChars = [int]$policy.router_decision_contract.fallback_short_text_max_chars
  }
  if ($null -ne $policy.router_decision_contract.fallback_long_text_min_chars) {
    $fallbackLongTextMinChars = [int]$policy.router_decision_contract.fallback_long_text_min_chars
  }
  $trimmedTaskLength = $TaskText.Trim().Length
  $fallbackEligible = (
    ($trimmedTaskLength -ge $fallbackLongTextMinChars) -or
    (($trimmedTaskLength -ge $fallbackShortTextMaxChars) -and ($fallbackMatched.Count -gt 0))
  )
  if ($fallbackEligible) {
    $fallbackModelJudgmentRecommended = $true
    $classificationConfidence = "low"
    $requiredGates += "model_boundary_review_gate"
    if ($fallbackMatched.Count -gt 0) {
      $matchedRiskTriggers["fallback_boundary"] = @($fallbackMatched)
    } else {
      $matchedRiskTriggers["fallback_boundary"] = @("long_unclassified_task")
    }
  }
}

if ($projectLane -ne "PROJECTLESS") {
  $requiredGates += "memory_isolation_gate"
  $requiredGates += "project_agents_gate"
}

$skillAuditDecision = Get-SkillAuditDecision
$skillAuditProfile = [string]$skillAuditDecision.profile
$skillAuditSignals = @($skillAuditDecision.signals)
if ($skillAuditProfile -ne "none") {
  $requiredGates += @($policy.router_decision_contract.skill_audit_contract.required_gates)
  $requiredSkills += [string]$policy.router_decision_contract.skill_audit_contract.required_skill
  if ($risk -in @("R0", "R1", "R2")) {
    $risk = [string]$policy.router_decision_contract.skill_audit_contract.minimum_risk
    $triggeredRisks += $risk
  }
  $matchedRiskTriggers["skill_audit"] = @($skillAuditSignals)
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

$targetSurface = if ($skillAuditProfile -ne "none") { "skill_matrix" } else { Get-TargetSurface }
if (($targetSurface -eq "current_chat") -and ($triggeredRisks -contains "R3")) {
  $targetSurface = "local_harness"
}
$firstPrinciplesDecision = Get-FirstPrinciplesDecision $risk $targetSurface
$firstPrinciplesProfile = [string]$firstPrinciplesDecision.profile
$firstPrinciplesSignals = @($firstPrinciplesDecision.signals)
if ($firstPrinciplesProfile -in @($policy.router_decision_contract.first_principles_contract.gate_profiles)) {
  $requiredGates += [string]$policy.router_decision_contract.first_principles_contract.required_gate
}
$audience = Get-Audience $projectLane
$semanticTriggers = $policy.router_decision_contract.semantic_ambiguity_triggers
if ($null -eq $semanticTriggers) {
  $semanticTriggers = @("update", "record", "publish", "call", "use", "memory", "skill", "route", "harness", "public", "internal", "whiteboard")
}
$semanticAmbiguity = @(Get-MatchedTriggers $semanticTriggers)
$scopeReassessmentTriggers = $policy.router_decision_contract.scope_reassessment_triggers
if ($null -eq $scopeReassessmentTriggers) {
  $scopeReassessmentTriggers = @("also", "plus", "not only", "but also", "multiple issues", "scope", "narrow", "re-evaluate scope")
}
$scopeReassessmentHits = Get-MatchedTriggers $scopeReassessmentTriggers
if ($scopeReassessmentHits.Count -gt 0) {
  $semanticAmbiguity += @("composite_or_scope_reassessment")
  $requiredGates += "scope_reassessment_gate"
}
$debtHygieneTriggers = $policy.router_decision_contract.debt_hygiene_triggers
if ($null -eq $debtHygieneTriggers) {
  $debtHygieneTriggers = @("technical debt", "dirty tree debt", "memory pollution", "target pollution", "cleanup grouping", "技术债", "候选技术债", "脏树债", "记忆污染", "目标污染", "清查分组", "整理清理")
}
$debtHygieneHits = Get-MatchedTriggers $debtHygieneTriggers
if ($debtHygieneHits.Count -gt 0) {
  $semanticAmbiguity += @("debt_hygiene_required")
  $requiredGates += "debt_hygiene_gate"
  $matchedRiskTriggers["debt_hygiene"] = @($debtHygieneHits)
}
$observationScopeTriggers = $policy.router_decision_contract.observation_scope_triggers
$observationScopeHits = Get-MatchedTriggers $observationScopeTriggers
if ($observationScopeHits.Count -gt 0) {
  $semanticAmbiguity += @("observation_scope_required")
  $requiredGates += "observation_scope_gate"
  $matchedRiskTriggers["observation_scope"] = @($observationScopeHits)
}
$feedbackLoopTriggers = $policy.router_decision_contract.feedback_loop_triggers
$feedbackLoopHits = Get-MatchedTriggers $feedbackLoopTriggers
$feedbackLoopProfile = "none"
if ($feedbackLoopHits.Count -gt 0) {
  $semanticAmbiguity += @("feedback_loop_required")
  $requiredGates += "feedback_loop_gate"
  $matchedRiskTriggers["feedback_loop"] = @($feedbackLoopHits)
  $feedbackLoopProfile = "explicit_cycle"
}
$issuePreventionGates = Get-ObjectPropertyValue $policy.router_decision_contract "issue_prevention_gates"
if ($null -ne $issuePreventionGates) {
  foreach ($gateEntry in $issuePreventionGates.PSObject.Properties) {
    $gateName = [string]$gateEntry.Name
    $gateTriggers = Get-ObjectPropertyValue $gateEntry.Value "triggers"
    $gateHits = Get-MatchedTriggers $gateTriggers
    if ($gateHits.Count -gt 0) {
      $semanticAmbiguity += @($gateName)
      $requiredGates += $gateName
      $matchedRiskTriggers[$gateName] = @($gateHits)
    }
  }
}
if ($triggeredRisks -contains "R3") {
  $semanticAmbiguity += @("governance_or_change_surface")
}
if ((Test-TaskContainsAny @("public", "whiteboard", "GitHub", "repo", "repository")) -and (Test-TaskContainsAny @("internal", "private", "local-only"))) {
  $semanticAmbiguity += @("public_internal_boundary")
}
$semanticAmbiguity = @($semanticAmbiguity | Select-Object -Unique)

$externalNeed = @()
$searchModes = $policy.search_and_learning_decision_matrix.search_modes
if ($null -ne $searchModes) {
  foreach ($mode in $searchModes.PSObject.Properties) {
    $modeTriggers = Get-ObjectPropertyValue $mode.Value "triggers"
    if ((Get-MatchedTriggers $modeTriggers).Count -gt 0) {
      $externalNeed += $mode.Name
    }
  }
}
if (($needsExternalResearch) -and ($externalNeed.Count -eq 0)) {
  $externalNeed += "official_authority_source_search"
}
if ($externalNeed.Count -eq 0) {
  $externalNeed += "none"
}
$externalNeed = @($externalNeed | Select-Object -Unique)

$memoryNeedTriggers = $policy.router_decision_contract.memory_need_triggers
if ($null -eq $memoryNeedTriggers) {
  $memoryNeedTriggers = @("memory", "history", "_META_INDEX", "capsule", "remember", "previous", "ERR-", "SOL-", "meta index", "meta summary")
}
$pairedMemoryTriggers = $policy.router_decision_contract.paired_memory_triggers
if ($null -eq $pairedMemoryTriggers) {
  $pairedMemoryTriggers = @("ERR-", "SOL-", "error memory", "solution memory", "self-reflection")
}
$explicitMemoryNeed = (Get-MatchedTriggers $memoryNeedTriggers).Count -gt 0
$pairedMemoryHits = Get-MatchedTriggers $pairedMemoryTriggers
$staticKnowledgeTriggers = $policy.router_decision_contract.static_knowledge_triggers
if ($null -eq $staticKnowledgeTriggers) {
  $staticKnowledgeTriggers = @("static knowledge", "project manual", "repository manual", "module map", "project map")
}
$staticKnowledgeHits = Get-MatchedTriggers $staticKnowledgeTriggers
if ($pairedMemoryHits.Count -gt 0) {
  $memoryNeed = "paired_err_sol"
} elseif (($explicitMemoryNeed) -or ($staticKnowledgeHits.Count -gt 0) -or ($feedbackLoopHits.Count -gt 0)) {
  $memoryNeed = "index_only"
} else {
  $memoryNeed = "none"
}
if ($pairedMemoryHits.Count -gt 0) {
  $semanticAmbiguity += @("feedback_loop_required")
  $requiredGates += "feedback_loop_gate"
  $matchedRiskTriggers["feedback_loop_memory"] = @($pairedMemoryHits)
  if ($feedbackLoopProfile -ne "explicit_cycle") {
    $feedbackLoopProfile = "prevention_review"
  }
}
if ($staticKnowledgeHits.Count -gt 0) {
  $requiredGates += "static_knowledge_index_gate"
}

$explicitRecordTriggers = $policy.router_decision_contract.explicit_record_triggers
if ($null -eq $explicitRecordTriggers) {
  $explicitRecordTriggers = @("record this error", "record this mistake", "remember this issue", "write this to memory", "add this to memory", "self-reflection matrix")
}
$commonErrorTriggers = $policy.router_decision_contract.common_error_triggers
if ($null -eq $commonErrorTriggers) {
  $commonErrorTriggers = @("common error", "common mistake", "field error", "schema error", "function call error", "tool call error", "semantic error", "patch context", "apply_patch context", "wildcard error", "quoting error")
}
$commonErrorPreventionTriggers = $policy.router_decision_contract.common_error_prevention_triggers
if ($null -eq $commonErrorPreventionTriggers) {
  $commonErrorPreventionTriggers = @("prevention", "prevent recurrence", "avoid recurrence", "use prevention", "continue diagnosis", "预防", "避免复发", "继续排查")
}
$projectizationTriggers = $policy.router_decision_contract.projectization_signals
if ($null -eq $projectizationTriggers) {
  $projectizationTriggers = @("version", "VERSION", "CHANGELOG", "README", "repository", "repo", "GitHub", "release", "tests", "adapter", "policy", "runtime", "docs", "template")
}
$explicitRecordHits = Get-MatchedTriggers $explicitRecordTriggers
$commonErrorHits = Get-MatchedTriggers $commonErrorTriggers
$commonErrorPreventionHits = Get-MatchedTriggers $commonErrorPreventionTriggers
$commonErrorWriteIntent = (($commonErrorHits.Count -gt 0) -and ($explicitRecordHits.Count -gt 0))
if (($explicitRecordHits.Count -gt 0) -and ($projectLane -ne "PROJECTLESS") -and ($risk -in @("R0", "R1", "R2"))) {
  $risk = "R3"
  $fallbackModelJudgmentRecommended = $false
  $classificationConfidence = "high"
  $requiredGates = @($requiredGates | Where-Object { $_ -ne "model_boundary_review_gate" })
  if ($matchedRiskTriggers.Contains("fallback_boundary")) {
    $matchedRiskTriggers.Remove("fallback_boundary")
  }
  $triggeredRisks += "R3"
  $riskCandidates["R3"] = @($explicitRecordHits)
  $matchedRiskTriggers["R3"] = @($explicitRecordHits)
  $risk_context_decisions["R3"] = [pscustomobject]@{
    decision = "project_memory_write"
    action_surface = "actionable_R3"
    promote_to_risk = $true
    candidate_terms = @($explicitRecordHits)
    negated_terms = @()
    diagnostic_terms = @()
    reason = "explicit_project_record_request"
  }
  foreach ($gate in (ConvertTo-Array (Get-ObjectPropertyValue $policy.risk_gate_rules "R3"))) {
    $requiredGates += [string]$gate
  }
}
$r5DecisionForMemoryIntent = $null
if ($risk_context_decisions.Contains("R5")) {
  $r5DecisionForMemoryIntent = $risk_context_decisions["R5"]
}
$r5CandidatesForMemoryIntent = @()
if (($null -ne $r5DecisionForMemoryIntent) -and ((Get-ObjectPropertyValue $r5DecisionForMemoryIntent "promote_to_risk") -eq $true)) {
  $r5CandidatesForMemoryIntent = @(ConvertTo-Array (Get-ObjectPropertyValue $r5DecisionForMemoryIntent "candidate_terms"))
}
$explicitLongTermMemoryWriteIntent = (($r5CandidatesForMemoryIntent | Where-Object { ([string]$_) -in @("write memory", "写入记忆") }).Count -gt 0)
if ($commonErrorHits.Count -gt 0) {
  if ($commonErrorWriteIntent) {
    if ($feedbackLoopProfile -eq "none") {
      $feedbackLoopProfile = "record_candidate"
    }
    $matchedRiskTriggers["common_error_candidate"] = @($commonErrorHits)
  } elseif ($commonErrorPreventionHits.Count -gt 0) {
    $semanticAmbiguity += @("feedback_loop_required")
    $requiredGates += "feedback_loop_gate"
    $matchedRiskTriggers["feedback_loop_common_error"] = @($commonErrorHits)
    if ($feedbackLoopProfile -ne "explicit_cycle") {
      $feedbackLoopProfile = "prevention_review"
    }
  } else {
    if ($feedbackLoopProfile -eq "none") {
      $feedbackLoopProfile = "index_hint"
    }
    $matchedRiskTriggers["common_error_index_hint"] = @($commonErrorHits)
  }
}
$semanticAmbiguity = @($semanticAmbiguity | Select-Object -Unique)
$conversationExplicitTriggers = $policy.router_decision_contract.conversation_memory_explicit_triggers
if ($null -eq $conversationExplicitTriggers) {
  $conversationExplicitTriggers = @("remember this conversation", "checkpoint this conversation", "continue this conversation later", "conversation memory", "thread memory")
}
$conversationSignalTriggers = $policy.router_decision_contract.conversation_memory_signals
if ($null -eq $conversationSignalTriggers) {
  $conversationSignalTriggers = @("long conversation", "context compression", "continue later", "open loops", "unresolved", "decision", "checkpoint", "handoff", "ordinary conversation", "projectless")
}
$conversationLaneDeclarationTriggers = $policy.router_decision_contract.conversation_lane_declaration_triggers
if ($null -eq $conversationLaneDeclarationTriggers) {
  $conversationLaneDeclarationTriggers = @("independent long conversation", "long single conversation lane", "this conversation is not a project", "独立的长单对话", "单长对话", "当前对话不是项目")
}
$projectizationSignals = Get-MatchedTriggers $projectizationTriggers
$conversationExplicitHits = Get-MatchedTriggers $conversationExplicitTriggers
$conversationSignals = Get-MatchedTriggers $conversationSignalTriggers
$conversationLaneDeclarationHits = Get-MatchedTriggers $conversationLaneDeclarationTriggers
if ($conversationLaneDeclarationHits.Count -gt 0) {
  $requiredGates += "lane_ownership_gate"
}
$selfReflectionRecordHits = @($explicitRecordHits)
if ($conversationExplicitHits.Count -gt 0) {
  $selfReflectionRecordHits = @()
}
$projectizationThreshold = 5
if ($null -ne $policy.router_decision_contract.projectization_threshold) {
  $projectizationThreshold = [int]$policy.router_decision_contract.projectization_threshold
}
$conversationThreshold = 5
if ($null -ne $policy.router_decision_contract.conversation_memory_threshold) {
  $conversationThreshold = [int]$policy.router_decision_contract.conversation_memory_threshold
}
$conversationFullLaneGroups = [ordered]@{}
$conversationFullLaneTriggered = $false
$conversationFullLaneConfig = Get-ObjectPropertyValue $policy.router_decision_contract "conversation_memory_full_lane_triggers"
$conversationThresholdGroups = Get-ObjectPropertyValue $conversationFullLaneConfig "threshold_groups"
if ($null -ne $conversationThresholdGroups) {
  foreach ($group in $conversationThresholdGroups.PSObject.Properties) {
    $groupThreshold = 1
    $configuredThreshold = Get-ObjectPropertyValue $group.Value "threshold"
    if ($null -ne $configuredThreshold) {
      $groupThreshold = [int]$configuredThreshold
    }
    $groupHits = Get-MatchedTriggers (Get-ObjectPropertyValue $group.Value "triggers")
    if ($groupHits.Count -gt 0) {
      $groupTriggered = ($groupHits.Count -ge $groupThreshold)
      $conversationFullLaneGroups[$group.Name] = [ordered]@{
        threshold = $groupThreshold
        hits = @($groupHits)
        triggered = [bool]$groupTriggered
      }
      if ($groupTriggered) {
        $conversationFullLaneTriggered = $true
      }
    }
  }
}

$projectizationDecision = "not_project"
if ($projectLane -ne "PROJECTLESS") {
  $projectizationDecision = "current_project"
} elseif ($projectizationSignals.Count -ge $projectizationThreshold) {
  $projectizationDecision = "emergent_project_candidate"
}

$conversationMemoryDecision = "none"
$readOnlyAuditTriggers = $policy.router_decision_contract.read_only_memory_audit_triggers
if ($null -eq $readOnlyAuditTriggers) {
  $readOnlyAuditTriggers = @("read-only", "readonly", "check whether", "verify whether")
}
$activeConversationWriteIntentTriggers = $policy.router_decision_contract.active_conversation_write_intent_triggers
if ($null -eq $activeConversationWriteIntentTriggers) {
  $activeConversationWriteIntentTriggers = @("fix", "modify", "change", "write", "record this", "implement")
}
$readOnlyAuditHits = Get-MatchedTriggers $readOnlyAuditTriggers
$activeConversationWriteIntentHits = Get-MatchedTriggers $activeConversationWriteIntentTriggers
$readOnlyMemoryAuditIntent = (
  ($readOnlyAuditHits.Count -gt 0) -and
  ($activeConversationWriteIntentHits.Count -eq 0) -and
  ($explicitRecordHits.Count -eq 0) -and
  (-not $commonErrorWriteIntent)
)
$activeConversationWriteIntent = (
  ($activeConversationWriteIntentHits.Count -gt 0) -or
  ($explicitRecordHits.Count -gt 0) -or
  $commonErrorWriteIntent
)
$activeConversationMemoryDurableSignal = (
  $hasActiveConversationMemoryLane -and
  (-not $readOnlyMemoryAuditIntent) -and (
    $activeConversationWriteIntent -or
    $conversationFullLaneTriggered -or
    ($conversationSignals.Count -ge $conversationThreshold) -or
    ($projectizationSignals.Count -ge $projectizationThreshold) -or
    ($risk -in @("R4", "R5"))
  ) -and
  (-not $commonErrorWriteIntent) -and
  ($commonErrorHits.Count -eq 0)
)
if ($projectLane -eq "PROJECTLESS") {
  if ($conversationExplicitHits.Count -gt 0) {
    $conversationMemoryDecision = "create_or_update_current_conversation"
  } elseif ($activeConversationMemoryDurableSignal) {
    $conversationMemoryDecision = "create_or_update_current_conversation"
  } elseif ((-not $readOnlyMemoryAuditIntent) -and ($projectizationDecision -eq "not_project") -and (($conversationSignals.Count -ge $conversationThreshold) -or $conversationFullLaneTriggered)) {
    $conversationMemoryDecision = "checkpoint_candidate"
  }
}

$linkIntent = "none"
$linkContract = $policy.conversation_linking_contract
if ($null -ne $linkContract) {
  if ((Get-MatchedTriggers (Get-ObjectPropertyValue $linkContract "merge_triggers")).Count -gt 0) {
    $linkIntent = "merge_memories_explicit"
  } elseif ((Get-MatchedTriggers (Get-ObjectPropertyValue $linkContract "archive_triggers")).Count -gt 0) {
    $linkIntent = "archive_or_seal_memory"
  } elseif ((Get-MatchedTriggers (Get-ObjectPropertyValue $linkContract "continue_reference_triggers")).Count -gt 0) {
    $linkIntent = "continue_from_referenced_memory"
  } elseif ((Get-MatchedTriggers (Get-ObjectPropertyValue $linkContract "continue_latest_triggers")).Count -gt 0) {
    $linkIntent = "continue_from_latest"
  }
}
if ($linkIntent -ne "none") {
  $linkShouldCreateCurrentConversation = (
    ($linkIntent -in @("continue_from_latest", "continue_from_referenced_memory")) -and
    (($conversationExplicitHits.Count -gt 0) -or $activeConversationWriteIntent)
  )
  if ($linkShouldCreateCurrentConversation) {
    $conversationMemoryDecision = "create_or_update_current_conversation"
  } else {
    $conversationMemoryDecision = "read_referenced_conversation"
  }
} else {
  $linkShouldCreateCurrentConversation = $false
}

if ($commonErrorHits.Count -gt 0) {
  $memoryNeed = "common_error_corpus"
} elseif (($selfReflectionRecordHits.Count -gt 0) -and ($memoryNeed -eq "none")) {
  $memoryNeed = "paired_err_sol"
} elseif ($explicitLongTermMemoryWriteIntent -and ($memoryNeed -eq "none")) {
  $memoryNeed = "index_only"
}

$recordIntent = "no_record"
if ($commonErrorWriteIntent) {
  $recordIntent = "inferred_reusable_error"
} elseif ($conversationMemoryDecision -eq "create_or_update_current_conversation") {
  if ($conversationExplicitHits.Count -gt 0) {
    $recordIntent = "explicit_conversation_memory_request"
  } else {
    $recordIntent = "conversation_checkpoint"
  }
} elseif ($selfReflectionRecordHits.Count -gt 0) {
  $recordIntent = "explicit_user_request"
} elseif ($explicitLongTermMemoryWriteIntent) {
  $recordIntent = "explicit_user_request"
} elseif ($conversationMemoryDecision -eq "checkpoint_candidate") {
  $recordIntent = "conversation_checkpoint"
} elseif ($projectizationDecision -eq "emergent_project_candidate") {
  $recordIntent = "projectization_review"
} elseif ($linkIntent -in @("merge_memories_explicit", "archive_or_seal_memory")) {
  $recordIntent = "explicit_cross_conversation_update"
} elseif ($linkIntent -ne "none") {
  $recordIntent = "conversation_link_review"
}

if (($linkIntent -ne "none") -and $linkShouldCreateCurrentConversation -and ($memoryNeed -eq "none")) {
  $memoryNeed = "conversation_state"
} elseif (($linkIntent -ne "none") -and ($memoryNeed -eq "none")) {
  $memoryNeed = "index_only"
} elseif (($conversationMemoryDecision -ne "none") -and ($memoryNeed -eq "none")) {
  $memoryNeed = "conversation_state"
}
if ($linkIntent -ne "none") {
  $requiredGates += "conversation_link_gate"
}

$memoryLane = "none"
if ($commonErrorHits.Count -gt 0) {
  $memoryLane = "common_error_corpus"
} elseif ($projectLane -ne "PROJECTLESS") {
  $memoryLane = "current_project"
} elseif (($linkIntent -ne "none") -and $linkShouldCreateCurrentConversation) {
  $memoryLane = "current_conversation"
} elseif ($linkIntent -ne "none") {
  $memoryLane = "referenced_conversation"
} elseif ($explicitLongTermMemoryWriteIntent -and $hasActiveConversationMemoryLane) {
  $memoryLane = "current_conversation"
} elseif ($explicitLongTermMemoryWriteIntent) {
  $memoryLane = "global_inbox"
} elseif (($projectLane -eq "PROJECTLESS") -and ($conversationLaneDeclarationHits.Count -gt 0)) {
  $memoryLane = "current_conversation"
} elseif (($conversationMemoryDecision -ne "none") -and ($hasActiveConversationMemoryLane -or ($conversationExplicitHits.Count -gt 0))) {
  $memoryLane = "current_conversation"
} elseif ($selfReflectionRecordHits.Count -gt 0) {
  $memoryLane = "self_reflection_matrix"
} elseif ($projectizationDecision -eq "emergent_project_candidate") {
  $memoryLane = "emergent_project_candidate"
} elseif ($conversationMemoryDecision -ne "none") {
  $memoryLane = "current_conversation"
}

$memoryMode = "none"
if (($recordIntent -eq "explicit_user_request") -or ($recordIntent -eq "inferred_reusable_error") -or ($recordIntent -eq "explicit_conversation_memory_request") -or ($recordIntent -eq "conversation_checkpoint") -or ($recordIntent -eq "explicit_cross_conversation_update")) {
  if (($memoryLane -eq "current_conversation") -and $hasActiveConversationMemoryLane) {
    $memoryMode = "update"
  } else {
    $memoryMode = "write"
  }
} elseif ($memoryNeed -ne "none") {
  $memoryMode = "read"
}

if (
  (($conversationMemoryDecision -eq "create_or_update_current_conversation") -and ($memoryMode -in @("write", "update"))) -or
  (($linkIntent -ne "none") -and ($memoryLane -eq "current_conversation"))
) {
  if ($risk -notin @("R5", "R4", "R3")) {
    $risk = "R3"
  }
  if ($triggeredRisks -notcontains "R3") {
    $triggeredRisks += "R3"
  }
  $r3Matches = @()
  if ($matchedRiskTriggers.Contains("R3")) {
    $r3Matches = @($matchedRiskTriggers["R3"])
  }
  $mergedR3Matches = @($r3Matches + "conversation_memory_write_or_link")
  $matchedRiskTriggers["R3"] = @($mergedR3Matches | Select-Object -Unique)
  $r3Gates = Get-ObjectPropertyValue $policy.risk_gate_rules "R3"
  foreach ($gate in (ConvertTo-Array $r3Gates)) {
    $requiredGates += [string]$gate
  }
}

$hybridRetrievalProfile = "none"
if ($memoryNeed -ne "none") {
  $hybridRetrievalProfile = "meta_first_hybrid_enhancement"
}
if (($memoryNeed -in @("capsule_payload", "paired_err_sol", "common_error_corpus", "conversation_state")) -or ($linkIntent -ne "none")) {
  $hybridRetrievalProfile = "meta_first_hybrid_required"
}

$memoryWriteProfile = "none"
if ($memoryMode -in @("write", "update")) {
  $memoryWriteProfile = "context_complete_required"
}
if ($recordIntent -in @("explicit_user_request", "explicit_conversation_memory_request", "explicit_cross_conversation_update")) {
  $memoryWriteProfile = "strict_capsule_required"
}

$readSemanticBoundary = @()
if (Test-TaskContainsAny @("continue this conversation", "resume", "handoff", "context compression", "open loops", "current goal", "global goal", "接续", "继续上一段", "上下文压缩", "任务源头", "当前目标", "全局目标", "交接", "未完成事项")) {
  $readSemanticBoundary += "continuity_goal"
}
if (Test-TaskContainsAny @("exact anchor", "exact wording", "DOI", "commit hash", "hash", "tag", "version marker", "lane id", "path", "精确锚点", "原文", "准确字面", "版本标记", "路径", "哈希", "标签")) {
  $readSemanticBoundary += "exact_anchor"
}
if (Test-TaskContainsAny @("command log", "tool log", "execution log", "error output", "actually ran", "whether I ran", "whether you ran", "skipped", "self-report", "命令日志", "工具日志", "执行日志", "错误输出", "是否真的运行", "是否执行", "尝试过", "跳过", "事后描述")) {
  $readSemanticBoundary += "execution_trace"
}
if (Test-TaskContainsAny @("PDF", "HTML", "README", "release", "artifact", "final output", "compiled output", "test output", "diff", "最终输出", "编译产物", "发布产物", "测试输出", "公开文档")) {
  $readSemanticBoundary += "output_truth"
}
if (($linkIntent -ne "none") -or (Test-TaskContainsAny @("cross lane", "cross project", "merge memory", "backfill", "archive memory", "cold lane", "backup snapshot", "lane ownership", "跨 lane", "跨项目", "合并记忆", "链接记忆", "归属", "回填", "归档记忆", "备份快照", "隔离互联"))) {
  $readSemanticBoundary += "cross_boundary"
}
if (Test-TaskContainsAny @("source validity", "source dependency", "official source", "authority", "conflict", "supersede", "retracted", "external evidence", "源证据", "来源依赖", "官方", "权威", "冲突", "覆盖旧", "失效", "撤回", "外部证据")) {
  $readSemanticBoundary += "source_validity"
}
if (Test-TaskContainsAny @("causal", "causality", "prove", "proves", "cause", "causes", "long-term", "global effect", "hallucination drift", "validated causality", "future similar cases", "similar future events", "recurrence risk", "prevent similar recurrence", "因果", "证明", "导致", "长期降低", "长期提升", "全局效果", "全局问题", "系统性问题", "后续可能", "后续同类", "同类事件", "类似事件", "复发风险", "预防同类", "幻觉漂移", "能力变化")) {
  $readSemanticBoundary += "causal_scope"
}
if (Test-TaskContainsAny @("modify", "update", "fix", "patch", "sync", "adapt", "rewrite", "delete", "remove", "configure", "AGENTS", "router", "policy", "修改", "更新", "修复", "补丁", "同步", "适配", "重写", "删除", "移除", "配置")) {
  $readSemanticBoundary += "change_integrity"
}
if (($debtHygieneHits.Count -gt 0) -or (Test-TaskContainsAny @("contamination", "pollution", "technical debt", "dirty tree debt", "cleanup grouping", "memory pollution", "target pollution", "污染", "记忆污染", "目标污染", "技术债", "脏树债", "清查分组", "候选技术债"))) {
  $readSemanticBoundary += "contamination_or_debt"
}
if (($readSemanticBoundary.Count -eq 0) -and (($memoryNeed -ne "none") -or ($targetSurface -in @("project_memory", "conversation_ledger", "skill_matrix", "local_harness")))) {
  $readSemanticBoundary += "orientation"
}
$readSemanticBoundary = @($readSemanticBoundary | Select-Object -Unique)

$readDepthProfile = "none"
if (($readSemanticBoundary -contains "contamination_or_debt") -and (Test-TaskContainsAny @("full audit", "full lane", "migration", "backfill", "cleanup", "全量审计", "全面审计", "全 lane", "迁移", "回填", "清查", "清理"))) {
  $readDepthProfile = "full_lane_audit"
} elseif (($readSemanticBoundary -contains "source_validity") -or ($readSemanticBoundary -contains "causal_scope")) {
  $readDepthProfile = "source_cascade_review"
} elseif ($readSemanticBoundary -contains "cross_boundary") {
  $readDepthProfile = "cross_lane_link_review"
} elseif ($readSemanticBoundary -contains "output_truth") {
  $readDepthProfile = "artifact_output_window"
} elseif (($readSemanticBoundary -contains "execution_trace") -or ($readSemanticBoundary -contains "exact_anchor")) {
  $readDepthProfile = "raw_context_window"
} elseif ($readSemanticBoundary -contains "change_integrity") {
  $readDepthProfile = "artifact_output_window"
} elseif ($readSemanticBoundary -contains "continuity_goal") {
  $readDepthProfile = "segment_window"
} elseif ($readSemanticBoundary -contains "orientation") {
  $readDepthProfile = "capsule_only"
}

$editOperationProfile = "none"
$readOnlyTask = Test-TaskContainsAny @("read-only", "readonly", "inspect only", "check only", "verify whether", "detect", "do not modify", "do not execute", "report only", "只读", "只检查", "检测", "核对", "不要修改", "不修改", "不要执行", "不执行", "先检查")
$diskDeleteMatch = [regex]::Match($TaskText, "(?i)(删除|移除|清理|delete|remove).{0,48}(文件夹|目录|folder|directory|file|文件|旧\s*release|release\s*folder)|\brm\s+-rf\b|Remove-Item")
$diskDeleteRequested = ($diskDeleteMatch.Success -and (-not (Test-NegatedMatch -source $TaskText -index $diskDeleteMatch.Index)))
$recordDeleteMatch = [regex]::Match($TaskText, "(?i)(删掉|删除|移除|去掉|remove|delete).{0,48}(段|描述|行|条目|内容|字段|section|paragraph|line|entry|README\s+中)")
$recordDeleteRequested = ($recordDeleteMatch.Success -and (-not (Test-NegatedMatch -source $TaskText -index $recordDeleteMatch.Index)))
$fullRewriteRequested = [regex]::IsMatch($TaskText, "(?i)(完全|整个|整份|全部|全量).{0,24}(重写|rewrite|replace|rebuild|重新生成)|full\s+rewrite|rewrite\s+the\s+whole|replace\s+the\s+whole")
$appendRequested = Test-TaskContainsAny @("append", "append-only", "append delta", "ledger", "jsonl", "changelog", "context backup", "execution log", "追加", "追加写入", "上下文备份", "执行日志", "对话账本", "变更日志")
$addNewRequested = Test-TaskContainsAny @("create new file", "add new file", "new artifact", "新增文件", "新建文件", "创建新文件", "新增产物")
$supersedeRequested = Test-TaskContainsAny @("supersede", "superseded", "replace while preserving", "替代并保留", "覆盖旧说法", "标记为 superseded")
$archiveRequested = Test-TaskContainsAny @("archive", "move to archive", "quarantine", "归档", "移动到归档", "隔离放入", "冷归档")
$sectionReplaceRequested = Test-TaskContainsAny @("section replace", "replace section", "replace paragraph", "小节替换", "替换这一段", "替换这段", "段落替换")
$inPlacePatchRequested = Test-TaskContainsAny @("update", "modify", "fix", "patch", "sync", "adapt", "optimize", "edit", "更新", "修改", "修复", "补丁", "同步", "适配", "优化", "改进")

if ($diskDeleteRequested) {
  $editOperationProfile = "delete_from_disk"
} elseif ($recordDeleteRequested) {
  $editOperationProfile = "delete_record_content"
} elseif ($fullRewriteRequested) {
  $editOperationProfile = "full_rewrite"
} elseif ($appendRequested) {
  $editOperationProfile = "append_delta"
} elseif ($addNewRequested) {
  $editOperationProfile = "add_new_artifact"
} elseif ($supersedeRequested) {
  $editOperationProfile = "supersede_with_link"
} elseif ($archiveRequested -and (-not $readOnlyTask)) {
  $editOperationProfile = "archive_or_move"
} elseif ($sectionReplaceRequested) {
  $editOperationProfile = "section_replace"
} elseif (($readOnlyTask -or ($risk -eq "R1")) -and ($risk -ne "R3")) {
  $editOperationProfile = "read_only"
} elseif ($inPlacePatchRequested -or ($risk -eq "R3")) {
  $editOperationProfile = "in_place_patch"
}

if ($readSemanticBoundary.Count -gt 0) {
  $matchedRiskTriggers["read_semantic_boundary"] = @($readSemanticBoundary)
}
if ($readDepthProfile -ne "none") {
  $matchedRiskTriggers["read_depth_profile"] = @($readDepthProfile)
}
if ($editOperationProfile -ne "none") {
  $matchedRiskTriggers["edit_operation_profile"] = @($editOperationProfile)
}

if (($selfReflectionRecordHits.Count -gt 0) -or ($commonErrorHits.Count -gt 0)) {
  $requiredSkills += "troubleshooting-skill-matrix"
}

$skillLifecycleProfile = "none"
$skillListingTriggers = @("skill listing", "skill list", "available skills", "skills list", "skill 清单", "技能清单")
$skillActiveFrameTriggers = @("skill", "SKILL.md", "skill matrix", "semantic anchor", "技能", "技能矩阵", "语义锚点")
$skillReleaseReceiptTriggers = @("skill release receipt", "release receipt", "skill ttl", "active frame ttl", "release skill", "clear skill body", "调用周期", "释放回执", "激活帧", "用完释放", "清理大正文")
$skillReactivateTriggers = @("reactivate skill", "reactivate from receipt", "resume skill", "resume from skill receipt", "重新激活", "恢复入口", "从回执恢复")
if ((Get-MatchedTriggers $skillListingTriggers).Count -gt 0) {
  $skillLifecycleProfile = "listing_only"
}
if (($targetSurface -eq "skill_matrix") -or ($requiredSkills.Count -gt 0) -or ((Get-MatchedTriggers $skillActiveFrameTriggers).Count -gt 0)) {
  $skillLifecycleProfile = "active_frame_required"
}
if ((Get-MatchedTriggers $skillReleaseReceiptTriggers).Count -gt 0) {
  $skillLifecycleProfile = "release_receipt_required"
}
if ((Get-MatchedTriggers $skillReactivateTriggers).Count -gt 0) {
  $skillLifecycleProfile = "reactivate_from_receipt"
}

$toolSurfaceNeed = "none"
$toolDiscoveryStatus = "not_needed"
$skillOrToolNeed = "none"
$pluginNeed = "none"
$preferredCallSurface = "none"
$toolSurfaceReason = @()

$toolSurfaceGroups = $policy.router_decision_contract.tool_surface_trigger_groups
$explicitToolSurfaceHits = Get-TaskMatchedTerms @("@github", "@browser", "@chrome", "@nvidia", "@hugging-face", "@vercel", "@gmail", "@slack", "@canva", "plugin://", "app://", "tool_search", "MCP", "connector", "plugin", "插件", "连接器")
$githubPluginHits = @()
$platformPluginHits = @()
$codexNativeSkillHits = @()
$browserSurfaceHits = @()
if ($null -ne $toolSurfaceGroups) {
  $githubPluginHits = Get-MatchedTriggers (Get-ObjectPropertyValue $toolSurfaceGroups "github_plugin")
  $platformPluginHits = Get-MatchedTriggers (Get-ObjectPropertyValue $toolSurfaceGroups "platform_plugin")
  $codexNativeSkillHits = Get-MatchedTriggers (Get-ObjectPropertyValue $toolSurfaceGroups "codex_native_skill")
  $browserSurfaceHits = Get-MatchedTriggers (Get-ObjectPropertyValue $toolSurfaceGroups "browser_surface")
}

if (($explicitToolSurfaceHits.Count -gt 0) -or ($githubPluginHits.Count -gt 0) -or ($platformPluginHits.Count -gt 0)) {
  $toolSurfaceNeed = "plugin_mcp"
  $skillOrToolNeed = "mcp_or_app_tool"
  $preferredCallSurface = "plugin_or_connector"
  if ($explicitToolSurfaceHits.Count -gt 0) {
    $pluginNeed = "user_named"
    $toolDiscoveryStatus = "user_named"
    $toolSurfaceReason += "explicit_plugin_or_connector"
  } else {
    $pluginNeed = "candidate_discovery_required"
    $toolDiscoveryStatus = "not_checked"
    $toolSurfaceReason += "platform_object_without_explicit_tool"
  }
}

if ($codexNativeSkillHits.Count -gt 0) {
  if ($toolSurfaceNeed -ne "none") {
    $toolSurfaceNeed = "multiple"
  } else {
    $toolSurfaceNeed = "native_skill"
    $toolDiscoveryStatus = "not_checked"
    $preferredCallSurface = "native_skill"
  }
  $skillOrToolNeed = "codex_native_skill"
  $toolSurfaceReason += "codex_native_skill_candidate"
}

if ($browserSurfaceHits.Count -gt 0) {
  if ($toolSurfaceNeed -ne "none") {
    $toolSurfaceNeed = "multiple"
  } else {
    $toolSurfaceNeed = "browser"
    $toolDiscoveryStatus = "not_checked"
  }
  $skillOrToolNeed = "mcp_or_app_tool"
  $preferredCallSurface = "browser_or_chrome"
  $toolSurfaceReason += "browser_or_chrome_candidate"
}

if ($targetSurface -eq "tool_call" -and $toolSurfaceNeed -eq "none") {
  $toolSurfaceNeed = "shell"
  $toolDiscoveryStatus = "not_needed"
  $skillOrToolNeed = "shell_or_local_tool"
  $preferredCallSurface = "shell"
  $toolSurfaceReason += "local_tool_or_shell_surface"
}

if ($toolDiscoveryStatus -in @("not_checked", "user_named")) {
  $requiredGates += "tool_surface_discovery_gate"
}
$toolSurfaceReason = @($toolSurfaceReason | Select-Object -Unique)
$correctionLifecycleProfile = "none"
if ($feedbackLoopProfile -in @("prevention_review", "explicit_cycle")) {
  $correctionLifecycleProfile = "memory_to_action"
} elseif ($toolSurfaceNeed -ne "none") {
  $correctionLifecycleProfile = "surface_preflight"
}

$strongClaimTerms = Get-MatchedTriggers $policy.blocked_claim_phrases_without_schema
if ($strongClaimTerms.Count -gt 0) {
  $claimRisk = "strong_claim_needs_schema"
} elseif (@($requiredGates | Where-Object { $_ -eq "claim_gate" }).Count -gt 0) {
  $claimRisk = "weak_claim"
} else {
  $claimRisk = "none"
}

$moduleNeed = @()
if ($projectLane -ne "PROJECTLESS") { $moduleNeed += "project_router" }
if (($requiredSkills.Count -gt 0) -or ($targetSurface -eq "skill_matrix") -or ($skillLifecycleProfile -ne "none")) { $moduleNeed += "skill_matrix" }
if ($semanticAmbiguity.Count -gt 0) { $moduleNeed += "semantic_anchors" }
if ($memoryNeed -ne "none") { $moduleNeed += "memory_meta_index" }
if ($staticKnowledgeHits.Count -gt 0) { $moduleNeed += "static_knowledge_index" }
if ($debtHygieneHits.Count -gt 0) { $moduleNeed += "debt_hygiene_gate" }
if ($targetSurface -eq "conversation_ledger") { $moduleNeed += "conversation_ledger_index" }
if ($toolDiscoveryStatus -in @("not_checked", "user_named")) { $moduleNeed += "tool_surface_discovery" }
if ($correctionLifecycleProfile -ne "none") { $moduleNeed += "correction_lifecycle" }
if ($conversationMemoryDecision -ne "none") { $moduleNeed += "conversation_memory_index" }
if ($linkIntent -ne "none") { $moduleNeed += "memory_link_ledger" }
if (($externalNeed.Count -gt 0) -and ($externalNeed[0] -ne "none")) { $moduleNeed += "external_research_gate" }
if ($claimRisk -ne "none") { $moduleNeed += "claim_schema_verifier" }
if (($risk -eq "R5") -or ($classificationConfidence -eq "low")) { $moduleNeed += "runtime_gate" }
if ($moduleNeed.Count -eq 0) { $moduleNeed += "none" }
$moduleNeed = @($moduleNeed | Select-Object -Unique)

$actionBindings = @()
if ($memoryNeed -ne "none") {
  $actionBindings += [pscustomobject]@{
    action = "retrieve_matching_memory"
    completion_evidence = "selected_record_id_and_provenance"
  }
}
if ($correctionLifecycleProfile -ne "none") {
  $actionBindings += [pscustomobject]@{
    action = "prepare_task_local_correction_bundle"
    completion_evidence = "task_local_correction_bundle"
  }
}
if (($externalNeed.Count -gt 0) -and ($externalNeed[0] -ne "none")) {
  $actionBindings += [pscustomobject]@{
    action = "perform_external_research_route"
    completion_evidence = "source_ledger_or_citations"
  }
}
$actionBindingIds = @($actionBindings | ForEach-Object { [string]$_.action } | Select-Object -Unique)

$memorySourceHints = @()
if (($memoryNeed -ne "none") -and $hasActiveConversationMemoryLane) {
  $memorySourceHints += [pscustomobject]@{
    lane = "current_conversation"
    root_path = $activeConversationMemoryLanePath
    meta_path = (Join-Path $activeConversationMemoryLanePath "_META_INDEX.md")
    isolation = "exact_active_conversation_lane"
  }
}
if (($memoryNeed -ne "none") -and ($projectLane -ne "PROJECTLESS")) {
  $projectMemoryRoots = ConvertTo-Array (Get-ObjectPropertyValue $policy.memory_roots $projectLane)
  foreach ($root in $projectMemoryRoots) {
    if (-not [string]::IsNullOrWhiteSpace([string]$root)) {
      $memorySourceHints += [pscustomobject]@{
        lane = "current_project"
        root_path = [string]$root
        meta_path = (Join-Path ([string]$root) "_META_INDEX.md")
        isolation = "registered_project_lane_root"
      }
    }
  }
}

$debugTriggers = Get-ObjectPropertyValue $policy.receipt_profiles "debug_triggers"
$debugHits = Get-MatchedTriggers $debugTriggers
$receiptProfile = "compact_runtime"
$profileReason = @("default_compact_runtime")
if ($debugHits.Count -gt 0) {
  $receiptProfile = "debug_receipt"
  $profileReason += "debug_requested"
} else {
  if ($targetSurface -in @("public_docs", "local_harness", "project_memory", "conversation_ledger", "skill_matrix", "adapter", "private_rule")) {
    $profileReason += "governance_surface"
  }
  if ($audience -in @("public_user", "local_maintainer")) {
    $profileReason += "audience_boundary"
  }
  if ($semanticAmbiguity.Count -gt 0) {
    $profileReason += "semantic_ambiguity"
  }
  if ($skillLifecycleProfile -ne "none") {
    $profileReason += "skill_lifecycle"
  }
  if (($memoryMode -eq "write") -or ($memoryMode -eq "update") -or ($recordIntent -ne "no_record")) {
    $profileReason += "memory_write_or_record"
  }
  if ($projectizationDecision -eq "emergent_project_candidate") {
    $profileReason += "projectization_candidate"
  }
  if ($conversationMemoryDecision -ne "none") {
    $profileReason += "conversation_memory_candidate"
  }
  if ($linkIntent -ne "none") {
    $profileReason += "conversation_link_boundary"
  }
  if ($profileReason.Count -gt 1) {
    $receiptProfile = "extended_governance"
  }
}
$profileReason = @($profileReason | Select-Object -Unique)
$humanConfirmationNeed = (@($approval | Select-Object -Unique).Count -gt 0)

$routingReceipt = [ordered]@{
  task_type = $risk
  target_surface = $targetSurface
  audience = $audience
  project_lane = $projectLane
  risk_level = $risk
  semantic_ambiguity = @($semanticAmbiguity)
  module_need = @($moduleNeed)
  tool_surface_need = $toolSurfaceNeed
  tool_discovery_status = $toolDiscoveryStatus
  skill_or_tool_need = $skillOrToolNeed
  plugin_need = $pluginNeed
  preferred_call_surface = $preferredCallSurface
  tool_surface_reason = @($toolSurfaceReason)
  skill_lifecycle_profile = $skillLifecycleProfile
  skill_audit_profile = $skillAuditProfile
  skill_audit_signals = @($skillAuditSignals)
  feedback_loop_profile = $feedbackLoopProfile
  correction_lifecycle_profile = $correctionLifecycleProfile
  first_principles_profile = $firstPrinciplesProfile
  first_principles_signals = @($firstPrinciplesSignals)
  read_semantic_boundary = @($readSemanticBoundary)
  read_depth_profile = $readDepthProfile
  edit_operation_profile = $editOperationProfile
  memory_need = $memoryNeed
  hybrid_retrieval_profile = $hybridRetrievalProfile
  memory_mode = $memoryMode
  memory_write_profile = $memoryWriteProfile
  memory_lane = $memoryLane
  memory_source_hints = @($memorySourceHints)
  action_bindings = @($actionBindings)
  record_intent = $recordIntent
  external_need = @($externalNeed)
  claim_risk = $claimRisk
  projectization_decision = $projectizationDecision
  conversation_memory_decision = $conversationMemoryDecision
  link_intent = $linkIntent
  receipt_profile = $receiptProfile
  projectization_signals = @($projectizationSignals)
  conversation_signals = @(@($conversationExplicitHits) + @($conversationSignals) + @($conversationLaneDeclarationHits) | Select-Object -Unique)
  conversation_full_lane_triggered = [bool]$conversationFullLaneTriggered
  conversation_full_lane_groups = $conversationFullLaneGroups
  required_gates = @($requiredGates | Select-Object -Unique)
}

$compactReceipt = [ordered]@{
  task_type = $risk
  risk_level = $risk
  required_gates = @($requiredGates | Select-Object -Unique)
  tool_surface_need = $toolSurfaceNeed
  tool_discovery_status = $toolDiscoveryStatus
  skill_or_tool_need = $skillOrToolNeed
  plugin_need = $pluginNeed
  preferred_call_surface = $preferredCallSurface
  skill_lifecycle_profile = $skillLifecycleProfile
  skill_audit_profile = $skillAuditProfile
  feedback_loop_profile = $feedbackLoopProfile
  correction_lifecycle_profile = $correctionLifecycleProfile
  first_principles_profile = $firstPrinciplesProfile
  read_semantic_boundary = @($readSemanticBoundary)
  read_depth_profile = $readDepthProfile
  edit_operation_profile = $editOperationProfile
  memory_mode = $memoryMode
  hybrid_retrieval_profile = $hybridRetrievalProfile
  memory_write_profile = $memoryWriteProfile
  memory_lane = $memoryLane
  memory_source_hints = @($memorySourceHints)
  action_binding_ids = @($actionBindingIds)
  conversation_memory_decision = $conversationMemoryDecision
  conversation_full_lane_triggered = [bool]$conversationFullLaneTriggered
  link_intent = $linkIntent
  external_need = @($externalNeed)
  claim_risk = $claimRisk
  human_confirmation_need = $humanConfirmationNeed
}

$result = [ordered]@{
  ts = (Get-Date).ToString("o")
  phase = "intake_router"
  status = "pass"
  cwd = $Cwd
  routing_receipt = $routingReceipt
  compact_receipt = $compactReceipt
  receipt_profile = $receiptProfile
  profile_reason = @($profileReason)
  target_surface = $targetSurface
  audience = $audience
  project_lane = $projectLane
  risk_level = $risk
  semantic_ambiguity = @($semanticAmbiguity)
  module_need = @($moduleNeed)
  tool_surface_need = $toolSurfaceNeed
  tool_discovery_status = $toolDiscoveryStatus
  skill_or_tool_need = $skillOrToolNeed
  plugin_need = $pluginNeed
  preferred_call_surface = $preferredCallSurface
  tool_surface_reason = @($toolSurfaceReason)
  skill_lifecycle_profile = $skillLifecycleProfile
  skill_audit_profile = $skillAuditProfile
  skill_audit_signals = @($skillAuditSignals)
  feedback_loop_profile = $feedbackLoopProfile
  correction_lifecycle_profile = $correctionLifecycleProfile
  first_principles_profile = $firstPrinciplesProfile
  first_principles_signals = @($firstPrinciplesSignals)
  read_semantic_boundary = @($readSemanticBoundary)
  read_depth_profile = $readDepthProfile
  edit_operation_profile = $editOperationProfile
  memory_need = $memoryNeed
  hybrid_retrieval_profile = $hybridRetrievalProfile
  memory_mode = $memoryMode
  memory_write_profile = $memoryWriteProfile
  memory_lane = $memoryLane
  memory_source_hints = @($memorySourceHints)
  action_bindings = @($actionBindings)
  action_binding_ids = @($actionBindingIds)
  record_intent = $recordIntent
  external_need = @($externalNeed)
  claim_risk = $claimRisk
  projectization_decision = $projectizationDecision
  conversation_memory_decision = $conversationMemoryDecision
  link_intent = $linkIntent
  projectization_signals = @($projectizationSignals)
  conversation_signals = @(@($conversationExplicitHits) + @($conversationSignals) + @($conversationLaneDeclarationHits) | Select-Object -Unique)
  conversation_full_lane_triggered = [bool]$conversationFullLaneTriggered
  conversation_full_lane_groups = $conversationFullLaneGroups
  triggered_risks = @($triggeredRisks | Select-Object -Unique)
  matched_risk_triggers = $matchedRiskTriggers
  negated_risk_triggers = $negatedRiskTriggers
  risk_candidates = $riskCandidates
  risk_context_decisions = $risk_context_decisions
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
