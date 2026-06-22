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

function Get-TargetSurface() {
  $rules = $policy.router_decision_contract.target_surface_trigger_rules
  if ($null -ne $rules) {
    foreach ($name in @("git_action", "tool_call", "adapter", "public_docs", "conversation_memory", "private_rule", "local_harness", "skill_matrix", "project_memory")) {
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
if ((Get-MatchedTriggers $pairedMemoryTriggers).Count -gt 0) {
  $memoryNeed = "paired_err_sol"
} elseif ($explicitMemoryNeed) {
  $memoryNeed = "index_only"
} else {
  $memoryNeed = "none"
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
$projectizationThreshold = 3
if ($null -ne $policy.router_decision_contract.projectization_threshold) {
  $projectizationThreshold = [int]$policy.router_decision_contract.projectization_threshold
}
$conversationThreshold = 2
if ($null -ne $policy.router_decision_contract.conversation_memory_threshold) {
  $conversationThreshold = [int]$policy.router_decision_contract.conversation_memory_threshold
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
  } elseif ((-not $readOnlyMemoryAuditIntent) -and ($projectizationDecision -eq "not_project") -and ($conversationSignals.Count -ge $conversationThreshold)) {
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
  $conversationMemoryDecision = "read_referenced_conversation"
}

if ($commonErrorHits.Count -gt 0) {
  $memoryNeed = "common_error_corpus"
} elseif (($explicitRecordHits.Count -gt 0) -and ($memoryNeed -eq "none")) {
  $memoryNeed = "paired_err_sol"
}

$recordIntent = "no_record"
if ($explicitRecordHits.Count -gt 0) {
  $recordIntent = "explicit_user_request"
} elseif ($commonErrorHits.Count -gt 0) {
  $recordIntent = "inferred_reusable_error"
} elseif ($conversationMemoryDecision -eq "create_or_update_current_conversation") {
  if ($conversationExplicitHits.Count -gt 0) {
    $recordIntent = "explicit_conversation_memory_request"
  } else {
    $recordIntent = "conversation_checkpoint"
  }
} elseif ($conversationMemoryDecision -eq "checkpoint_candidate") {
  $recordIntent = "conversation_checkpoint"
} elseif ($projectizationDecision -eq "emergent_project_candidate") {
  $recordIntent = "projectization_review"
} elseif ($linkIntent -in @("merge_memories_explicit", "archive_or_seal_memory")) {
  $recordIntent = "explicit_cross_conversation_update"
} elseif ($linkIntent -ne "none") {
  $recordIntent = "conversation_link_review"
}

if (($linkIntent -ne "none") -and ($memoryNeed -eq "none")) {
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
} elseif ($explicitRecordHits.Count -gt 0) {
  $memoryLane = "self_reflection_matrix"
} elseif ($projectLane -ne "PROJECTLESS") {
  $memoryLane = "current_project"
} elseif ($linkIntent -ne "none") {
  $memoryLane = "referenced_conversation"
} elseif (($conversationMemoryDecision -ne "none") -and ($hasActiveConversationMemoryLane -or ($conversationExplicitHits.Count -gt 0))) {
  $memoryLane = "current_conversation"
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

if (($explicitRecordHits.Count -gt 0) -or ($commonErrorHits.Count -gt 0)) {
  $requiredSkills += "troubleshooting-skill-matrix"
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
if ($requiredSkills.Count -gt 0) { $moduleNeed += "skill_matrix" }
if ($semanticAmbiguity.Count -gt 0) { $moduleNeed += "semantic_anchors" }
if ($memoryNeed -ne "none") { $moduleNeed += "memory_meta_index" }
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
  if ($targetSurface -in @("public_docs", "local_harness", "project_memory", "skill_matrix", "adapter", "private_rule")) {
    $profileReason += "governance_surface"
  }
  if ($audience -in @("public_user", "local_maintainer")) {
    $profileReason += "audience_boundary"
  }
  if ($semanticAmbiguity.Count -gt 0) {
    $profileReason += "semantic_ambiguity"
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
  memory_need = $memoryNeed
  memory_mode = $memoryMode
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
  required_gates = @($requiredGates | Select-Object -Unique)
}

$compactReceipt = [ordered]@{
  task_type = $risk
  risk_level = $risk
  required_gates = @($requiredGates | Select-Object -Unique)
  memory_mode = $memoryMode
  memory_lane = $memoryLane
  conversation_memory_decision = $conversationMemoryDecision
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
  memory_need = $memoryNeed
  memory_mode = $memoryMode
  memory_lane = $memoryLane
  record_intent = $recordIntent
  external_need = @($externalNeed)
  claim_risk = $claimRisk
  projectization_decision = $projectizationDecision
  conversation_memory_decision = $conversationMemoryDecision
  link_intent = $linkIntent
  projectization_signals = @($projectizationSignals)
  conversation_signals = @(@($conversationExplicitHits) + @($conversationSignals) | Select-Object -Unique)
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



