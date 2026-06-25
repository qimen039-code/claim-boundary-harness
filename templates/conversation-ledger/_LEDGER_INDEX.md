# Conversation Ledger Index

This is the first file an agent reads before using this conversation ledger.

## Ledger

```text
ledger_id: LEDGER_TEMPLATE
ledger_type: conversation_ledger
status: TEMPLATE
owner: adopting workspace
project_lane: PROJECTLESS_OR_PROJECT_ID
created_at: YYYY-MM-DDTHH:MM:SS+00:00
updated_at: YYYY-MM-DDTHH:MM:SS+00:00
raw_sessions: []
conversation_memory_ids: []
project_memory_ids: []
```

## Retrieval Rule

```text
read _LEDGER_INDEX.md
-> choose domain_index.json, capsules.jsonl, or sessions.jsonl
-> open matching segments.jsonl records
-> open selected evidence_refs.jsonl records
-> inspect raw session snippets or artifacts only when exact detail matters
```

## Source Boundary

- Raw session JSONL and artifact/test outputs are canonical evidence.
- Ledger summaries are navigation only.
- `evidence_refs.jsonl` must carry source-monitoring fields and raw refs.
- Client-compacted summaries must not be treated as full-detail evidence.

## Record Families

| File | Type | Use When | Not For |
| --- | --- | --- | --- |
| `sessions.jsonl` | raw session manifest | Need session ids, paths, cwd, model, time bounds | Transcript replay |
| `turns.jsonl` | turn index | Need per-turn environment, counts, token pressure | Full conversation text |
| `segments.jsonl` | bounded summaries | Need continuation context or domain chunks | Exact facts without refs |
| `capsules.jsonl` | event/domain capsules | Need compact meta-summary plus event/domain classification | Replacing segment/evidence refs |
| `time_anchors.jsonl` | anchor records | Need start/end/compaction/artifact/decision anchors | Narrative memory |
| `evidence_refs.jsonl` | evidence pointers | Need raw refs, hashes, artifact paths, source monitoring | Replacing raw evidence |
| `links.jsonl` | cross-lane links | Need project/conversation/raw/artifact edges | Copying linked payloads |
| `domain_index.json` | machine index | Need domain tag to segment lookup | Human narrative |
