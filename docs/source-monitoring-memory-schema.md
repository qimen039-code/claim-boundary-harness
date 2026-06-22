# Source Monitoring Memory Schema

This schema gives memory capsules a provenance and belief-state layer. Its goal is not to calculate whether a claim is universally true. Its goal is to track where a claim came from, what verification stage it has reached, and what evidence supports that current status.

Use it for project memory capsules, conversation memory capsules, source-grounded learning records, rejected paths, and compressed summaries derived from older records.

## Core Fields

| Field | Required | Purpose |
| --- | --- | --- |
| `source_tag` | Yes | Origin class for the capsule content. |
| `belief_status` | Yes | Verification-process state for the claim or memory content. |
| `confidence` | Yes | Evidence strength for assigning the current `belief_status`, not the probability that the claim content is true. |
| `derived_from` | Conditional | Provenance records and relationship boundaries. Required for compressed, synthesized, or memory-derived capsules. |
| `source_monitoring` | Recommended | Current observation or audit state and why the capsule was placed there. |
| `belief_trace` | Recommended | Append-only status transition events while the capsule is active. |
| `belief_trace_summary` | Recommended for compressed capsules | Compact trace summary after memory compression. |

Keep the active capsule small. Raw transcripts, long traces, test logs, and source excerpts belong in raw logs, source ledgers, or archive payloads.

## `source_tag`

Recommended values:

```text
user_claim
model_hypothesis
tool_output
external_source
memory_capsule
local_test
inferred_synthesis
```

`source_tag: memory_capsule` and `source_tag: inferred_synthesis` require `derived_from` at write time. Do not defer this check until a later compression pass; otherwise the upstream boundary can be lost.

## `belief_status`

Recommended values:

| Value | Meaning |
| --- | --- |
| `hypothesis` | Generated or proposed, but not yet sourced or locally checked. |
| `source_prior` | Seen in a source or prior record, but not locally verified. |
| `bounded_claim` | Usable only inside an explicit evidence or scope boundary. |
| `local_validated` | Checked in the adopting workspace under stated conditions. |
| `conflicted` | Evidence, sources, tests, or memory records disagree. |
| `rejected` | A path, claim, or previous capsule was rejected and should remain as error memory. |

`belief_status` is a state machine. It is not a truth score.

## `confidence`

`confidence` describes the evidence strength for assigning the current `belief_status`.

It does not describe the raw probability that the original claim is true. This distinction matters:

- A plausible but unverified claim can still have `belief_status: hypothesis` and `confidence.label: unverified`.
- A rejected claim can have `confidence.label: verified` when local tests strongly prove that the rejection status is correct.

Recommended shape:

```json
{
  "label": "medium",
  "basis": "Status assigned from EXT-DEMO-001 and MEM-DEMO-001; no local runtime test has been run.",
  "score": 0.72,
  "score_method": "CEC"
}
```

Recommended labels:

```text
unverified
low
medium
high
verified
conflicted
```

Rules:

- `basis` is required and should include both the status-assignment reason and an evidence reference.
- `score` is optional and only allowed when an actual method computed it.
- If `score` exists, `score_method` must exist and must not be `none`.
- If `score_method: none` is used, `score` must be absent.
- Do not write `score: 0` or `score: null` to mean unknown.
- Prefer `label + basis` over naked numeric precision.

## `derived_from`

Recommended item shape:

```json
{
  "type": "source_note",
  "ref_id": "EXT-DEMO-001",
  "relationship": "synthesized_from",
  "inherited_boundary": "source_prior only; no local runtime verification"
}
```

Recommended `type` values:

```text
raw_log
conversation_memory
source_note
user_confirmation
test_result
external_search
previous_capsule
```

Recommended `relationship` values:

```text
distilled_from
corrects
extends
synthesized_from
contradicts
```

Conditional rules:

- `relationship: distilled_from` requires `inherited_boundary`.
- `relationship: synthesized_from` requires `inherited_boundary`.
- `relationship: corrects` requires `correction_evidence_ref`.
- `relationship: corrects` is the only common relationship where the new capsule may exceed the upstream confidence boundary, and only because correction evidence is explicit.
- `relationship: contradicts` should normally move the capsule toward `belief_status: conflicted` or require a trace event explaining why it was rejected or bounded instead.

