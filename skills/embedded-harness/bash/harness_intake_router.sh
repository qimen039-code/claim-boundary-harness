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

first_matching_rule() {
  local filter="$1"
  shift
  local name trigger
  for name in "$@"; do
    while IFS= read -r trigger; do
      [ -z "$trigger" ] && continue
      if match_trigger "$TASK_TEXT" "$trigger"; then
        printf '%s\n' "$name"
        return 0
      fi
    done < <(triggers_from_filter "${filter}.${name}")
  done
  return 1
}

collect_matching_triggers() {
  local filter="$1"
  local -n target="$2"
  local trigger
  while IFS= read -r trigger; do
    [ -z "$trigger" ] && continue
    if match_trigger "$TASK_TEXT" "$trigger"; then
      add_unique target "$trigger"
    fi
  done < <(triggers_from_filter "$filter")
}

array_contains() {
  local seek="$1"
  shift
  local item
  for item in "$@"; do
    [ "$item" = "$seek" ] && return 0
  done
  return 1
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

target_surface="$(first_matching_rule '.router_decision_contract.target_surface_trigger_rules' git_action tool_call adapter public_docs private_rule local_harness skill_matrix conversation_memory project_memory || true)"
[ -z "$target_surface" ] && target_surface="current_chat"
if [ "$target_surface" = "current_chat" ] && array_contains "R3" "${triggered_risks[@]}"; then
  target_surface="local_harness"
fi

audience="$(first_matching_rule '.router_decision_contract.audience_trigger_rules' public_user local_maintainer || true)"
if [ -z "$audience" ]; then
  if [ "$project_lane" != "PROJECTLESS" ]; then
    audience="project_operator"
  else
    audience="current_chat"
  fi
fi

semantic_ambiguity=()
collect_matching_triggers '.router_decision_contract.semantic_ambiguity_triggers' semantic_ambiguity
if array_contains "R3" "${triggered_risks[@]}"; then
  add_unique semantic_ambiguity "governance_or_change_surface"
fi

external_need=()
mapfile -t search_mode_names < <(jq -r '.search_and_learning_decision_matrix.search_modes // {} | keys[]' "$POLICY_PATH" | tr -d '\r')
for mode_name in "${search_mode_names[@]}"; do
  mode_hits=()
  while IFS= read -r trigger; do
    [ -z "$trigger" ] && continue
    if match_trigger "$TASK_TEXT" "$trigger"; then
      add_unique mode_hits "$trigger"
    fi
  done < <(jq -r --arg mode "$mode_name" '.search_and_learning_decision_matrix.search_modes[$mode].triggers // [] | .[]' "$POLICY_PATH" | tr -d '\r')
  if [ "${#mode_hits[@]}" -gt 0 ]; then
    add_unique external_need "$mode_name"
  fi
done
if [ "$needs_external_research" = true ] && [ "${#external_need[@]}" -eq 0 ]; then
  add_unique external_need "official_authority_source_search"
fi
if [ "${#external_need[@]}" -eq 0 ]; then
  add_unique external_need "none"
fi

memory_need="none"
memory_hits=()
paired_memory_hits=()
collect_matching_triggers '.router_decision_contract.memory_need_triggers' memory_hits
collect_matching_triggers '.router_decision_contract.paired_memory_triggers' paired_memory_hits
if [ "${#paired_memory_hits[@]}" -gt 0 ]; then
  memory_need="paired_err_sol"
elif [ "${#memory_hits[@]}" -gt 0 ]; then
  memory_need="index_only"
fi

explicit_record_hits=()
common_error_hits=()
projectization_signals=()
conversation_explicit_hits=()
conversation_signals=()
collect_matching_triggers '.router_decision_contract.explicit_record_triggers' explicit_record_hits
collect_matching_triggers '.router_decision_contract.common_error_triggers' common_error_hits
collect_matching_triggers '.router_decision_contract.projectization_signals' projectization_signals
collect_matching_triggers '.router_decision_contract.conversation_memory_explicit_triggers' conversation_explicit_hits
collect_matching_triggers '.router_decision_contract.conversation_memory_signals' conversation_signals
projectization_threshold="$(jq -r '.router_decision_contract.projectization_threshold // 3' "$POLICY_PATH" | tr -d '\r')"
conversation_threshold="$(jq -r '.router_decision_contract.conversation_memory_threshold // 2' "$POLICY_PATH" | tr -d '\r')"

projectization_decision="not_project"
if [ "$project_lane" != "PROJECTLESS" ]; then
  projectization_decision="current_project"
elif [ "${#projectization_signals[@]}" -ge "$projectization_threshold" ]; then
  projectization_decision="emergent_project_candidate"
fi

conversation_memory_decision="none"
if [ "$project_lane" = "PROJECTLESS" ] && [ "$projectization_decision" = "not_project" ]; then
  if [ "${#conversation_explicit_hits[@]}" -gt 0 ]; then
    conversation_memory_decision="create_or_update_current_conversation"
  elif [ "${#conversation_signals[@]}" -ge "$conversation_threshold" ]; then
    conversation_memory_decision="checkpoint_candidate"
  fi
fi

if [ "${#common_error_hits[@]}" -gt 0 ]; then
  memory_need="common_error_corpus"
elif [ "${#explicit_record_hits[@]}" -gt 0 ] && [ "$memory_need" = "none" ]; then
  memory_need="paired_err_sol"
fi

record_intent="no_record"
if [ "${#explicit_record_hits[@]}" -gt 0 ]; then
  record_intent="explicit_user_request"
elif [ "${#common_error_hits[@]}" -gt 0 ]; then
  record_intent="inferred_reusable_error"
elif [ "$projectization_decision" = "emergent_project_candidate" ]; then
  record_intent="projectization_review"
elif [ "$conversation_memory_decision" = "create_or_update_current_conversation" ]; then
  record_intent="explicit_conversation_memory_request"
elif [ "$conversation_memory_decision" = "checkpoint_candidate" ]; then
  record_intent="conversation_checkpoint"
fi

if [ "$conversation_memory_decision" != "none" ] && [ "$memory_need" = "none" ]; then
  memory_need="conversation_state"
fi

memory_lane="none"
if [ "${#common_error_hits[@]}" -gt 0 ]; then
  memory_lane="common_error_corpus"
elif [ "${#explicit_record_hits[@]}" -gt 0 ]; then
  memory_lane="self_reflection_matrix"
elif [ "$project_lane" != "PROJECTLESS" ]; then
  memory_lane="current_project"
elif [ "$projectization_decision" = "emergent_project_candidate" ]; then
  memory_lane="emergent_project_candidate"
elif [ "$conversation_memory_decision" != "none" ]; then
  memory_lane="current_conversation"
fi

memory_mode="none"
if [ "$record_intent" = "explicit_user_request" ] || [ "$record_intent" = "inferred_reusable_error" ] || [ "$record_intent" = "explicit_conversation_memory_request" ] || [ "$record_intent" = "conversation_checkpoint" ]; then
  memory_mode="write"
elif [ "$memory_need" != "none" ]; then
  memory_mode="read"
fi

if [ "${#explicit_record_hits[@]}" -gt 0 ] || [ "${#common_error_hits[@]}" -gt 0 ]; then
  add_unique required_skills "troubleshooting-skill-matrix"
fi

claim_risk="none"
strong_claim_hits=()
collect_matching_triggers '.blocked_claim_phrases_without_schema' strong_claim_hits
if [ "${#strong_claim_hits[@]}" -gt 0 ]; then
  claim_risk="strong_claim_needs_schema"
elif array_contains "claim_gate" "${required_gates[@]}"; then
  claim_risk="weak_claim"
fi

module_need=()
[ "$project_lane" != "PROJECTLESS" ] && add_unique module_need "project_router"
[ "${#required_skills[@]}" -gt 0 ] && add_unique module_need "skill_matrix"
[ "${#semantic_ambiguity[@]}" -gt 0 ] && add_unique module_need "semantic_anchors"
[ "$memory_need" != "none" ] && add_unique module_need "memory_meta_index"
[ "$conversation_memory_decision" != "none" ] && add_unique module_need "conversation_memory_index"
if [ "${#external_need[@]}" -gt 0 ] && [ "${external_need[0]}" != "none" ]; then
  add_unique module_need "external_research_gate"
fi
[ "$claim_risk" != "none" ] && add_unique module_need "claim_schema_verifier"
if [ "$risk" = "R5" ] || [ "$classification_confidence" = "low" ]; then
  add_unique module_need "runtime_gate"
fi
[ "${#module_need[@]}" -eq 0 ] && add_unique module_need "none"

debug_hits=()
collect_matching_triggers '.receipt_profiles.debug_triggers' debug_hits
receipt_profile="compact_runtime"
profile_reason=("default_compact_runtime")
if [ "${#debug_hits[@]}" -gt 0 ]; then
  receipt_profile="debug_receipt"
  add_unique profile_reason "debug_requested"
else
  case "$target_surface" in
    public_docs|local_harness|project_memory|skill_matrix|adapter|private_rule)
      add_unique profile_reason "governance_surface"
      ;;
  esac
  case "$audience" in
    public_user|local_maintainer)
      add_unique profile_reason "audience_boundary"
      ;;
  esac
  [ "${#semantic_ambiguity[@]}" -gt 0 ] && add_unique profile_reason "semantic_ambiguity"
  if [ "$memory_mode" = "write" ] || [ "$memory_mode" = "update" ] || [ "$record_intent" != "no_record" ]; then
    add_unique profile_reason "memory_write_or_record"
  fi
  [ "$projectization_decision" = "emergent_project_candidate" ] && add_unique profile_reason "projectization_candidate"
  [ "$conversation_memory_decision" != "none" ] && add_unique profile_reason "conversation_memory_candidate"
  if [ "${#profile_reason[@]}" -gt 1 ]; then
    receipt_profile="extended_governance"
  fi
