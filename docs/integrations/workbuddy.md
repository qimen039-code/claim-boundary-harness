# WorkBuddy Integration Example

This repository includes an experimental WorkBuddy-oriented Python runtime adapter:

```text
integrations/workbuddy-python-runtime
```

Use it when the host can call Python functions inside the agent control flow instead of launching a shell script for every decision.

## Boundary

The adapter is not automatically installed into WorkBuddy and does not patch the installed WorkBuddy application. It is a reference implementation of the decision layer:

- `intake_router`;
- `memory_isolation_gate`;
- `claim_schema_verifier`;
- `runtime_enforcer`.

Hard enforcement requires WorkBuddy or a WorkBuddy-compatible host to call the adapter immediately before action execution and to stop when it returns `status: blocked`.

If the host still has any execution path that bypasses this function or hook, enforcement for that path is advisory.

## Recommended WorkBuddy Hook Deployment

The most practical public deployment is:

```text
UserPromptSubmit hook
-> workbuddy_harness.hook_runner stores the original prompt and route context
PreToolUse hook
-> workbuddy_harness.hook_runner calls runtime_enforcer
-> blocked decision returns permissionDecision: deny and exits with code 2
```

That gives the harness a real pre-tool interception point without editing WorkBuddy internals.

### 1. Place The Adapter In The Workspace

Keep this directory inside the adopting workspace:

```text
integrations/workbuddy-python-runtime
```

Keep or create a root instruction file such as:

```text
AGENTS.md
```

The runtime enforcer checks for this constitution entry on nontrivial work unless you explicitly pass `--constitution-reviewed`.

### 2. Configure WorkBuddy Hooks

Add hook commands through the hook/settings surface supported by your WorkBuddy version. Some WorkBuddy/CodeBuddy builds run command hooks through a Bash-compatible shell; for those, use the included Bash wrapper.

Example project-level hook shape:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT=\"$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime\" bash \"$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime/scripts/workbuddy-hook.sh\" --stage user_prompt --constitution-path \"$CODEBUDDY_PROJECT_DIR/AGENTS.md\" --log-dir \"$CODEBUDDY_PROJECT_DIR/.harness-logs\""
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT=\"$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime\" bash \"$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime/scripts/workbuddy-hook.sh\" --stage pre_tool --constitution-path \"$CODEBUDDY_PROJECT_DIR/AGENTS.md\" --log-dir \"$CODEBUDDY_PROJECT_DIR/.harness-logs\""
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT=\"$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime\" bash \"$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime/scripts/workbuddy-hook.sh\" --stage post_tool --log-dir \"$CODEBUDDY_PROJECT_DIR/.harness-logs\""
          }
        ]
      }
    ]
  }
}
```

If your shell does not expose `python3`, set `PYTHON_BIN=python` in the command. If your WorkBuddy build does not expose `CODEBUDDY_PROJECT_DIR`, replace it with your workspace path. If your WorkBuddy version runs hooks through a different shell, call the module directly with your shell's quoting rules:

```bash
python -m workbuddy_harness.hook_runner --stage pre_tool --constitution-path "$CODEBUDDY_PROJECT_DIR/AGENTS.md"
```

Use WorkBuddy's own hook review UI or hook inspection command after editing settings. Hook settings are version-specific, so confirm the exact path and review behavior for your installed WorkBuddy build.

### 3. Verify The Hard Block

Run the adapter tests:

```bash
python -m unittest discover -s integrations/workbuddy-python-runtime/tests
```

Then verify the actual WorkBuddy hook path:

1. Send a normal read-only task and confirm it proceeds.
2. Try a known high-risk command such as a destructive shell command in a disposable test workspace.
3. Confirm WorkBuddy stops before the tool executes.
4. Confirm `.harness-logs/workbuddy_harness_events.jsonl` records the decision.

The expected hard-block behavior is:

```text
hook event: PreToolUse
runner output: permissionDecision = deny
runner exit code: 2
tool execution: stopped before running
```

If WorkBuddy logs show the hook ran but the tool still executed, the host is not honoring the hook denial on that path. Treat that path as advisory until the WorkBuddy runtime or settings are corrected.

### 4. Setup Mode Versus Enforcement Mode

During first-time setup, `--fail-open` can help diagnose Python paths or shell quoting without blocking normal work.

For enforcement, remove `--fail-open`. The default is fail-closed for `PreToolUse`: if the hook runner itself fails, it denies the tool call instead of silently bypassing the harness.

## Validation Status

This adapter has not been fully tested across WorkBuddy versions, operating systems, permission modes, or real production agent loops. It was adapted from one local device environment and verified as a standalone Python decision layer.

Before relying on it:

1. Confirm the WorkBuddy version and hook or loop surface.
2. Confirm the adapter loads the intended `embedded_harness_policy.json`.
3. Run the unit tests.
4. Wire either the hook runner or the in-process function before action execution.
5. Test an allowed tool call, an R5 command, a memory-boundary violation, and a strong-claim final check.

When wiring a pre-tool hook after a pre-task router, preserve the original task text. Passing only a compact field such as `risk_level` can remove the task evidence that the runtime enforcer needs for routing. The Python adapter accepts `original_task_text` and an explicit `risk_level` override for this case.

If event logging is enabled, pass `log_path` for a concrete JSONL file or `log_dir` for a directory. `log_dir` mode writes to `workbuddy_harness_events.jsonl` inside that directory.

The hook runner also stores `workbuddy_hook_state.json` in the log directory so `PreToolUse` can use the original `UserPromptSubmit` text instead of routing from a compact field such as `R5`.

## Smoke Test

```bash
python -m unittest discover -s integrations/workbuddy-python-runtime/tests
```
