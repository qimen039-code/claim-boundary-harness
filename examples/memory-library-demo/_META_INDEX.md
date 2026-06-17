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

| Category | Root | Purpose | Current Example | Notes |
| --- | --- | --- | --- | --- |
| governance | `governance/` | Rules, decisions, boundaries, and operating contracts. | `GOV-DEMO-001` | Use for durable project rules. |
| memory_hierarchy | `memory_hierarchy/` | Memory capsules, active context, progress, and supersession chains. | `MEM-DEMO-002` | Shows an old capsule superseded by a newer one. |
| external_references | `external_references/` | Source notes and adoption boundaries. | `EXT-DEMO-001` | Source notes are not local validation. |
| raw_logs | `raw_logs/` | Raw observations retained for audit. | `RAW-DEMO-001` | Raw records are not final guidance. |
