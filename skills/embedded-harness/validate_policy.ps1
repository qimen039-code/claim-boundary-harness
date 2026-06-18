param(
  [string]$PolicyPath = (Join-Path $PSScriptRoot "embedded_harness_policy.json"),
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$issues = @()
$policy = $null

function ConvertTo-Array($value) {
  if ($null -eq $value) { return @() }
  if ($value -is [System.Array]) { return @($value) }
  return @($value)
}

function Add-Issue([string]$issue) {
  $script:issues += $issue
}

try {
  if (-not (Test-Path -LiteralPath $PolicyPath)) {
    Add-Issue "policy_file_missing"
  } else {
    $policy = Get-Content -LiteralPath $PolicyPath -Raw | ConvertFrom-Json
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
}

$status = if ($issues.Count -gt 0) { "blocked" } else { "pass" }
$result = [ordered]@{
  ts = (Get-Date).ToString("o")
  phase = "validate_policy"
  status = $status
  policy_path = $PolicyPath
  issues = @($issues | Select-Object -Unique)
  rule = "lightweight parse and shape check only; not a full JSON Schema validator"
}

$json = $result | ConvertTo-Json -Depth 20
if ($OutputPath) {
  $dir = Split-Path -Parent $OutputPath
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
}
$json
if ($status -eq "blocked") { exit 2 }
