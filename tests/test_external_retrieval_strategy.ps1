$ErrorActionPreference = "Stop"
$root = Join-Path (Split-Path -Parent $PSScriptRoot) "skills\embedded-harness"
$routeCwd = Join-Path ([System.IO.Path]::GetTempPath()) "cbh-public-external-retrieval-fixture"

function Assert-True([string]$Name, [bool]$Condition) {
  if (-not $Condition) {
    throw "assertion failed: $Name"
  }
}

function Assert-Contains([string]$Name, $Collection, [string]$Expected) {
  if (@($Collection) -notcontains $Expected) {
    throw "assertion failed: $Name expected '$Expected'"
  }
}

function Invoke-Route([string]$TaskText) {
  return (& (Join-Path $root "harness_intake_router.ps1") -TaskText $TaskText -Cwd $routeCwd -ReceiptMode diagnostic | ConvertFrom-Json)
}

function Invoke-ExternalGate([string]$TaskText, [string]$AttemptJson = "", [string]$ClaimText = "") {
  return (& (Join-Path $root "harness_external_research_gate.ps1") -TaskText $TaskText -ClaimText $ClaimText -AttemptJson $AttemptJson | ConvertFrom-Json)
}

$projectTask = '搜索 GitHub 开源项目 "Claim Boundary Harness"'
$projectRoute = Invoke-Route $projectTask
$projectGate = Invoke-ExternalGate $projectTask
Assert-True "project exact route is R4" ($projectRoute.risk_level -eq "R4")
Assert-True "project exact route needs external research" ([bool]$projectRoute.needs_external_research)
Assert-True "project exact route is not a patch" ($projectRoute.edit_operation_profile -ne "in_place_patch")
Assert-Contains "project exact route gate" $projectRoute.required_gates "exact_anchor_preservation_gate"
Assert-Contains "project exact route action" $projectRoute.action_binding_ids "perform_external_research_route"
Assert-True "project name is preserved" (@($projectGate.external_retrieval_receipt.exact_anchors | Where-Object raw_text -eq "Claim Boundary Harness").Count -eq 1)
Assert-True "project original query preserves Unicode" (-not $projectGate.external_retrieval_receipt.original_query.Contains([char]0xFFFD))
Assert-True "project anchor preservation passes" ($projectGate.external_retrieval_receipt.anchor_preservation_status -eq "pass")

$slug = "qimen039-code/claim-boundary-harness"
$slugTask = "搜索 GitHub 仓库 $slug"
$slugRoute = Invoke-Route $slugTask
$slugGate = Invoke-ExternalGate $slugTask
Assert-True "slug route is R4" ($slugRoute.risk_level -eq "R4")
Assert-True "slug route is not a patch" ($slugRoute.edit_operation_profile -ne "in_place_patch")
Assert-Contains "slug route web mode" $slugRoute.external_need "general_web_cross_check"
Assert-Contains "slug route GitHub mode" $slugRoute.external_need "github_open_source_repository_search"
Assert-True "slug is preserved" (@($slugGate.external_retrieval_receipt.exact_anchors | Where-Object raw_text -eq $slug).Count -eq 1)
Assert-True "slug has source-native fallback" (@($slugGate.external_retrieval_receipt.query_plan | Where-Object query_text -eq "repo:$slug").Count -eq 1)
Assert-True "slug has direct URL verification" (@($slugGate.external_retrieval_receipt.query_plan | Where-Object direct_url -eq "https://github.com/$slug").Count -ge 1)

$featureTask = "按自然搜索查找能做 claim boundary、evidence verification、memory continuity、risk routing 的开源 AI 框架"
$featureRoute = Invoke-Route $featureTask
$featureGate = Invoke-ExternalGate $featureTask
Assert-True "feature route is R4" ($featureRoute.risk_level -eq "R4")
Assert-Contains "feature route web mode" $featureRoute.external_need "general_web_cross_check"
Assert-Contains "feature route GitHub mode" $featureRoute.external_need "github_open_source_repository_search"
Assert-True "feature wording does not request local memory" ($featureRoute.memory_need -eq "none")
Assert-True "feature route does not retrieve correction memory" (@($featureRoute.action_binding_ids) -notcontains "retrieve_matching_memory")
Assert-True "feature route does not open correction lifecycle" ($featureRoute.correction_lifecycle_profile -eq "none")
Assert-True "feature plan is facet coverage" ($featureGate.external_retrieval_receipt.retrieval_profile -eq "facet_coverage")

