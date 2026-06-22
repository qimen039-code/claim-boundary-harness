# Global Memory Archive Meta Index

This is an optional cold archive. It is not the default active memory lane.

Read this file only when the user asks for archive lookup, an active lane has no relevant record, or a lane is being sealed or snapshotted.

## Archive Rule

```text
active lane first
-> active lane _META_INDEX.md
-> matching active payload
-> only then check this archive when needed
```

## Operation Boundary

Default archive operations:

```text
ARCHIVE_MOVE
ARCHIVE_COPY
```

Use `ARCHIVE_SUMMARY_CAPSULE` only with explicit compression, migration, de-identification, public-release, or storage-reduction intent.

Do not regenerate old memory content as a default archive step.

## Record Families

| File | Purpose |
| --- | --- |
| `archive_index.jsonl` | Append-only archive index records. |
| `conversation_index.jsonl` | Cold lookup index for sealed or archived conversation memories by memory_id, title, summary, updated_at, retrieval terms, and semantic anchors. |
| `memory_links.jsonl` | Cross-lane continuation, merge, supersession, archive, and reference edges. |
| `source_refs.jsonl` | Source lane, original path, archive path, and evidence boundary references. |
| `supersession.jsonl` | Optional links between old and replacement archive records. |
| `capsules/` | Optional cold payload folders or compressed capsules. |

Archived capsules should keep source-monitoring fields when they exist: `source_tag`, `belief_status`, `confidence`, `derived_from`, `source_monitoring`, and `belief_trace_summary`. Keep the index row compact and open payloads only after meta-level selection.

## Retrieval Boundary

- Read archive meta first.
- Select one archive index or conversation index record.
- For continuation or merge lookup, read one matching `memory_links.jsonl` edge before opening payloads.
- Open one matching capsule only when needed.
- Do not scan all capsules by default.
