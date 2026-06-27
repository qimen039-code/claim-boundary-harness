# CE-EXAMPLE-YYYY-MM-DD

ce_id: CE-EXAMPLE-YYYY-MM-DD
class: patch_context_error
status: TEMPLATE
surface: apply_patch / file edit
last_reviewed: YYYY-MM-DD

## Symptom

Short description of the recurring small mistake.

## Cause

Why the mistake happened.

## Solution Applied

What fixed the issue this time. Include the smallest repeatable fix path, not just a general recommendation.

## Prevention

Small reusable rule that prevents the mistake.

## Validation

How the fix was checked. Include command output, file inspection, test result, or another bounded verification signal.

## Upgrade To ERR/SOL When

When this lightweight sample should become a full paired incident.

## Evidence

Synthetic or adopter-owned evidence only. Do not include private records in the public template.

## Feedback Loop

Optional. Use only when this CE record should predict and check future
behavior.

```yaml
feedback_loop:
  prediction:
    statement: "What should happen differently next time."
    trigger: "When this prediction applies."
    expected_behavior: "Small action or routing behavior expected next time."
    belief_status: hypothesis
  verification:
    status: pending
    evidence_ref: null
    result_summary: null
  calibration:
    action: "What to change if the prediction succeeds or fails."
    confidence_delta: unchanged
    updated_boundary: null
```
