#!/usr/bin/env bash
set -euo pipefail

TASK_TEXT=""
CWD="$(pwd)"
OUTPUT_PATH=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
POLICY_PATH="$(cd "$SCRIPT_DIR/.." && pwd -P)/embedded_harness_policy.json"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --task-text|-TaskText) TASK_TEXT="${2:-}"; shift 2 ;;
    --cwd|-Cwd) CWD="${2:-}"; shift 2 ;;
    --output|-OutputPath) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --policy|-PolicyPath) POLICY_PATH="${2:-}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if ! command -v jq >/dev/null 2>&1; then
  echo '{"phase":"intake_router","status":"blocked","issues":["jq_missing"]}'
  exit 1
fi

if [ "${BASH_VERSINFO[0]}" -lt 4 ]; then
  echo '{"phase":"intake_router","status":"blocked","issues":["bash_4_required"]}'
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

triggers_for_risk() {
  local risk="$1"
  jq -r --arg risk "$risk" '
    ((.risk_trigger_rules // .risk_keyword_rules // {})[$risk])
    | if . == null then empty
      elif type == "array" then .[]
      elif type == "object" then .[] | .[]
      else .
      end
  ' "$POLICY_PATH" | tr -d '\r'
}

triggers_from_filter() {
  local filter="$1"
  jq -r "$filter | if . == null then empty elif type == \"array\" then .[] elif type == \"object\" then .[] | .[] else . end" "$POLICY_PATH" | tr -d '\r'
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

set_object_array() {
  local file="$1"
  local key="$2"
  shift 2
  local arr_json tmp
  arr_json="$(json_array "$@")"
  tmp="${file}.tmp"
  jq --arg key "$key" --argjson arr "$arr_json" '. + {($key): $arr}' "$file" > "$tmp"
  mv "$tmp" "$file"
}

matched_file="$(mktemp)"
negated_file="$(mktemp)"
trap 'rm -f "$matched_file" "$negated_file" "${matched_file}.tmp" "${negated_file}.tmp"' EXIT
printf '{}\n' > "$matched_file"
printf '{}\n' > "$negated_file"

project_lane="PROJECTLESS"
cwd_canon="$(with_sep "$(canonical_path "$CWD")")"
while IFS=$'\t' read -r lane root; do
  [ -z "${lane:-}" ] && continue
  root_canon="$(with_sep "$(canonical_path "$root")")"
  if [[ "$cwd_canon" == "$root_canon"* ]]; then
    project_lane="$lane"
    break
  fi
done < <(jq -r '(.project_lanes // {}) | to_entries[]? | .key as $k | .value[] | [$k, .] | @tsv' "$POLICY_PATH" | tr -d '\r')

risk="R0"
classification_confidence="high"
fallback_model_judgment_recommended=false
needs_external_research=false
triggered_risks=()
required_gates=("microkernel")
required_skills=()
approval_required=()

mapfile -t risk_order < <(jq -r '.risk_order_high_to_low[]' "$POLICY_PATH" | tr -d '\r')
for risk_name in "${risk_order[@]}"; do
  positives=()
  negated=()
  while IFS= read -r trigger; do
    [ -z "$trigger" ] && continue
    if match_trigger "$TASK_TEXT" "$trigger"; then
      add_unique positives "$trigger"
    else
      rc=$?
      if [ "$rc" -eq 2 ]; then
        add_unique negated "$trigger"
      fi
    fi
  done < <(triggers_for_risk "$risk_name")

  if [ "${#negated[@]}" -gt 0 ]; then
    set_object_array "$negated_file" "$risk_name" "${negated[@]}"
  fi
  if [ "${#positives[@]}" -gt 0 ]; then
    add_unique triggered_risks "$risk_name"
    set_object_array "$matched_file" "$risk_name" "${positives[@]}"
    while IFS= read -r gate; do add_unique required_gates "$gate"; done < <(jq -r --arg risk "$risk_name" '.risk_gate_rules[$risk] // [] | .[]' "$POLICY_PATH" | tr -d '\r')
    while IFS= read -r approval; do add_unique approval_required "$approval"; done < <(jq -r --arg risk "$risk_name" '.risk_approval_rules[$risk] // [] | .[]' "$POLICY_PATH" | tr -d '\r')
  fi
done

for risk_name in "${risk_order[@]}"; do
  for triggered in "${triggered_risks[@]}"; do
    if [ "$triggered" = "$risk_name" ]; then
      risk="$risk_name"
      break 2
    fi
  done
done

if [ "${#triggered_risks[@]}" -eq 0 ]; then
  fallback=()
  while IFS= read -r trigger; do
    [ -z "$trigger" ] && continue
    if match_trigger "$TASK_TEXT" "$trigger"; then
      add_unique fallback "$trigger"
    fi
  done < <(triggers_from_filter '.fallback_boundary_triggers')
  if [ "${#fallback[@]}" -gt 0 ]; then
    fallback_model_judgment_recommended=true
    classification_confidence="low"
    add_unique required_gates "model_boundary_review_gate"
    set_object_array "$matched_file" "fallback_boundary" "${fallback[@]}"
  fi
fi

if [ "$project_lane" != "PROJECTLESS" ]; then
  add_unique required_gates "memory_isolation_gate"
  add_unique required_gates "project_agents_gate"
  add_unique required_skills "${project_lane} project AGENTS/router"
fi

skill_hits=()
while IFS= read -r trigger; do
  [ -z "$trigger" ] && continue
  if match_trigger "$TASK_TEXT" "$trigger"; then
    add_unique skill_hits "$trigger"
  fi
done < <(triggers_from_filter '.skill_matrix_triggers')
if [ "${#skill_hits[@]}" -gt 0 ]; then
  add_unique required_skills "troubleshooting-skill-matrix"
fi

external_hits=()
external_negated=()
while IFS= read -r trigger; do
  [ -z "$trigger" ] && continue
  if match_trigger "$TASK_TEXT" "$trigger"; then
    add_unique external_hits "$trigger"
  else
    rc=$?
    if [ "$rc" -eq 2 ]; then
      add_unique external_negated "$trigger"
    fi
  fi
done < <(triggers_from_filter '.external_research_triggers')
if [ "${#external_hits[@]}" -gt 0 ]; then
  needs_external_research=true
  set_object_array "$matched_file" "external_research" "${external_hits[@]}"
fi
if [ "${#external_negated[@]}" -gt 0 ]; then
  set_object_array "$negated_file" "external_research" "${external_negated[@]}"
fi

result="$(
  jq -n \
    --arg phase "intake_router" \
    --arg status "pass" \
    --arg cwd "$CWD" \
    --arg project_lane "$project_lane" \
    --arg risk_level "$risk" \
    --arg classification_confidence "$classification_confidence" \
    --argjson triggered_risks "$(json_array "${triggered_risks[@]}")" \
    --argjson matched_risk_triggers "$(cat "$matched_file")" \
    --argjson negated_risk_triggers "$(cat "$negated_file")" \
    --argjson required_gates "$(json_array "${required_gates[@]}")" \
    --argjson required_skills "$(json_array "${required_skills[@]}")" \
    --argjson needs_external_research "$needs_external_research" \
    --argjson approval_required "$(json_array "${approval_required[@]}")" \
    --argjson fallback_model_judgment_recommended "$fallback_model_judgment_recommended" \
    --arg enforcement_boundary "$(jq -r '.gate_enforcement_boundary // ""' "$POLICY_PATH" | tr -d '\r')" \
    '{
      ts: (now | todateiso8601),
      phase: $phase,
      status: $status,
      cwd: $cwd,
      project_lane: $project_lane,
      risk_level: $risk_level,
      triggered_risks: $triggered_risks,
      matched_risk_triggers: $matched_risk_triggers,
      negated_risk_triggers: $negated_risk_triggers,
      classification_confidence: $classification_confidence,
      required_gates: $required_gates,
      required_skills: $required_skills,
      needs_external_research: $needs_external_research,
      approval_required: $approval_required,
      fallback_model_judgment_used: false,
      fallback_model_judgment_recommended: $fallback_model_judgment_recommended,
      enforcement_boundary: $enforcement_boundary
    }'
)"

if [ -n "$OUTPUT_PATH" ]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  printf '%s\n' "$result" > "$OUTPUT_PATH"
fi
printf '%s\n' "$result"
