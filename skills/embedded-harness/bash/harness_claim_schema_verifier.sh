#!/usr/bin/env bash
set -euo pipefail

CLAIM_JSON=""
CLAIM_FILE=""
FINAL_TEXT=""
OUTPUT_PATH=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
POLICY_PATH="$(cd "$SCRIPT_DIR/.." && pwd -P)/embedded_harness_policy.json"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --claim-json|-ClaimJson) CLAIM_JSON="${2:-}"; shift 2 ;;
    --claim-file|-ClaimFile) CLAIM_FILE="${2:-}"; shift 2 ;;
    --final-text|-FinalText) FINAL_TEXT="${2:-}"; shift 2 ;;
    --output|-OutputPath) OUTPUT_PATH="${2:-}"; shift 2 ;;
    --policy|-PolicyPath) POLICY_PATH="${2:-}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if ! command -v jq >/dev/null 2>&1; then
  echo '{"phase":"claim_schema_verifier","status":"blocked","issues":["jq_missing"]}'
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

if [ -n "$CLAIM_FILE" ]; then
  CLAIM_JSON="$(cat "$CLAIM_FILE")"
fi

issues=()
claims_checked=0

if [ -n "$CLAIM_JSON" ]; then
  if ! printf '%s' "$CLAIM_JSON" | jq empty >/dev/null 2>&1; then
    add_unique issues "claim_json_parse_failed"
  else
    claims_checked="$(printf '%s' "$CLAIM_JSON" | jq 'if type == "array" then length else 1 end')"
    for field in claim_type source_type evidence_boundary; do
      missing_count="$(printf '%s' "$CLAIM_JSON" | jq --arg field "$field" '[if type == "array" then .[] else . end | select((has($field) | not) or ((.[$field] | tostring) == ""))] | length')"
      if [ "$missing_count" -gt 0 ]; then
        add_unique issues "missing_${field}"
      fi
    done
    while IFS= read -r source_type; do
      [ -z "$source_type" ] && continue
      add_unique issues "missing_source_ref_for_${source_type}"
    done < <(printf '%s' "$CLAIM_JSON" | jq -r --argjson policy "$(cat "$POLICY_PATH")" '
      def tok: tostring | ascii_downcase | gsub("^[[:space:]]+|[[:space:]]+$"; "") | gsub("[[:space:]]+"; "_") | gsub("-+"; "_");
      ($policy.claim_schema_contract.source_ref_required_for // ["external_retrieval","memory_capsule_ref"] | map(tok)) as $required
      | if type == "array" then .[] else . end
      | (.source_type | tok) as $source_type
      | select(($required | index($source_type)) and ((has("source_ref") | not) or ((.source_ref | tostring) == "")))
      | $source_type
    ' | tr -d '\r')

    while IFS= read -r issue; do
      [ -z "$issue" ] && continue
      add_unique issues "$issue"
    done < <(printf '%s' "$CLAIM_JSON" | jq -r --argjson policy "$(cat "$POLICY_PATH")" '
      def tok: tostring | ascii_downcase | gsub("^[[:space:]]+|[[:space:]]+$"; "") | gsub("[[:space:]]+"; "_") | gsub("-+"; "_");
      ($policy.claim_schema_contract.allowed_source_types // [] | map(tok)) as $sources
      | ($policy.claim_schema_contract.evidence_boundary_enum // [] | map(tok)) as $boundaries
      if type == "array" then .[] else . end
      | (.source_type | tok) as $source_type
      | (.evidence_boundary | tok) as $boundary
      | if (($sources | length) > 0 and (($sources | index($source_type)) | not)) then
          "unsupported_source_type:\(.source_type)"
        elif (($boundaries | length) > 0 and (($boundaries | index($boundary)) | not)) then
          "unsupported_evidence_boundary:\(.evidence_boundary)"
        else empty end
    ' | tr -d '\r')
  fi
fi

if [ -n "$FINAL_TEXT" ]; then
  while IFS= read -r phrase; do
    [ -z "$phrase" ] && continue
    if printf '%s' "$FINAL_TEXT" | grep -Fqi -- "$phrase"; then
      if [ "$claims_checked" -eq 0 ]; then
        add_unique issues "blocked_claim_phrase_without_schema:${phrase}"
      else
        strong_match_count="$(printf '%s' "$CLAIM_JSON" | jq -r --argjson policy "$(cat "$POLICY_PATH")" '
          def tok: tostring | ascii_downcase | gsub("^[[:space:]]+|[[:space:]]+$"; "") | gsub("[[:space:]]+"; "_") | gsub("-+"; "_");
          ($policy.claim_schema_contract.strong_claim_evidence_boundaries // [] | map(tok)) as $strong
          | [if type == "array" then .[] else . end
             | select(($strong | index(.evidence_boundary | tok)) != null)] | length
        ' | tr -d '\r')"
        if [ "$strong_match_count" -eq 0 ]; then
          add_unique issues "insufficient_evidence_boundary_for_strong_phrase:${phrase}"
        fi
      fi
    fi
  done < <(jq -r '.blocked_claim_phrases_without_schema[]?' "$POLICY_PATH" | tr -d '\r')
fi

status="pass"
if [ "${#issues[@]}" -gt 0 ]; then
  status="blocked"
fi

result="$(
  jq -n \
    --arg phase "claim_schema_verifier" \
    --arg status "$status" \
    --argjson claims_checked "$claims_checked" \
    --argjson issues "$(json_array "${issues[@]}")" \
    '{
      ts: (now | todateiso8601),
      phase: $phase,
      status: $status,
      claims_checked: $claims_checked,
      issues: $issues,
      rule: "schema enum and evidence-boundary check only; no extra model judgment"
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
