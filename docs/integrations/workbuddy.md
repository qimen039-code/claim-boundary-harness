# WorkBuddy Integration

The public WorkBuddy adapter is a reference bridge for model-facing routing,
bounded context, and optional nonblocking behavior correction. It does not
patch or auto-register itself in the installed WorkBuddy client.

## Capability Boundary

| Capability | Public status | Activation requirement |
| --- | --- | --- |
| `UserPromptSubmit` route context | repository-tested advisory path | target WorkBuddy version can pass prompt JSON to the wrapper |
| Agent-loop action contract | repository-tested schema | host loop consumes every action and returns a receipt |
| Memory context selection | repository-tested reference consumer | host gives selected context back to the model before planning |
| `PreToolUse` current-input correction | optional, disabled by default | exact host rewrite and permission semantics verified |
| R5 authorization and sensitive actions | outside CBH correction | governing instructions plus host-native permission/security boundary |
| `Stop` or final-answer interception | not registered by CBH | not part of this adapter |

The WorkBuddy model agent remains the task owner. CBH does not become a
standalone executor.

## Deployment

Stage a named profile rather than copying the repository:

```bash
python integrations/workbuddy-python-runtime/scripts/build-deployment-bundle.py \
  --profile workbuddy-hook-minimal --output ./cbh-workbuddy-bundle
```

The generated receipt is deployment evidence for the file set, not proof that
the client loaded or called the hook.

The safe default registers only `UserPromptSubmit`:

```text
prompt JSON
-> workbuddy_harness.hook_runner
-> compact advisory route context
-> WorkBuddy model agent plans and executes
```

## Optional PreToolUse Protocol

Do not register this path until the exact WorkBuddy version has been checked.
When verified, configure both the executor dialect and wire protocol:

```bash
python -m workbuddy_harness.hook_runner \
  --stage pre_tool \
  --executor-environment powershell \
  --rewrite-protocol codex_allow_updated_input
```

Only an accepted deterministic profile can return `allow + updatedInput`.
The current public migration covers the historically recurring PowerShell
statement-loop pipeline shape and verifies the rewritten candidate with the
actual PowerShell parser while preserving the command subject, working
directory, and non-command input fields.

No match, ambiguity, parser failure, missing module, invalid input, or
unsupported environment produces an empty output and exit code `0`. This path
never emits deny, freezes a task, stores approval state, writes memory, mutates
policy, or creates a permit.

Because `permissionDecision: allow` may have host-specific permission meaning,
the target WorkBuddy build must prove that this optional protocol does not
bypass its native confirmation or sandbox before registration. Otherwise keep
the adapter in advisory prompt-only mode.

## Full Agent-Loop Integration

Use `workbuddy-loop-integration-sdk` only when the host can call:

- `intake_router(...)`;
- `build_agent_loop_contract(route)`;
- `harness_action_consumer.py` or an equivalent bounded context consumer;
- `validate_agent_loop_receipt(contract, receipt)`.

Route fields such as `memory_source_hints`, `external_need`,
`feedback_loop_profile`, `skill_lifecycle_profile`, `tool_surface_need`,
`preferred_call_surface`, `first_principles_profile`, and `skill_audit_profile` are only context until
the matching host-owned surface consumes them. Do not report full activation
without a complete consumption receipt.

## Validation

Run repository tests first:

```bash
python -m unittest discover -s integrations/workbuddy-python-runtime/tests
python -m pytest -q tests/test_nonblocking_runtime_contract.py
```

Then, in a disposable workspace on the exact target WorkBuddy version:

1. verify the prompt hook loads and returns advisory context;
2. verify normal tasks still proceed when the bridge emits no output;
3. if considering PreToolUse, inspect the real event/tool-input schema;
4. verify native permission prompts remain authoritative;
5. replay the known `foreach {...} | ...` regression and confirm the rewritten
   input preserves all non-command fields;
6. force a parser or module failure and confirm silent no-op behavior.

Client version, event names, matcher syntax, payload shape, and permission
semantics are drift-sensitive. Re-run these checks after WorkBuddy updates.

## Non-Goals

- no installed-client patching or plugin auto-registration;
- no CBH-owned authorization, deny, freeze, permit, or replay ledger;
- no `Stop` hook or final-answer blocker;
- no replacement for WorkBuddy's native permission system, sandbox, UAC, or
  operating-system access control.

Implementation details and bundle commands are in
[`integrations/workbuddy-python-runtime/README.md`](../../integrations/workbuddy-python-runtime/README.md).
