# Conversation Ledger Contract

Conversation ledger is the derived index layer between raw host sessions and
memory lanes.

It exists to solve a narrow problem: raw session logs are too large to load on
every continuation, while client-compacted summaries can lose exact details.
The ledger keeps retrieval cheap without making summaries the source of truth.

## Position

```text
T0 raw session JSONL, artifacts, diffs, test output
-> T1 conversation ledger evidence pointers and indexes
-> T2 bounded segment summaries
-> T3 project memory or long-conversation memory rollups
```

Rules:

- T0 is canonical evidence.
- T1 is a lossless-enough pointer layer.
- T2 and T3 may be lossy summaries.
- Strong details must be recoverable through `raw_ref`, `artifact_ref`, or
  another evidence reference.

Conversation ledger does not replace project memory or conversation memory.
Project memory remains the project rollup. A conversation memory lane remains
the durable state for one long or explicitly continued conversation. The
ledger connects those lanes to raw host sessions.

## Creation Model

Use a hybrid model:

- every meaningful host conversation gets a lightweight session/segment ledger;
- only long, high-value, compressed, decision-heavy, artifact-heavy, or
  explicitly continued conversations get a full conversation memory lane;
- project lanes keep a project-scoped conversation ledger that links project
  sessions, per-conversation lanes, project memory, artifacts, and tests;
- projectless long conversations may keep a local conversation ledger beside
  their conversation memory lane.

Do not create a full memory lane for every short chat. Do not load or rewrite
raw session logs during normal retrieval.

## Context Backup Append Rule

When a deployment keeps a detailed context-backup memory, that backup is the
full-detail continuation surface. It should append the new original context and
execution evidence for each closed task segment instead of rewriting the whole
backup file or replacing raw evidence with a summary.

Append the exact new material that makes later reconstruction possible:

- user instruction window for the segment;
- material agent responses or task-status notes;
- tool calls, command output, errors, tests, diffs, artifact paths, and
  verification results;
- compaction, interruption, stop, resume, and handoff boundaries;
- unresolved open loops and verification debt.

The append record may store bounded raw text directly, raw-session refs plus
hashes, or both, depending on host support. The invariant is that later readers
can recover what happened without trusting a lossy capsule. Summaries, segment
capsules, and project or conversation rollups remain navigation layers over
this appended evidence.

Do not re-generate or rewrite the entire context-backup memory for an update.
Use the same file-operation semantics as normal project edits: update means
append or patch the selected new section; replacement, archive, or deletion are
separate higher-risk actions.

## Required Files

```text
conversation-ledger/
  _LEDGER_INDEX.md
  domain_index.json
  sessions.jsonl
  turns.jsonl
  segments.jsonl
  capsules.jsonl
  time_anchors.jsonl
  evidence_refs.jsonl
  links.jsonl
```

Field intent:

- `_LEDGER_INDEX.md`: first-read human routing surface.
- `domain_index.json`: machine index from domain tags to segment ids.
- `sessions.jsonl`: one record per raw host session.
- `turns.jsonl`: one record per host turn or equivalent unit.
- `segments.jsonl`: bounded segment summaries with evidence pointers.
- `capsules.jsonl`: compatibility view for meta-summary plus event/domain
  classification capsules derived from segments and evidence refs.
- `time_anchors.jsonl`: start/end/compaction/decision/artifact time anchors.
- `evidence_refs.jsonl`: raw line/offset/hash/path pointers and evidence kind.
- `links.jsonl`: edges to raw sessions, project memory, conversation memory,
  artifacts, tests, and prior/next ledgers.

## Evidence Reference Schema

Minimum record:

```json
{
  "ref_id": "EVID-TEMPLATE-001",
  "ledger_id": "LEDGER_TEMPLATE",
  "session_id": "HOST_SESSION_ID",
  "turn_id": "optional_turn_id",
  "evidence_kind": "user_message | task_complete | patch | compaction | token_count | web_search | tool_call | artifact | test_output",
  "source_tag": "raw_session",
  "belief_status": "raw_observed",
  "confidence": "high",
  "derived_from": {
    "source_type": "raw_session_jsonl",
    "path": "relative/or/absolute/path.jsonl",
    "line_start": 1,
    "line_end": 1,
    "sha256_16": "abcdef0123456789"
  },
  "source_monitoring": {
    "raw_log_is_canonical": true,
    "summary_is_navigation_only": true
  },
  "lifecycle": "active",
  "created_at": "YYYY-MM-DDTHH:MM:SS+00:00"
}
```

