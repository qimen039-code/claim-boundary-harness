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
- Provide a command-hook runner for WorkBuddy/CodeBuddy-style hook JSON on stdin.
- Prefer `compact_receipt` for ordinary local execution and expand to the full `routing_receipt` only when `receipt_profile` is `extended_governance` or `debug_receipt`.
- Avoid PowerShell subprocesses in the decision path.
- Do not auto-register a WorkBuddy plugin or patch the installed application.

## Integration Boundary

This package implements the decision layer but does not claim that it is automatically wired into WorkBuddy's internal "execute action" loop.

To make enforcement hard inside WorkBuddy, the host must call `runtime_enforcer(...)` immediately before action execution and treat `status == "blocked"` as a stop. If WorkBuddy still has a direct path that bypasses this function, enforcement is advisory for that path.

For WorkBuddy/CodeBuddy hook deployments, use the provided hook runner:

```bash
AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT="$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime" \
bash "$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime/scripts/workbuddy-hook.sh" \
  --stage pre_tool \
  --constitution-path "$CODEBUDDY_PROJECT_DIR/AGENTS.md" \
  --log-dir "$CODEBUDDY_PROJECT_DIR/.harness-logs"
```

The runner reads hook JSON from stdin. On `UserPromptSubmit`, it stores the original prompt and returns compact route context. On `PreToolUse`, it calls `runtime_enforcer(...)`. If the decision is blocked, it prints a WorkBuddy hook denial payload with `permissionDecision: deny` and exits with code `2`.

If your WorkBuddy build runs command hooks through a Bash-compatible shell, call `scripts/workbuddy-hook.sh` with `bash` as shown above. If your build runs native commands another way, call the Python module directly:

```bash
python -m workbuddy_harness.hook_runner --stage pre_tool --constitution-path "$CODEBUDDY_PROJECT_DIR/AGENTS.md"
```

Set `PYTHON_BIN=python` or `PYTHON_BIN=python3` when the shell cannot find the intended interpreter. Use `--fail-open` only during first-time hook setup; hard enforcement should fail closed.

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

If your host pre-task router stores a routing receipt, keep the original user task text and pass it into pre-tool checks:

```python
decision = runtime_enforcer(
    stage="pre_tool",
    task_text=receipt["risk_level"],
    original_task_text=receipt["original_task_text"],
    tool_name=tool_name,
    tool_input=tool_input,
    constitution_reviewed=True,
)
```

The adapter also accepts `risk_level="R5"` as an explicit override when the host already classified the task. Do not pass only `"R5"` as a replacement for the original task text unless you intentionally want a risk-level-only fallback.

Optional JSONL event logging can write to a specific file with `log_path` or to a directory with `log_dir`. In `log_dir` mode the adapter writes `workbuddy_harness_events.jsonl` inside that directory.

## Verify

From the repository root:

```bash
python -m unittest discover -s integrations/workbuddy-python-runtime/tests
```

To manually smoke-test the hook runner from the adapter root:

```bash
printf '{"hook_event_name":"UserPromptSubmit","session_id":"demo","cwd":".","prompt":"inspect files"}' \
  | python -m workbuddy_harness.hook_runner --stage user_prompt --constitution-reviewed --log-dir ./.harness-logs

printf '{"hook_event_name":"PreToolUse","session_id":"demo","cwd":".","tool_name":"Bash","tool_input":{"command":"rm -rf build"}}' \
  | python -m workbuddy_harness.hook_runner --stage pre_tool --constitution-reviewed --log-dir ./.harness-logs
```

The second command should exit with code `2` and return `permissionDecision: deny`.
