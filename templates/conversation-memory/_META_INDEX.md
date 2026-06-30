# Conversation Memory Meta Index

This is the first file an agent must read before using this conversation memory lane.

## Lane

```text
memory_id: CONVERSATION_TEMPLATE
memory_type: conversation
lane: CONVERSATION_TEMPLATE
lane_state: active
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
-> check lane_state
-> choose conversation_state.md, index.json, memory_links.jsonl, or one JSONL record family
-> open only matching records
```

If `lane_state` is `frozen_readonly`, do not inject this conversation as active
memory and do not write to it. Read it only for explicit audit, migration, or
A/B/C comparison. If `lane_state` is `cleared`, use only the audit marker or an
explicit archive link.

## Capsule Schema

When this lane is compressed into a reusable capsule, use:

```text
source-monitoring-memory-schema:
source_tag
belief_status
confidence
derived_from
source_validity_dependency
source_monitoring
lifecycle
belief_trace_summary
```

Conversation-derived claims normally start as `source_prior` or `bounded_claim`; promote them to `local_validated` only with local evidence.

When returning selected conversation memory to an agent, include these fields with the selected text: `source_tag` `derived_from` `belief_status` `confidence` `score_method`. Use `score_method: none` when no numeric retrieval score is computed.

If conversation-derived capsules conflict, resolve them by scope and confidence
tier, not by timestamp alone. Same/higher-confidence corrected records can
supersede older ones; lower-confidence contradictions remain conflicted and
audit-required. If a required source reference is invalidated, retracted, or
deleted, cascade the source-validity dependency before reusable retrieval.

Memory content should preserve the original language. Keep structure fields in
English, but do not translate Chinese or English source content only for
normalization. Durable capsules should be context-complete and should not save
isolated fragments as reusable guidance.

After a candidate is selected, the route or decision layer should choose the
smallest sufficient reading profile: `baseline`, `evidence_window`,
`middle_safe`, or `full_audit`. Baseline reads identify the source shape before
payload reading and prefer existing maps and indexes; when none exist, create a
temporary micro-map from file name, size, heading/key/symbol/record anchors, and
known evidence refs. Evidence reads return a compact source context header and
note unread zones as verification debt when coverage is partial.

For long sources, use middle-safe evidence layout. Keep an evidence inventory
next to the original windows, write per-window conclusion cards before
synthesis, keep multi-hop evidence adjacent, repeat a short key-evidence
reminder near strong claims, and mark `position_risk` when sparse reading could
hide middle-only facts. If head/tail anchors are insufficient for a strong
claim, reread bounded middle windows around structural anchors before promoting
the claim.

## Latest And Fuzzy Lookup

Use `updated_at` as the cheap shortcut for "continue the previous conversation". If the user remembers only keywords, search index-level fields first:

```text
title / summary / retrieval_terms / semantic_anchors / open_loops
-> exact phrase / original-language keyword / Chinese character n-gram / English term match
-> source-shape identification and bounded evidence window
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