## `source_monitoring`

Recommended shape:

```json
{
  "observation_state": "audit_required",
  "trigger_reason": "source_conflict",
  "last_checked": "2026-06-22T00:00:00Z"
}
```

Recommended `observation_state` values:

```text
none
watch
audit_required
resolved
```

Recommended `trigger_reason` values:

```text
manual_review
user_correction
source_conflict
tool_failure
local_test
external_update
claim_escalation
novelty
```

`trigger_reason: novelty` is reserved for OOD or novelty adapters. If no OOD adapter is active, it should be written only by a human or an external tool that explicitly made that judgment.

## `belief_trace`

Recommended event shape:

```json
{
  "ts": "2026-06-22T00:00:00Z",
  "from": "source_prior",
  "to": "bounded_claim",
  "reason": "The claim was narrowed to a documented adapter boundary.",
  "evidence_ref": "DOC-DEMO-001"
}
```

Rules:

- A `rejected` capsule must keep at least one trace event with `to: rejected` and a reason.
- A `conflicted` capsule should keep the conflicting reference IDs in either `belief_trace` or `derived_from`.
- When a capsule is compressed, `belief_trace` can be folded into `belief_trace_summary` while the complete trace moves to raw logs or archive.

Recommended compressed summary:

```json
{
  "initial_status": "hypothesis",
  "current_status": "bounded_claim",
  "intermediate_steps_count": 2,
  "archived_trace_ref": "raw_logs/TRACE-DEMO-001"
}
```

Invariant: `belief_trace_summary.current_status` must always equal `belief_status`.

## Soft Constraints

| `belief_status` | Typical confidence labels | Source monitoring expectation |
| --- | --- | --- |
| `hypothesis` | `unverified` | `watch` or omitted |
| `source_prior` | `unverified`, `low`, `medium` | `watch` or `audit_required` |
| `bounded_claim` | `medium`, `high` | `resolved` when the boundary is explicit |
| `local_validated` | `medium`, `high`, `verified` | `resolved` |
| `conflicted` | `conflicted` | `audit_required` |
| `rejected` | `high` or `verified` when rejection evidence is strong; `low` only when rejection itself is weak | `resolved` |

These are soft constraints, not replacement logic for human or project-specific review. The important rule is that labels describe evidence for the status assignment.

## Optional Adapters

This core schema does not require embeddings, OOD detection, NLI, or a confidence engine.

Optional adapters may compute a score such as CEC:

```text
CEC = weighted geometric aggregation of entailment, relevance, authority, and time decay
```

If used, the score should be converted into `confidence.label + confidence.basis`. Store raw scores only as supporting metadata with a clear `score_method`. Keep correlated signals, source variance, conflicts, and claim type decay rules visible in the basis or adapter report.

## Minimal Capsule Example

```json
{
  "memory_id": "MEM-DEMO-SOURCE-001",
  "record_type": "project_memory_capsule",
  "status": "ACTIVE",
  "source_tag": "inferred_synthesis",
  "belief_status": "bounded_claim",
  "content_summary": "The adapter can enforce a claim boundary only on execution paths that call it and honor blocked results.",
  "confidence": {
    "label": "high",
    "basis": "Status assigned from DOC-DEMO-001 and TEST-DEMO-001; the boundary is explicit and local smoke output covered the documented path."
  },
  "derived_from": [
    {
      "type": "source_note",
      "ref_id": "DOC-DEMO-001",
      "relationship": "synthesized_from",
      "inherited_boundary": "documentation-level source prior"
    },
    {
      "type": "test_result",
      "ref_id": "TEST-DEMO-001",
      "relationship": "extends"
    }
  ],
  "source_monitoring": {
    "observation_state": "resolved",
    "trigger_reason": "local_test",
    "last_checked": "2026-06-22T00:00:00Z"
  },
  "belief_trace_summary": {
    "initial_status": "source_prior",
    "current_status": "bounded_claim",
    "intermediate_steps_count": 1,
    "archived_trace_ref": "raw_logs/TRACE-DEMO-001"
  }
}
```
