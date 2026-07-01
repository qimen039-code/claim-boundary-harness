# Memory Feedback Loop Trial

This trial adds an optional memory feedback loop to existing memory capsules,
common error records, and paired incident records. It is not a new memory
backend, not a task-cost ledger, and not a requirement for every turn.

Its primary role is internalized reusable-memory use: when the framework selects
a reusable capsule, CE record, ERR/SOL pair, or decision record, the agent should
quietly ask what that memory predicts for the current task, verify whether the
expected behavior is happening, and calibrate the record if the prediction fails.
The operator can still explicitly request or correct this loop, but the design
does not depend on the operator saying "please predict" each time.

Use it only when a selected or newly written memory is expected to prevent
repeated mistakes, guide a future route decision, or change future validation
behavior.

This loop is separate from the causal-attribution loop in
[router-decision-contract.md](router-decision-contract.md). The feedback loop
asks "what should happen next time, and did it happen?" The causal-attribution
gate asks "is this explanation overclaiming mechanism, effect, or causality?"
They may both apply to the same event, but neither one upgrades the other: a
matched feedback prediction does not prove causality, and a causal hypothesis
does not write memory unless the memory route separately authorizes it.

## Loop Shape

```text
memory
-> prediction
-> verification
-> calibration
```

- `memory`: the capsule, CE record, ERR/SOL pair, or decision record being used.
- `prediction`: what this memory expects the agent or route to do when the same
  pattern appears.
- `verification`: what actually happened in the current or later matching task.
- `calibration`: how the rule, confidence, trigger, or boundary changed.

The loop is optional at the schema level but mandatory in decision behavior when
the route selects a reusable record that already carries a `feedback_loop`, a
paired ERR/SOL memory, or a common-error prevention record. Omit it when the
record is a one-off note, a raw observation, an ordinary task state, or a static
manual page.

Route or decision layers should require feedback-loop review for:

- explicit user requests to run the memory/prediction/verification/calibration
  loop;
- selected reusable memory, CE, ERR/SOL, or decision records that already carry
  `feedback_loop`;
- common-error or paired incident records being used to prevent recurrence;
- new reusable records whose purpose is future prevention, routing, or
  validation behavior.

Ordinary discussion and normal task execution should not pay this cost.
Reading a common-error record is not the same as preventing recurrence or
writing a new one.

## Profile And Cost Control

The router exposes `feedback_loop_profile` so adapters can keep the loop cheap:

| Profile | Cost boundary |
| --- | --- |
| `none` | Do not load feedback-loop state. |
| `index_hint` | Expose only compact corpus/index hints; do not open full payloads for the loop. |
| `record_candidate` | Prepare a compact CE candidate after verification; do not run full prediction review by default. |
| `prevention_review` | Open only the selected CE, ERR/SOL, capsule, or decision payload needed to prevent recurrence. |
| `explicit_cycle` | Run the full loop because the user or task explicitly requested it. |

This profile is independent of `risk_level`, `external_need`, `claim_risk`, and
`record_intent`. Those gates still combine by union. For example, a routing
mistake with a current external-source claim may be both a CE write candidate
and an external-research task, without paying the full feedback-loop cost.

## Field Shape

```json
{
  "feedback_loop": {
    "prediction": {
      "statement": "Future PR-publication checks should include current-repo and author-scoped PR lookup before concluding that no PR exists.",
      "trigger": "User asks about previously published PRs, external publication PRs, queue position, or review state.",
      "expected_behavior": "State the lookup scope, check the current repository, then check author-scoped open and closed PRs when publication wording is ambiguous.",
      "belief_status": "hypothesis"
    },
    "verification": {
      "status": "pending",
      "evidence_ref": null,
      "result_summary": null
    },
    "calibration": {
      "action": "If the lookup is missed again, upgrade this CE record to a paired ERR/SOL or router regression.",
      "confidence_delta": "unchanged",
      "updated_boundary": null
    }
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

Recommended `confidence_delta` values:

```text
up
down
unchanged
conflicted
```

## Boundaries

- A prediction is not evidence that the predicted behavior is true or already
  fixed. Keep it as `hypothesis` until later task evidence verifies it.
- Do not add a feedback loop to every small record. The loop is for reusable,
  repeated, high-impact, or explicitly user-requested learning records.
- Do not wait for the operator to request prediction when a selected reusable
  memory already includes a feedback loop or recurrence-prevention role. Treat
  that as part of competent memory reuse.
- Do not create a separate consumption ledger only to support the loop.
- Do not use the loop to promote a claim beyond its `belief_status`.
- Verification must point to evidence refs, raw session records, tool outputs,
  tests, diffs, or reviewed artifacts. A derived summary alone is not enough.
- Calibration changes the future applicability or confidence boundary. It does
  not rewrite the original event.

## Where To Store It

Use this field inside existing records:

- memory capsules that encode reusable behavior or project rules;
- `CE-*` common error records for small recurring mistakes;
- paired `ERR-*` / `SOL-*` incident records;
- decision records whose future route behavior should be checked.

Keep index rows compact. Indexes may mention that a record has
`feedback_loop: pending` or `feedback_loop: matched`, but the full loop belongs
inside the selected payload.

## Promotion Rule

If a prediction succeeds repeatedly, calibration may raise confidence or keep
the rule active. If it fails after being recorded, upgrade the record:

```text
CE-* -> ERR-* / SOL-* pair
or
memory capsule -> superseding capsule with corrected trigger/boundary
or
router rule -> regression test if the behavior is executable
```

This keeps the trial lightweight while still making wrong predictions visible.
