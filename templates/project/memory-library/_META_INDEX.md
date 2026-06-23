# Memory Library Meta Index

Whiteboard template. Copy this library into one project lane, then replace all placeholders after adoption.

Mandatory retrieval rule:

```text
read this meta index
-> choose one category
-> read that category index
-> open only the matching capsule
```

Do not open category payloads before this file has selected the category. If this file is missing in an adopted project, treat that as an adaptation gap.

| Category | Root | Purpose | Status | Notes |
| --- | --- | --- | --- | --- |
| governance | `governance/` | Project rules, decisions, boundaries, and operating contracts. | TEMPLATE | Add real records after adoption. |
| memory_hierarchy | `memory_hierarchy/` | Reusable memory capsules, active context, progress notes, and supersession chains. | TEMPLATE | Keep capsule status and supersession explicit. |
| external_references | `external_references/` | Source notes, outside mechanisms, citations, and adoption boundaries. | TEMPLATE | Keep source boundary separate from local validation. |
| raw_logs | `raw_logs/` | Raw or near-raw observations that should not be treated as final memory. | TEMPLATE | Promote into another category only after review. |

For reusable memory capsules, use the source-monitoring schema fields: `source_tag` `belief_status` `confidence` `derived_from` `source_monitoring` `lifecycle` `belief_trace_summary`. Keep only compact routing fields in category indexes and open full payloads only when selected.

Retrieval outputs that leave this memory library should include these fields with the selected text: `source_tag` `derived_from` `belief_status` `confidence` `score_method`. If no numeric score is computed, use `score_method: none` and omit `score`.

Status values:

- `ACTIVE`: current guidance.
- `SUPERSEDED_BY:<ID>`: replaced by a newer record.
- `DEPRECATED`: retained for audit but not current guidance.
- `TEMPLATE`: placeholder or example only.
