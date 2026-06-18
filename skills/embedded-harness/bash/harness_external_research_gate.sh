#!/usr/bin/env bash
set -euo pipefail

TASK_TEXT=""
CLAIM_TEXT=""
OUTPUT_PATH=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
POLICY_PATH="$(cd "$SCRIPT_DIR/.." && pwd -P)/embedded_harness_policy.json"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --task-text|-TaskText) TASK_TEXT="${2:-}"; shift 2 ;;
    --claim-text|-ClaimText) CLAIM_TEXT="${2:-}"; shift 2 ;;
    --output|-OutputPath) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --policy|-PolicyPath) POLICY_PATH="${2:-}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if ! command -v jq >/dev/null 2>&1; then
  echo '{"phase":"external_research_gate","status":"blocked","issues":["jq_missing"]}'
  exit 1
fi

if [ "${BASH_VERSINFO[0]}" -lt 4 ]; then
  echo '{"phase":"external_research_gate","status":"blocked","issues":["bash_4_required"]}'
  exit 1
fi

COMBINED="${TASK_TEXT}
${CLAIM_TEXT}"

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

regex_escape() {
  local input="$1"
  local output=""
  local char
  local i
  for ((i = 0; i < ${#input}; i++)); do
    char="${input:i:1}"
    case "$char" in
      "\\"|"."|"^"|"$"|"*"|"+"|"?"|"|"|"["|"]"|"("|")"|"{"|"}"|"-") output+="\\${char}" ;;
      *) output+="${char}" ;;
    esac
  done
  printf '%s' "$output"
}

is_english_trigger() {
  [[ "$1" =~ [A-Za-z0-9] ]]
}

match_trigger() {
  local source="$1"
  local trigger="$2"
  local escaped regex neg_regex
  escaped="$(regex_escape "$trigger")"
  if is_english_trigger "$trigger"; then
    regex="(^|[^A-Za-z0-9_])${escaped}([^A-Za-z0-9_]|$)"
  else
    regex="$escaped"
  fi
  shopt -s nocasematch
  if [[ ! "$source" =~ $regex ]]; then
    return 1
  fi
  if is_english_trigger "$trigger"; then
    neg_regex="(do[[:space:]]+not|don't|never|not|no)[[:space:][:alnum:]_'-]{0,36}${escaped}"
    if [[ "$source" =~ $neg_regex ]]; then
      return 2
    fi
  fi
  return 0
}

triggers_from_filter() {
  local filter="$1"
  jq -r "$filter | if . == null then empty elif type == \"array\" then .[] elif type == \"object\" then .[] | .[] else . end" "$POLICY_PATH" | tr -d '\r'
}

matched_triggers=()
negated_triggers=()
recommended_modes=()

while IFS= read -r trigger; do
  [ -z "$trigger" ] && continue
  if match_trigger "$COMBINED" "$trigger"; then
    add_unique matched_triggers "$trigger"
  else
    rc=$?
    if [ "$rc" -eq 2 ]; then
      add_unique negated_triggers "$trigger"
    fi
  fi
done < <(triggers_from_filter '.external_research_triggers')

if printf '%s' "$COMBINED" | grep -Eq '\b20[0-9]{2}[-/][0-9]{1,2}([-/][0-9]{1,2})?\b'; then
  add_unique matched_triggers "date_pattern"
fi
if printf '%s' "$COMBINED" | grep -Eiq '\b(v[0-9]+\.[0-9]+(\.[0-9]+)?|(version|release|sdk|node|python|npm|package|plugin)[[:space:]]*:?[[:space:]]*v?[0-9]+\.[0-9]+(\.[0-9]+)?)\b'; then
  add_unique matched_triggers "version_pattern"
fi
if printf '%s' "$COMBINED" | grep -Eiq 'https?://|github\.com'; then
  add_unique matched_triggers "url_or_github_pattern"
fi

needs_external_research=false
if [ "${#matched_triggers[@]}" -gt 0 ]; then
  needs_external_research=true
fi

if [ "$needs_external_research" = true ]; then
  if printf '%s' "$COMBINED" | grep -Eiq 'github|github\.com|repo|repository|open source|release|changelog|issue|license'; then
    add_unique recommended_modes "github_open_source_repository_search"
  fi
  if printf '%s' "$COMBINED" | grep -Eiq 'official|authority|policy|law|price|product|institution|current|latest|version|release|CEO|president'; then
    add_unique recommended_modes "official_authority_source_search"
  fi
  if printf '%s' "$COMBINED" | grep -Eiq 'compare|comparison|ecosystem|community|trend|tutorial'; then
    add_unique recommended_modes "general_web_cross_check"
  fi
  if printf '%s' "$COMBINED" | grep -Eiq 'mechanism|external architecture|architecture comparison|learn from|source-grounded|external mechanism|avoid closed-door'; then
    add_unique recommended_modes "source_grounded_learning_intake"
  fi
  if [ "${#recommended_modes[@]}" -eq 0 ]; then
    add_unique recommended_modes "general_web_cross_check"
  fi
fi

mapfile -t labels < <(jq -r '.search_and_learning_decision_matrix.classification_labels[]?' "$POLICY_PATH" | tr -d '\r')

result="$(
  jq -n \
    --arg phase "external_research_gate" \
    --arg status "pass" \
    --argjson needs_external_research "$needs_external_research" \
    --argjson matched_triggers "$(json_array "${matched_triggers[@]}")" \
    --argjson negated_triggers "$(json_array "${negated_triggers[@]}")" \
    --argjson recommended_search_modes "$(json_array "${recommended_modes[@]}")" \
    --argjson learning_classification_labels "$(json_array "${labels[@]}")" \
    '{
      ts: (now | todateiso8601),
      phase: $phase,
      status: $status,
      needs_external_research: $needs_external_research,
      matched_triggers: $matched_triggers,
      negated_triggers: $negated_triggers,
      recommended_search_modes: $recommended_search_modes,
      learning_classification_labels: $learning_classification_labels,
      rule: "deterministic trigger plus search-mode routing; no extra model judgment"
    }'
)"

if [ -n "$OUTPUT_PATH" ]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  printf '%s\n' "$result" > "$OUTPUT_PATH"
fi
printf '%s\n' "$result"
