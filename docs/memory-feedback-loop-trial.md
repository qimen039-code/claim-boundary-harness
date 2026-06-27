# Memory Feedback Loop Trial

This trial adds an optional memory feedback loop to existing memory capsules,
common error records, and paired incident records. It is not a new memory
backend, not a task-cost ledger, and not a requirement for every turn.

Use it only when a memory is expected to prevent repeated mistakes, guide a
future route decision, or change future validation behavior.

## Loop Shape

```text
memory
-> prediction
-> verification
-> calibration
```

- `memory`: the capsule, CE record, ERR/SOL pair, or decision record being used.
- `prediction`: what should happen the next time the same pattern appears.
- `verification`: what actually happened when the pattern reappeared.
- `calibration`: how the rule, confidence, trigger, or boundary changed.

The loop is optional. Omit it when the record is a one-off note, a raw
observation, an ordinary task state, or a static manual page.

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