Line ranges are preferred for JSONL. Byte offsets are optional. Hashes should be
computed from the raw line or bounded raw snippet so later readers can detect
drift. If the host format cannot provide stable line references, record the
best available event id plus a clear `score_method: none` boundary.

## Segment Schema

Minimum record:

```json
{
  "segment_id": "SEG-TEMPLATE-001",
  "ledger_id": "LEDGER_TEMPLATE",
  "session_id": "HOST_SESSION_ID",
  "turn_id": "optional_turn_id",
  "time_start": "YYYY-MM-DDTHH:MM:SS+00:00",
  "time_end": "YYYY-MM-DDTHH:MM:SS+00:00",
  "domain_tags": ["conversation_memory", "artifact"],
  "summary": "Bounded navigation summary only.",
  "compaction_boundary": false,
  "evidence_refs": ["EVID-TEMPLATE-001"],
  "source_tag": "conversation_ledger",
  "belief_status": "bounded_claim",
  "confidence": "medium",
  "derived_from": ["EVID-TEMPLATE-001"],
  "score_method": "none"
}
```

Segments should be small enough for cheap continuation. They are not a full
transcript. A segment summary must not be treated as exact user wording,
validated test output, or complete patch content unless it points back to the
raw evidence.

## Meta Summary And Classification Capsules

The ledger must preserve the earlier meta-summary and event/domain capsule
design. They are compatible with the low-cost ledger chain:

```text
_LEDGER_INDEX.md = outer meta-summary and first routing surface
segments.jsonl = bounded continuation summaries with evidence refs
capsules.jsonl = event/domain classification capsules derived from segments
domain_index.json = lookup from domain tag to segment and capsule ids
evidence_refs.jsonl = raw-source pointers behind the capsules
```

Capsules are not a new source of truth. They are a compact retrieval view over
existing ledger records, intended for "what happened in this event/domain"
questions without opening the raw transcript.

Ledger capsules are navigation records, not full semantic-memory capsules. If a
ledger capsule is promoted into reusable memory, rewrite it with
context-complete content according to
[memory-write-granularity-contract.md](memory-write-granularity-contract.md)
and preserve its `derived_from` evidence refs.

Minimum capsule record:

```json
{
  "capsule_id": "CAP-TEMPLATE-001",
  "capsule_type": "event_domain_classification",
  "ledger_id": "LEDGER_TEMPLATE",
  "session_id": "HOST_SESSION_ID",
  "turn_id": "optional_turn_id",
  "time_start": "YYYY-MM-DDTHH:MM:SS+00:00",
  "time_end": "YYYY-MM-DDTHH:MM:SS+00:00",
  "domain_tags": ["conversation_memory", "artifact"],
  "event_kinds": ["user_message", "patch", "task_complete"],
  "meta_summary": "Bounded navigation summary only.",
  "compaction_boundary": false,
  "evidence_refs": ["EVID-TEMPLATE-001"],
  "source_tag": "conversation_ledger_capsule",
  "belief_status": "bounded_claim",
  "confidence": "medium",
  "derived_from": {
    "segment_id": "SEG-TEMPLATE-001",
    "evidence_refs": ["EVID-TEMPLATE-001"]
  },
  "source_monitoring": {
    "raw_log_is_canonical": true,
    "summary_is_navigation_only": true,
    "classification_is_derivative": true
  },
  "score_method": "deterministic_event_mapping",
  "lifecycle": "active"
}
```

The classification fields must be deterministic or clearly marked as
`source_prior`/`hypothesis` if a runtime adds model-assisted labels later.
Phase 1 uses deterministic event mapping only.

## Compaction Safety

Client compaction events are routing boundaries, not factual proof.

When the host emits `context_compacted`, `compacted`, or an equivalent event:

