# MEM-DEMO-002

status: ACTIVE
record_type: project_memory_capsule
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
review_rule: Keep this capsule short. Move raw observations to `raw_logs` and source notes to `external_references`.
