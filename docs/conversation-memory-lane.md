# Conversation Memory Lane

Conversation Memory Lane covers long-running conversations that have not been assigned to a project lane.

It closes a common gap: a user may keep working in an ordinary chat until the context becomes too long, but the work is not yet a project and therefore does not benefit from project memory. Conversation memory gives that chat an isolated, meta-first memory lane without polluting project memory or global memory.

## Position In The Memory Model

```text
project memory lane
-> project-owned rules, decisions, progress, incidents, and references

conversation memory lane
-> one long-running conversation or thread, isolated by session/thread id
-> can link to older conversation lanes without writing into them

common error corpus
-> reusable small error-and-solution samples across work surfaces

global memory lane
-> manual-only cross-project rules or durable user-approved context

optional global archive
-> cold index and sealed snapshots; not active memory
```

## Creation Rule

Do not create a conversation memory lane for every short chat.

Create or update it only when the router detects one of these:

- the user explicitly asks to remember, checkpoint, or continue this conversation later;
- the conversation accumulates repeated decisions, open loops, versioning, deployment, architecture, or troubleshooting state;
- context compression or handoff risk becomes visible;
- the conversation is projectless but has become a durable workflow;
- the user asks another conversation to reference this conversation's memory.

If project signals become strong enough for a real project lane, mark `projectization_decision: emergent_project_candidate` before writing project memory. Until the user chooses a project lane, the conversation memory may hold a checkpoint and references, but it should not silently become project memory.

## Isolation Rules

- Current conversation writes only to its own conversation memory lane.
- Other conversations may read this lane only by explicit reference or user request.
- New conversations that continue this lane should create their own memory and append a `continues` link; they should not write into the old lane by default.
- Other conversations may not write to this lane unless the user explicitly asks to update that specific conversation memory.
- Project memory must not be written from conversation memory by default.
- Conversation memory must not copy another project's private payloads. Use references and boundaries instead.
- Global memory is not inferred from conversation memory.
- Global archive is not checked unless the active lane has no match or the user asks for archive lookup.
- Persona state may be kept in this lane only for the current conversation and may not affect work decisions.

## Mandatory Meta-First Retrieval

Conversation memory follows the same retrieval rule as project memory:

```text
conversation-memory/_META_INDEX.md
-> conversation_state.md, index.json, memory_links.jsonl, or one JSONL record family
-> only matching record(s)
```

Do not scan all conversation memory files because a context-compressed chat asks for prior context. Read `_META_INDEX.md` first, then select the smallest matching file.

## Recommended File Layout

```text
conversation-memory/
  _META_INDEX.md
  conversation_state.md
  index.json
  memory_links.jsonl
  decisions.jsonl
  open_loops.jsonl
  errors_and_solutions.jsonl
  references.jsonl
  persona_state.md
```

Field intent:

- `_META_INDEX.md`: first-read routing surface, scope, lane id, record families, freshness, and cross-reference rules.
- `conversation_state.md`: human-readable current state summary.
- `index.json`: machine-readable retrieval surface for scripts or agents, including `memory_id`, `created_at`, `updated_at`, retrieval terms, and link policy.
- `memory_links.jsonl`: append-only continuation, reference, merge, archive, and supersession edges.
- `decisions.jsonl`: append-only decision records.
- `open_loops.jsonl`: unresolved questions, tasks, and verification debt.
- `errors_and_solutions.jsonl`: paired lightweight errors and applied solutions discovered in this conversation.
- `references.jsonl`: links to files, repositories, docs, project memory records, or other conversation lanes without copying their payloads.
- `persona_state.md`: optional conversation-only tone or companion state. It is default-off and cannot affect facts, risk, verification, project boundaries, memory boundaries, search, claim gates, or tests.

## Router Contract

Recommended receipt additions:

```text
conversation_memory_decision
conversation_signals
```

Recommended values:

```text
conversation_memory_decision:
  none
  create_or_update_current_conversation
  checkpoint_candidate
  read_referenced_conversation
  explicit_cross_conversation_update

link_intent:
  none
  continue_from_latest
  continue_from_referenced_memory
  merge_memories_explicit
  archive_or_seal_memory
```

`create_or_update_current_conversation` requires an explicit user request. `checkpoint_candidate` is the router saying the conversation is becoming durable; the adopting agent can ask, create a lightweight checkpoint, or state the assumption according to local policy.

## Continuation And Merge Policy

Default continuation is link-only:

```text
old conversation memory
-> new conversation memory with a new memory_id
-> append continues edge old -> new in memory_links.jsonl or global link ledger
-> copy only a bounded summary snapshot from the old meta/current-state summary
-> write new durable state only to the new memory
```

Do not mutate the old memory just because a new conversation continues it. If the user explicitly asks to merge two conversations, create a new merged memory, append `merged_into` links, mark old memories as sealed or redirected in indexes, and keep old payloads for audit unless deletion is separately confirmed.

Use `updated_at` to support "continue the previous conversation" lookups. If the user remembers only vague keywords, search the index-level fields first: title, summary, retrieval terms, semantic anchors, and open loops. Ask the user to choose among candidates when ambiguous before opening payload records.

See [memory-linking-contract.md](memory-linking-contract.md) for the cross-lane link schema.

## Write Policy

Write only compact durable state:

- decisions the user accepted;
- open loops that matter for later continuation;
- explicit constraints and boundaries;
- reusable errors plus applied solutions;
- references to outside material and their evidence boundaries.

Do not write:

- every ordinary reply;
- raw transcripts by default;
- private project content copied from another lane;
- credentials, personal values, or sensitive payloads;
- speculative claims without evidence labels.

## Capsule Compression Schema

When a conversation lane is summarized into a reusable memory capsule, use the same source-monitoring fields as project memory:

```text
source_tag
belief_status
confidence
derived_from
source_monitoring
lifecycle
belief_trace_summary
```

Typical conversation-memory compression starts as `source_tag: conversation_memory`. If the capsule is distilled from prior chat state or older capsules, `derived_from` must preserve the source memory ID, source record IDs, and inherited boundary.

Do not promote a conversation-derived claim to `local_validated` unless there is local file, test, tool, or explicit evidence for that status. Most conversation summaries should remain `source_prior` or `bounded_claim`.

When a conversation memory is returned to an agent, the selected result should include these fields: `source_tag` `derived_from` `belief_status` `confidence` `score_method`. If no numeric retrieval score was computed, use `score_method: none` and omit `score`.

See [source-monitoring-memory-schema.md](source-monitoring-memory-schema.md) for the complete field contract.

## Template

Use `templates/conversation-memory/` as a blank starting point. The template is synthetic and contains no real conversation history.

## Archive Boundary

When a conversation lane ends, archive it by moving or copying the lane directory by default. Do not regenerate the conversation memory as a new "old memory" file. Summary capsules are allowed only when the user explicitly asks for compression, migration, de-identification, public release, or storage reduction.
