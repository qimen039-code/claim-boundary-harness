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
  [string]$HumanConfirmationPermitPath = "",
  [string]$HumanConfirmationPermitJson = "",
  [string]$HumanConfirmationPermitUseLedgerPath = "",
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
  if ($Object -is [System.Collections.IDictionary]) {
    if ($Object.Contains($Name)) { return $Object[$Name] }
    return $null
  }
  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property) { return $null }
  return $property.Value
}

function Set-ObjectProperty($Object, [string]$Name, $Value) {
  if ($null -eq $Object) { return }
  if ($Object -is [System.Collections.IDictionary]) {
    $Object[$Name] = $Value
    return
  }
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

function Get-Sha256Hex([string]$text) {
  $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$text)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    return (($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") }) -join "")
  } finally {
    $sha.Dispose()
  }
}

function Read-HumanConfirmationPermit([string]$path, [string]$jsonText) {
  if (-not [string]::IsNullOrWhiteSpace($jsonText)) {
    return $jsonText | ConvertFrom-Json
  }
  if (-not [string]::IsNullOrWhiteSpace($path)) {
    if (-not (Test-Path -LiteralPath $path)) {
      throw "permit_path_not_found"
    }
    return Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
  }
  return $null
}

function Get-HumanConfirmationPermitUseLedgerPath([string]$path) {
  if (-not [string]::IsNullOrWhiteSpace($path)) {
    return $path
  }
  if (-not [string]::IsNullOrWhiteSpace($env:CBH_R5_PERMIT_USE_LEDGER)) {
    return $env:CBH_R5_PERMIT_USE_LEDGER
  }
  $base = $env:LOCALAPPDATA
  if ([string]::IsNullOrWhiteSpace($base)) {
    $base = $env:TEMP
  }
  if ([string]::IsNullOrWhiteSpace($base)) {
    $base = [System.IO.Path]::GetTempPath()
  }
  return (Join-Path (Join-Path $base "codex-embedded-harness") "r5_permit_use_ledger.jsonl")
}

function Get-HumanConfirmationPermitConsumeKey([string]$permitId, [string]$taskHash, [string]$toolHash) {
  return Get-Sha256Hex "$permitId`n$taskHash`n$toolHash"
}

function Test-HumanConfirmationPermitAlreadyUsed([string]$ledgerPath, [string]$consumeKey) {
  if ([string]::IsNullOrWhiteSpace($ledgerPath) -or [string]::IsNullOrWhiteSpace($consumeKey)) {
    return $false
  }
  if (-not (Test-Path -LiteralPath $ledgerPath)) {
    return $false
  }
  foreach ($line in (Get-Content -LiteralPath $ledgerPath -Encoding UTF8)) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    try {
      $record = $line | ConvertFrom-Json
      if ([string](Get-ObjectPropertyValue $record "consume_key") -eq $consumeKey) {
        return $true
      }
    } catch {
      continue
    }
  }
  return $false
}

