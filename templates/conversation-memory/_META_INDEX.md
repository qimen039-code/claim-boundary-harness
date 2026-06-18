# Conversation Memory Meta Index

This is the first file an agent must read before using this conversation memory lane.

## Lane

```text
lane: CONVERSATION_TEMPLATE
scope: one isolated long-running conversation or thread
status: TEMPLATE
owner: adopting workspace
last_reviewed: YYYY-MM-DD
```

## Retrieval Rule

```text
read this _META_INDEX.md
-> choose conversation_state.md, index.json, or one JSONL record family
-> open only matching records
```

## Record Families

| File | Type | Use When | Not For |
| --- | --- | --- | --- |
| `conversation_state.md` | summary | Need current state, scope, assumptions, and continuation note | Raw transcript storage |
| `index.json` | machine index | Need stable fields for routing or scripts | Human narrative |
| `decisions.jsonl` | append-only decisions | User accepted a durable decision | Ordinary assistant wording |
| `open_loops.jsonl` | append-only open loops | Something remains unresolved or unverified | Completed tasks |
| `errors_and_solutions.jsonl` | append-only paired fixes | A reusable mistake was solved in this conversation | Unsovled speculation |
| `references.jsonl` | append-only references | This conversation points to a file, repo, source, project memory, or another conversation memory | Copying another lane's private payload |
| `persona_state.md` | conversation-only tone state | User explicitly wants a local companion/persona style in this conversation | Facts, risk, verification, project boundaries, memory boundaries, search, or claim decisions |

## Isolation Boundary

- Write only this conversation's durable state here.
- Do not write another conversation's content unless the user explicitly asks to update this lane.
- Do not copy project memory payloads here. Link by reference and evidence boundary.
- Do not write credentials, personal values, or sensitive payloads.
