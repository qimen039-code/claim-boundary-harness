param(
  [string]$ProjectLane = "PROJECTLESS",
  [string]$RequestedPath = "",
  [switch]$CrossReferenceAllow,
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$policy = Get-Content -LiteralPath (Join-Path $PSScriptRoot "embedded_harness_policy.json") -Raw | ConvertFrom-Json

$allowedRoots = @()
if ($policy.memory_roots.PSObject.Properties.Name -contains $ProjectLane) {
  $allowedRoots = @($policy.memory_roots.$ProjectLane)
}

function ConvertTo-Array($value) {
  if ($null -eq $value) { return @() }
  if ($value -is [System.Array]) { return @($value) }
  return @($value)
}

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


