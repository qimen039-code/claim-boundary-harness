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
  local -n array_ref="$1"
  local value="$2"
  local item
  [ -z "$value" ] && return 0
  for item in "${array_ref[@]}"; do
    [ "$item" = "$value" ] && return 0
  done
  array_ref+=("$value")
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
    neg_regex="(do[[:space:]]+not|don't|never|not|no)[[:space:][:alnum:]_'-]{0,128}${escaped}"
    if [[ "$source" =~ $neg_regex ]]; then
      return 2
    fi
  fi
  return 0
}

set_object_json() {
  local file="$1"
  local key="$2"
  local value_json="$3"
  local tmp
  tmp="${file}.tmp"
  jq --arg key "$key" --argjson value "$value_json" '. + {($key): $value}' "$file" > "$tmp"
  mv "$tmp" "$file"
}

is_r5_direct_action_context() {
  has_matches_filter '.r5_context_decision_rules.direct_action_terms' && return 0
  if has_candidate_in_filter '.r5_context_decision_rules.always_action_candidate_terms' && ! has_matches_filter '.r5_context_decision_rules.documentation_context_terms'; then
    return 0
  fi
  if has_candidate_in_filter '.r5_context_decision_rules.context_required_candidate_terms' && has_matches_filter '.r5_context_decision_rules.action_context_terms' && ! has_matches_filter '.r5_context_decision_rules.non_action_context_terms'; then
    return 0
  fi
  return 1
}

is_r5_documentation_or_discussion_context() {
  has_matches_filter '.r5_context_decision_rules.documentation_context_terms' && return 0
  has_matches_filter '.r5_context_decision_rules.non_action_context_terms' && return 0
  return 1
}

has_matches_filter() {
  local filter="$1"
  local hits=()
  collect_matching_triggers "$filter" hits
  [ "${#hits[@]}" -gt 0 ]
}

has_candidate_in_filter() {
  local filter="$1"
  local candidate term
  for candidate in "${positives[@]}"; do
    while IFS= read -r term; do
      [ -z "$term" ] && continue
      if [ "${candidate,,}" = "${term,,}" ]; then
        return 0
      fi
    done < <(triggers_from_filter "$filter")
  done
  return 1
}

r5_context_decision_json() {
  local decision="$1"
  local action_surface="$2"
  local promote="$3"
  local reason="$4"
  local candidate_json negated_json
  candidate_json="$(json_array "${positives[@]}")"
  negated_json="$(json_array "${negated[@]}")"
  jq -n \
    --arg decision "$decision" \
    --arg action_surface "$action_surface" \
    --arg reason "$reason" \
    --argjson promote "$promote" \
    --argjson candidate_terms "$candidate_json" \
    --argjson negated_terms "$negated_json" \
    '{
      decision: $decision,
      action_surface: $action_surface,
      promote_to_risk: $promote,
      candidate_terms: $candidate_terms,
      negated_terms: $negated_terms,
      reason: $reason
    }'
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
  local target_array_name="$2"
  local trigger
  while IFS= read -r trigger; do
    [ -z "$trigger" ] && continue
    if match_trigger "$TASK_TEXT" "$trigger"; then
      add_unique "$target_array_name" "$trigger"
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

