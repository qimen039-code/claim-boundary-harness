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
| `lifecycle` | Recommended | Memory lifecycle metadata for retrieval priority and retention policy. |
| `belief_trace` | Recommended | Append-only status transition events while the capsule is active. |
| `belief_trace_summary` | Recommended for compressed capsules | Compact trace summary after memory compression. |
| `feedback_loop` | Optional for reusable rules | Lightweight memory -> prediction -> verification -> calibration loop for records meant to prevent future mistakes. |

Keep the active capsule small. Raw transcripts, long traces, test logs, and source excerpts belong in raw logs, source ledgers, or archive payloads.

## Content Plane And Write Granularity

The schema fields are stable machine-facing structure. They should normally use
English keys and enumerated values. The memory content itself should preserve
the original source language. Do not translate Chinese memory content into
English, or English code/API content into Chinese, only to make the capsule look
uniform.

Reusable semantic memory should be context-complete. A promoted capsule should
state the actor or source, action/claim/decision, object and scope, time or
version when relevant, evidence boundary, and non-applicable boundary when
needed. Isolated fragments are allowed in scratch notes, but not in durable
capsules.

Recommended content-plane shape:

```json
{
  "content": {
    "language": "zh-CN",
    "original_text": "Source-language memory text or bounded restatement.",
    "context_complete_summary": "Self-contained capsule summary with enough subject, action, object, scope, time, and boundary to survive compaction.",
    "key_terms": ["original-language term", "domain term"],
    "non_applicable_boundary": "Where this memory must not be applied."
  }
}
```

Ledger capsules and route summaries may remain shorter because they are
navigation records. When promoted into reusable semantic memory, rewrite them
according to the full granularity rule and preserve `derived_from`.

## `source_tag`

Recommended values:

```text
user_claim
model_hypothesis
tool_output
external_source
static_knowledge
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
static_knowledge_page
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

## `feedback_loop`

`feedback_loop` is a lightweight trial field for memories that are expected to
change future behavior. It should not appear on every capsule.

Recommended shape:

```json
{
  "prediction": {
    "statement": "What this memory predicts or should cause next time.",
    "trigger": "When the prediction applies.",
    "expected_behavior": "What the agent or workflow should do.",
    "belief_status": "hypothesis"
  },
  "verification": {
    "status": "pending",
    "evidence_ref": null,
    "result_summary": null
  },
  "calibration": {
    "action": "How to update the record if verification succeeds or fails.",
    "confidence_delta": "unchanged",
    "updated_boundary": null
  }
}
```

Recommended verification status values:

```text
pending
matched
failed
partial
not_applicable
```

Rules:

- Treat `prediction` as `hypothesis` unless later evidence verifies it.
- Use the loop only for reusable, repeated, high-impact, or user-requested
  learning records.
- Do not create a separate task-consumption ledger just to support the loop.
- `verification.evidence_ref` should point to raw session records, tool output,
  tests, diffs, or reviewed artifacts. A derived summary alone is not enough.
- Calibration changes future applicability or confidence boundaries. It does
  not overwrite the original event.

See [memory-feedback-loop-trial.md](memory-feedback-loop-trial.md).

## `lifecycle`

`lifecycle` describes how the record should be used by retrieval and retention policies. It does not change the truth value of the capsule.

Recommended shape:

```json
{
  "stage": "capsule",
  "retention_policy": "preserve",
  "last_accessed_at": "2026-06-23T00:00:00Z",
  "promotion_reason": "Repeated deployment failure class with a verified fix.",
  "decay_reason": null
}
```

Recommended `stage` values:

| Value | Meaning | Default retrieval behavior |
| --- | --- | --- |
| `raw_observation` | Direct event, tool output, user wording, screenshot summary, or log excerpt. | Do not treat as current guidance. Open only as evidence. |
| `working_memory` | Short-horizon task state, blocker, plan, or current open loop. | Use only inside the current task, conversation, or active lane. |
| `capsule` | Compact reusable memory with source, provenance, status, and claim boundary. | Eligible for meta-first retrieval. |
| `archive` | Cold record or full historical payload retained for audit, reproduction, or long projects. | Do not open by default; use index and capsule first. |

Recommended `retention_policy` values:

```text
preserve
until_superseded
until_resolved
user_pinned
delete_on_request
```

Rules:

- `stage: raw_observation` should normally have `belief_status: hypothesis`, `source_prior`, or a narrow `bounded_claim`; it should not become `local_validated` without a separate verification record.
- `stage: capsule` should include `derived_from` unless the capsule is a direct user-maintained note with its own evidence boundary.
- `stage: archive` means default retrieval priority is low, not that the record is untrusted or obsolete.
- `last_accessed_at` is a retrieval hint for recent-use ranking. It is not evidence strength.
- `promotion_reason` should say why the record was promoted from raw or working state into a reusable capsule.
- `decay_reason` means reduced default retrieval priority, not reduced truth. Use values such as `superseded_by_newer_fix`, `low_recent_relevance`, `obsolete_adapter`, or `resolved_issue`.

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
  "lifecycle": {
    "stage": "capsule",
    "retention_policy": "preserve",
    "last_accessed_at": "2026-06-23T00:00:00Z",
    "promotion_reason": "Reusable adapter boundary extracted from source note and local smoke result.",
    "decay_reason": null
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
  },
  "feedback_loop": {
    "prediction": {
      "statement": "Future adapter claims should state which execution path invoked and honored the gate.",
      "trigger": "A later task asks whether the adapter hard-enforces a boundary.",
      "expected_behavior": "Return a bounded claim unless the exact host path was locally tested.",
      "belief_status": "hypothesis"
    },
    "verification": {
      "status": "pending",
      "evidence_ref": null,
      "result_summary": null
    },
    "calibration": {
      "action": "If a later task overclaims hard enforcement again, supersede this capsule or add an ERR/SOL pair.",
      "confidence_delta": "unchanged",
      "updated_boundary": null
    }
  }
}
```
