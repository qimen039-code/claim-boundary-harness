# Common Error Corpus

The common error corpus stores lightweight execution error-and-solution samples. It is for useful recurring mistakes that are worth preserving as agent training material, including the applied solution and validation, but not severe enough for a full paired `ERR-*` / `SOL-*` incident.

For public, reusable issue classes collected during framework adaptation and
release work, see [common-issues-and-solutions.md](common-issues-and-solutions.md).
Keep private local incidents in lane-scoped `CE-*` records instead of publishing
machine-specific logs or paths.

## When To Use

Use a `CE-*` common error record when:

- the mistake is small but likely to recur;
- it helps future routing or tool-call preflight;
- the user calls it a common error or useful sample;
- the issue is fixed immediately and the solution can be recorded without needing a full incident pair.

Do not use it for:

- data loss or irreversible action risk;
- public/private exposure mistakes;
- repeated failures after prevention was already recorded;
- user-explicit request for full self-reflection matrix recording.

Those should become paired `ERR-*` / `SOL-*` records.

## Auto-Record Boundary

When the adopting runtime allows lane-scoped maintenance writes, the agent may
auto-record a small `CE-*` lesson after it fixes and verifies the issue. This
does not authorize public documentation changes, router-policy changes,
trigger-list edits, cross-lane memory writes, or high-risk incident records.
Mentioning or reading a common-error record only selects this corpus for reuse;
it does not by itself authorize a durable CE write.

Use `feedback_loop_profile` to keep this path cheap:

| Case | Profile | Behavior |
| --- | --- | --- |
| Corpus may be relevant | `index_hint` | Read meta/category hints only. |
| User asks to record a fixed reusable error | `record_candidate` | Write a compact CE candidate after verification. |
| User asks to use prevention or continue diagnosis from a record | `prevention_review` | Open the selected CE payload and apply its prevention loop. |
| User explicitly asks for memory -> prediction -> verification -> calibration | `explicit_cycle` | Run the full feedback loop within normal evidence budgets. |

For the full human/agent split, see
[correction-and-reflection-guide.md](correction-and-reflection-guide.md).

## CE Record Shape

```text
ce_id:
class:
status:
surface:
symptom:
cause:
solution_applied:
prevention:
validation:
upgrade_to_err_sol_when:
evidence:
feedback_loop:
last_reviewed:
```

`feedback_loop` is optional. Use it only when the CE record should actively
predict and check future behavior. For example, a tool-call mistake can predict
that the next similar command should use a corrected flag pattern. If the
mistake recurs after recording, calibrate the record and consider upgrading it
to a paired `ERR-*` / `SOL-*` incident.

Minimal feedback-loop shape:

```text
prediction:
  statement:
  trigger:
  expected_behavior:
  belief_status: hypothesis
verification:
  status: pending | matched | failed | partial | not_applicable
  evidence_ref:
  result_summary:
calibration:
  action:
  confidence_delta: up | down | unchanged | conflicted
  updated_boundary:
```

See [memory-feedback-loop-trial.md](memory-feedback-loop-trial.md).

Recommended classes:

```text
field_schema_error
function_tool_call_error
semantic_routing_error
patch_context_error
powershell_encoding_path_error
git_repo_action_error
```

## Retrieval Chain

```text
common-error-corpus/_META_INDEX.md
-> one class/category row
-> one matching CE-* payload
```

The corpus should stay compact. If it becomes large, split by class indexes before reading payloads.
