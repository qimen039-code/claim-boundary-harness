# Edit Operation Contract

This contract defines how agents should interpret add, update, modify, trim,
rewrite, archive, and delete requests across files, memory records, ledgers,
docs, configs, generated artifacts, and public surfaces.

The default is conservative local editing. A request to "update", "sync",
"improve", "adapt", "补充", "修改", "更新", or "优化" does not imply a
full-file rewrite or deletion.

## Operation Classes

| Operation | Meaning | Default boundary |
| --- | --- | --- |
| `read_only` | Inspect, audit, compare, or report without mutation. | No file or memory write. |
| `append_delta` | Add new material to an existing log, ledger, context backup, changelog, or append-only record. | Append only the new segment or record. |
| `in_place_patch` | Modify a bounded existing section, field, paragraph, function, test, or table row. | Smallest anchored edit. |
| `section_replace` | Replace one bounded section whose old content is obsolete or structurally incompatible. | Preserve surrounding content and review diff. |
| `add_new_artifact` | Create a new file, lane, capsule, report, or generated output because no target exists or a new artifact was explicitly requested. | Do not demote or delete older artifacts by default. |
| `supersede_with_link` | Create a successor while keeping the old item for audit. | Mark old item superseded/redirected; do not delete payload. |
| `archive_or_move` | Move or copy a finished or cold item into archive/storage. | Preserve source refs and checksums when practical. |
| `full_rewrite` | Regenerate or replace the whole existing content surface. | Requires explicit trigger and whole-surface review. |
| `delete_from_disk` | Remove a file or directory from the filesystem. | R5; explicit confirmation required. |
| `delete_record_content` | Remove durable content inside an existing file, memory, ledger, or public artifact. | Requires explicit scope and diff review; high-impact records may require R5-style confirmation. |

## Default Selection Rules

- Existing target plus ordinary update wording -> `in_place_patch` or
  `append_delta`.
- Context backup, raw execution log, session ledger, changelog, and JSONL
  event streams -> `append_delta` unless a repair/migration route explicitly
  selects another operation.
- Project memory, long-conversation memory, and domain memory -> update the
  selected capsule/row or add a new compact rollup capsule with evidence refs.
  Do not rewrite the lane because new context exists.
- Generated outputs may be regenerated only when the source file/template is
  the canonical editable surface or the user asks for a new generated artifact.
- Public docs/config/policy/AGENTS/router files -> default to `in_place_patch`
  or `section_replace`; avoid whole-file regeneration because comments,
  ordering, encoding, anchors, and private/local exclusions can be lost.

## Full Rewrite Triggers

Use `full_rewrite` only when at least one trigger is explicit and the surface is
safe to replace:

- the user explicitly asks to rewrite, regenerate, rebuild, recreate, reset, or
  replace the whole file/surface;
- the whole file is the declared target, not merely one section;
- the file is generated from a canonical source and the generator is the normal
  source of truth;
- a schema migration or format conversion cannot preserve structure with
  bounded patches;
- the existing file is corrupted, unparsable, or internally inconsistent enough
  that local patches would be less safe than replacement;
- the user approves a cleanup/migration plan that archives or supersedes the
  old surface first.

Before `full_rewrite`:

1. read the whole current surface or its authoritative source;
2. identify what must be preserved: anchors, comments, private exclusions,
   encoding, line endings, metadata, permissions, and generated sections;
3. create a backup or supersession link for high-impact or non-regenerable
   surfaces;
4. state why local patching is insufficient;
5. review the full diff and run the relevant validation.

## Delete And Trim Boundary

Deleting from disk is different from trimming content inside a file.

- `delete_from_disk` removes a file or directory and is always high risk.
- `delete_record_content` removes durable content inside a file or memory lane.
  Treat it as high impact when it touches memory, user data, public docs,
  config, policy, history, audit evidence, or source refs.
- "清理", "删减", "去掉", "移除", and "清空" are candidates, not automatic
  permission. Determine whether the user means removing text from a section,
  archiving stale content, superseding a record, or deleting from disk.
- Prefer `supersede_with_link`, quarantine, archive, or tombstone markers when
  auditability matters.
- Never remove old evidence after creating a summary capsule unless a separate
  deletion/redaction policy or explicit user confirmation says so.

## Diff And Verification Rules

For any mutating operation:

- read the current target and nearby anchors before editing;
- preserve unrelated ordering and formatting;
- keep generated-output notes, internal reminders, and temporary plans out of
  formal content unless that content is meant to carry them;
- inspect the diff for unrelated churn, encoding changes, line-ending drift,
  accidental deletion, and private/public boundary leaks;
- validate with the smallest relevant test, parser, schema check, or final
  artifact inspection.

If the operation class is ambiguous, choose the safer narrower operation first
or ask for confirmation before widening.
