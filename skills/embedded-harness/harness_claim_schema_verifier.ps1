param(
  [string]$ClaimJson = "",
  [string]$ClaimFile = "",
  [string]$FinalText = "",
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$policy = Get-Content -LiteralPath (Join-Path $PSScriptRoot "embedded_harness_policy.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$issues = @()
$claims = @()

if ($ClaimFile) {
  $ClaimJson = Get-Content -LiteralPath $ClaimFile -Raw
}

if ($ClaimJson) {
  try {
    $parsed = $ClaimJson | ConvertFrom-Json
    if ($parsed -is [array]) {
      $claims = @($parsed)
    } else {
      $claims = @($parsed)
    }
  } catch {
    $issues += "claim_json_parse_failed"
  }
}

foreach ($claim in $claims) {
  foreach ($field in @("claim_type","source_type","evidence_boundary")) {
    if (-not ($claim.PSObject.Properties.Name -contains $field) -or [string]::IsNullOrWhiteSpace([string]$claim.$field)) {
      $issues += "missing_$field"
    }
  }
  if ($claim.source_type -in @("external_retrieval","memory_capsule_ref") -and (-not ($claim.PSObject.Properties.Name -contains "source_ref") -or [string]::IsNullOrWhiteSpace([string]$claim.source_ref))) {
    $issues += "missing_source_ref_for_$($claim.source_type)"
  }
}

if ($FinalText) {
  foreach ($phrase in $policy.blocked_claim_phrases_without_schema) {
    if ($FinalText -match [regex]::Escape($phrase) -and $claims.Count -eq 0) {
      $issues += "blocked_claim_phrase_without_schema:$phrase"
    }
  }
}

$status = if ($issues.Count -gt 0) { "blocked" } else { "pass" }
$result = [ordered]@{
  ts = (Get-Date).ToString("o")
  phase = "claim_schema_verifier"
  status = $status
  claims_checked = $claims.Count
  issues = @($issues | Select-Object -Unique)
  rule = "schema completeness check only; no extra LLM judgment"
}

$json = $result | ConvertTo-Json -Depth 20
if ($OutputPath) {
  $dir = Split-Path -Parent $OutputPath
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
}
$json
if ($status -eq "blocked") { exit 2 }
