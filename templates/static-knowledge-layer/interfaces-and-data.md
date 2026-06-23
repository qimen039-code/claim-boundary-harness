# Interfaces And Data

knowledge_id: `SKL-INTERFACES`
source_tag: `static_knowledge`
belief_status: `source_prior`
last_reviewed: `YYYY-MM-DD`

## Interface Notes

| Interface | Shape | Used by | Boundary |
| --- | --- | --- | --- |
| Routing receipt | JSON-like object | Router, adapters, final review. | Fields may differ by adapter version. |
| Memory retrieval result | Metadata plus selected snippet | Memory and static knowledge lookup. | Relevance is not validation. |
| Compatibility manifest | JSON | Adapter install and drift checks. | Describes checked behavior only. |

## Data Boundary

Static notes should point to schemas, tests, or source files. They should not be
treated as live runtime output unless a verification record says so.

