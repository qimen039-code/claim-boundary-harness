# Memory Meta Index Contract

Memory retrieval must start from a meta layer. The agent should never deep-scan project memories or incident payloads when a meta index can select the correct lane, category, and record first.

## Required Chain

```text
memory_summary / _META_INDEX / router manifest
-> category index / point index / outer_retrieval_surface
-> only matching capsule / ERR-* / SOL-* payload
```

For optional static knowledge layers, use the equivalent static chain:

```text
_STATIC_KNOWLEDGE_INDEX.md
-> one selected static manual page
-> optional memory capsule, source ledger, or test result only when linked
```

## Meta Index Fields

Every project, conversation, or skill memory library should expose a compact meta surface with these fields or equivalents:

| Field | Purpose |
| --- | --- |
| `memory_id` | Stable identifier for this memory lane, capsule, or record; do not rely on paths as identity. |
| `memory_type` | Project, conversation, global archive, common error corpus, self-reflection, skill memory, static knowledge, or another adopted type. |
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
| `source_tag` | Optional index-level source class for capsules or static notes, such as `user_claim`, `external_source`, `static_knowledge`, `memory_capsule`, or `inferred_synthesis`. |
| `belief_status` | Optional index-level verification state for capsules, such as `source_prior`, `bounded_claim`, `local_validated`, `conflicted`, or `rejected`. |
| `confidence_label` | Optional compact evidence-strength label for the current `belief_status`; full basis stays in the payload. |
| `lifecycle_stage` | Optional compact stage for reusable records: `raw_observation`, `working_memory`, `capsule`, or `archive`. |
| `retention_policy` | Optional retention rule such as `preserve`, `until_superseded`, `until_resolved`, `user_pinned`, or `delete_on_request`. |
| `promotion_reason` | Optional reason a record moved to a higher lifecycle stage or stronger guidance surface. |
| `decay_reason` | Optional reason a record was demoted, archived, superseded, or made lower priority. |
| `created_at` | Creation timestamp for initial ordering and audit. |
| `updated_at` | Last durable memory update; use for latest-continuation lookup, not every ordinary chat turn. |
| `last_accessed_at` | Optional retrieval hint for recent-use ranking; not a confidence or truth signal. |
| `link_policy` | Default link behavior, such as `link_only_by_default` or `explicit_merge_required`. |
| `last_reviewed` | Date or version marker for staleness checks. |

## Capsule Source Monitoring Fields

Memory capsules that contain reusable claims, compressed summaries, source-grounded learning, rejected paths, or synthesized guidance should use the source-monitoring schema:

```text
source_tag
belief_status
confidence
derived_from
source_monitoring
lifecycle
belief_trace or belief_trace_summary
```

See [source-monitoring-memory-schema.md](source-monitoring-memory-schema.md) for the full field contract.

Important boundaries:

- `belief_status` tracks the verification-process state. It is not a truth score.
- `confidence` tracks the evidence strength for assigning the current `belief_status`, not the probability that the original claim is true.
- `derived_from` is required when a capsule is compressed, synthesized, or derived from another memory capsule.
- `belief_trace_summary.current_status` must match `belief_status`.
- Optional numeric scores are adapter metadata. They should not replace `confidence.label` and `confidence.basis`.
- `lifecycle.stage` controls retrieval priority and retention handling. It does not make a record more or less true.
- `promotion_reason` and `decay_reason` explain lifecycle movement. They are routing and maintenance metadata, not claim evidence.
- Static knowledge notes should use `source_tag: static_knowledge` and normally start as `belief_status: source_prior` until checked against files, tests, schemas, or other evidence.
- Static knowledge retrieval results should use `derived_from.type` =
  `static_knowledge_page` when the selected snippet came from a static manual
  page.

## Retrieval Result Minimum

A memory or static-knowledge retrieval adapter should not return only a free-text snippet. Every selected result should carry enough metadata for the agent to keep source, provenance, and evidence boundaries intact.

Minimum result shape:

```json
{
  "memory_id": "MEM-DEMO-001",
  "snippet": "Short selected text, not a full history dump.",
  "source_tag": "memory_capsule",
  "belief_status": "bounded_claim",
  "confidence": {
    "label": "medium",
    "basis": "Status assigned from the capsule payload; no local runtime check was run in this retrieval step."
  },
  "derived_from": [
    {
      "type": "previous_capsule",
      "ref_id": "MEM-DEMO-000",
      "relationship": "distilled_from",
      "inherited_boundary": "source_prior"
    }
  ],
  "score_method": "none"
}
```

Rules:

- `source_tag`, `belief_status`, `confidence`, `derived_from`, and `score_method` are required on returned reusable memories or static knowledge notes.
- If no numeric retrieval score is returned, use `score_method: none` and omit `score`.
- If `score` is returned, `score_method` must name the method, such as `bm25`, `vector_cosine`, `graph_rank`, `rrf`, or an adopted local method.
- Retrieval scores rank candidate relevance. They do not replace `belief_status` or `confidence.basis`.
- Raw observations can be returned as evidence, but the result must say they are `raw_observation` or equivalent so the agent does not treat them as current guidance.

## Link And Timestamp Rules

Do not make the router a path map. Route by stable `memory_id`, `module_id`, lane, and intent; resolve paths through a registry, `_META_INDEX`, or machine index.

Use append-only link ledgers for relationships:

```text
continues
references
merged_into
supersedes
archived_as
```

Default continuation is link-only. A new conversation that continues an old one creates its own memory ID and appends a `continues` edge. It does not write new content into the old memory unless the user explicitly asks.

Explicit merges create a new merged memory, append `merged_into` edges, and mark old memories as sealed or redirected in indexes. Do not delete old payloads unless separately confirmed.

For fuzzy retrieval, first search `updated_at`, title, summary, retrieval terms, semantic anchors, and open loops in index-level records. Open payloads only after a small candidate set is selected.

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
ID | Type | Status | Updated At | Lifecycle Stage | Belief Status | Source Tag | Confidence | Summary | Retrieval Terms | Semantic Anchors | Applies | Not Applies | Linked Modules | Linked Records | Promotion Reason | Decay Reason | Supersedes | Superseded By
```

For paired incident records, keep `ERR-*` and `SOL-*` linked both ways. The index should be enough to decide whether the payload is relevant before opening it.

For static knowledge indexes, use the same selection discipline with smaller
rows. The row should be enough to choose `project-map.md`,
`entrypoints-and-commands.md`, `conventions.md`, or another static page before
opening it. Static pages should not be treated as current validation results
unless a linked evidence record says so.

## Missing Meta Rule

If a project has not adopted `_META_INDEX.md` yet, use the smallest available top-level index, router manifest, or skill manifest as a temporary meta layer. Mark the result as partially adapted and avoid treating a direct deep read as authoritative.

## Update Rule

When a new record changes current guidance:

1. Add or update the new row with `status: ACTIVE`.
2. Mark replaced rows as `SUPERSEDED_BY:<ID>` or equivalent.
3. Put the reverse link in the new row.
4. Keep raw logs separate from current guidance.
5. Keep project-specific memories inside the project lane, conversation-specific memories inside the conversation lane, and shared framework rules inside the whiteboard core.
6. Update `updated_at` when durable state changes.
7. Append link records for continuation, merge, archive, or supersession instead of rewriting unrelated payloads.