find_active_conversation_memory_lane() {
  local current="$1"
  local depth root lane meta index combined parent
  if [ -d "$current" ]; then
    current="$(cd "$current" 2>/dev/null && pwd -P || printf '%s' "$current")"
  fi
  for depth in 0 1 2 3 4; do
    [ -z "$current" ] && break
    root="${current%/}/local-conversation-memory"
    if [ -d "$root" ]; then
      for lane in "$root"/*; do
        [ -d "$lane" ] || continue
        meta="${lane%/}/_META_INDEX.md"
        index="${lane%/}/index.json"
        [ -f "$meta" ] || [ -f "$index" ] || continue
        combined="$(cat "$meta" "$index" 2>/dev/null || true)"
        case "$combined" in
          *"status: ACTIVE"*|*'"status": "ACTIVE"'*|*"lane_state: ACTIVE"*|*'"lane_state": "ACTIVE"'*|*"lane_state: active"*|*'"lane_state": "active"'*|*"single_conversation_project_shaped_lane"*)
            printf '%s' "$lane"
            return 0
            ;;
        esac
      done
    fi
    parent="$(dirname "$current")"
    [ "$parent" = "$current" ] && break
    current="$parent"
  done
  return 0
}

matched_file="$(mktemp)"
negated_file="$(mktemp)"
candidates_file="$(mktemp)"
context_file="$(mktemp)"
trap 'rm -f "$matched_file" "$negated_file" "$candidates_file" "$context_file" "${matched_file}.tmp" "${negated_file}.tmp" "${candidates_file}.tmp" "${context_file}.tmp"' EXIT
printf '{}\n' > "$matched_file"
printf '{}\n' > "$negated_file"
printf '{}\n' > "$candidates_file"
printf '{}\n' > "$context_file"

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

active_conversation_memory_lane_path="$(find_active_conversation_memory_lane "$CWD")"
has_active_conversation_memory_lane=false
[ -n "$active_conversation_memory_lane_path" ] && has_active_conversation_memory_lane=true

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
  if [ "$risk_name" = "R5" ] && [ "${#positives[@]}" -gt 0 ]; then
    set_object_array "$candidates_file" "R5" "${positives[@]}"
    if is_r5_direct_action_context; then
      set_object_json "$context_file" "R5" "$(r5_context_decision_json "requires_confirmation" "actionable_R5" true "action_context_detected")"
    elif is_r5_documentation_or_discussion_context; then
      set_object_json "$context_file" "R5" "$(r5_context_decision_json "contextual_review" "documentation_or_discussion" false "R5_terms_are_context_not_action")"
      continue
    else
      classification_confidence="low"
      add_unique required_gates "risk_context_review_gate"
      set_object_json "$context_file" "R5" "$(r5_context_decision_json "contextual_review" "ambiguous_R5_candidate" false "R5_candidate_needs_context_review")"
      continue
    fi
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
  fallback_short_max="$(jq -r '.router_decision_contract.fallback_short_text_max_chars // 30' "$POLICY_PATH" | tr -d '\r')"
  fallback_long_min="$(jq -r '.router_decision_contract.fallback_long_text_min_chars // 100' "$POLICY_PATH" | tr -d '\r')"
  task_trimmed="$(printf '%s' "$TASK_TEXT" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  task_length="${#task_trimmed}"
  fallback_eligible=false
  if [ "$task_length" -ge "$fallback_long_min" ] || { [ "$task_length" -ge "$fallback_short_max" ] && [ "${#fallback[@]}" -gt 0 ]; }; then
    fallback_eligible=true
  fi
  if [ "$fallback_eligible" = true ]; then
    fallback_model_judgment_recommended=true
    classification_confidence="low"
    add_unique required_gates "model_boundary_review_gate"
    if [ "${#fallback[@]}" -gt 0 ]; then
      set_object_array "$matched_file" "fallback_boundary" "${fallback[@]}"
    else
      set_object_array "$matched_file" "fallback_boundary" "long_unclassified_task"
    fi
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

target_surface="$(first_matching_rule '.router_decision_contract.target_surface_trigger_rules' git_action tool_call adapter public_docs conversation_memory private_rule local_harness skill_matrix project_memory || true)"
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
debt_hygiene_hits=()
collect_matching_triggers '.router_decision_contract.debt_hygiene_triggers' debt_hygiene_hits
if [ "${#debt_hygiene_hits[@]}" -gt 0 ]; then
  add_unique semantic_ambiguity "debt_hygiene_required"
  add_unique required_gates "debt_hygiene_gate"
  set_object_array "$matched_file" "debt_hygiene" "${debt_hygiene_hits[@]}"
fi
observation_scope_hits=()
collect_matching_triggers '.router_decision_contract.observation_scope_triggers' observation_scope_hits
if [ "${#observation_scope_hits[@]}" -gt 0 ]; then
  add_unique semantic_ambiguity "observation_scope_required"
  add_unique required_gates "observation_scope_gate"
  set_object_array "$matched_file" "observation_scope" "${observation_scope_hits[@]}"
fi
feedback_loop_hits=()
feedback_loop_profile="none"
collect_matching_triggers '.router_decision_contract.feedback_loop_triggers' feedback_loop_hits
if [ "${#feedback_loop_hits[@]}" -gt 0 ]; then
  add_unique semantic_ambiguity "feedback_loop_required"
  add_unique required_gates "feedback_loop_gate"
  set_object_array "$matched_file" "feedback_loop" "${feedback_loop_hits[@]}"
  feedback_loop_profile="explicit_cycle"
fi
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
static_knowledge_hits=()
collect_matching_triggers '.router_decision_contract.memory_need_triggers' memory_hits
collect_matching_triggers '.router_decision_contract.paired_memory_triggers' paired_memory_hits
collect_matching_triggers '.router_decision_contract.static_knowledge_triggers' static_knowledge_hits
if [ "${#paired_memory_hits[@]}" -gt 0 ]; then
  memory_need="paired_err_sol"
elif [ "${#memory_hits[@]}" -gt 0 ] || [ "${#static_knowledge_hits[@]}" -gt 0 ] || [ "${#feedback_loop_hits[@]}" -gt 0 ]; then
  memory_need="index_only"
fi
if [ "${#paired_memory_hits[@]}" -gt 0 ]; then
  add_unique semantic_ambiguity "feedback_loop_required"
  add_unique required_gates "feedback_loop_gate"
  set_object_array "$matched_file" "feedback_loop_memory" "${paired_memory_hits[@]}"
  if [ "$feedback_loop_profile" != "explicit_cycle" ]; then
    feedback_loop_profile="prevention_review"
  fi
fi
if [ "${#static_knowledge_hits[@]}" -gt 0 ]; then
  add_unique required_gates "static_knowledge_index_gate"
fi

explicit_record_hits=()
common_error_hits=()
common_error_prevention_hits=()
projectization_signals=()
conversation_explicit_hits=()
conversation_signals=()
read_only_memory_audit_hits=()
active_conversation_write_intent_hits=()
collect_matching_triggers '.router_decision_contract.explicit_record_triggers' explicit_record_hits
collect_matching_triggers '.router_decision_contract.common_error_triggers' common_error_hits
collect_matching_triggers '.router_decision_contract.common_error_prevention_triggers' common_error_prevention_hits
collect_matching_triggers '.router_decision_contract.projectization_signals' projectization_signals
collect_matching_triggers '.router_decision_contract.conversation_memory_explicit_triggers' conversation_explicit_hits
collect_matching_triggers '.router_decision_contract.conversation_memory_signals' conversation_signals
collect_matching_triggers '.router_decision_contract.read_only_memory_audit_triggers' read_only_memory_audit_hits
collect_matching_triggers '.router_decision_contract.active_conversation_write_intent_triggers' active_conversation_write_intent_hits
self_reflection_record_hits=("${explicit_record_hits[@]}")
if [ "${#conversation_explicit_hits[@]}" -gt 0 ]; then
  self_reflection_record_hits=()
fi
common_error_write_intent=false
if [ "${#common_error_hits[@]}" -gt 0 ] && [ "${#explicit_record_hits[@]}" -gt 0 ]; then
  common_error_write_intent=true
fi
projectization_threshold="$(jq -r '.router_decision_contract.projectization_threshold // 5' "$POLICY_PATH" | tr -d '\r')"
conversation_threshold="$(jq -r '.router_decision_contract.conversation_memory_threshold // 5' "$POLICY_PATH" | tr -d '\r')"

projectization_decision="not_project"
if [ "$project_lane" != "PROJECTLESS" ]; then
  projectization_decision="current_project"
elif [ "${#projectization_signals[@]}" -ge "$projectization_threshold" ]; then
  projectization_decision="emergent_project_candidate"
fi

conversation_memory_decision="none"
read_only_memory_audit_intent=false
if [ "${#read_only_memory_audit_hits[@]}" -gt 0 ] && [ "${#active_conversation_write_intent_hits[@]}" -eq 0 ] && [ "${#explicit_record_hits[@]}" -eq 0 ] && [ "${#common_error_hits[@]}" -eq 0 ]; then
  read_only_memory_audit_intent=true
fi
active_conversation_write_intent=false
if [ "${#active_conversation_write_intent_hits[@]}" -gt 0 ]; then
  active_conversation_write_intent=true
fi
if [ "${#explicit_record_hits[@]}" -gt 0 ] || [ "$common_error_write_intent" = true ]; then
  active_conversation_write_intent=true
fi
active_conversation_memory_durable_signal=false
if [ "$has_active_conversation_memory_lane" = true ]; then
  if [ "$read_only_memory_audit_intent" = false ] && { [ "$active_conversation_write_intent" = true ] || [ "${#conversation_signals[@]}" -ge "$conversation_threshold" ] || [ "${#projectization_signals[@]}" -ge "$projectization_threshold" ] || array_contains "$risk" R4 R5; }; then
    active_conversation_memory_durable_signal=true
  fi
fi
if [ "$project_lane" = "PROJECTLESS" ]; then
  if [ "${#conversation_explicit_hits[@]}" -gt 0 ]; then
    conversation_memory_decision="create_or_update_current_conversation"
  elif [ "$active_conversation_memory_durable_signal" = true ]; then
    conversation_memory_decision="create_or_update_current_conversation"
  elif [ "$read_only_memory_audit_intent" = false ] && [ "${#conversation_signals[@]}" -ge "$conversation_threshold" ]; then
    if [ "$projectization_decision" = "not_project" ]; then
      conversation_memory_decision="checkpoint_candidate"
    fi
  fi
fi

if [ "${#common_error_hits[@]}" -gt 0 ]; then
  memory_need="common_error_corpus"
  if [ "$common_error_write_intent" = true ]; then
    [ "$feedback_loop_profile" = "none" ] && feedback_loop_profile="record_candidate"
    set_object_array "$matched_file" "common_error_candidate" "${common_error_hits[@]}"
  elif [ "${#common_error_prevention_hits[@]}" -gt 0 ]; then
    add_unique semantic_ambiguity "feedback_loop_required"
    add_unique required_gates "feedback_loop_gate"
    set_object_array "$matched_file" "feedback_loop_common_error" "${common_error_hits[@]}"
    if [ "$feedback_loop_profile" != "explicit_cycle" ]; then
      feedback_loop_profile="prevention_review"
    fi
  else
    [ "$feedback_loop_profile" = "none" ] && feedback_loop_profile="index_hint"
    set_object_array "$matched_file" "common_error_index_hint" "${common_error_hits[@]}"
  fi
elif [ "${#self_reflection_record_hits[@]}" -gt 0 ] && [ "$memory_need" = "none" ]; then
  memory_need="paired_err_sol"
fi

record_intent="no_record"
if [ "$common_error_write_intent" = true ]; then
  record_intent="inferred_reusable_error"
elif [ "$conversation_memory_decision" = "create_or_update_current_conversation" ]; then
  if [ "${#conversation_explicit_hits[@]}" -gt 0 ]; then
    record_intent="explicit_conversation_memory_request"
  else
    record_intent="conversation_checkpoint"
  fi
elif [ "${#self_reflection_record_hits[@]}" -gt 0 ]; then
  record_intent="explicit_user_request"
elif [ "$conversation_memory_decision" = "checkpoint_candidate" ]; then
  record_intent="conversation_checkpoint"
elif [ "$projectization_decision" = "emergent_project_candidate" ]; then
  record_intent="projectization_review"
fi

if [ "$conversation_memory_decision" != "none" ] && [ "$memory_need" = "none" ]; then
  memory_need="conversation_state"
fi

memory_lane="none"
if [ "${#common_error_hits[@]}" -gt 0 ]; then
  memory_lane="common_error_corpus"
elif [ "$project_lane" != "PROJECTLESS" ]; then
  memory_lane="current_project"
elif [ "$conversation_memory_decision" != "none" ] && { [ "$has_active_conversation_memory_lane" = true ] || [ "${#conversation_explicit_hits[@]}" -gt 0 ]; }; then
  memory_lane="current_conversation"
elif [ "${#self_reflection_record_hits[@]}" -gt 0 ]; then
  memory_lane="self_reflection_matrix"
elif [ "$projectization_decision" = "emergent_project_candidate" ]; then
  memory_lane="emergent_project_candidate"
elif [ "$conversation_memory_decision" != "none" ]; then
  memory_lane="current_conversation"
fi

memory_mode="none"
if [ "$record_intent" = "explicit_user_request" ] || [ "$record_intent" = "inferred_reusable_error" ] || [ "$record_intent" = "explicit_conversation_memory_request" ] || [ "$record_intent" = "conversation_checkpoint" ]; then
  if [ "$memory_lane" = "current_conversation" ] && [ "$has_active_conversation_memory_lane" = true ]; then
    memory_mode="update"
  else
    memory_mode="write"
  fi
elif [ "$memory_need" != "none" ]; then
  memory_mode="read"
fi

if [ "${#self_reflection_record_hits[@]}" -gt 0 ] || [ "${#common_error_hits[@]}" -gt 0 ]; then
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
[ "${#static_knowledge_hits[@]}" -gt 0 ] && add_unique module_need "static_knowledge_index"
[ "${#debt_hygiene_hits[@]}" -gt 0 ] && add_unique module_need "debt_hygiene_gate"
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
    --arg feedback_loop_profile "$feedback_loop_profile" \
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
    --argjson risk_candidates "$(cat "$candidates_file")" \
    --argjson risk_context_decisions "$(cat "$context_file")" \
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
        feedback_loop_profile: $feedback_loop_profile,
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
        feedback_loop_profile: $feedback_loop_profile,
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
      feedback_loop_profile: $feedback_loop_profile,
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
      risk_candidates: $risk_candidates,
      risk_context_decisions: $risk_context_decisions,
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
