param(
  [ValidateSet("pre_task", "pre_tool", "post_tool", "final")]
  [string]$Stage = "pre_task",
  [string]$TaskText = "",
  [string]$Cwd = (Get-Location).Path,
  [string]$ToolName = "",
  [string]$ToolInputJson = "",
  [string]$ClaimJson = "",
  [string]$ConstitutionPath = "",
  [string]$OutputPath = "",
  [switch]$HumanConfirmed,
  [switch]$BoundaryReviewed,
  [switch]$ConstitutionReviewed
)

$ErrorActionPreference = "Stop"

function ConvertTo-Array($value) {
  if ($null -eq $value) { return @() }
  if ($value -is [System.Array]) { return @($value) }
  return @($value)
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

function Get-ToolText([string]$name, [string]$jsonText) {
  $parts = @($name)
  if (-not [string]::IsNullOrWhiteSpace($jsonText)) {
    try {
      $parsed = $jsonText | ConvertFrom-Json
      foreach ($prop in $parsed.PSObject.Properties) {
        if ($null -ne $prop.Value -and ($prop.Value -isnot [System.Array])) {
          $parts += [string]$prop.Value
        }
      }
    } catch {
      $parts += $jsonText
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
$policy = Get-Content -LiteralPath $policyPath -Raw | ConvertFrom-Json
$routeText = (($TaskText, $ToolName, $ToolInputJson) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join "`n"
$routeJson = & (Join-Path $PSScriptRoot "harness_intake_router.ps1") -TaskText $routeText -Cwd $Cwd
$route = $routeJson | ConvertFrom-Json

$toolText = Get-ToolText -name $ToolName -jsonText $ToolInputJson
$hardToolPatterns = @(
  '(?i)\bRemove-Item\b',
  '(?i)\brmdir\b',
  '(?i)\bdel\b',
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

if (($route.risk_level -ne "R0") -and [string]::IsNullOrWhiteSpace($resolvedConstitution) -and -not $ConstitutionReviewed) {
  $blocked += "constitution_entry_missing_or_unreviewed"
}

if ($Stage -eq "final") {
  if (-not [string]::IsNullOrWhiteSpace($ClaimJson)) {
    $claimJsonResult = & (Join-Path $PSScriptRoot "harness_claim_schema_verifier.ps1") -ClaimJson $ClaimJson
    $claimResult = $claimJsonResult | ConvertFrom-Json
    if ($claimResult.status -ne "pass") {
      $blocked += "claim_schema_verifier_blocked"
    }
  } else {
    foreach ($phrase in (ConvertTo-Array $policy.blocked_claim_phrases_without_schema)) {
      if ($TaskText -match [regex]::Escape([string]$phrase)) {
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
  tool_name = $ToolName
  tool_hard_hits = @($hardHits)
  tool_change_hits = @($changeHits)
  constitution_path = $resolvedConstitution
  blocked_reasons = @($blocked | Select-Object -Unique)
  warnings = @($warnings | Select-Object -Unique)
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
