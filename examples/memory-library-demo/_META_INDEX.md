# Demo Memory Library Meta Index

This is a synthetic project memory library. It demonstrates the structure only.

Mandatory retrieval rule:

```text
read this file
-> choose one category
-> read the category index
-> open only the matching capsule
```

This file is the required first read for the demo memory library. The category indexes and capsule payloads are second- and third-step reads.

Memory capsules in `memory_hierarchy/` use source-monitoring and lifecycle fields so the index can route by `source_tag` `belief_status`, confidence label, and lifecycle stage before opening payloads.

Retrieval outputs should return these fields with the selected text: `source_tag` `derived_from` `belief_status` `confidence` `score_method`.

| Category | Root | Purpose | Current Example | Notes |
| --- | --- | --- | --- | --- |
| governance | `governance/` | Rules, decisions, boundaries, and operating contracts. | `GOV-DEMO-001` | Use for durable project rules. |
| memory_hierarchy | `memory_hierarchy/` | Memory capsules, active context, progress, and supersession chains. | `MEM-DEMO-002` | Shows an old capsule superseded by a newer one. |
| external_references | `external_references/` | Source notes and adoption boundaries. | `EXT-DEMO-001` | Source notes are not local validation. |
| raw_logs | `raw_logs/` | Raw observations retained for audit. | `RAW-DEMO-001` | Raw records are not final guidance. |
