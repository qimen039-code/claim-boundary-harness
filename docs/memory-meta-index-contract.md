# Memory Meta Index Contract

Memory retrieval must start from a meta layer. The agent should never deep-scan project memories or incident payloads when a meta index can select the correct lane, category, and record first.

## Required Chain

```text
memory_summary / _META_INDEX / router manifest
-> category index / point index / outer_retrieval_surface
-> only matching capsule / ERR-* / SOL-* payload
```

## Meta Index Fields

Every project, conversation, or skill memory library should expose a compact meta surface with these fields or equivalents:

| Field | Purpose |
| --- | --- |
| `lane` | The project, conversation, or global lane that owns the memory. |
| `scope` | The boundary where this memory applies. |
| `category` | Governance, memory hierarchy, external references, raw logs, semantic anchors, ERR points, SOL points, or another local category. |
| `record_type` | Capsule, decision, error point, solution point, source ledger, progress state, rule, or template. |
| `status` | Active, superseded, deprecated, template, draft, or blocked. |
| `retrieval_terms` | Short bilingual or domain-specific terms that should route here. |
| `applies_when` | Positive trigger surface. |
| `does_not_apply_when` | Explicit non-applicable boundary. |
| `linked_modules` | Project router, semantic anchor file, skill, gate, or script that should be opened next. |
| `linked_records` | Related capsule IDs, ERR/SOL pairs, supersession links, or source-ledger IDs. |
| `last_reviewed` | Date or version marker for staleness checks. |

## Default Retrieval Budget

The default budget for ordinary memory lookup is intentionally small:

```text
max meta indexes: 1
max category indexes: 1
max payloads: 2
full history scan: false
```

Use a broader scan only when the task is explicitly a full audit, migration, cleanup, or memory-library rebuild.

## Category Index Row Shape

Use a compact table or structured record:

```text
ID | Type | Status | Summary | Retrieval Terms | Applies | Not Applies | Linked Modules | Linked Records | Supersedes | Superseded By
```

For paired incident records, keep `ERR-*` and `SOL-*` linked both ways. The index should be enough to decide whether the payload is relevant before opening it.

## Missing Meta Rule

If a project has not adopted `_META_INDEX.md` yet, use the smallest available top-level index, router manifest, or skill manifest as a temporary meta layer. Mark the result as partially adapted and avoid treating a direct deep read as authoritative.

## Update Rule

When a new record changes current guidance:

1. Add or update the new row with `status: ACTIVE`.
2. Mark replaced rows as `SUPERSEDED_BY:<ID>` or equivalent.
3. Put the reverse link in the new row.
4. Keep raw logs separate from current guidance.
5. Keep project-specific memories inside the project lane, conversation-specific memories inside the conversation lane, and shared framework rules inside the whiteboard core.
