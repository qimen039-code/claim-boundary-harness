# Memory Library Meta Index

Whiteboard template. Copy this library into one project lane, then replace all placeholders after adoption.

Mandatory retrieval rule:

```text
read this meta index
-> check lane_state
-> choose one category
-> read that category index
-> open only the matching capsule
```

Do not open category payloads before this file has selected the category. If this file is missing in an adopted project, treat that as an adaptation gap.

```text
lane_state: active
```

If `lane_state` is `frozen_readonly`, do not inject this library as active
memory and do not write to it. Read it only for explicit audit, migration, or
A/B/C comparison. If `lane_state` is `cleared`, use only the audit marker or an
explicit archive link.

| Category | Root | Purpose | Status | Notes |
| --- | --- | --- | --- | --- |
| governance | `governance/` | Project rules, decisions, boundaries, and operating contracts. | TEMPLATE | Add real records after adoption. |
| memory_hierarchy | `memory_hierarchy/` | Reusable memory capsules, active context, progress notes, and supersession chains. | TEMPLATE | Keep capsule status and supersession explicit. |
| external_references | `external_references/` | Source notes, outside mechanisms, citations, and adoption boundaries. | TEMPLATE | Keep source boundary separate from local validation. |
| raw_logs | `raw_logs/` | Raw or near-raw observations that should not be treated as final memory. | TEMPLATE | Promote into another category only after review. |

For reusable memory capsules, use the source-monitoring schema fields: `source_tag` `belief_status` `confidence` `derived_from` `source_validity_dependency` `source_monitoring` `lifecycle` `belief_trace_summary`. Add optional `feedback_loop` only for records that should predict and check future behavior. Keep only compact routing fields in category indexes and open full payloads only when selected.

Retrieval outputs that leave this memory library should include these fields with the selected text: `source_tag` `derived_from` `belief_status` `confidence` `score_method`. If no numeric score is computed, use `score_method: none` and omit `score`.

Reusable memory content should be context-complete and should preserve the
original source language. Use English structure fields for adapter stability,
but keep Chinese content Chinese and English content English.

Hybrid retrieval is meta-first: after this file selects a category, use lane,
domain, time, source, status, lifecycle, retrieval terms, exact phrase,
original-language keyword, Chinese character n-gram, or English term matching
before opening payloads. Optional lexical ranking is adapter metadata only.
Adapters may expose this as `hybrid_retrieval_profile:
meta_first_hybrid_enhancement` or `meta_first_hybrid_required`, but the profile
only strengthens this bounded chain. It does not replace this meta index,
category indexes, source-monitoring, or claim gates.

Durable project-memory writes should expose `memory_write_profile:
context_complete_required`; explicit reusable capsules should use
`strict_capsule_required`. The profile constrains write shape and does not
authorize cross-lane writes by itself.

Before reading a selected payload, the route or decision layer should choose the
smallest sufficient reading profile: `baseline`, `evidence_window`,
`middle_safe`, or `full_audit`. Baseline reads identify source shape and use the
smallest native evidence window: heading block, complete JSON object, JSONL
record, code symbol, raw-session line window, or test-output block. If no map
exists, create a temporary micro-map. Evidence reads record unread zones as
verification debt when the claim depends on partial reading.

For long payloads or multi-hop claims, use middle-safe evidence layout:
evidence inventory plus original windows, per-window conclusion cards before
synthesis, adjacent evidence clusters, key evidence reminders near strong
claims, and `position_risk` markers. If head/tail anchors are insufficient for
a strong claim, reread bounded middle windows around structural anchors before
promoting the claim.

When a selected record includes `feedback_loop`, use `feedback_loop_profile`
to decide the depth. `index_hint` and `record_candidate` stay compact;
`prevention_review` and `explicit_cycle` may apply the loop as part of memory
reuse. Treat predictions as hypotheses until later evidence verifies them. Index
rows may expose only compact states such as `feedback_loop: pending`, `matched`,
or `failed`; calibration details belong in the payload.

If two selected records conflict, use the source-monitoring conflict policy:
same/higher confidence plus explicit evidence may supersede; lower-confidence
contradictions coexist as conflicted/audit-required records. If an upstream
required source becomes invalid, retracted, or deleted, cascade the dependency
before treating the derived capsule as reusable guidance.

Status values:

- `ACTIVE`: current guidance.
- `SUPERSEDED_BY:<ID>`: replaced by a newer record.
- `DEPRECATED`: retained for audit but not current guidance.
- `TEMPLATE`: placeholder or example only.
