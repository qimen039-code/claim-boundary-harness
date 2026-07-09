# Memory Linking Contract

Memory linking keeps independent memory lanes connected without mixing their payloads.

The framework uses a hybrid scheme:

```text
stable memory_id / module_id
-> self-describing metadata in each lane or module
-> generated or maintained registry/index for id-to-path lookup
-> append-only link ledger for continuation, reference, merge, supersession, and archive edges
-> updated_at timestamps for cheap latest-check retrieval
-> active-lane filtering before latest lookup
-> bounded link depth with merge suggestions
-> meta-first lookup before payload reads
```

Do not put every concrete path into the router. The router should output identifiers and intent, such as `memory_lane`, `memory_id`, `module_id`, `conversation_memory_decision`, or `link_intent`. A registry, meta index, or link ledger resolves the path.

## Required Memory Metadata

Every project memory, conversation memory, and archive capsule should expose these fields or equivalents in its meta index or machine index:

```yaml
memory_id: conv_YYYYMMDD_shortid
memory_type: conversation | project | global_archive | backup_snapshot | common_error_corpus | self_reflection
project_lane: PROJECTLESS | example_project | global
conversation_id: optional_host_thread_or_session_id
status: active | paused | sealed | archived | merged | superseded | quarantined | template
title: short human title
summary: compact current-state summary
created_at: YYYY-MM-DDTHH:MM:SS+08:00
updated_at: YYYY-MM-DDTHH:MM:SS+08:00
retrieval_terms: []
semantic_anchors: []
open_loops: []
link_policy: link_only_by_default
max_continuation_depth: 5
active_successor_memory_id: null
redirect_read_to: null
```

Update `updated_at` only when durable memory state changes: accepted decisions, open loops, applied solutions, retrieval terms, links, merge state, archive state, or summary capsules. Do not update it for every ordinary chat message.

## Active Conversation Rule

`latest` never means globally latest across all projects. Resolve active conversation candidates in this order:

```text
current project lane or PROJECTLESS lane
-> status in active / paused / checkpoint_candidate
-> not sealed, archived, merged, or superseded
-> matching conversation/thread scope when known
-> highest updated_at
```

If the current lane has no match and the user explicitly asks for historical lookup, then check the global archive index. Do not jump from one project lane to another just because another memory has a newer timestamp.

## Cold Evidence And Backup Boundary

Backups, sealed snapshots, and recovery copies are cold evidence, not active
memory lanes. They may help prove what an instruction, memory, or artifact used
to say, but they must not be injected as current guidance by default.

Read cold evidence only for explicit recovery, historical audit, comparison, or
root-cause analysis. When it is read, keep the result read-only and expose the
boundary in the link or audit record:

```json
{
  "source_lane": "backup_snapshot:AGENTS-20260709",
  "target_lane": "current_global_rules",
  "purpose": "historical_comparison",
  "read_mode": "read_only",
  "write_policy": "no_write_from_backup",
  "merge_allowed": false,
  "evidence_boundary": "cold evidence; not active guidance"
}
```

Promotion from a backup or archive into an active lane requires a normal memory
write/update route, source-monitoring metadata, and explicit user or project
authorization. A backup path, newer timestamp, or matching keyword is never a
merge decision.

## Link Ledger

Use JSONL for links because links are append-only facts. Recommended file names:

```text
memory_links.jsonl
references.jsonl
supersession.jsonl
archive_index.jsonl
conversation_index.jsonl
```

Recommended link record:

```json
{
  "link_id": "LINK-TEMPLATE-001",
  "link_type": "continuation",
  "from_memory_id": "conv_old",
  "to_memory_id": "conv_new",
  "from_conversation_id": "optional_host_conversation_id",
  "to_conversation_id": "optional_host_conversation_id",
  "created_at": "YYYY-MM-DDTHH:MM:SS+08:00",
  "created_by": "user_explicit_request",
  "reason": "continue previous conversation by explicit request",
  "summary_snapshot": "Short snapshot imported from source meta only.",
  "write_policy": "new_memory_only",
  "evidence_boundary": "meta_snapshot_only"
}
```

