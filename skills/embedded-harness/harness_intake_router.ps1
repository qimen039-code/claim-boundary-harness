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
  return ($prefix -match "(?i)(\bdo\s+not\b|\bdon't\b|\bnever\b|\bnot\b|\bno\b)[\s\w'-]{0,128}$")
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
  $actionContextHits = Get-SourceMatchedTerms -source $sourceText -terms $contextRules.action_context_terms
  $documentationContextHits = Get-SourceMatchedTerms -source $sourceText -terms $contextRules.documentation_context_terms
  $nonActionContextHits = Get-SourceMatchedTerms -source $sourceText -terms $contextRules.non_action_context_terms
  $contextRequiredCandidateHits = Get-TermIntersection -leftTerms $candidateTerms -rightTerms $contextRules.context_required_candidate_terms
  $alwaysActionCandidateHits = Get-TermIntersection -leftTerms $candidateTerms -rightTerms $contextRules.always_action_candidate_terms

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
          if (($combined -match "status[`"']?\s*[:=]\s*[`"']?ACTIVE") -or ($combined -match "single_conversation_project_shaped_lane")) {
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

$targetSurface = Get-TargetSurface
if (($targetSurface -eq "current_chat") -and ($triggeredRisks -contains "R3")) {
  $targetSurface = "local_harness"
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
$staticKnowledgeTriggers = $policy.router_decision_contract.static_knowledge_triggers
if ($null -eq $staticKnowledgeTriggers) {
  $staticKnowledgeTriggers = @("static knowledge", "project manual", "repository manual", "module map", "project map")
}
$staticKnowledgeHits = Get-MatchedTriggers $staticKnowledgeTriggers
if ((Get-MatchedTriggers $pairedMemoryTriggers).Count -gt 0) {
  $memoryNeed = "paired_err_sol"
} elseif (($explicitMemoryNeed) -or ($staticKnowledgeHits.Count -gt 0)) {
  $memoryNeed = "index_only"
} else {
  $memoryNeed = "none"
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
$projectizationTriggers = $policy.router_decision_contract.projectization_signals
if ($null -eq $projectizationTriggers) {
  $projectizationTriggers = @("version", "VERSION", "CHANGELOG", "README", "repository", "repo", "GitHub", "release", "tests", "adapter", "policy", "runtime", "docs", "template")
}
$explicitRecordHits = Get-MatchedTriggers $explicitRecordTriggers
$commonErrorHits = Get-MatchedTriggers $commonErrorTriggers
$conversationExplicitTriggers = $policy.router_decision_contract.conversation_memory_explicit_triggers
if ($null -eq $conversationExplicitTriggers) {
  $conversationExplicitTriggers = @("remember this conversation", "checkpoint this conversation", "continue this conversation later", "conversation memory", "thread memory")
}
$conversationSignalTriggers = $policy.router_decision_contract.conversation_memory_signals
if ($null -eq $conversationSignalTriggers) {
  $conversationSignalTriggers = @("long conversation", "context compression", "continue later", "open loops", "unresolved", "decision", "checkpoint", "handoff", "ordinary conversation", "projectless")
}
$projectizationSignals = Get-MatchedTriggers $projectizationTriggers
$conversationExplicitHits = Get-MatchedTriggers $conversationExplicitTriggers
$conversationSignals = Get-MatchedTriggers $conversationSignalTriggers
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
  ($commonErrorHits.Count -eq 0)
)
$activeConversationWriteIntent = (
  ($activeConversationWriteIntentHits.Count -gt 0) -or
  ($explicitRecordHits.Count -gt 0) -or
  ($commonErrorHits.Count -gt 0)
)
$activeConversationMemoryDurableSignal = (
  $hasActiveConversationMemoryLane -and
  (-not $readOnlyMemoryAuditIntent) -and (
    $activeConversationWriteIntent -or
    $conversationFullLaneTriggered -or
    ($conversationSignals.Count -ge $conversationThreshold) -or
    ($projectizationSignals.Count -ge $projectizationThreshold) -or
    ($risk -in @("R4", "R5"))
  )
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
}

$recordIntent = "no_record"
if ($commonErrorHits.Count -gt 0) {
  $recordIntent = "inferred_reusable_error"
} elseif ($conversationMemoryDecision -eq "create_or_update_current_conversation") {
  if ($conversationExplicitHits.Count -gt 0) {
    $recordIntent = "explicit_conversation_memory_request"
  } else {
    $recordIntent = "conversation_checkpoint"
  }
} elseif ($selfReflectionRecordHits.Count -gt 0) {
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
if ($targetSurface -eq "conversation_ledger") { $moduleNeed += "conversation_ledger_index" }
if ($conversationMemoryDecision -ne "none") { $moduleNeed += "conversation_memory_index" }
if ($linkIntent -ne "none") { $moduleNeed += "memory_link_ledger" }
if (($externalNeed.Count -gt 0) -and ($externalNeed[0] -ne "none")) { $moduleNeed += "external_research_gate" }
if ($claimRisk -ne "none") { $moduleNeed += "claim_schema_verifier" }
if (($risk -eq "R5") -or ($classificationConfidence -eq "low")) { $moduleNeed += "runtime_gate" }
if ($moduleNeed.Count -eq 0) { $moduleNeed += "none" }
$moduleNeed = @($moduleNeed | Select-Object -Unique)

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
  skill_lifecycle_profile = $skillLifecycleProfile
  memory_need = $memoryNeed
  hybrid_retrieval_profile = $hybridRetrievalProfile
  memory_mode = $memoryMode
  memory_write_profile = $memoryWriteProfile
  memory_lane = $memoryLane
  record_intent = $recordIntent
  external_need = @($externalNeed)
  claim_risk = $claimRisk
  projectization_decision = $projectizationDecision
  conversation_memory_decision = $conversationMemoryDecision
  link_intent = $linkIntent
  receipt_profile = $receiptProfile
  projectization_signals = @($projectizationSignals)
  conversation_signals = @(@($conversationExplicitHits) + @($conversationSignals) | Select-Object -Unique)
  conversation_full_lane_triggered = [bool]$conversationFullLaneTriggered
  conversation_full_lane_groups = $conversationFullLaneGroups
  required_gates = @($requiredGates | Select-Object -Unique)
}

$compactReceipt = [ordered]@{
  task_type = $risk
  risk_level = $risk
  required_gates = @($requiredGates | Select-Object -Unique)
  skill_lifecycle_profile = $skillLifecycleProfile
  memory_mode = $memoryMode
  hybrid_retrieval_profile = $hybridRetrievalProfile
  memory_write_profile = $memoryWriteProfile
  memory_lane = $memoryLane
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
  skill_lifecycle_profile = $skillLifecycleProfile
  memory_need = $memoryNeed
  hybrid_retrieval_profile = $hybridRetrievalProfile
  memory_mode = $memoryMode
  memory_write_profile = $memoryWriteProfile
  memory_lane = $memoryLane
  record_intent = $recordIntent
  external_need = @($externalNeed)
  claim_risk = $claimRisk
  projectization_decision = $projectizationDecision
  conversation_memory_decision = $conversationMemoryDecision
  link_intent = $linkIntent
  projectization_signals = @($projectizationSignals)
  conversation_signals = @(@($conversationExplicitHits) + @($conversationSignals) | Select-Object -Unique)
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
