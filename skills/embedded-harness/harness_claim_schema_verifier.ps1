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

function Normalize-ContractToken([string]$value) {
  return (([string]$value).Trim().ToLowerInvariant() -replace '[\s-]+', '_')
}

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

$contract = $policy.claim_schema_contract
$allowedSourceTypes = @((ConvertTo-Array (Get-ObjectPropertyValue $contract "allowed_source_types")) | ForEach-Object { Normalize-ContractToken $_ })
$sourceRefRequiredFor = @((ConvertTo-Array (Get-ObjectPropertyValue $contract "source_ref_required_for")) | ForEach-Object { Normalize-ContractToken $_ })
$allowedEvidenceBoundaries = @((ConvertTo-Array (Get-ObjectPropertyValue $contract "evidence_boundary_enum")) | ForEach-Object { Normalize-ContractToken $_ })
$strongEvidenceBoundaries = @((ConvertTo-Array (Get-ObjectPropertyValue $contract "strong_claim_evidence_boundaries")) | ForEach-Object { Normalize-ContractToken $_ })

foreach ($claim in $claims) {
  foreach ($field in @("claim_type","source_type","evidence_boundary")) {
    if (-not ($claim.PSObject.Properties.Name -contains $field) -or [string]::IsNullOrWhiteSpace([string]$claim.$field)) {
      $issues += "missing_$field"
    }
  }

  $sourceType = Normalize-ContractToken ([string]$claim.source_type)
  $evidenceBoundary = Normalize-ContractToken ([string]$claim.evidence_boundary)

  if (($allowedSourceTypes.Count -gt 0) -and ($allowedSourceTypes -notcontains $sourceType)) {
    $issues += "unsupported_source_type:$($claim.source_type)"
  }
  if (($allowedEvidenceBoundaries.Count -gt 0) -and ($allowedEvidenceBoundaries -notcontains $evidenceBoundary)) {
    $issues += "unsupported_evidence_boundary:$($claim.evidence_boundary)"
  }
  if (($sourceRefRequiredFor -contains $sourceType) -and (-not ($claim.PSObject.Properties.Name -contains "source_ref") -or [string]::IsNullOrWhiteSpace([string]$claim.source_ref))) {
    $issues += "missing_source_ref_for_$($claim.source_type)"
  }
}

if ($FinalText) {
  foreach ($phrase in $policy.blocked_claim_phrases_without_schema) {
    if ($FinalText -match [regex]::Escape($phrase)) {
      if ($claims.Count -eq 0) {
        $issues += "blocked_claim_phrase_without_schema:$phrase"
        continue
      }
      $hasStrongEvidence = $false
      foreach ($claim in $claims) {
        $boundary = Normalize-ContractToken ([string]$claim.evidence_boundary)
        if ($strongEvidenceBoundaries -contains $boundary) {
          $hasStrongEvidence = $true
          break
        }
      }
      if (-not $hasStrongEvidence) {
        $issues += "insufficient_evidence_boundary_for_strong_phrase:$phrase"
      }
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
  rule = "schema enum and evidence-boundary check only; no extra LLM judgment"
}

$json = $result | ConvertTo-Json -Depth 20
if ($OutputPath) {
  $dir = Split-Path -Parent $OutputPath
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
}
$json
if ($status -eq "blocked") { exit 2 }
