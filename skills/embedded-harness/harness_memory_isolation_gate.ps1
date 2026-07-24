param(
  [string]$ProjectLane = "PROJECTLESS",
  [string]$RequestedPath = "",
  [switch]$CrossReferenceAllow,
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$policy = Get-Content -LiteralPath (Join-Path $PSScriptRoot "embedded_harness_policy.json") -Raw -Encoding UTF8 | ConvertFrom-Json

function ConvertTo-Array($value) {
  if ($null -eq $value) { return @() }
  if ($value -is [System.Array]) { return @($value) }
  return @($value)
}

function Get-ObjectPropertyValue($object, [string]$name) {
  if ($null -eq $object) { return $null }
  $prop = $object.PSObject.Properties[$name]
  if ($null -eq $prop) { return $null }
  return $prop.Value
}

$allowedRoots = @(ConvertTo-Array (Get-ObjectPropertyValue (Get-ObjectPropertyValue $policy "memory_roots") $ProjectLane))
$overlayConfig = Get-ObjectPropertyValue $policy "local_project_lane_overlay"
if (($null -eq $overlayConfig) -or ((Get-ObjectPropertyValue $overlayConfig "enabled") -ne $false)) {
  $overlayEnvVar = [string](Get-ObjectPropertyValue $overlayConfig "env_var")
  if ([string]::IsNullOrWhiteSpace($overlayEnvVar)) { $overlayEnvVar = "CBH_PROJECT_LANES_FILE" }
  $overlayFilename = [string](Get-ObjectPropertyValue $overlayConfig "default_filename")
  if ([string]::IsNullOrWhiteSpace($overlayFilename)) { $overlayFilename = "embedded_harness_policy.local.json" }
  $overlayCandidates = @()
  $overlayEnvPath = [Environment]::GetEnvironmentVariable($overlayEnvVar)
  if (-not [string]::IsNullOrWhiteSpace($overlayEnvPath)) { $overlayCandidates += $overlayEnvPath }
  $overlayCandidates += (Join-Path $PSScriptRoot $overlayFilename)
  foreach ($overlayCandidate in $overlayCandidates) {
    if ([string]::IsNullOrWhiteSpace([string]$overlayCandidate) -or
        -not (Test-Path -LiteralPath $overlayCandidate -PathType Leaf)) { continue }
    $overlay = Get-Content -LiteralPath $overlayCandidate -Raw -Encoding UTF8 | ConvertFrom-Json
    $expectedSchema = [string](Get-ObjectPropertyValue $overlayConfig "schema")
    $actualSchema = [string](Get-ObjectPropertyValue $overlay "schema")
    if ((-not [string]::IsNullOrWhiteSpace($expectedSchema)) -and
        (-not [string]::IsNullOrWhiteSpace($actualSchema)) -and
        ($actualSchema -ne $expectedSchema)) { continue }
    $overlayRoots = Get-ObjectPropertyValue (Get-ObjectPropertyValue $overlay "memory_roots") $ProjectLane
    $allowedRoots += @(ConvertTo-Array $overlayRoots)
    break
  }
}
$allowedRoots = @($allowedRoots | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -Unique)

function Normalize-FullPath([string]$PathText) {
  return [System.IO.Path]::GetFullPath($PathText).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
}

function Add-TrailingSeparator([string]$PathText) {
  $trimmed = Normalize-FullPath $PathText
  return $trimmed + [System.IO.Path]::DirectorySeparatorChar
}

function Resolve-ReparsePoints([string]$PathText) {
  $full = Normalize-FullPath $PathText
  $root = [System.IO.Path]::GetPathRoot($full)
  if ([string]::IsNullOrWhiteSpace($root)) {
    return $full
  }

  $relative = $full.Substring($root.Length)
  $segments = @($relative -split '[\\/]' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  $current = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  if ([string]::IsNullOrWhiteSpace($current)) { $current = $root }

  foreach ($segment in $segments) {
    $candidate = Join-Path $current $segment
    if (Test-Path -LiteralPath $candidate) {
      $item = Get-Item -LiteralPath $candidate -Force
      if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -and $item.Target) {
        $target = @($item.Target)[0]
        if (-not [System.IO.Path]::IsPathRooted($target)) {
          $target = Join-Path (Split-Path -Parent $candidate) $target
        }
        $current = Normalize-FullPath $target
      } else {
        $current = Normalize-FullPath $candidate
      }
    } else {
      $current = Normalize-FullPath $candidate
    }
  }

  return Normalize-FullPath $current
}

function Test-PathInsideRoot([string]$PathText, [string]$RootText) {
  $pathWithSep = Add-TrailingSeparator $PathText
  $rootWithSep = Add-TrailingSeparator $RootText
  return $pathWithSep.StartsWith($rootWithSep, [System.StringComparison]::OrdinalIgnoreCase)
}

$status = "pass"
$reason = "no requested path"
$resolvedRequested = $null
$reparseResolvedRequested = $null
$allowedRootsResolved = @()

if ($RequestedPath) {
  $resolvedRequested = Normalize-FullPath $RequestedPath
  $reparseResolvedRequested = Resolve-ReparsePoints $RequestedPath

  $inside = $false
  foreach ($root in (ConvertTo-Array $allowedRoots)) {
    $rootFull = Normalize-FullPath $root
    $rootResolved = Resolve-ReparsePoints $root
    $allowedRootsResolved += $rootResolved

    $lexicalInside = Test-PathInsideRoot -PathText $resolvedRequested -RootText $rootFull
    $resolvedInside = Test-PathInsideRoot -PathText $reparseResolvedRequested -RootText $rootResolved
    if ($lexicalInside -and $resolvedInside) {
      $inside = $true
      break
    }
  }

  if ($inside) {
    $reason = "requested path is inside active project memory roots"
  } elseif ($CrossReferenceAllow) {
    $status = "cross_reference_allowed"
    $reason = "requested path is outside active lane but explicit cross-reference allow was provided"
  } else {
    $status = "blocked"
    $reason = "requested path is outside active project memory roots"
  }
}

$result = [ordered]@{
  ts = (Get-Date).ToString("o")
  phase = "memory_isolation_gate"
  status = $status
  project_lane = $ProjectLane
  allowed_roots = $allowedRoots
  allowed_roots_resolved = @($allowedRootsResolved | Select-Object -Unique)
  requested_path = $RequestedPath
  resolved_requested_path = $resolvedRequested
  reparse_resolved_requested_path = $reparseResolvedRequested
  reason = $reason
}

$json = $result | ConvertTo-Json -Depth 20
if ($OutputPath) {
  $dir = Split-Path -Parent $OutputPath
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
}
$json
if ($status -eq "blocked") { exit 2 }