fi

human_confirmation_need=false
if [ "${#approval_required[@]}" -gt 0 ]; then
  human_confirmation_need=true
fi

result="$(
  jq -n \
    --arg phase "intake_router" \
    --arg status "pass" \
    --arg cwd "$CWD" \
    --arg target_surface "$target_surface" \
    --arg audience "$audience" \
    --arg project_lane "$project_lane" \
    --arg risk_level "$risk" \
    --arg memory_need "$memory_need" \
    --arg memory_mode "$memory_mode" \
    --arg memory_lane "$memory_lane" \
    --arg record_intent "$record_intent" \
    --arg claim_risk "$claim_risk" \
    --arg projectization_decision "$projectization_decision" \
    --arg conversation_memory_decision "$conversation_memory_decision" \
    --arg receipt_profile "$receipt_profile" \
    --argjson projectization_signals "$(json_array "${projectization_signals[@]}")" \
    --argjson conversation_signals "$(json_array "${conversation_explicit_hits[@]}" "${conversation_signals[@]}")" \
    --argjson profile_reason "$(json_array "${profile_reason[@]}")" \
    --argjson semantic_ambiguity "$(json_array "${semantic_ambiguity[@]}")" \
    --argjson module_need "$(json_array "${module_need[@]}")" \
    --argjson external_need "$(json_array "${external_need[@]}")" \
    --arg classification_confidence "$classification_confidence" \
    --argjson triggered_risks "$(json_array "${triggered_risks[@]}")" \
    --argjson matched_risk_triggers "$(cat "$matched_file")" \
    --argjson negated_risk_triggers "$(cat "$negated_file")" \
    --argjson required_gates "$(json_array "${required_gates[@]}")" \
    --argjson required_skills "$(json_array "${required_skills[@]}")" \
    --argjson needs_external_research "$needs_external_research" \
    --argjson approval_required "$(json_array "${approval_required[@]}")" \
    --argjson human_confirmation_need "$human_confirmation_need" \
    --argjson fallback_model_judgment_recommended "$fallback_model_judgment_recommended" \
    --arg enforcement_boundary "$(jq -r '.gate_enforcement_boundary // ""' "$POLICY_PATH" | tr -d '\r')" \
    '{
      ts: (now | todateiso8601),
      phase: $phase,
      status: $status,
      cwd: $cwd,
      routing_receipt: {
        task_type: $risk_level,
        target_surface: $target_surface,
        audience: $audience,
        project_lane: $project_lane,
        risk_level: $risk_level,
        semantic_ambiguity: $semantic_ambiguity,
        module_need: $module_need,
        memory_need: $memory_need,
        memory_mode: $memory_mode,
        memory_lane: $memory_lane,
        record_intent: $record_intent,
        external_need: $external_need,
        claim_risk: $claim_risk,
        projectization_decision: $projectization_decision,
        conversation_memory_decision: $conversation_memory_decision,
        receipt_profile: $receipt_profile,
        projectization_signals: $projectization_signals,
        conversation_signals: $conversation_signals,
        required_gates: $required_gates
      },
      compact_receipt: {
        task_type: $risk_level,
        risk_level: $risk_level,
        required_gates: $required_gates,
        memory_mode: $memory_mode,
        memory_lane: $memory_lane,
        conversation_memory_decision: $conversation_memory_decision,
        external_need: $external_need,
        claim_risk: $claim_risk,
        human_confirmation_need: $human_confirmation_need
      },
      receipt_profile: $receipt_profile,
      profile_reason: $profile_reason,
      target_surface: $target_surface,
      audience: $audience,
      project_lane: $project_lane,
      risk_level: $risk_level,
      semantic_ambiguity: $semantic_ambiguity,
      module_need: $module_need,
      memory_need: $memory_need,
      memory_mode: $memory_mode,
      memory_lane: $memory_lane,
      record_intent: $record_intent,
      external_need: $external_need,
      claim_risk: $claim_risk,
      projectization_decision: $projectization_decision,
      conversation_memory_decision: $conversation_memory_decision,
      projectization_signals: $projectization_signals,
      conversation_signals: $conversation_signals,
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