function Add-HumanConfirmationPermitUse([string]$ledgerPath, $record) {
  if ([string]::IsNullOrWhiteSpace($ledgerPath)) {
    return
  }
  $dir = Split-Path -Parent $ledgerPath
  if (-not [string]::IsNullOrWhiteSpace($dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
  $json = $record | ConvertTo-Json -Compress -Depth 10
  Add-Content -LiteralPath $ledgerPath -Value $json -Encoding UTF8
}

function Test-HumanConfirmationPermit(
  [string]$path,
  [string]$jsonText,
  [string]$useLedgerPath,
  [string]$taskText,
  [string]$toolText,
  $policy
) {
  $expectedTaskHash = Get-Sha256Hex $taskText
  $expectedToolHash = Get-Sha256Hex $toolText
  $result = [ordered]@{
    status = "missing"
    permit_id = $null
    issues = @()
    expected_task_sha256 = $expectedTaskHash
    expected_tool_sha256 = $expectedToolHash
    consume_key = $null
    use_ledger_path = $null
    consumed = $false
    pending_consume = $false
    rule = "short-lived single-event scoped permit only; natural-language approval is not sufficient; a concrete tool-event permit is recorded as used before the caller proceeds"
  }
  if ([string]::IsNullOrWhiteSpace($path) -and [string]::IsNullOrWhiteSpace($jsonText)) {
    return $result
  }

  $config = Get-ObjectPropertyValue $policy.runtime_enforcement "human_confirmation_permit"
  if (($null -ne $config) -and ($false -eq [bool](Get-ObjectPropertyValue $config "enabled"))) {
    $result.status = "blocked"
    $result.issues = @("permit_disabled_by_policy")
    return $result
  }

  $issues = @()
  $permit = $null
  try {
    $permit = Read-HumanConfirmationPermit $path $jsonText
  } catch {
    $issues += "permit_parse_failed:$($_.Exception.Message)"
  }
  if ($null -eq $permit) {
    if ($issues.Count -eq 0) { $issues += "permit_missing" }
  } else {
    $result.permit_id = Get-ObjectPropertyValue $permit "permit_id"
    if ([string](Get-ObjectPropertyValue $permit "schema") -ne "cbh.r5_human_confirmation_permit.v1") {
      $issues += "unsupported_permit_schema"
    }
    if ([string](Get-ObjectPropertyValue $permit "status") -ne "active") {
      $issues += "permit_not_active"
    }
    if ([string](Get-ObjectPropertyValue $permit "confirmed_by") -ne "human") {
      $issues += "permit_not_human_confirmed"
    }
    if ([string](Get-ObjectPropertyValue $permit "risk_level") -ne "R5") {
      $issues += "permit_not_r5_scoped"
    }
    if ([string](Get-ObjectPropertyValue $permit "scope") -ne "single_event") {
      $issues += "permit_not_single_event_scoped"
    }
    if ([string](Get-ObjectPropertyValue $permit "task_sha256") -ne $expectedTaskHash) {
      $issues += "task_hash_mismatch"
    }
    if (-not [string]::IsNullOrWhiteSpace($toolText) -and [string](Get-ObjectPropertyValue $permit "tool_sha256") -ne $expectedToolHash) {
      $issues += "tool_hash_mismatch"
    }
    $expiresText = [string](Get-ObjectPropertyValue $permit "expires_at_utc")
    $expiresAt = [datetimeoffset]::MinValue
    if ([string]::IsNullOrWhiteSpace($expiresText) -or -not [datetimeoffset]::TryParse($expiresText, [ref]$expiresAt)) {
      $issues += "permit_expiry_missing_or_invalid"
    } elseif ($expiresAt.UtcDateTime -lt (Get-Date).ToUniversalTime()) {
      $issues += "permit_expired"
    }
    $consumeOnPass = $true
    if (($null -ne $config) -and ($false -eq [bool](Get-ObjectPropertyValue $config "consume_on_pass"))) {
      $consumeOnPass = $false
    }
    $consumeRequiresToolText = $true
    if (($null -ne $config) -and ($false -eq [bool](Get-ObjectPropertyValue $config "consume_requires_tool_text"))) {
      $consumeRequiresToolText = $false
    }
    if (($issues.Count -eq 0) -and $consumeOnPass -and ((-not $consumeRequiresToolText) -or -not [string]::IsNullOrWhiteSpace($toolText))) {
      $ledgerPath = Get-HumanConfirmationPermitUseLedgerPath $useLedgerPath
      $permitId = [string](Get-ObjectPropertyValue $permit "permit_id")
      $consumeKey = Get-HumanConfirmationPermitConsumeKey $permitId $expectedTaskHash $expectedToolHash
      $result.consume_key = $consumeKey
      $result.use_ledger_path = $ledgerPath
      if (Test-HumanConfirmationPermitAlreadyUsed $ledgerPath $consumeKey) {
        $issues += "permit_already_used"
      } else {
        $result.pending_consume = $true
      }
    }
  }
  $result.issues = @($issues | Select-Object -Unique)
  $result.status = if ($issues.Count -eq 0) { "pass" } else { "blocked" }
  return $result
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
$permitResult = Test-HumanConfirmationPermit `
  -path $HumanConfirmationPermitPath `
  -jsonText $HumanConfirmationPermitJson `
  -useLedgerPath $HumanConfirmationPermitUseLedgerPath `
  -taskText $taskTextForRoute `
  -toolText $toolText `
  -policy $policy
$effectiveHumanConfirmed = ([bool]$HumanConfirmed) -or ([string]$permitResult.status -eq "pass")

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
$preExecutionStage = (($Stage -eq "pre_task") -or ($Stage -eq "pre_tool"))

if ($preExecutionStage -and $route.risk_level -eq "R5" -and -not $effectiveHumanConfirmed) {
  $blocked += "human_confirmation_required_for_R5"
}

if ($preExecutionStage -and $hardHits.Count -gt 0 -and -not $effectiveHumanConfirmed) {
  $blocked += "tool_call_requires_human_confirmation"
}

if ($preExecutionStage -and $route.fallback_model_judgment_recommended -and -not $BoundaryReviewed) {
  $blocked += "boundary_review_required_for_low_confidence_route"
}

$linkRequiredIntents = ConvertTo-Array $policy.conversation_linking_contract.link_required_intents
$linkIntent = [string]$route.link_intent
if ($preExecutionStage -and ($linkRequiredIntents -contains $linkIntent) -and -not $ConversationLinkResolved) {
  $reason = [string]$policy.conversation_linking_contract.unresolved_block_reason
  if ([string]::IsNullOrWhiteSpace($reason)) { $reason = "conversation_link_decision_required" }
  $blocked += $reason
}

if ($preExecutionStage -and ($route.risk_level -ne "R0") -and [string]::IsNullOrWhiteSpace($resolvedConstitution) -and -not $ConstitutionReviewed) {
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

if (($Stage -eq "pre_tool") -and ($blocked.Count -eq 0) -and ([bool](Get-ObjectPropertyValue $permitResult "pending_consume"))) {
  try {
    Add-HumanConfirmationPermitUse ([string](Get-ObjectPropertyValue $permitResult "use_ledger_path")) ([ordered]@{
      schema = "cbh.r5_human_confirmation_permit_use.v1"
      permit_id = [string](Get-ObjectPropertyValue $permitResult "permit_id")
      consume_key = [string](Get-ObjectPropertyValue $permitResult "consume_key")
      task_sha256 = [string](Get-ObjectPropertyValue $permitResult "expected_task_sha256")
      tool_sha256 = [string](Get-ObjectPropertyValue $permitResult "expected_tool_sha256")
      used_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    })
    Set-ObjectProperty $permitResult "consumed" $true
  } catch {
    $blocked += "human_confirmation_permit_consume_failed"
    $permitIssues = @((ConvertTo-Array (Get-ObjectPropertyValue $permitResult "issues")) + "permit_use_ledger_write_failed:$($_.Exception.Message)")
    Set-ObjectProperty $permitResult "issues" @($permitIssues | Select-Object -Unique)
    Set-ObjectProperty $permitResult "status" "blocked"
    $effectiveHumanConfirmed = $false
  }
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
  human_confirmed = [bool]$HumanConfirmed
  effective_human_confirmed = [bool]$effectiveHumanConfirmed
  human_confirmation_permit = $permitResult
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
