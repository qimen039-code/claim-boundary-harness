param(
  [ValidateSet("pre_tool", "post_tool")]
  [string]$Stage = "pre_tool",
  [string]$TaskText = "",
  [string]$Cwd = (Get-Location).Path,
  [string]$ToolName = "",
  [string]$ToolInputJson = "",
  [string]$ConstitutionPath = "",
  [string]$OutputPath = "",
  [switch]$HumanConfirmed,
  [switch]$BoundaryReviewed,
  [switch]$ConstitutionReviewed
)

$ErrorActionPreference = "Stop"

$argsForGate = @{
  Stage = $Stage
  TaskText = $TaskText
  Cwd = $Cwd
  ToolName = $ToolName
  ToolInputJson = $ToolInputJson
  ConstitutionPath = $ConstitutionPath
  OutputPath = $OutputPath
}
if ($HumanConfirmed) { $argsForGate.HumanConfirmed = $true }
if ($BoundaryReviewed) { $argsForGate.BoundaryReviewed = $true }
if ($ConstitutionReviewed) { $argsForGate.ConstitutionReviewed = $true }

$gateOutput = & (Join-Path $PSScriptRoot "harness_runtime_enforcer.ps1") @argsForGate
$gateExit = $LASTEXITCODE
$gateOutput
if ($gateExit -ne 0) {
  exit $gateExit
}
