# Memory Routing Contract

Memory use is a router decision. The framework should not open memory just because memory exists, and it should not write memory just because an error happened.

## Contract Fields

Add these fields to the routing receipt:

```text
memory_need
memory_mode
memory_lane
record_intent
projectization_decision
```

Meanings:

| Field | Values | Purpose |
| --- | --- | --- |
| `memory_need` | `none`, `meta_only`, `index_only`, `capsule_payload`, `paired_err_sol`, `common_error_corpus` | How deep memory lookup should go. |
| `memory_mode` | `none`, `read`, `write`, `update` | Whether the task should skip, read, write, or update memory. |
| `memory_lane` | `none`, `current_project`, `emergent_project_candidate`, `common_error_corpus`, `self_reflection_matrix`, `global_inbox` | Where the memory action belongs. |
| `record_intent` | `no_record`, `explicit_user_request`, `inferred_reusable_error`, `projectization_review` | Why a record would be written. |
| `projectization_decision` | `not_project`, `current_project`, `emergent_project_candidate` | Whether projectless work is becoming a durable project lane. |

## Recording Rules

Explicit user phrases such as "record this error", "remember this issue", or equivalent local-language wording should route to memory writing after lane and sensitivity checks.

Small but reusable mistakes should go to a common error corpus first. Full paired `ERR-*` / `SOL-*` records are reserved for high-impact incidents, repeated failures, or explicit self-reflection requests.

Ordinary chat and small corrected mistakes should not create memory records by default.

## Projectization Drift

If projectless work accumulates durable signals, mark it as `emergent_project_candidate` before writing project memory:

```text
repository / GitHub / release
VERSION / CHANGELOG / README
docs / templates / examples
tests / adapters / runtime policy
repeated architecture decisions
```

This marker does not automatically create a project. It tells the agent to ask, state an assumption, or keep the work isolated until a lane exists.

## Default Decision Table

| Situation | memory_mode | memory_lane | record_intent |
| --- | --- | --- | --- |
| Ordinary chat | `none` | `none` | `no_record` |
| Read prior context | `read` | `current_project` or `global_inbox` | `no_record` |
| User says to record an error | `write` | `self_reflection_matrix` or `common_error_corpus` | `explicit_user_request` |
| Reusable small execution mistake | `write` | `common_error_corpus` | `inferred_reusable_error` |
| Projectless work becomes durable | `none` or `read` | `emergent_project_candidate` | `projectization_review` |

## Boundary

Memory writing is still subject to:

- project lane isolation;
- public/private audience checks;
- sensitive data redaction;
- user confirmation for high-risk or cross-project writes;
- meta-first retrieval before payload reads.