Required fields: `link_id`, `link_type`, `from_memory_id`, `to_memory_id`, `created_at`, `created_by`, `write_policy`, and `evidence_boundary`. Host-specific `conversation_id` fields are optional metadata, not identity.

Allowed `link_type` values:

| Edge | Meaning | Write behavior |
| --- | --- | --- |
| `continuation` | A new conversation continues from an older conversation memory. | Write new content only to the new memory. |
| `reference` | One lane points to another file, source, project, or memory without copying payload. | No payload copy. |
| `merge` | Two or more memories were explicitly merged into a new memory. | Old memories become sealed or redirected. |
| `supersession` | A newer record replaces an older record. | Keep both sides linked. |
| `archive` | A lane was moved, copied, or summarized into cold archive. | Preserve source reference and operation type. |

## Continuation Rule

When a new conversation continues an old conversation, default to link-only continuation:

```text
read old memory meta first
-> create new conversation memory with its own memory_id
-> copy only a bounded summary_snapshot from old meta/current-state summary
-> append continues edge old -> new
-> write all new durable state into the new memory only
```

Do not write into the old conversation memory unless the user explicitly asks to update that specific old memory.

## Link Depth Rule

Link-only continuation should not grow forever. Track continuation depth in the active index or by following `continuation` links through index-level metadata.

Default threshold:

```text
max_continuation_depth: 5
```

When adding another continuation would exceed the threshold, the router should set `merge_suggested` or equivalent boundary context and ask whether to create a merged memory. It must not auto-merge without explicit user instruction.

## Explicit Merge Rule

Only merge memories when the user explicitly asks for merge/consolidation.

```text
old memory A + old memory B
-> new merged memory C
-> C declares merged_from: [A, B]
-> link ledger appends merged_into edges A -> C and B -> C
-> old memories become sealed, merged, or redirected in their own meta/index rows and the global/conversation index
```

A merge is not a rewrite of hidden history. Keep old payloads available for audit unless the user separately asks for deletion or redaction. Deletion remains high risk.

Redirect semantics apply to both retrieval indexes and read actions:

```text
old _META_INDEX / index.json status: merged
old merged_into: new_memory_id
old redirect_read_to: new_memory_id
conversation_index active_successor_memory_id: new_memory_id
```

Normal lookup follows the redirect to the merged memory. Audit lookup may still open the sealed source memory after making the boundary explicit.

## Latest And Fuzzy Retrieval

For "continue the previous conversation" or similar requests, use the lane-scoped timestamp shortcut first:

```text
read current lane conversation index first
-> filter by current project lane or PROJECTLESS lane
-> exclude sealed / archived / merged / superseded memories
-> sort active conversation memories by updated_at descending
-> choose the latest likely candidate
-> open only its current-state summary
```

If the user remembers only keywords or vague content, use layered fuzzy lookup:

```text
conversation_index.jsonl / index.json
-> match title, summary, retrieval_terms, semantic_anchors, open_loops
-> inspect at most a few candidate summaries
-> ask the user to choose when ambiguous
-> only then open matching payload records
```

Do not jump to full transcript or full payload scans unless the user explicitly asks for an audit or no index-level candidate is enough.

## Registry Boundary

Use stable IDs plus registries instead of path-heavy routing:

```text
router emits module_id / memory_id / link_intent / link_decision_status
-> registry or index resolves relative path
-> meta index chooses one payload
```

For stable modules, an adopter may keep a small `module.json` beside each module and generate a central registry. The registry is a lookup surface, not another always-loaded memory layer.

## Enforcement Boundary

Conversation linking should be enforced through the same selective runtime boundary as other gates when the host supports it.

If a task requires continuation, referenced-conversation lookup, explicit merge, archive, or cross-conversation update, the runtime should require a resolved link decision before the first protected tool call:

```text
conversation_link_required
+ link_decision_status != resolved
+ host has PreToolUse / wrapper / tool proxy
-> block with conversation_link_decision_required
```

If the host has no pre-tool or pre-action interception point, this requirement degrades to advisory. Do not claim hard enforcement for runtimes that can bypass the gate.
