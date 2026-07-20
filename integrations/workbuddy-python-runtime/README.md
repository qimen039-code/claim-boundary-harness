# WorkBuddy Python Runtime Adapter

Experimental public WorkBuddy-oriented Python adapter for Claim Boundary Harness.

This adapter shows how the same routing, bounded memory-context selection,
memory-isolation, claim-check, and runtime-enforcement decisions can be called
inside a WorkBuddy model-agent loop instead of launching PowerShell subprocesses.
The host model remains responsible for the user's task, tools, semantic
judgment, recovery, and final answer.

It is not a general Python distribution of the framework. It is a reference adapter for hosts that own or can modify their agent execution loop.

## Validation Boundary

This adapter has not been fully tested across WorkBuddy versions, operating systems, or real production agent loops. It is a public reference adapter verified with local Python unit tests against the shared policy file; adopters must validate the exact runtime surface they use.

Treat it as a starting point. Before relying on it as a hard control path, test it inside the exact WorkBuddy version, workspace, tool schema, permission mode, and hook or loop entry point you use.

## Deployment Profiles: Do Not Copy The Repository

Use `deployment-profiles.json` as the machine-readable deployment source. The
default WorkBuddy profile contains only the Python hook runtime, wrappers,
root instruction entry, and compiled policy; it excludes papers, articles,
research notes, examples, changelog material, and development tests.

List the exact files without writing anything:

```bash
python integrations/workbuddy-python-runtime/scripts/build-deployment-bundle.py --profile workbuddy-hook-minimal --list
```

Stage a clean bundle into an empty directory:

```bash
python integrations/workbuddy-python-runtime/scripts/build-deployment-bundle.py --profile workbuddy-hook-minimal --output ./cbh-workbuddy-bundle
```

The output receipt records the profile and exact file list. Copying the entire
repository is a source/development operation, not the supported runtime
deployment path.

## Hook-Only Versus Agent-Loop Integration

Hook-only mode hard-enforces only the WorkBuddy paths that actually call the
hook: the wired pre-tool R5/path checks. The minimal profile keeps `Stop`
disabled by default because some WorkBuddy builds stream part of the answer
before the hook finishes and render Stop feedback as a user prompt. Route
fields such as `memory_mode`, `memory_source_hints`, `external_need`,
`feedback_loop_profile`, `skill_lifecycle_profile`, `tool_surface_need`,
`first_principles_profile`, and `skill_audit_profile` remain prompt context
unless the host Agent Loop consumes them.

`build_agent_loop_contract(route)` converts those fields into explicit host
actions using schema `cbh.workbuddy_agent_loop_contract.v1`.
`validate_agent_loop_receipt(contract, receipt)` checks a host-owned
consumption receipt. These functions make the missing integration testable;
they do not claim that stock WorkBuddy calls the consumer. Use the
`workbuddy-loop-integration-sdk` profile only when the host team will wire that
consumer into its real planning, memory, search, tool-selection, skill, and
final-review surfaces.

For memory reads, the contract exposes `memory_context_retrieval` with exact
route-declared roots and `result_target: model_agent_additional_context`. The
loop-integration bundle includes the generic `harness_action_consumer.py`; a
host may call it or an equivalent consumer, then give the selected bounded
context back to the model before planning. This is context compilation, not an
independent WorkBuddy task runner.

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

Wire prompt and command-tool stages for the safe default hook-only deployment:

```text
UserPromptSubmit -> original-task state, with silent route classification by default
PreToolUse(Bash|PowerShell) -> command-tool hard gate before execution
```

`UserPromptSubmit` stores the original task before planning.
It keeps ordinary low-risk classification silent and injects only minimal boundary context when memory, search, claim, confirmation, low-confidence, governance, conversation-linking, or debug behavior changes the next action.
`PreToolUse` enforces the protected command-tool path before execution.
It also blocks continuation, merge, archive, or cross-conversation memory tasks until the adapter marks the conversation-link decision as resolved.
Keep final-claim handling advisory/self-downgrading unless the exact host build
passes all three Stop compatibility checks: no user-prompt injection, no
partial stream fragment, and no attribution of hook feedback to the user.
Only then opt in to `Stop` as a conditional final-claim gate.

Route output also includes `skill_lifecycle_profile`,
`hybrid_retrieval_profile`, and `memory_write_profile`. These fields let a host
loop keep idle skills listing-only, open selected active frames, write
`skill_release_receipt` records, strengthen memory lookup inside the existing
meta-first path, and enforce context-complete write shape when a durable memory
write/update has already been selected. They are advisory unless the host owns
the relevant skill context or memory read/write execution path.

The prompt hook now records an `agent_loop_contract` in
`workbuddy_hook_state.json` and emits compact `loop_actions=...` plus
`loop_consumer=required` context when host-loop work is needed. This remains
advisory until the WorkBuddy Agent Loop reads the contract and returns a
consumption receipt.

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

The hook runner also includes a WorkBuddy confirmation bridge. A host-owned
permission prompt can attach a `cbh.workbuddy_human_confirmation.v1` envelope
to the exact `PreToolUse` payload, or use the compact
`runtime_human_confirmation="confirmed"`, `runtime_confirmation_ts`, and
`runtime_confirmation_id` fields. The hook trusts those fields only as a host
contract: the WorkBuddy adapter must set them after an actual human response,
not from model-generated text.

An explicit user reply in the conversation can also arm the next matching R5
tool event. Full phrases such as `允许执行`, `授权完整清除`, or `确认放行` are
accepted; a short `允许` or `确认` is accepted only when the stored session route
was already waiting for human confirmation. The bridge creates the exact
task/tool permit only at `PreToolUse`, stores its use in the configured
workspace log directory, and removes the pending confirmation after one pass.
Keep every hook stage on the same absolute `--log-dir`; do not use a
`LOCALAPPDATA` confirmation file as cross-account IPC.

This is a CBH hook release only. It does not grant administrator privileges or
bypass UAC. A command that passes CBH can still fail with an operating-system
permission error and then needs WorkBuddy's real elevation path or manual
execution in an administrator-owned terminal.

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
