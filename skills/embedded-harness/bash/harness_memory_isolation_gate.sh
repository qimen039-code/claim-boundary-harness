#!/usr/bin/env bash
set -euo pipefail

PROJECT_LANE="PROJECTLESS"
REQUESTED_PATH=""
CROSS_REFERENCE_ALLOW=false
OUTPUT_PATH=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
POLICY_PATH="$(cd "$SCRIPT_DIR/.." && pwd -P)/embedded_harness_policy.json"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project-lane|-ProjectLane) PROJECT_LANE="${2:-}"; shift 2 ;;
    --requested-path|-RequestedPath) REQUESTED_PATH="${2:-}"; shift 2 ;;
    --cross-reference-allow|-CrossReferenceAllow) CROSS_REFERENCE_ALLOW=true; shift ;;
    --output|-OutputPath) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --policy|-PolicyPath) POLICY_PATH="${2:-}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if ! command -v jq >/dev/null 2>&1; then
  echo '{"phase":"memory_isolation_gate","status":"blocked","issues":["jq_missing"]}'
  exit 1
fi

json_array() {
  if [ "$#" -eq 0 ]; then
    printf '[]'
  else
    printf '%s\n' "$@" | jq -R . | jq -s .
  fi
}

canonical_path() {
  local path_text="$1"
  if command -v realpath >/dev/null 2>&1; then
    realpath -m "$path_text" 2>/dev/null && return 0
  fi
  local dir base
  dir="$(dirname "$path_text")"
  base="$(basename "$path_text")"
  if [ -d "$dir" ]; then
    (cd -P "$dir" && printf '%s/%s\n' "$(pwd -P)" "$base")
  else
    printf '%s\n' "$path_text"
  fi
}

with_sep() {
  local path_text="${1%/}"
  printf '%s/\n' "$path_text"
}

allowed_roots=()
allowed_roots_resolved=()
while IFS= read -r root; do
  [ -z "$root" ] && continue
  allowed_roots+=("$root")
  allowed_roots_resolved+=("$(canonical_path "$root")")
done < <(jq -r --arg lane "$PROJECT_LANE" '.memory_roots[$lane] // [] | .[]' "$POLICY_PATH" | tr -d '\r')

status="pass"
reason="no requested path"
resolved_requested=""
reparse_resolved_requested=""

if [ -n "$REQUESTED_PATH" ]; then
  resolved_requested="$(canonical_path "$REQUESTED_PATH")"
  reparse_resolved_requested="$resolved_requested"
  inside=false
  requested_with_sep="$(with_sep "$resolved_requested")"

  for root in "${allowed_roots_resolved[@]}"; do
    root_with_sep="$(with_sep "$root")"
    if [[ "$requested_with_sep" == "$root_with_sep"* ]]; then
      inside=true
      break
    fi
  done

  if [ "$inside" = true ]; then
    reason="requested path is inside active project memory roots"
  elif [ "$CROSS_REFERENCE_ALLOW" = true ]; then
    status="cross_reference_allowed"
    reason="requested path is outside active lane but explicit cross-reference allow was provided"
  else
    status="blocked"
    reason="requested path is outside active project memory roots"
  fi
fi

result="$(
  jq -n \
    --arg phase "memory_isolation_gate" \
    --arg status "$status" \
    --arg project_lane "$PROJECT_LANE" \
    --arg requested_path "$REQUESTED_PATH" \
    --arg resolved_requested_path "$resolved_requested" \
    --arg reparse_resolved_requested_path "$reparse_resolved_requested" \
    --arg reason "$reason" \
    --argjson allowed_roots "$(json_array "${allowed_roots[@]}")" \
    --argjson allowed_roots_resolved "$(json_array "${allowed_roots_resolved[@]}")" \
    '{
      ts: (now | todateiso8601),
      phase: $phase,
      status: $status,
      project_lane: $project_lane,
      allowed_roots: $allowed_roots,
      allowed_roots_resolved: $allowed_roots_resolved,
      requested_path: $requested_path,
      resolved_requested_path: $resolved_requested_path,
      reparse_resolved_requested_path: $reparse_resolved_requested_path,
      reason: $reason
    }'
)"

if [ -n "$OUTPUT_PATH" ]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  printf '%s\n' "$result" > "$OUTPUT_PATH"
fi
printf '%s\n' "$result"
if [ "$status" = "blocked" ]; then
  exit 2
fi
