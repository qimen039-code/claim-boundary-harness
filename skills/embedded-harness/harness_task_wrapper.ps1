param(
  [string]$TaskText,
  [string]$CommandPath,
  [string[]]$CommandArgs = @(),
  [string]$Cwd = (Get-Location).Path,
  [string]$ConstitutionPath = "",
  [switch]$HumanConfirmed,
  [switch]$BoundaryReviewed,
  [switch]$ConstitutionReviewed
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($TaskText)) {
  throw "TaskText is required."
}
if ([string]::IsNullOrWhiteSpace($CommandPath)) {
  throw "CommandPath is required."
}

$toolInput = [ordered]@{
  command = (($CommandPath, $CommandArgs) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join " "
} | ConvertTo-Json -Depth 5

$gateArgs = @{
  Stage = "pre_task"
  TaskText = $TaskText
  Cwd = $Cwd
  ToolName = "wrapped_command"
  ToolInputJson = $toolInput
  ConstitutionPath = $ConstitutionPath
}
if ($HumanConfirmed) { $gateArgs.HumanConfirmed = $true }
if ($BoundaryReviewed) { $gateArgs.BoundaryReviewed = $true }
if ($ConstitutionReviewed) { $gateArgs.ConstitutionReviewed = $true }

$gateOutput = & (Join-Path $PSScriptRoot "harness_runtime_enforcer.ps1") @gateArgs
$gateExit = $LASTEXITCODE
$gateOutput | Out-Host
if ($gateExit -ne 0) {
  exit $gateExit
}

Push-Location -LiteralPath $Cwd
try {
  & $CommandPath @CommandArgs
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
