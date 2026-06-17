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

Status values:

- `ACTIVE`: current guidance.
- `SUPERSEDED_BY:<ID>`: replaced by a newer record.
- `DEPRECATED`: retained for audit but not current guidance.
- `TEMPLATE`: placeholder or example only.
