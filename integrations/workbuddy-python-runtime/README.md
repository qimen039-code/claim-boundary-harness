# WorkBuddy Python Runtime Adapter

Experimental public WorkBuddy-oriented Python adapter for Claim Boundary Harness.

This adapter shows how the same routing, memory-isolation, claim-check, and runtime-enforcement decisions can be called as in-process Python functions instead of launching PowerShell subprocesses.

It is not a general Python distribution of the framework. It is a reference adapter for hosts that own or can modify their agent execution loop.

## Validation Boundary

This adapter has not been fully tested across WorkBuddy versions, operating systems, or real production agent loops. It is a public reference adapter verified with local Python unit tests against the shared policy file; adopters must validate the exact runtime surface they use.

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

Wire prompt, command-tool, and final-answer stages when you want the strongest hook-only deployment:

```text
UserPromptSubmit -> original-task state, with silent route classification by default
PreToolUse(Bash|PowerShell) -> command-tool hard gate before execution
Stop -> final strong-claim gate before display
```

`UserPromptSubmit` stores the original task before planning.
It keeps ordinary low-risk classification silent and injects only minimal boundary context when memory, search, claim, confirmation, low-confidence, governance, conversation-linking, or debug behavior changes the next action.
`PreToolUse` enforces the protected command-tool path before execution.
It also blocks continuation, merge, archive, or cross-conversation memory tasks until the adapter marks the conversation-link decision as resolved.
`Stop` can block or downgrade final answers that contain strong validation claims without claim-schema evidence.

Route output also includes `skill_lifecycle_profile`,
`hybrid_retrieval_profile`, and `memory_write_profile`. These fields let a host
loop keep idle skills listing-only, open selected active frames, write
`skill_release_receipt` records, strengthen memory lookup inside the existing
meta-first path, and enforce context-complete write shape when a durable memory
write/update has already been selected. They are advisory unless the host owns
the relevant skill context or memory read/write execution path.

Route output may also include `tool_surface_need`,
`tool_discovery_status`, `skill_or_tool_need`, `plugin_need`, and
`preferred_call_surface`. A WorkBuddy-compatible loop can use these fields to
check native skills, plugins, connectors, MCP/app tools, or browser surfaces
before falling back to shell or raw web. They are advisory unless the host owns
tool selection; using an external account, login, connector, or different
execution surface still requires the host's normal authorization boundary.

When the host writes memory payloads, it may preserve optional `feedback_loop`
fields from the memory feedback-loop trial. The Python adapter does not verify
that loop by itself. Treat `prediction` as a hypothesis, require a later
evidence reference before `verification` becomes matched, and keep this separate
from any per-task token or consumption ledger.

Prefer a command-tool matcher such as `Bash|PowerShell` for the first hard `PreToolUse` deployment. A broad `*` matcher can route Write/Edit file content through the command-risk gate and create false positives when a document merely mentions high-risk words. Gate file tools with a separate schema-aware file policy if you need hard file-write enforcement.

If your WorkBuddy build runs command hooks through a Bash-compatible shell, call `scripts/workbuddy-hook.sh` with `bash` as shown above. If your build runs native commands another way, call the Python module directly:

```bash
python -m workbuddy_harness.hook_runner --stage pre_tool --constitution-path "$CODEBUDDY_PROJECT_DIR/AGENTS.md"
```

On Windows, if `bash` is not available on PATH, use `scripts/workbuddy-hook.cmd` through `cmd.exe /c` and set `PYTHON_BIN` when plain `python` is not the intended interpreter.

Set `PYTHON_BIN=python`, `PYTHON_BIN=python3`, or an absolute Python executable path when the shell cannot find the intended interpreter. The included Bash and `cmd.exe` wrappers set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` by default so Chinese prompts and other non-ASCII hook payloads do not fail in mixed Windows shell environments. Use `--fail-open` only during first-time hook setup; hard enforcement should fail closed.

Some WorkBuddy builds may not expose a visible hook UI. If that happens, inspect the documented project or user settings JSON for that exact version and edit it only with operator approval. Hook settings, event names, matcher syntax, and denial behavior are client-version sensitive.

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
    conversation_link_resolved=conversation_link_resolved,
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

For an explicit R5 confirmation, prefer a short-lived single-event permit over a broad boolean flag:

```python
decision = runtime_enforcer(
    stage="pre_tool",
    task_text=user_prompt,
    tool_name=tool_name,
    tool_input=tool_input,
    human_confirmation_permit_json=permit_json,
    human_confirmation_permit_use_ledger_path=".harness-logs/r5-permit-uses.jsonl",
    constitution_reviewed=True,
)
```

The permit must use schema `cbh.r5_human_confirmation_permit.v1`, `scope="single_event"`, an unexpired timestamp, and hashes for the exact task text plus command-scoped tool text. After a concrete tool event passes, the used-ledger blocks replay of the same permit/task/tool combination.

For conversation-memory continuation or merge tasks, run meta-first lookup and link selection before the first protected tool call. Then pass `conversation_link_resolved=True` to the in-process adapter or `--conversation-link-resolved` to the hook runner. Without that flag, `PreToolUse` blocks with `conversation_link_decision_required`.

Optional quality-reference and claim-artifact surfaces are outside the current hard gate path. A WorkBuddy host may pass `domain_aesthetic_rubric` or `domain_source_tier_catalog` records to its planner as advisory context, but the Python runtime should still treat them as source-prior metadata rather than execution permissions or validated facts. If the host adds a claim-artifact renderer, prefer a JSON file handoff with original evidence refs and a bounded repair loop; do not pass large nested artifacts through shell arguments.

Optional JSONL event logging can write to a specific file with `log_path` or to a directory with `log_dir`. In `log_dir` mode the adapter writes `workbuddy_harness_events.jsonl` inside that directory.

Hook payloads are sanitized before routing and logging. If the host passes stdin JSON containing lone UTF-16 surrogate escapes such as `\udcac` or `\udc80`, the runner replaces them with `<invalid-surrogate>` so malformed payload text does not disable active routing or pre-tool enforcement.

Recording or voice input is supported only as host-provided text. The hook runner can extract bounded text from fields such as `transcript`, `transcription`, `caption`, `content`, `message`, or `text`, including inside a recording or attachment object. It ignores raw media blobs, bytes, base64 strings, and binary fields. If the host only provides a recording file path or audio bytes, add transcription in the host first; this adapter does not open or decode arbitrary recording files.

For final-answer gating, send the Stop/final hook payload with one of `final_text`, `response`, `answer`, `message`, `content`, `output`, or `text`. The runner passes that body into `runtime_enforcer(stage="final")`.

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

printf '{"hook_event_name":"Stop","session_id":"demo","cwd":".","final_text":"This result is validated and verified successfully."}' \
  | python -m workbuddy_harness.hook_runner --stage final --constitution-reviewed --log-dir ./.harness-logs
```

The second command should exit with code `2` and return `permissionDecision: deny`.
The third command should also exit with code `2` unless you provide a valid claim schema through a custom final-check path.
