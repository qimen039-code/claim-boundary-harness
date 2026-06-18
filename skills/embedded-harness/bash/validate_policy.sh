#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
POLICY_PATH="$(cd "$SCRIPT_DIR/.." && pwd -P)/embedded_harness_policy.json"
OUTPUT_PATH=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --policy|-PolicyPath) POLICY_PATH="${2:-}"; shift 2 ;;
    --output|-OutputPath) OUTPUT_PATH="${2:-}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if ! command -v jq >/dev/null 2>&1; then
  echo '{"phase":"validate_policy","status":"blocked","issues":["jq_missing"]}'
  exit 1
fi

json_array() {
  if [ "$#" -eq 0 ]; then
    printf '[]'
  else
    printf '%s\n' "$@" | jq -R . | jq -s .
  fi
}

add_unique() {
  local -n target="$1"
  local value="$2"
  local item
  [ -z "$value" ] && return 0
  for item in "${target[@]}"; do
    [ "$item" = "$value" ] && return 0
  done
  target+=("$value")
}

issues=()

if [ ! -f "$POLICY_PATH" ]; then
  add_unique issues "policy_file_missing"
elif ! jq empty "$POLICY_PATH" >/dev/null 2>&1; then
  add_unique issues "json_parse_failed"
else
  if ! jq -e '(.risk_trigger_rules // .risk_keyword_rules) != null' "$POLICY_PATH" >/dev/null; then
    add_unique issues "risk_trigger_rules_missing"
  else
    for risk in R0 R1 R2 R3 R4 R5; do
      if ! jq -e --arg risk "$risk" '((.risk_trigger_rules // .risk_keyword_rules) | has($risk))' "$POLICY_PATH" >/dev/null; then
        add_unique issues "risk_rule_missing:${risk}"
      fi
    done
  fi

  if ! jq -e '.memory_roots != null' "$POLICY_PATH" >/dev/null; then
    add_unique issues "memory_roots_missing"
  else
    while IFS=$'\t' read -r lane root; do
      if [ -z "$root" ]; then
        add_unique issues "memory_root_empty:${lane}"
      fi
      if printf '%s' "$root" | grep -Eq '[<>|"]'; then
        add_unique issues "memory_root_invalid_path_char:${lane}"
      fi
    done < <(jq -r '.memory_roots | to_entries[] | .key as $k | .value[] | [$k, .] | @tsv' "$POLICY_PATH" | tr -d '\r')
  fi
fi

status="pass"
if [ "${#issues[@]}" -gt 0 ]; then
  status="blocked"
fi

result="$(
  jq -n \
    --arg phase "validate_policy" \
    --arg status "$status" \
    --arg policy_path "$POLICY_PATH" \
    --argjson issues "$(json_array "${issues[@]}")" \
    '{
      ts: (now | todateiso8601),
      phase: $phase,
      status: $status,
      policy_path: $policy_path,
      issues: $issues,
      rule: "lightweight parse and shape check only; not a full JSON Schema validator"
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