$localTask = "只在本地搜索 Claim Boundary Harness"
$localRoute = Invoke-Route $localTask
$localGate = Invoke-ExternalGate $localTask
Assert-True "local-only search is not external" (-not [bool]$localRoute.needs_external_research)
Assert-True "local-only route has no external action" (@($localRoute.action_binding_ids) -notcontains "perform_external_research_route")
Assert-True "local-only gate is not requested" ($localGate.external_retrieval_receipt.coverage_status -eq "not_requested")

$attempt = [ordered]@{
  query_id = "q-001"
  mode = "general_web_cross_check"
  provider = "web"
  provider_status = "ok"
  result_count = 10
  exact_anchor_hits = @()
  source_read = $false
} | ConvertTo-Json -Compress
$fallbackGate = Invoke-ExternalGate $slugTask $attempt
Assert-True "provider miss requires fallback" ($fallbackGate.external_retrieval_receipt.coverage_status -eq "fallback_required")
Assert-True "fallback selects GitHub native" ($fallbackGate.external_retrieval_receipt.fallback_state.next_mode -eq "github_open_source_repository_search")
Assert-True "provider miss is not absence" ($fallbackGate.external_retrieval_receipt.negative_evidence_boundary -match "never proof of absence")

$doiGate = Invoke-ExternalGate "核对 DOI 10.1145/290941.291025"
Assert-True "DOI typed identifier activates external retrieval" ([bool]$doiGate.needs_external_research)
Assert-True "DOI uses resolver" (@($doiGate.external_retrieval_receipt.query_plan | Where-Object direct_url -eq "https://doi.org/10.1145/290941.291025").Count -ge 1)

$hfTask = "查找 Hugging Face 模型 meta-llama/Llama-3.1-8B-Instruct"
$hfRoute = Invoke-Route $hfTask
$hfGate = Invoke-ExternalGate $hfTask
Assert-True "HF route activates" ([bool]$hfRoute.needs_external_research)
Assert-True "HF id is typed" (@($hfGate.external_retrieval_receipt.exact_anchors | Where-Object { $_.type -eq "model_or_dataset_id" -and $_.provider_hint -eq "huggingface" }).Count -eq 1)
Assert-True "HF direct URL exists" (@($hfGate.external_retrieval_receipt.query_plan | Where-Object direct_url -eq "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct").Count -ge 1)
Assert-True "HF does not get GitHub URL" (@($hfGate.external_retrieval_receipt.query_plan | Where-Object { [string]$_.direct_url -match "github\.com" }).Count -eq 0)

$unknownTask = "搜索 acme/widget"
$unknownRoute = Invoke-Route $unknownTask
$unknownGate = Invoke-ExternalGate $unknownTask
Assert-True "unknown namespace does not request GitHub mode" (@($unknownRoute.external_need) -notcontains "github_open_source_repository_search")
Assert-True "unknown namespace uses capability discovery" (@($unknownGate.external_retrieval_receipt.source_capability_candidates | Where-Object source_route_id -eq "namespace_discovery").Count -eq 1)
Assert-True "unknown namespace has no guessed direct URL" (@($unknownGate.external_retrieval_receipt.query_plan | Where-Object direct_url).Count -eq 0)

$claimOnlyDoi = Invoke-ExternalGate "查找论文" "" "候选 DOI 10.1145/290941.291025"
Assert-True "claim text participates in anchor extraction" (@($claimOnlyDoi.external_retrieval_receipt.exact_anchors | Where-Object type -eq "doi").Count -eq 1)
Assert-True "claim text survives UTF-8 transport" (-not $claimOnlyDoi.external_retrieval_receipt.original_query.Contains([char]0xFFFD))

$currentRoleTask = "Sam Altman 现在担任什么职务？"
$currentRoleRoute = Invoke-Route $currentRoleTask
$currentRoleGate = Invoke-ExternalGate $currentRoleTask
Assert-True "Chinese currentness activates router" ([bool]$currentRoleRoute.needs_external_research)
Assert-True "Chinese currentness activates gate" ([bool]$currentRoleGate.needs_external_research)
Assert-Contains "Chinese currentness selects official mode" $currentRoleGate.recommended_search_modes "official_authority_source_search"

[pscustomobject]@{
  status = "pass"
  assertions = 42
  real_failure_cases = @(
    "quoted_project_name",
    "owner_repo_slug",
    "natural_feature_search",
    "provider_miss_then_native_fallback",
    "local_only_exclusion",
    "doi_native_resolver",
    "huggingface_not_github",
    "unknown_namespace_capability_discovery",
    "claim_text_anchor_transport",
    "currentness_without_search_verb"
  )
} | ConvertTo-Json -Depth 6
