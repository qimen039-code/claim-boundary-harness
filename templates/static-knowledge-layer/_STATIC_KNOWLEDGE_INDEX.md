# Static Knowledge Index

This index is the first file an agent should read before opening static project
manual pages. Keep it short. Open only the matching page.

| knowledge_id | page | status | source_tag | belief_status | confidence | lifecycle_stage | retention_policy | promotion_reason | decay_reason | retrieval_terms | applies_when | does_not_apply_when | last_reviewed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `SKL-PROJECT-MAP` | `project-map.md` | template | `static_knowledge` | `source_prior` | `unverified` | `working_memory` | `until_superseded` | initial manual seed | none | modules; layout; ownership; map | Agent needs repository orientation. | Agent needs volatile decisions or incident history. | YYYY-MM-DD |
| `SKL-ENTRYPOINTS` | `entrypoints-and-commands.md` | template | `static_knowledge` | `source_prior` | `unverified` | `working_memory` | `until_superseded` | initial manual seed | none | commands; entry points; scripts; tests | Agent needs a likely command or entry point. | Agent needs proof that a command currently passes. | YYYY-MM-DD |
| `SKL-CONVENTIONS` | `conventions.md` | template | `static_knowledge` | `source_prior` | `unverified` | `working_memory` | `until_superseded` | initial manual seed | none | conventions; style; rules | Agent needs project-specific conventions. | Rule conflicts with root instructions or current user request. | YYYY-MM-DD |
| `SKL-INTERFACES` | `interfaces-and-data.md` | template | `static_knowledge` | `source_prior` | `unverified` | `working_memory` | `until_superseded` | initial manual seed | none | interfaces; schemas; data | Agent needs stable interface or data-shape notes. | Agent needs current runtime output or live schema validation. | YYYY-MM-DD |

Retrieval output must include:

```text
source_tag
derived_from
belief_status
confidence
score_method
```

Use `score_method: none` and omit `score` when no ranking score was computed.
