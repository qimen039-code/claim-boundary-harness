# Format Layering Strategy

Use formats according to who must read and update the content.

Markdown is good for human-facing explanations, but Markdown tables and long lines are fragile for repeated machine patching. Structured or append-only formats should hold the machine-owned facts.

## Recommended Split

| Layer | Recommended format | Use for |
| --- | --- | --- |
| Human explanation | Markdown | README, adoption notes, architecture, integration guides, examples. |
| Policy and routing facts | JSON, TOML, or YAML | Risk rules, trigger lists, adapter config, route contracts. |
| Append-only event records | JSONL | Decisions, errors, solutions, logs, checkpoints, source ledgers. |
| Simple tabular data | CSV or TSV | Large matrices, comparison rows, import/export data. |
| Queryable local state | SQLite | Larger memory libraries, indexed state, cross-record queries. |
| Hybrid human/machine record | Markdown with fenced JSON/YAML | Small capsules that need both explanation and structured fields. |
| Public presentation | Generated Markdown | README tables or docs generated from structured source. |

## Default Repository Pattern

```text
docs/*.md
  human-readable guidance and examples

skills/embedded-harness/embedded_harness_policy.json
  router and gate policy

skills/embedded-harness/embedded_harness_policy.authoring.toml
  human-maintained high-churn policy sections; compile/check into JSON

templates/**/_META_INDEX.md
  mandatory human-readable retrieval surface

templates/**/*.json
  machine-readable index or retrieval surface

templates/**/*.jsonl
  append-only records for decisions, open loops, errors, solutions, references

templates/global-memory-archive/**/*.jsonl
  cold archive indexes and source references; not active memory
```

## Patch Stability Rules

- Avoid hand-maintained Markdown tables for data that changes often.
- Avoid very long Markdown lines when agents will patch the file repeatedly.
- Prefer one JSONL object per record for append-only memory.
- Prefer stable IDs over row position.
- Keep human docs as summaries of structured records, not the only source of truth.
- If a Markdown table is public-facing, consider generating it from JSON/CSV.
- Keep runtime adapters on JSON unless the runtime has a specific reason to parse
  another format. TOML can be an authoring layer, but the generated JSON remains
  the compatibility surface for PowerShell, Bash, Python, and hosted adapters.

## Memory-Library Rule

Memory systems should use:

```text
_META_INDEX.md
-> human-readable first-read routing surface

index.json
-> machine-readable routing surface

*.jsonl
-> append-only durable records

*.md
-> short summaries, capsules, and adoption notes
```

This gives agents a robust edit surface while keeping the repository easy for humans to inspect.

## Archive Rule

Archive indexes should be JSONL. Archive payloads should be moved or copied source files/directories by default. Do not make a newly generated Markdown summary the replacement source unless the user explicitly asked for compression or migration.

## Boundary

This strategy does not ban Markdown. It narrows Markdown to the work it is good at: explanation, entry points, summaries, and public docs. Machine-owned facts should live in structured files whenever they need stable parsing, stable appends, or frequent updates.
