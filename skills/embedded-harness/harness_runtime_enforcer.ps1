param(
  [ValidateSet("pre_task", "pre_tool", "post_tool", "final")]
  [string]$Stage = "pre_task",
  [string]$TaskText = "",
  [string]$OriginalTaskText = "",
  [string]$RiskLevel = "",
  [string]$Cwd = (Get-Location).Path,
  [string]$ToolName = "",
  [string]$ToolInputJson = "",
  [string]$ClaimJson = "",
  [string]$FinalText = "",
  [string]$ConstitutionPath = "",
  [string]$OutputPath = "",
  [switch]$HumanConfirmed,
  [switch]$BoundaryReviewed,
  [switch]$ConversationLinkResolved,
  [switch]$ConstitutionReviewed
)

$ErrorActionPreference = "Stop"

function ConvertTo-Array($value) {
  if ($null -eq $value) { return @() }
  if ($value -is [System.Array]) { return @($value) }
  return @($value)
}

function Get-ObjectPropertyValue($Object, [string]$Name) {
  if ($null -eq $Object) { return $null }
  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property) { return $null }
  return $property.Value
}

function Set-ObjectProperty($Object, [string]$Name, $Value) {
  if ($null -eq $Object) { return }
  if ($Object.PSObject.Properties.Name -contains $Name) {
    $Object.$Name = $Value
  } else {
    $Object | Add-Member -MemberType NoteProperty -Name $Name -Value $Value -Force
  }
}

function Add-UniqueStringArrayProperty($Object, [string]$Name, $Values) {
  if ($null -eq $Object) { return }
  $mergedInput = @()
  $mergedInput += @(ConvertTo-Array (Get-ObjectPropertyValue $Object $Name))
  $mergedInput += @(ConvertTo-Array $Values)
  $merged = @($mergedInput | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -Unique)
  Set-ObjectProperty $Object $Name $merged
}

function Get-FirstExistingPath($paths) {
  foreach ($path in (ConvertTo-Array $paths)) {
    if ([string]::IsNullOrWhiteSpace($path)) { continue }
    if (Test-Path -LiteralPath $path) {
      return (Resolve-Path -LiteralPath $path).Path
    }
  }
  return ""
}

function Get-RiskLabel([string]$text) {
  $trimmed = ([string]$text).Trim()
  if ($trimmed -match '^(?i)R[0-5]$') {
    return $trimmed.ToUpperInvariant()
  }
  return ""
}

function Get-RiskRank([string]$risk, $policy) {
  $order = @("R5","R4","R3","R2","R1","R0")
  $configured = ConvertTo-Array $policy.risk_order_high_to_low
  if ($configured.Count -gt 0) {
    $order = @($configured + @("R0") | Select-Object -Unique)
  }
  $index = [array]::IndexOf($order, $risk)
  if ($index -lt 0) { return 999 }
  return $index
}

function Get-HigherRisk([string]$left, [string]$right, $policy) {
  if ([string]::IsNullOrWhiteSpace($left)) { return $right }
  if ([string]::IsNullOrWhiteSpace($right)) { return $left }
  if ((Get-RiskRank $right $policy) -lt (Get-RiskRank $left $policy)) {
    return $right
  }
  return $left
}

function Apply-RiskOverride($route, [string]$riskLevel, $policy) {
  $risk = Get-RiskLabel $riskLevel
  if ([string]::IsNullOrWhiteSpace($risk)) { return $route }

  $current = [string](Get-ObjectPropertyValue $route "risk_level")
  if ([string]::IsNullOrWhiteSpace($current)) { $current = "R0" }
  $merged = Get-HigherRisk $current $risk $policy
  Set-ObjectProperty $route "risk_level" $merged
  Set-ObjectProperty $route "task_type" $merged
  Add-UniqueStringArrayProperty $route "triggered_risks" @($risk)

  if ($merged -eq "R5") {
    Add-UniqueStringArrayProperty $route "approval_required" @("explicit_human_confirmation")
    Add-UniqueStringArrayProperty $route "required_gates" @("runtime_gate")
  }

  foreach ($receiptName in @("routing_receipt","compact_receipt")) {
    $receipt = Get-ObjectPropertyValue $route $receiptName
    if ($null -ne $receipt) {
      Set-ObjectProperty $receipt "risk_level" $merged
      Set-ObjectProperty $receipt "task_type" $merged
      if ($merged -eq "R5") {
        Set-ObjectProperty $receipt "human_confirmation_need" $true
        Add-UniqueStringArrayProperty $receipt "required_gates" @("runtime_gate")
      }
    }
  }
  return $route
}

function Get-InputKey([string]$value) {
  return -join (([string]$value).ToLowerInvariant().ToCharArray() | Where-Object { [char]::IsLetterOrDigit($_) })
}

