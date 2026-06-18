# Conversation Memory Lane

Conversation Memory Lane covers long-running conversations that have not been assigned to a project lane.

It closes a common gap: a user may keep working in an ordinary chat until the context becomes too long, but the work is not yet a project and therefore does not benefit from project memory. Conversation memory gives that chat an isolated, meta-first memory lane without polluting project memory or global memory.

## Position In The Memory Model

```text
project memory lane
-> project-owned rules, decisions, progress, incidents, and references

conversation memory lane
-> one long-running conversation or thread, isolated by session/thread id

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
-> conversation_state.md or one JSONL record family
-> only matching record(s)
```

Do not scan all conversation memory files because a context-compressed chat asks for prior context. Read `_META_INDEX.md` first, then select the smallest matching file.

## Recommended File Layout

```text
conversation-memory/
  _META_INDEX.md
  conversation_state.md
  index.json
  decisions.jsonl
  open_loops.jsonl
  errors_and_solutions.jsonl
  references.jsonl
  persona_state.md
```

Field intent:

- `_META_INDEX.md`: first-read routing surface, scope, lane id, record families, freshness, and cross-reference rules.
- `conversation_state.md`: human-readable current state summary.
- `index.json`: machine-readable retrieval surface for scripts or agents.
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
```

`create_or_update_current_conversation` requires an explicit user request. `checkpoint_candidate` is the router saying the conversation is becoming durable; the adopting agent can ask, create a lightweight checkpoint, or state the assumption according to local policy.

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

## Template

Use `templates/conversation-memory/` as a blank starting point. The template is synthetic and contains no real conversation history.

## Archive Boundary

When a conversation lane ends, archive it by moving or copying the lane directory by default. Do not regenerate the conversation memory as a new "old memory" file. Summary capsules are allowed only when the user explicitly asks for compression, migration, de-identification, public release, or storage reduction.
