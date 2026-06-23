#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
POLICY_PATH="$(cd "$SCRIPT_DIR/.." && pwd -P)/embedded_harness_policy.json"
REPO_ROOT=""
OUTPUT_PATH=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --policy|-PolicyPath) POLICY_PATH="${2:-}"; shift 2 ;;
    --repo-root|-RepoRoot) REPO_ROOT="${2:-}"; shift 2 ;;
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

check_text_belief_invariants() {
  local file="$1"
  local root="$2"
  local relative="${file#$root/}"
  awk -v file="$relative" '
    /^[[:space:]]*belief_status:[[:space:]]*/ {
      status=$0
      sub(/^[[:space:]]*belief_status:[[:space:]]*`?/, "", status)
      sub(/`?[[:space:]#].*$/, "", status)
      saw_summary=0
      next
    }
    status != "" && /^[[:space:]]*belief_trace_summary:[[:space:]]*/ {
      saw_summary=1
      next
    }
    status != "" && saw_summary && /^[[:space:]]*current_status:[[:space:]]*/ {
      current=$0
      sub(/^[[:space:]]*current_status:[[:space:]]*`?/, "", current)
      sub(/`?[[:space:]#].*$/, "", current)
      if (current != status) {
        printf "belief_trace_current_status_mismatch:%s:%d:%s!=%s\n", file, NR, status, current
      }
      status=""
      saw_summary=0
    }
    END {
      if (status != "" && saw_summary) {
        printf "belief_trace_summary_current_status_missing:%s\n", file
      }
    }
  ' "$file"
}

check_json_belief_invariants() {
  local file="$1"
  local root="$2"
  local relative="${file#$root/}"
  if [ "${file##*.}" = "jsonl" ]; then
    jq -r --arg file "$relative" '
      def check:
        .. | objects
        | select(has("belief_status") and has("belief_trace_summary"))
        | if (.belief_trace_summary.current_status == null) then
            "belief_trace_summary_current_status_missing:\($file)"
          elif ((.belief_trace_summary.current_status | tostring) != (.belief_status | tostring)) then
            "belief_trace_current_status_mismatch:\($file):\(.belief_status)!=\(.belief_trace_summary.current_status)"
          else empty end;
      check
    ' "$file" 2>/dev/null || printf 'belief_invariant_json_parse_failed:%s\n' "$relative"
  else
    jq -r --arg file "$relative" '
      .. | objects
      | select(has("belief_status") and has("belief_trace_summary"))
      | if (.belief_trace_summary.current_status == null) then
          "belief_trace_summary_current_status_missing:\($file)"
        elif ((.belief_trace_summary.current_status | tostring) != (.belief_status | tostring)) then
          "belief_trace_current_status_mismatch:\($file):\(.belief_status)!=\(.belief_trace_summary.current_status)"
        else empty end
    ' "$file" 2>/dev/null || printf 'belief_invariant_json_parse_failed:%s\n' "$relative"
  fi
}

check_belief_invariants() {
  local root="$1"
  local item file issue
  for item in docs examples templates skills AGENTS.md README.md; do
    [ -e "$root/$item" ] || continue
    if [ -d "$root/$item" ]; then
      while IFS= read -r -d '' file; do
        case "$file" in
          *.md|*.yaml|*.yml)
            while IFS= read -r issue; do add_unique issues "$issue"; done < <(check_text_belief_invariants "$file" "$root")
            ;;
          *.json|*.jsonl)
            while IFS= read -r issue; do add_unique issues "$issue"; done < <(check_json_belief_invariants "$file" "$root")
            ;;
        esac
      done < <(find "$root/$item" -type f -print0)
    else
      file="$root/$item"
      while IFS= read -r issue; do add_unique issues "$issue"; done < <(check_text_belief_invariants "$file" "$root")
    fi
  done
}

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

  if ! jq -e '.r5_context_decision_rules != null' "$POLICY_PATH" >/dev/null; then
    add_unique issues "r5_context_decision_rules_missing"
  else
    for field in direct_action_terms context_required_candidate_terms always_action_candidate_terms action_context_terms non_action_context_terms documentation_context_terms; do
      if ! jq -e --arg field "$field" '(.r5_context_decision_rules[$field] // []) | length > 0' "$POLICY_PATH" >/dev/null; then
        add_unique issues "r5_context_decision_rule_empty:${field}"
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

if [ -z "$REPO_ROOT" ]; then
  candidate="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
  if [ -f "$candidate/VERSION" ] && [ -f "$candidate/skills/embedded-harness/embedded_harness_policy.json" ]; then
    REPO_ROOT="$candidate"
  fi
fi
if [ -n "$REPO_ROOT" ] && [ -d "$REPO_ROOT" ]; then
  check_belief_invariants "$(cd "$REPO_ROOT" && pwd -P)"
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
      rule: "lightweight policy parse, shape check, and belief_trace_summary.current_status invariant check when repo root is available; not a full JSON Schema validator"
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
