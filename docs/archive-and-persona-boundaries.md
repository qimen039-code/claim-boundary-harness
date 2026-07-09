# Archive And Persona Boundaries

This guide separates two ideas that should not be mixed:

- optional cold memory archive;
- conversation-only persona state.

The archive exists for long-term storage and retrieval. Persona state exists only for user-approved tone or companion-style behavior inside a conversation.

## Optional Cold Archive

The global archive is not a second active memory layer. It is an optional index-of-index and cold capsule store.

Default lookup order:

```text
active project or conversation lane
-> its _META_INDEX.md
-> matching category/index/payload
-> stop
```

Only check the global archive when:

- the user explicitly asks for historical lookup;
- a lane has ended and should be sealed;
- a project phase needs a snapshot;
- the active lane cannot find a relevant record;
- the user asks to archive a conversation or project lane.

Backups and recovery copies are even narrower than archive lanes. A backup is a
point-in-time recovery artifact, not a memory lane and not an archive capsule.
Use it only for recovery, historical comparison, checksum verification, or
root-cause analysis. Do not let backup content participate in normal active
retrieval, latest-memory selection, project ownership inference, or automatic
backfill.

## Archive Operations

Default archive operations are file-system operations:

```text
ARCHIVE_MOVE
ARCHIVE_COPY
ARCHIVE_SUMMARY_CAPSULE
```

Use `ARCHIVE_MOVE` when a lane is finished and should no longer be active.

```text
move original lane directory or file
-> archive location
-> update archive meta index
-> leave tombstone or reference pointer at the original location
```

Use `ARCHIVE_COPY` when the lane remains active but needs a sealed snapshot.

```text
copy original lane directory or file
-> archive snapshot location
-> update archive meta index
-> keep source lane unchanged
```

Use `ARCHIVE_SUMMARY_CAPSULE` only when the user explicitly asks for compression, migration, de-identification, public release, or storage reduction.

```text
read source meta first
-> select bounded payload
-> create compressed capsule
-> preserve source_ref
-> do not delete original unless separately confirmed
```

## Archive Hard Rules

- Do not regenerate archived memory content by default.
- Do not treat a backup or sealed snapshot as current memory without an
  explicit promotion or recovery route.
- Do not summarize raw memory as a replacement for source unless the user asks for compression or migration.
- Do not delete source after creating a summary capsule unless separately confirmed.
- Move or copy before editing archive indexes.
- Preserve source reference, source lane, source path, archive path, timestamp, operation type, and checksum when practical.
- Treat source deletion as R5.

Recommended archive index record:

```json
{
  "archive_id": "ARCHIVE-TEMPLATE-001",
  "operation_type": "ARCHIVE_COPY",
  "source_lane": "conversation:TEMPLATE",
  "source_path": "conversation-memory/",
  "archive_path": "global-memory-archive/capsules/conversation/TEMPLATE/",
  "source_ref": "conversation-memory/_META_INDEX.md",
  "checksum": "optional",
  "summary": "Light routing summary only; not a rewritten memory payload.",
  "retrieval_terms": ["template"],
  "status": "archived",
  "created_at": "YYYY-MM-DD"
}
```

## Persona State Boundary

Some users want a personality, companion style, or roleplay-like state for ordinary conversation. That can be useful, but it must not contaminate work.

Persona state is allowed only under this boundary:

```text
scope: current conversation only
default: off
storage: conversation memory lane only
global propagation: no
project propagation: no
work decisions: no
```

Persona state may influence:

- tone;
- pacing;
- roleplay style;
- companion-style continuity inside the current conversation.

Persona state must not influence:

- factual claims;
- risk classification;
- verification requirements;
- project boundaries;
- memory isolation;
- external research decisions;
- claim schema outcomes;
- whether to run or skip tests.

## User Operating Preferences

Durable user preference memory should be operational, explicit, and auditable.

Allowed examples:

- default language;
- answer density;
- verification preference;
- confirmation boundaries;
- formatting preferences;
- preferred durable artifact style.

Disallowed by default:

- personality judgment;
- motive inference;
- identity inference;
- emotional profiling;
- broad claims like "the user always wants";
- using persona state as evidence.

Recommended rule:

```text
Operating preferences may shape interaction.
Persona state may shape only the current conversation tone.
Neither may replace current evidence.
```
