# MEM-DEMO-001

status: SUPERSEDED_BY:MEM-DEMO-002
record_type: project_memory_capsule
source_tag: model_hypothesis
belief_status: rejected
purpose_anchor: Preserve the previous routing note for audit.
meaning_anchor: Older records should remain traceable but should not drive current behavior.
retrieval_terms:
- routing note
- old rule
content_summary: The previous note did not include a clear claim boundary.
supersedes: none
superseded_by: MEM-DEMO-002
evidence_boundary: Synthetic demo record.
confidence:
  label: high
  basis: Status is rejected for current guidance because MEM-DEMO-002 supersedes it and the missing claim boundary is recorded in this synthetic example.
lifecycle:
  stage: capsule
  retention_policy: preserve
  last_accessed_at: YYYY-MM-DDTHH:MM:SSZ
  promotion_reason: Superseded demo capsule retained as audit memory.
  decay_reason: superseded_by_newer_fix
derived_from:
- type: raw_log
  ref_id: RAW-DEMO-001
  relationship: distilled_from
  inherited_boundary: old demo note retained for audit only
source_monitoring:
  observation_state: resolved
  trigger_reason: manual_review
  last_checked: YYYY-MM-DDTHH:MM:SSZ
belief_trace_summary:
  initial_status: source_prior
  current_status: rejected
  intermediate_steps_count: 1
  archived_trace_ref: none
current_use_rule: Do not use as current guidance. Open `MEM-DEMO-002` instead.