$commandToolNameRegex = '(?i)(bash|powershell|shell|terminal|cmd|command|exec|run)'
$commandInputKeyNames = @(
  "args",
  "arguments",
  "cmd",
  "command",
  "commandline",
  "input",
  "powershellcommand",
  "script",
  "shellcommand"
)

function ConvertTo-CompactJsonText($value) {
  try {
    return ($value | ConvertTo-Json -Depth 20 -Compress)
  } catch {
    return [string]$value
  }
}

function Test-CommandTool([string]$name, $inputObject) {
  if ($name -match $commandToolNameRegex) { return $true }
  if ($null -ne $inputObject -and $inputObject.PSObject.Properties.Count -gt 0) {
    foreach ($prop in $inputObject.PSObject.Properties) {
      if ($commandInputKeyNames -contains (Get-InputKey $prop.Name)) {
        return $true
      }
    }
  }
  return $false
}

function Get-CommandInputParts($value, [int]$depth = 0) {
  if ($depth -gt 4 -or $null -eq $value) { return @() }
  if ($value -is [string]) { return @([string]$value) }
  if ($value -is [System.Array]) {
    $parts = @()
    foreach ($item in $value) {
      $parts += Get-CommandInputParts $item ($depth + 1)
    }
    return @($parts)
  }
  if ($value.PSObject.Properties.Count -gt 0) {
    $parts = @()
    foreach ($prop in $value.PSObject.Properties) {
      if ($commandInputKeyNames -contains (Get-InputKey $prop.Name)) {
        if ($prop.Value -is [string]) {
          $parts += [string]$prop.Value
        } else {
          $parts += ConvertTo-CompactJsonText $prop.Value
        }
      } elseif ($null -ne $prop.Value -and ($prop.Value -isnot [string])) {
        $parts += Get-CommandInputParts $prop.Value ($depth + 1)
      }
    }
    return @($parts)
  }
  return @()
}

function Get-ToolText([string]$name, [string]$jsonText) {
  $parts = @()
  if (-not [string]::IsNullOrWhiteSpace($name)) {
    $parts += $name
  }
  if ([string]::IsNullOrWhiteSpace($jsonText)) {
    return ($parts -join "`n")
  }

  $parsed = $null
  $parsedOk = $false
  try {
    $parsed = $jsonText | ConvertFrom-Json
    $parsedOk = $true
  } catch {
    if ($name -match $commandToolNameRegex) {
      $parts += $jsonText
    }
    return ($parts -join "`n")
  }

  if (Test-CommandTool $name $parsed) {
    $commandParts = Get-CommandInputParts $parsed
    if ($commandParts.Count -gt 0) {
      $parts += $commandParts
    } elseif ($parsedOk -and $parsed -is [string]) {
      $parts += [string]$parsed
    }
  }
  return ($parts -join "`n")
}

function Get-PatternHits([string]$text, [string[]]$patterns) {
  $hits = @()
  foreach ($pattern in $patterns) {
    if ($text -match $pattern) {
      $hits += $pattern
    }
  }
  return @($hits | Select-Object -Unique)
}

$policyPath = Join-Path $PSScriptRoot "embedded_harness_policy.json"
$policy = Get-Content -LiteralPath $policyPath -Raw -Encoding UTF8 | ConvertFrom-Json

