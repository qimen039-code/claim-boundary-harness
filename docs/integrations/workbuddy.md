# WorkBuddy Integration Example

This repository includes an experimental WorkBuddy-oriented Python runtime adapter:

```text
integrations/workbuddy-python-runtime
```

Use it when the host can call Python functions inside the agent control flow instead of launching a shell script for every decision.

## Boundary

The adapter is not automatically installed into WorkBuddy. It is a reference implementation of the decision layer:

- `intake_router`;
- `memory_isolation_gate`;
- `claim_schema_verifier`;
- `runtime_enforcer`.

Hard enforcement requires WorkBuddy or a WorkBuddy-compatible host to call `runtime_enforcer(...)` immediately before action execution and to stop when it returns `status: blocked`.

If the host still has any execution path that bypasses this function, enforcement for that path is advisory.

## Validation Status

This adapter has not been fully tested across WorkBuddy versions, operating systems, permission modes, or real production agent loops. It was adapted from one local device environment and verified as a standalone Python decision layer.

Before relying on it:

1. Confirm the WorkBuddy version and hook or loop surface.
2. Confirm the adapter loads the intended `embedded_harness_policy.json`.
3. Run the unit tests.
4. Wire the function before action execution.
5. Test an allowed tool call, an R5 command, a memory-boundary violation, and a strong-claim final check.

## Smoke Test

```bash
python -m unittest discover -s integrations/workbuddy-python-runtime/tests
```
