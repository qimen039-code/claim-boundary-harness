param(
  [string]$PolicyPath = (Join-Path $PSScriptRoot "embedded_harness_policy.json"),
  [string]$RepoRoot = "",
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$issues = @()
$warnings = @()
$policy = $null

function ConvertTo-Array($value) {
  if ($null -eq $value) { return @() }
  if ($value -is [System.Array]) { return @($value) }
  return @($value)
}

function Add-Issue([string]$issue) {
  $script:issues += $issue
}

function Add-Warning([string]$warning) {
  $script:warnings += $warning
}

function Get-RelativeDisplayPath([string]$Path, [string]$Root) {
  try {
    $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
    $resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
    if ($resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
      return $resolvedPath.Substring($resolvedRoot.Length).TrimStart('\','/')
    }
  } catch {
  }
  return $Path
}

function Get-ObjectPropertyValue($Object, [string]$Name) {
  if ($null -eq $Object) { return $null }
  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property) { return $null }
  return $property.Value
}

function Test-JsonBeliefInvariant($Node, [string]$Source, [string]$Root) {
  if ($null -eq $Node) { return }
  if ($Node -is [System.Array]) {
    foreach ($item in $Node) { Test-JsonBeliefInvariant $item $Source $Root }
    return
  }
  if ($Node -isnot [pscustomobject]) { return }

  $beliefStatus = Get-ObjectPropertyValue $Node "belief_status"
  $traceSummary = Get-ObjectPropertyValue $Node "belief_trace_summary"
  if (($null -ne $beliefStatus) -and ($null -ne $traceSummary)) {
    $currentStatus = Get-ObjectPropertyValue $traceSummary "current_status"
    $relative = Get-RelativeDisplayPath $Source $Root
    if ($null -eq $currentStatus) {
      Add-Issue "belief_trace_summary_current_status_missing:$relative"
    } elseif ([string]$currentStatus -ne [string]$beliefStatus) {
      Add-Issue "belief_trace_current_status_mismatch:${relative}:${beliefStatus}!=$currentStatus"
    }
  }

  foreach ($property in $Node.PSObject.Properties) {
    Test-JsonBeliefInvariant $property.Value $Source $Root
  }
}

function Test-TextBeliefInvariant([string]$Path, [string]$Root) {
  $relative = Get-RelativeDisplayPath $Path $Root
  $lines = Get-Content -LiteralPath $Path -Encoding UTF8
  $beliefStatus = $null
  $sawSummary = $false
  $lineNumber = 0
  foreach ($line in $lines) {
    $lineNumber += 1
    if ($line -match '^\s*belief_status:\s*`?([^`\s#]+)`?') {
      $beliefStatus = $Matches[1].Trim()
      $sawSummary = $false
      continue
    }
    if ($null -eq $beliefStatus) { continue }
    if ($line -match '^\s*belief_trace_summary:\s*') {
      $sawSummary = $true
      continue
    }
    if ($sawSummary -and ($line -match '^\s*current_status:\s*`?([^`\s#]+)`?')) {
      $currentStatus = $Matches[1].Trim()
      if ($currentStatus -ne $beliefStatus) {
        Add-Issue "belief_trace_current_status_mismatch:${relative}:${lineNumber}:${beliefStatus}!=$currentStatus"
      }
      $beliefStatus = $null
      $sawSummary = $false
    }
  }
  if (($null -ne $beliefStatus) -and $sawSummary) {
    Add-Issue "belief_trace_summary_current_status_missing:$relative"
  }
}

function Test-BeliefTraceInvariants([string]$Root) {
  if ([string]::IsNullOrWhiteSpace($Root) -or -not (Test-Path -LiteralPath $Root)) {
    return
  }
  $resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
  $textExtensions = @(".md", ".yaml", ".yml")
  $jsonExtensions = @(".json", ".jsonl")
  $scanRoots = @("docs", "examples", "templates", "skills", "AGENTS.md", "README.md")
  foreach ($entry in $scanRoots) {
    $entryPath = Join-Path $resolvedRoot $entry
    if (-not (Test-Path -LiteralPath $entryPath)) { continue }
    $files = if ((Get-Item -LiteralPath $entryPath).PSIsContainer) {
      Get-ChildItem -LiteralPath $entryPath -Recurse -File
    } else {
      @(Get-Item -LiteralPath $entryPath)
    }
    foreach ($file in $files) {
      if ($textExtensions -contains $file.Extension.ToLowerInvariant()) {
        Test-TextBeliefInvariant $file.FullName $resolvedRoot
      } elseif ($jsonExtensions -contains $file.Extension.ToLowerInvariant()) {
        try {
          if ($file.Extension.ToLowerInvariant() -eq ".jsonl") {
            foreach ($line in (Get-Content -LiteralPath $file.FullName -Encoding UTF8)) {
              if ([string]::IsNullOrWhiteSpace($line)) { continue }
              Test-JsonBeliefInvariant ($line | ConvertFrom-Json) $file.FullName $resolvedRoot
            }
          } else {
            Test-JsonBeliefInvariant ((Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8) | ConvertFrom-Json) $file.FullName $resolvedRoot
          }
        } catch {
          Add-Issue "belief_invariant_json_parse_failed:$(Get-RelativeDisplayPath $file.FullName $resolvedRoot)"
        }
      }
    }
  }
}

try {
  if (-not (Test-Path -LiteralPath $PolicyPath)) {
    Add-Issue "policy_file_missing"
  } else {
    $policy = Get-Content -LiteralPath $PolicyPath -Raw -Encoding UTF8 | ConvertFrom-Json
  }
} catch {
  Add-Issue "json_parse_failed"
}

if ($null -ne $policy) {
  $riskRules = $policy.risk_trigger_rules
  if ($null -eq $riskRules) {
    $riskRules = $policy.risk_keyword_rules
  }

  if ($null -eq $riskRules) {
    Add-Issue "risk_trigger_rules_missing"
  } else {
    foreach ($risk in @("R0","R1","R2","R3","R4","R5")) {
      if (-not ($riskRules.PSObject.Properties.Name -contains $risk)) {
        Add-Issue "risk_rule_missing:$risk"
      }
    }
  }

  $r5ContextRules = $policy.r5_context_decision_rules
  if ($null -eq $r5ContextRules) {
    Add-Issue "r5_context_decision_rules_missing"
  } else {
    foreach ($field in @("direct_action_terms","context_required_candidate_terms","always_action_candidate_terms","action_context_terms","non_action_context_terms","documentation_context_terms")) {
      $value = Get-ObjectPropertyValue $r5ContextRules $field
      if ((ConvertTo-Array $value).Count -eq 0) {
        Add-Issue "r5_context_decision_rule_empty:$field"
      }
    }
  }

  if ($null -eq $policy.memory_roots) {
    Add-Issue "memory_roots_missing"
  } else {
    $invalidPathChars = [System.IO.Path]::GetInvalidPathChars()
    foreach ($lane in $policy.memory_roots.PSObject.Properties) {
      foreach ($path in (ConvertTo-Array $lane.Value)) {
        $pathText = [string]$path
        if ([string]::IsNullOrWhiteSpace($pathText)) {
          Add-Issue "memory_root_empty:$($lane.Name)"
          continue
        }
        foreach ($char in $invalidPathChars) {
          if ($pathText.Contains([string]$char)) {
            Add-Issue "memory_root_invalid_path_char:$($lane.Name)"
            break
          }
        }
      }
    }
  }

  $routerContract = $policy.router_decision_contract
  if ($null -eq $routerContract) {
    Add-Issue "router_decision_contract_missing"
  } else {
    $fullLaneConfig = Get-ObjectPropertyValue $routerContract "conversation_memory_full_lane_triggers"
    $thresholdGroups = Get-ObjectPropertyValue $fullLaneConfig "threshold_groups"
    if ($null -eq $thresholdGroups) {
      Add-Warning "conversation_memory_full_lane_triggers_missing"
    } else {
      foreach ($group in $thresholdGroups.PSObject.Properties) {
        $threshold = Get-ObjectPropertyValue $group.Value "threshold"
        $triggers = ConvertTo-Array (Get-ObjectPropertyValue $group.Value "triggers")
        $thresholdInt = 0
        try {
          if ($null -ne $threshold) { $thresholdInt = [int]$threshold }
        } catch {
          $thresholdInt = 0
        }
        if ($thresholdInt -lt 1) {
          Add-Issue "conversation_full_lane_group_invalid_threshold:$($group.Name)"
        }
        if ($triggers.Count -eq 0) {
          Add-Issue "conversation_full_lane_group_empty_triggers:$($group.Name)"
        }
      }
    }
  }

  $runtimeEnforcement = $policy.runtime_enforcement
  if ($null -eq $runtimeEnforcement) {
    Add-Issue "runtime_enforcement_missing"
  } else {
    $permitConfig = Get-ObjectPropertyValue $runtimeEnforcement "human_confirmation_permit"
    if ($null -eq $permitConfig) {
      Add-Warning "human_confirmation_permit_missing"
    } else {
      if ((Get-ObjectPropertyValue $permitConfig "schema") -ne "cbh.r5_human_confirmation_permit.v1") {
        Add-Issue "human_confirmation_permit_schema_invalid"
      }
      if ((Get-ObjectPropertyValue $permitConfig "required_scope") -ne "single_event") {
        Add-Issue "human_confirmation_permit_scope_not_single_event"
      }
      if ($false -eq [bool](Get-ObjectPropertyValue $permitConfig "consume_on_pass")) {
        Add-Issue "human_confirmation_permit_consume_on_pass_disabled"
      }
      if ($false -eq [bool](Get-ObjectPropertyValue $permitConfig "consume_requires_tool_text")) {
        Add-Warning "human_confirmation_permit_can_consume_without_tool_text"
      }
      if ([string]::IsNullOrWhiteSpace([string](Get-ObjectPropertyValue $permitConfig "used_ledger_env_var"))) {
        Add-Issue "human_confirmation_permit_used_ledger_env_var_missing"
      }
    }
  }

  $placeholderPaths = @()
  if ($null -ne $policy.project_lanes) {
    foreach ($lane in $policy.project_lanes.PSObject.Properties) {
      if ($lane.Name -eq "EXAMPLE_PROJECT") {
        Add-Warning "template_project_lane_present:EXAMPLE_PROJECT"
      }
      foreach ($path in (ConvertTo-Array $lane.Value)) {
        if ([string]$path -like "C:\path\to\*") {
          $placeholderPaths += [string]$path
        }
      }
    }
  }
  if ($null -ne $policy.memory_roots) {
    foreach ($lane in $policy.memory_roots.PSObject.Properties) {
      foreach ($path in (ConvertTo-Array $lane.Value)) {
        if ([string]$path -like "C:\path\to\*") {
          $placeholderPaths += [string]$path
        }
      }
    }
  }
  if ($placeholderPaths.Count -gt 0) {
    Add-Warning "template_placeholder_paths_present:replace_before_production_use"
  }

  $claimContract = $policy.claim_schema_contract
  if ($null -eq $claimContract) {
    Add-Issue "claim_schema_contract_missing"
  } else {
    foreach ($field in @("allowed_source_types","source_ref_required_for","evidence_boundary_enum","strong_claim_evidence_boundaries")) {
      if ((ConvertTo-Array (Get-ObjectPropertyValue $claimContract $field)).Count -eq 0) {
        Add-Issue "claim_schema_contract_empty:$field"
      }
    }
  }
}

$repoCandidate = if ($RepoRoot) { $RepoRoot } else { Join-Path $PSScriptRoot "..\.." }
if ((Test-Path -LiteralPath (Join-Path $repoCandidate "VERSION")) -and
    (Test-Path -LiteralPath (Join-Path $repoCandidate "skills\embedded-harness\embedded_harness_policy.json"))) {
  Test-BeliefTraceInvariants $repoCandidate
}

$status = if ($issues.Count -gt 0) { "blocked" } else { "pass" }
$result = [ordered]@{
  ts = (Get-Date).ToString("o")
  phase = "validate_policy"
  status = $status
  policy_path = $PolicyPath
  issues = @($issues | Select-Object -Unique)
  warnings = @($warnings | Select-Object -Unique)
  rule = "lightweight policy parse, shape check, claim schema contract check, placeholder warnings, and belief_trace_summary.current_status invariant check when repo root is available; not a full JSON Schema validator"
}

$json = $result | ConvertTo-Json -Depth 20
if ($OutputPath) {
  $dir = Split-Path -Parent $OutputPath
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
}
$json
if ($status -eq "blocked") { exit 2 }