$toolText = Get-ToolText -name $ToolName -jsonText $ToolInputJson
$taskTextForRoute = $TaskText
if (-not [string]::IsNullOrWhiteSpace($OriginalTaskText)) {
  $taskTextForRoute = $OriginalTaskText
} elseif (-not [string]::IsNullOrWhiteSpace((Get-RiskLabel $TaskText))) {
  $taskTextForRoute = ""
}
$explicitRiskLevel = $RiskLevel
if ([string]::IsNullOrWhiteSpace($explicitRiskLevel)) {
  $explicitRiskLevel = Get-RiskLabel $TaskText
}
$routeText = (($taskTextForRoute, $toolText) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join "`n"
$routeJson = & (Join-Path $PSScriptRoot "harness_intake_router.ps1") -TaskText $routeText -Cwd $Cwd
$route = $routeJson | ConvertFrom-Json
$route = Apply-RiskOverride $route $explicitRiskLevel $policy

$hardToolPatterns = ConvertTo-Array $policy.runtime_enforcement.hard_tool_patterns
if ($hardToolPatterns.Count -eq 0) {
  $hardToolPatterns = @(
    '(?i)\bRemove-Item\b',
    '(?i)\brmdir\b',
    '(?i)\bdel\b',
    '(?i)\brm\s+-(?:[a-z]*r[a-z]*f|[a-z]*f[a-z]*r)\b',
    '(?i)\brm\s+-[^\s]*r[^\s]*\s+-[^\s]*f\b',
    '(?i)\brm\s+-[^\s]*f[^\s]*\s+-[^\s]*r\b',
    '(?i)\bgit\s+commit\b',
    '(?i)\bgit\s+push\b',
    '(?i)\bgit\s+reset\b',
    '(?i)\bgit\s+checkout\b',
    '(?i)\binstall\b',
    '(?i)\blogin\b',
    '(?i)\bpayment\b',
    '(?i)\bpermission\b',
    '(?i)\bfirewall\b',
    '(?i)\bproxy\b',
    '(?i)\bnetsh\b',
    '(?i)\bSet-ExecutionPolicy\b',
    '(?i)\blong-term memory\b',
    '(?i)\bwrite memory\b',
    '(?i)\bsensitive transfer\b'
  )
}
$changeToolPatterns = @(
  '(?i)\bapply_patch\b',
  '(?i)\bSet-Content\b',
  '(?i)\bAdd-Content\b',
  '(?i)\bMove-Item\b',
  '(?i)\bCopy-Item\b',
  '(?i)\bgit\s+add\b'
)

$hardHits = Get-PatternHits -text $toolText -patterns $hardToolPatterns
$changeHits = Get-PatternHits -text $toolText -patterns $changeToolPatterns

$homeAgents = ""
if ($env:USERPROFILE) {
  $homeAgents = Join-Path $env:USERPROFILE ".agent\AGENTS.md"
}
$constitutionCandidates = @(
  $ConstitutionPath,
  (Join-Path $Cwd "AGENTS.md"),
  $homeAgents
)
$resolvedConstitution = Get-FirstExistingPath $constitutionCandidates

$blocked = @()
$warnings = @()

if ($route.risk_level -eq "R5" -and -not $HumanConfirmed) {
  $blocked += "human_confirmation_required_for_R5"
}

if ($hardHits.Count -gt 0 -and -not $HumanConfirmed) {
  $blocked += "tool_call_requires_human_confirmation"
}

if ($route.fallback_model_judgment_recommended -and -not $BoundaryReviewed) {
  $blocked += "boundary_review_required_for_low_confidence_route"
}

$linkRequiredIntents = ConvertTo-Array $policy.conversation_linking_contract.link_required_intents
$linkIntent = [string]$route.link_intent
if ((($Stage -eq "pre_task") -or ($Stage -eq "pre_tool")) -and ($linkRequiredIntents -contains $linkIntent) -and -not $ConversationLinkResolved) {
  $reason = [string]$policy.conversation_linking_contract.unresolved_block_reason
  if ([string]::IsNullOrWhiteSpace($reason)) { $reason = "conversation_link_decision_required" }
  $blocked += $reason
}

if (($route.risk_level -ne "R0") -and [string]::IsNullOrWhiteSpace($resolvedConstitution) -and -not $ConstitutionReviewed) {
  $blocked += "constitution_entry_missing_or_unreviewed"
}

if ($Stage -eq "final") {
  if (-not [string]::IsNullOrWhiteSpace($ClaimJson)) {
    $claimJsonResult = & (Join-Path $PSScriptRoot "harness_claim_schema_verifier.ps1") -ClaimJson $ClaimJson -FinalText $FinalText
    $claimResult = $claimJsonResult | ConvertFrom-Json
    if ($claimResult.status -ne "pass") {
      $blocked += "claim_schema_verifier_blocked"
    }
  } else {
    $textToScan = $TaskText
    if (-not [string]::IsNullOrWhiteSpace($FinalText)) {
      $textToScan = $FinalText
    }
    foreach ($phrase in (ConvertTo-Array $policy.blocked_claim_phrases_without_schema)) {
      if ($textToScan -match [regex]::Escape([string]$phrase)) {
        $blocked += "claim_schema_required_for_strong_phrase"
        break
      }
    }
  }
}

if ($changeHits.Count -gt 0 -and $route.risk_level -eq "R0") {
  $warnings += "tool_looks_mutating_but_route_is_R0"
}

$status = "pass"
if ($blocked.Count -gt 0) {
  $status = "blocked"
}

$result = [ordered]@{
  ts = (Get-Date).ToString("o")
  phase = "runtime_enforcer"
  stage = $Stage
  status = $status
  cwd = $Cwd
  route = $route
  task_text_for_route = $taskTextForRoute
  explicit_risk_level = $explicitRiskLevel
  tool_name = $ToolName
  tool_hard_hits = @($hardHits)
  tool_change_hits = @($changeHits)
  conversation_link_required = ($linkRequiredIntents -contains $linkIntent)
  conversation_link_resolved = [bool]$ConversationLinkResolved
  constitution_path = $resolvedConstitution
  blocked_reasons = @($blocked | Select-Object -Unique)
  warnings = @($warnings | Select-Object -Unique)
  final_text_scanned = ($Stage -eq "final" -and (-not [string]::IsNullOrWhiteSpace($FinalText)))
  enforcement = "hard_exit_when_called_by_hook_wrapper_or_tool_proxy"
}

$json = $result | ConvertTo-Json -Depth 30
if ($OutputPath) {
  $dir = Split-Path -Parent $OutputPath
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
}
$json

if ($status -eq "blocked") {
  exit 2
}
