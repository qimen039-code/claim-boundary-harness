# Conversation Memory Meta Index

This is the first file an agent must read before using this conversation memory lane.

## Lane

```text
memory_id: CONVERSATION_TEMPLATE
memory_type: conversation
lane: CONVERSATION_TEMPLATE
scope: one isolated long-running conversation or thread
status: TEMPLATE
owner: adopting workspace
created_at: YYYY-MM-DDTHH:MM:SS+00:00
updated_at: YYYY-MM-DDTHH:MM:SS+00:00
last_reviewed: YYYY-MM-DD
link_policy: link_only_by_default
max_continuation_depth: 5
active_successor_memory_id: null
redirect_read_to: null
```

## Retrieval Rule

```text
read this _META_INDEX.md
-> choose conversation_state.md, index.json, memory_links.jsonl, or one JSONL record family
-> open only matching records
```

## Capsule Schema

When this lane is compressed into a reusable capsule, use:

```text
source-monitoring-memory-schema:
source_tag
belief_status
confidence
derived_from
source_monitoring
lifecycle
belief_trace_summary
```

Conversation-derived claims normally start as `source_prior` or `bounded_claim`; promote them to `local_validated` only with local evidence.

When returning selected conversation memory to an agent, include `source_tag`, `derived_from`, `belief_status`, `confidence`, and `score_method` with the selected text. Use `score_method: none` when no numeric retrieval score is computed.

## Latest And Fuzzy Lookup

Use `updated_at` as the cheap shortcut for "continue the previous conversation". If the user remembers only keywords, search index-level fields first:

```text
title / summary / retrieval_terms / semantic_anchors / open_loops
-> candidate summaries
-> user choice when ambiguous
-> matching payload records only
```

## Record Families

| File | Type | Use When | Not For |
| --- | --- | --- | --- |
| `conversation_state.md` | summary | Need current state, scope, assumptions, and continuation note | Raw transcript storage |
| `index.json` | machine index | Need stable fields, timestamps, retrieval terms, link policy, or script routing | Human narrative |
| `memory_links.jsonl` | append-only links | Continuing from, referencing, merging, archiving, or superseding another memory | Copying another lane's payload |
| `decisions.jsonl` | append-only decisions | User accepted a durable decision | Ordinary assistant wording |
| `open_loops.jsonl` | append-only open loops | Something remains unresolved or unverified | Completed tasks |
| `errors_and_solutions.jsonl` | append-only paired fixes | A reusable mistake was solved in this conversation | Unsolved speculation |
| `references.jsonl` | append-only references | This conversation points to a file, repo, source, project memory, or another conversation memory | Copying another lane's private payload |
| `persona_state.md` | conversation-only tone state | User explicitly wants a local companion/persona style in this conversation | Facts, risk, verification, project boundaries, memory boundaries, search, or claim decisions |

## Isolation Boundary

- Write only this conversation's durable state here.
- New conversations that continue this memory should create their own memory and append a `continues` link.
- Do not write another conversation's content unless the user explicitly asks to update this lane.
- Do not copy project memory payloads here. Link by reference and evidence boundary.
- Do not write credentials, personal values, or sensitive payloads.
- Merges require explicit user instruction and should create a new merged memory rather than silently rewriting old payloads.
