# WorkBuddy Python Runtime Adapter

Experimental public WorkBuddy-oriented Python adapter for Agent Memory Lane Harness.

This adapter shows how the same routing, memory-isolation, claim-check, and runtime-enforcement decisions can be called as in-process Python functions instead of launching PowerShell subprocesses.

It is not a general Python distribution of the framework. It is a reference adapter for hosts that own or can modify their agent execution loop.

## Validation Boundary

This adapter has not been fully tested across WorkBuddy versions, operating systems, or real production agent loops. It was drafted from one local device's WorkBuddy/CodeBuddy runtime surface and verified only with local Python unit tests against the shared policy file.

Treat it as a starting point. Before relying on it as a hard control path, test it inside the exact WorkBuddy version, workspace, tool schema, permission mode, and hook or loop entry point you use.

## Scope

- Reuse the public `embedded_harness_policy.json` as the policy source.
- Provide in-process Python functions for routing, memory isolation, claim checks, and runtime enforcement decisions.
- Prefer `compact_receipt` for ordinary local execution and expand to the full `routing_receipt` only when `receipt_profile` is `extended_governance` or `debug_receipt`.
- Avoid PowerShell subprocesses in the decision path.
- Do not auto-register a WorkBuddy plugin or patch the installed application.

## Integration Boundary

This package implements the decision layer but does not claim that it is automatically wired into WorkBuddy's internal "execute action" loop.

To make enforcement hard inside WorkBuddy, the host must call `runtime_enforcer(...)` immediately before action execution and treat `status == "blocked"` as a stop. If WorkBuddy still has a direct path that bypasses this function, enforcement is advisory for that path.

## Expected Host Hook

```python
from workbuddy_harness import load_policy, runtime_enforcer

policy = load_policy()

decision = runtime_enforcer(
    stage="pre_tool",
    task_text=user_prompt,
    cwd=current_workspace,
    tool_name=tool_name,
    tool_input=tool_input,
    human_confirmed=user_confirmed,
    boundary_reviewed=boundary_reviewed,
    constitution_reviewed=constitution_reviewed,
    constitution_path=project_agents_path,
    policy=policy,
)

if decision["status"] == "blocked":
    raise RuntimeError(decision["blocked_reasons"])
```

## Verify

From the repository root:

```bash
python -m unittest discover -s integrations/workbuddy-python-runtime/tests
```
