function ConvertTo-TriggerList($value) {
  $items = @()
  if ($null -eq $value) {
    return @()
  }
  if ($value -is [System.Array]) {
    foreach ($entry in $value) {
      $items += ConvertTo-TriggerList $entry
    }
    return @($items)
  }
  if (($value -isnot [string]) -and $value.PSObject.Properties.Count -gt 0) {
    foreach ($prop in $value.PSObject.Properties) {
      $items += ConvertTo-TriggerList $prop.Value
    }
    return @($items)
  }
  return @([string]$value)
}

function Test-EnglishTrigger([string]$text) {
  return (($text -match '^[\x20-\x7E]+$') -and ($text -match '[A-Za-z0-9]'))
}

function New-TriggerRegex([string]$text) {
  $escaped = [regex]::Escape($text)
  if (Test-EnglishTrigger $text) {
    return "(?i)(?<![A-Za-z0-9_])$escaped(?![A-Za-z0-9_])"
  }
  return $escaped
}

function Test-NegatedMatch([string]$source, [int]$index) {
  $start = [Math]::Max(0, $index - 256)
  $prefix = $source.Substring($start, $index - $start)
  if ($prefix -match "(?i)(\bdo\s+not\b|\bdon't\b|\bnever\b|\bnot\b|\bno\b)[\s\w'-]{0,128}$") {
    return $true
  }
  $shortStart = [Math]::Max(0, $index - 32)
  $shortPrefix = $source.Substring($shortStart, $index - $shortStart)
  return ($shortPrefix -match "(不需要|无需|不要|别|禁止|不)\s*$")
}

function Test-ExternalNegatedMatch([string]$source, [int]$index) {
  $start = [Math]::Max(0, $index - 256)
  $prefix = $source.Substring($start, $index - $start)
  if ($prefix -match "(?i)(\bdo\s+not\b|\bdon't\b|\bnever\b|\bnot\b|\bno\b)[\s\w'-]{0,128}$") {
    return $true
  }
  $shortStart = [Math]::Max(0, $index - 32)
  $shortPrefix = $source.Substring($shortStart, $index - $shortStart)
  return ($shortPrefix -match "(不需要|无需|不要|别|禁止|不)[^。！？\r\n]{0,24}$")
}

function Get-ExternalTriggerMatchSet([string]$source, $triggers) {
  $matched = @()
  $negated = @()
  foreach ($trigger in (ConvertTo-TriggerList $triggers)) {
    $text = [string]$trigger
    if ([string]::IsNullOrWhiteSpace($text)) {
      continue
    }
    $regex = New-TriggerRegex $text
    foreach ($hit in [regex]::Matches($source, $regex)) {
      if (Test-ExternalNegatedMatch -source $source -index $hit.Index) {
        $negated += $text
      } else {
        $matched += $text
      }
    }
  }
  return [pscustomobject]@{
    positive = @($matched | Select-Object -Unique)
    negated = @($negated | Select-Object -Unique)
  }
}

function Get-DerivedExternalSignalMatchSet([string]$source) {
  $patterns = @(
    [pscustomobject]@{ id = "date_pattern"; regex = '\b20\d{2}[-/]\d{1,2}([-/]\d{1,2})?\b' },
    [pscustomobject]@{ id = "version_pattern"; regex = '\b(v\d+\.\d+(\.\d+)?|(?:version|release|sdk|node|python|npm|package|plugin|model)\s*:?\s*v?\d+\.\d+(\.\d+)?)\b' },
    [pscustomobject]@{ id = "url_or_github_pattern"; regex = 'https?://|github\.com' },
    [pscustomobject]@{ id = "typed_external_identifier_pattern"; regex = '(?i)\bRFC\s*-?\s*\d{3,5}\b|\bCVE-\d{4}-\d{4,}\b|\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b|\barXiv\s*:\s*\d{4}\.\d{4,5}(?:v\d+)?\b|\barXiv\s+\d{4}\.\d{4,5}(?:v\d+)?\b|\b(?:ISO(?:/IEC)?|IEC|IEEE)\s+\d+(?:[-:]\d+)*(?::\d{4})?\b|(?<![A-Za-z0-9_.-])@[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*|\b(?:PyPI|npm|Hugging\s*Face)\b' },
    [pscustomobject]@{ id = "currentness_pattern"; regex = '(?i)\bnow\b|\bcurrently\b|\bpresent\s+(?:role|office|holder)\b|现在|现任|目前' }
  )
  $positive = @()
  $negated = @()
  foreach ($pattern in $patterns) {
    foreach ($hit in [regex]::Matches($source, [string]$pattern.regex)) {
      if (Test-ExternalNegatedMatch -source $source -index $hit.Index) {
        $negated += [string]$pattern.id
      } else {
        $positive += [string]$pattern.id
      }
    }
  }
  return [pscustomobject]@{
    positive = @($positive | Select-Object -Unique)
    negated = @($negated | Select-Object -Unique)
  }
}