1. close the current segment;
2. write a `time_anchors.jsonl` record with `anchor_type: compaction_boundary`;
3. set `compaction_boundary: true` on the affected segment;
4. retain evidence references to the raw event and nearby turn ids;
5. append the pre/post-compaction context-backup delta when a context-backup
   memory is enabled;
6. prefer raw evidence over the compacted replacement summary when exact detail
   matters.

Never rely only on a compacted summary for:

- exact user wording or preferences;
- decisions and boundary rules;
- code diffs or artifact contents;
- command, test, or error output;
- external-source claims;
- R5 confirmations;
- memory links, merge decisions, or archive actions.

## Full Conversation Lane Triggers

Create or update a full conversation memory lane when any configured threshold
or explicit request applies:

- explicit user request to remember/checkpoint/continue the conversation;
- `context_compacted` or equivalent compaction occurred;
- high token-pressure event crosses a local threshold;
- decisions, open loops, artifacts, tests, or code changes were produced;
- continuation links to another conversation are required;
- the conversation is projectless but has become a durable workflow.

The full lane stores rollups and decisions. The ledger stores session and
evidence pointers. The raw session remains canonical.

## Retrieval Order

```text
_LEDGER_INDEX.md
-> domain_index.json, capsules.jsonl, or sessions.jsonl
-> retrieval_terms, exact phrase, original-language keyword, Chinese character n-gram, or English term match over the narrowed candidate set
-> matching segment records
-> evidence_refs.jsonl for selected refs
-> raw JSONL line window or artifact/test path only when exact details matter
```

Default retrieval should not open entire raw sessions. If a selected segment
does not contain enough evidence pointers for a strong detail, downgrade the
claim or inspect the raw source.

## Low-Cost Runtime Operations

The ledger should not depend on the user noticing every missing or stale
checkpoint. It should run cheap boundary checks automatically, while keeping
expensive reads event-triggered.

Recommended modes:

- `auto`: boundary check for task start, after decision/artifact creation,
  before compaction when available, and stop/final review. Default behavior is
  stat-only. It may build a missing ledger or refresh a stale ledger only when
  local policy enables `refresh_on_stale` and session paths are available.
- `doctor`: validate ledger files, JSON/JSONL structure, memory links,
  compaction anchors, and raw session file stats. It must not read raw session
  payloads.
- `refresh`: run `doctor` first and rebuild only when forced, missing, failed,
  or raw file stats indicate staleness.
- `resolve`: read only the selected evidence reference line window from the
  raw session, with bounded context and display truncation. Hash verification
  must use the full raw line, not the truncated display text. If the selected
  line window lacks subject, scope, time, or evidence context, expand only the
  missing adjacent boundary and record any unread zone as verification debt.

Do not place full ledger refresh on every tool call. Tool-level hooks should
only invoke ledger checks for critical events such as memory writes, strong
claims, artifact publication, or compaction-sensitive continuation.

## Codex Session Event Mapping

For Codex Desktop JSONL, Phase 1 should map these events:

| Event | Ledger use |
| --- | --- |
| `session_meta` | session id, cwd, model, client metadata |
| `turn_context` | turn id, model, cwd, environment boundary |
| `event_msg.user_message` | user-intent evidence |
| `event_msg.task_complete` | bounded agent-summary evidence |
| `compacted` / `event_msg.context_compacted` | compaction boundary anchor |
| `event_msg.token_count` | token-pressure and lane-upgrade heuristic |
| `event_msg.patch_apply_end` | artifact/code-change evidence |
| `response_item.function_call` | tool-call evidence |
| `response_item.web_search_call` / `event_msg.web_search_end` | external-research evidence |

This mapping is an adapter, not a universal host standard. Other runtimes can
produce the same ledger files from their own event streams.

## Non-Goals

Phase 1 does not require:

- SQL, SQLite, vector stores, or another database as a semantic-memory core;
- local small LLMs or classifiers;
- external memory providers;
- autonomous memory writing without router gates;
- bulk backfill of all historical sessions;
- hard enforcement on runtimes that do not call a hook, wrapper, or tool proxy.

Those can be evaluated later only if they preserve lane isolation, provenance,
and the lightweight control-plane premise.
