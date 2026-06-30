# Memory Routing Contract

Memory use is a router decision. The framework should not open memory just because memory exists, and it should not write memory just because an error happened.

## Contract Fields

Add these fields to the routing receipt:

```text
memory_need
hybrid_retrieval_profile
memory_mode
memory_write_profile
memory_lane
record_intent
projectization_decision
conversation_memory_decision
link_intent
```

Conversation ledger is not a separate memory lane. It is a derived index that
may be selected by `module_need: conversation_ledger_index` or by local adapter
policy when raw host sessions must be linked to project or conversation memory.

Meanings:

| Field | Values | Purpose |
| --- | --- | --- |
| `memory_need` | `none`, `meta_only`, `index_only`, `capsule_payload`, `paired_err_sol`, `common_error_corpus` | How deep memory lookup should go. |
| `hybrid_retrieval_profile` | `none`, `meta_first_hybrid_enhancement`, `meta_first_hybrid_required` | Whether to augment meta-first lookup with bounded lexical, original-language, Chinese n-gram, English term, and optional lexical-rank signals. |
| `memory_mode` | `none`, `read`, `write`, `update` | Whether the task should skip, read, write, or update memory. |
| `memory_write_profile` | `none`, `context_complete_required`, `strict_capsule_required` | Whether a selected write/update must satisfy context-complete or strict reusable-capsule shape. |
| `memory_lane` | `none`, `current_project`, `current_conversation`, `referenced_conversation`, `emergent_project_candidate`, `common_error_corpus`, `self_reflection_matrix`, `global_inbox` | Where the memory action belongs. |
| `record_intent` | `no_record`, `explicit_user_request`, `inferred_reusable_error`, `projectization_review`, `conversation_checkpoint`, `explicit_conversation_memory_request` | Why a record would be written. |
| `projectization_decision` | `not_project`, `current_project`, `emergent_project_candidate` | Whether projectless work is becoming a durable project lane. |
| `conversation_memory_decision` | `none`, `create_or_update_current_conversation`, `checkpoint_candidate`, `read_referenced_conversation`, `explicit_cross_conversation_update` | Whether projectless long-chat state needs an isolated conversation memory lane. |
| `link_intent` | `none`, `continue_from_latest`, `continue_from_referenced_memory`, `merge_memories_explicit`, `archive_or_seal_memory` | Whether this memory action should create or follow a link without mixing payloads. |

## Recording Rules

Explicit user phrases such as "record this error", "remember this issue", or equivalent local-language wording should route to memory writing after lane and sensitivity checks.

Small but reusable mistakes should go to a common error corpus first as compact error-and-solution records. Full paired `ERR-*` / `SOL-*` records are reserved for high-impact incidents, repeated failures, or explicit self-reflection requests.

Ordinary chat and small corrected mistakes should not create memory records by default.

Long-running projectless conversations may create a `current_conversation` lane when the user explicitly asks for a checkpoint or when durable conversation signals accumulate. This lane is isolated by conversation or thread id, can be read by other conversations only through explicit reference, and cannot write another conversation's memory unless the user explicitly asks.

When raw host session logs are available, first write or update a conversation
ledger record for the session. Promote to a full conversation memory lane only
when explicit user intent or full-lane triggers apply. The ledger points to raw
sessions and artifacts; the memory lane stores decisions, open loops, reusable
constraints, and rollups.

Full-lane triggers are grouped so one class of durable signal can be acted on
without inflating the whole trigger list. Context compaction or loss can trigger
on one hit; durable decisions, open loops, and artifact/code-change clusters
use group thresholds. A ledger summary is not a fact source for memory: promote
only records that retain raw references, evidence boundaries, and source
monitoring.

Conversation memory and ledger maintenance may be semi-automatic only after the
router or decision layer selects a bounded write/update path. In practice this
means `auto`/`doctor`/`refresh` can run at task, decision, artifact, stop, or
final boundaries, but only for the active lane and only after stat or trigger
checks say the ledger is stale or the conversation has crossed a full-lane
threshold. This is not permission to auto-write every memory, backfill every raw
session, or treat a ledger summary as promoted fact.

When a new conversation continues an older one, default to `link_intent: continue_from_latest` or `continue_from_referenced_memory`. Create a new memory lane and append a `continues` link. Do not write into the old lane by default.

When the user explicitly asks to merge conversations, use `link_intent: merge_memories_explicit`. Create a new merged memory and append `merged_into` links from the old memory IDs.

When the route writes or updates a reusable memory capsule, apply the source-monitoring schema from [source-monitoring-memory-schema.md](source-monitoring-memory-schema.md). In particular, compressed or synthesized memory must preserve `derived_from`, and untested conversation or source-derived claims should remain `source_prior` or `bounded_claim`.

When `memory_need` is not `none`, adapters may expose
`hybrid_retrieval_profile: meta_first_hybrid_enhancement`. Tasks that read or
write reusable capsules, ERR/SOL records, common-error records, conversation
state, or memory links should expose `meta_first_hybrid_required`. This profile
adds the channels from [hybrid-memory-retrieval-contract.md](hybrid-memory-retrieval-contract.md)
after the meta/index layer has selected a bounded lane and category. It is not
a separate retrieval backend and must not replace memory isolation,
source-monitoring, or claim verification.

When `memory_mode` is `write` or `update`, adapters should expose
`memory_write_profile: context_complete_required`; explicit reusable memory,
conversation-memory, or cross-conversation writes should use
`strict_capsule_required`. These profiles decide the shape of the selected
write; they do not by themselves grant permission to write memory.

