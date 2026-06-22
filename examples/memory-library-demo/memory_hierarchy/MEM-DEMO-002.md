# MEM-DEMO-002

status: ACTIVE
record_type: project_memory_capsule
source_tag: inferred_synthesis
belief_status: bounded_claim
purpose_anchor: Route project tasks without reading unrelated memory.
meaning_anchor: The agent should identify the active project lane, then read only the memory category needed for the task.
retrieval_terms:
- routing note
- project boundary
- claim boundary
content_summary: For a project task, use the project instruction file, the memory meta index, and only the relevant category index before opening a capsule.
supersedes: MEM-DEMO-001
superseded_by: none
applicable_boundaries:
- project task routing
- new conversation continuation
- memory lookup
non_applicable_boundaries:
- unrelated project lanes
- global framework changes
claim_boundary: This record is a demo shape, not evidence that a specific runtime honored the route.
evidence_boundary: Synthetic demo record.
confidence:
  label: medium
  basis: Status is bounded_claim because this capsule has explicit applicability and claim boundaries but is still a synthetic demo record.
derived_from:
- type: previous_capsule
  ref_id: MEM-DEMO-001
  relationship: corrects
  correction_evidence_ref: RAW-DEMO-001
  inherited_boundary: previous record lacked explicit claim boundary
source_monitoring:
  observation_state: resolved
  trigger_reason: manual_review
  last_checked: YYYY-MM-DDTHH:MM:SSZ
belief_trace_summary:
  initial_status: source_prior
  current_status: bounded_claim
  intermediate_steps_count: 1
  archived_trace_ref: none
review_rule: Keep this capsule short. Move raw observations to `raw_logs` and source notes to `external_references`.