Before reading or writing a lane, check its `lane_state` when the meta index
exposes one:

- `active`: normal routed retrieval and gated writes may proceed.
- `frozen_readonly`: skip default retrieval injection and block writes. Allow
  reads only for explicit audit, A/B/C comparison, migration review, or user
  requested inspection, and label the result as frozen-lane evidence.
- `cleared`: do not use as active memory. Treat any remaining index as an
  audit marker unless an archive link is explicitly selected.

This state check is a lane-level contamination guard. It does not change the
truth of any capsule and it does not replace source-validity cascade checks.

## Explicit Memory Command Semantics

Adopting agents may expose slash commands, UI commands, or natural-language equivalents. The framework does not require a CLI, but it should route these intents consistently:

| Intent | Example phrases | Default route | Boundary |
| --- | --- | --- | --- |
| `recall` | recall, find prior context, continue from memory, 找回, 接着上次 | `memory_mode: read` | Meta-first lookup before payloads; no write by default. |
| `remember` | remember this, record this issue, 记一下, 记录这个问题 | `memory_mode: write` or `update` | Lane, sensitivity, and explicit-record checks before writing. |
| `forget` | forget this, remove this memory, 忘掉, 删除这条记忆 | R5 memory action | Requires explicit confirmation and a deletion or seal policy. |
| `recap` | recap, summarize checkpoint, 总结断点 | `memory_mode: write` when durable | Write a bounded summary only when checkpoint intent is clear. |
| `handoff` | handoff, transfer context, 交接 | R2/R3 artifact plus optional memory | Keep claim and project boundaries visible. |
| `session_history` | session history, show conversation memory, 会话历史 | `memory_mode: read` | Read the current or referenced conversation index first. |
| `commit_context` | commit context, release context, version context | R3/R5 depending on action | Context is readable; commit or release still needs explicit confirmation. |

Rules:

- These command names are semantic anchors, not mandatory product features.
- A visible command does not bypass lane isolation, source-monitoring fields, or explicit confirmation for high-risk memory actions.
- If the user uses vague wording, route to `recall` or `recap` only after the lane is clear.
- Do not treat `remember` as permission to write into another project or another conversation lane.
- A remembered item should keep `source_tag` `derived_from` `belief_status` `confidence`, plus lifecycle metadata, when it becomes a reusable capsule.

## Projectization Drift

If projectless work accumulates durable signals, mark it as `emergent_project_candidate` before writing project memory:

```text
repository / GitHub / release
VERSION / CHANGELOG / README
docs / templates / examples
tests / adapters / runtime policy
repeated architecture decisions
```

This marker does not automatically create a project. It tells the agent to ask, state an assumption, or keep the work isolated until a lane exists.

## Default Decision Table

| Situation | memory_mode | memory_lane | record_intent |
| --- | --- | --- | --- |
| Ordinary chat | `none` | `none` | `no_record` |
| Read prior context | `read` | `current_project` or `global_inbox` | `no_record` |
| User says to record an error | `write` | `self_reflection_matrix` or `common_error_corpus` | `explicit_user_request` |
| Reusable small execution mistake | `write` | `common_error_corpus` | `inferred_reusable_error`; include applied solution and validation |
| User asks to checkpoint this conversation | `write` | `current_conversation` | `explicit_conversation_memory_request` |
| Projectless long conversation accumulates durable decisions or open loops | `write` or local-policy ask first | `current_conversation` | `conversation_checkpoint` |
| Projectless work becomes durable | `none` or `read` | `emergent_project_candidate` | `projectization_review` |
| User asks to continue the previous conversation | `read` then `write` | `current_conversation` | `explicit_conversation_memory_request`; `link_intent: continue_from_latest` |
| Raw host session needs indexing | `write` or local-policy update | `current_conversation` or `current_project` | `conversation_checkpoint`; write conversation ledger first, full lane only on threshold |
| User gives vague keywords for an old conversation | `read` | `referenced_conversation` or `global_inbox` | `no_record`; search index fields before payloads |
| User explicitly asks to merge conversations | `write` | `current_conversation` or selected lane | `explicit_conversation_memory_request`; `link_intent: merge_memories_explicit` |
| User asks for project maps, entry points, commands, or conventions | `read` | current project static knowledge index | `no_record`; read `_STATIC_KNOWLEDGE_INDEX.md` before selected static pages |

## Boundary

Memory writing is still subject to:

- project lane isolation;
- public/private audience checks;
- sensitive data redaction;
- conversation/thread isolation;
- explicit cross-conversation reference or update rules;
- user confirmation for high-risk or cross-project writes;
- meta-first retrieval before payload reads;
- hybrid retrieval only as a meta-first enhancement, never as a replacement for lane/category filtering;
- context-complete write granularity when a durable memory write/update is selected;
- stable `memory_id` and `updated_at` metadata;
- append-only link records for continuation, merge, archive, or supersession.
- static knowledge retrieval through `_STATIC_KNOWLEDGE_INDEX.md` before opening a manual page;
- `source_tag: static_knowledge` and `belief_status: source_prior` for static manual notes until local verification exists.

See [memory-linking-contract.md](memory-linking-contract.md) for the link ledger schema and fuzzy retrieval order.
See [conversation-ledger-contract.md](conversation-ledger-contract.md) for raw-session ledger schema.
See [static-knowledge-layer.md](static-knowledge-layer.md) for the optional static project manual layer.
