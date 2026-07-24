# WorkBuddy Python Runtime Adapter

Experimental, model-facing WorkBuddy reference adapter for Claim Boundary
Harness. The WorkBuddy model agent remains responsible for planning, semantic
judgment, tool use, recovery, and the final answer.

## Verified Boundary

Repository tests currently verify:

- advisory `UserPromptSubmit` routing context;
- host-model ownership through `cbh.workbuddy_agent_loop_contract.v1`;
- stateless, nonblocking current-input correction for the bundled PowerShell
  `foreach {...} | ...` regression shape;
- silent no-op on no match, ambiguity, parser failure, invalid payload, or
  unavailable correction code;
- no CBH permit ledger, denial, freeze, approval state, or `Stop` hook.

This is not a WorkBuddy-version certification. In particular, the optional
`allow + updatedInput` protocol is reused from the reference hook contract and
must not be registered until the exact target WorkBuddy version's rewrite and
permission semantics are verified. CBH does not grant execution authority.

## Deploy A Named Profile

List the minimal bundle without writing it:

```bash
python integrations/workbuddy-python-runtime/scripts/build-deployment-bundle.py \
  --profile workbuddy-hook-minimal --list
```

Stage the exact runtime bundle:

```bash
python integrations/workbuddy-python-runtime/scripts/build-deployment-bundle.py \
  --profile workbuddy-hook-minimal --output ./cbh-workbuddy-bundle
```

The generated `cbh-deployment-receipt.json` records the selected profile and
files. Do not deploy the entire repository as a runtime bundle.

## Default Hook Mode

The public default registers only `UserPromptSubmit`:

```text
UserPromptSubmit
-> compact advisory route context
-> host model agent continues the task
```

The wrappers read hook JSON from stdin and always fail open to an empty output
with exit code `0`. They do not store session or authorization state.

```bash
bash integrations/workbuddy-python-runtime/scripts/workbuddy-hook.sh \
  --stage user_prompt --cwd "$CODEBUDDY_PROJECT_DIR"
```

On Windows, use `scripts/workbuddy-hook.cmd`; set `PYTHON_BIN` when `python` is
not the intended interpreter.

## Optional PreToolUse Correction

Enable this only after the host protocol has been verified:

```bash
python -m workbuddy_harness.hook_runner \
  --stage pre_tool \
  --executor-environment powershell \
  --rewrite-protocol codex_allow_updated_input
```

The payload must expose a command-shaped `tool_input` and a recognized command
tool name (`Bash`, `PowerShell`, `shell`, or `shell_command`). An accepted
deterministic profile may return:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "updatedInput": {"command": "<verified rewrite>"}
  }
}
```

No match or any verification failure returns no output. The rewrite preserves
the other `tool_input` fields. The `allow` token is part of this optional wire
format; it is not a CBH authorization decision, so the target host must prove
that it does not bypass native permission checks before registration.

## Agent-Loop Integration

`build_agent_loop_contract(route)` turns routed memory, research, skill,
tool-surface, claim, and review fields into explicit host-owned actions.
`validate_agent_loop_receipt(contract, receipt)` checks that every action was
consumed or marked not applicable with a reason.

Relevant advisory fields include `memory_mode`, `memory_source_hints`,
`external_need`, `feedback_loop_profile`, `skill_lifecycle_profile`,
`tool_surface_need`, `preferred_call_surface`, `first_principles_profile`, and
`skill_audit_profile`.

The `workbuddy-loop-integration-sdk` profile also includes
`harness_action_consumer.py`. A host may use it to select bounded,
provenance-bearing memory context and return that context to the model before
planning. It does not execute the user's task.

Do not claim full-loop activation until the real WorkBuddy Agent Loop returns a
complete host-owned consumption receipt.

## Tests

```bash
python -m unittest discover -s integrations/workbuddy-python-runtime/tests
python -m pytest -q tests/test_nonblocking_runtime_contract.py
```

The staged-bundle regression launches the packaged module in a subprocess and
checks the real PowerShell parser-backed `foreach` correction. These tests prove
the repository-side adapter contract only; adopters must still test their exact
WorkBuddy build and hook payload.

## Non-Goals

- no plugin auto-registration or installed-client patching;
- no CBH-owned R5 permit, deny, freeze, approval, or replay state;
- no `Stop`, final-answer interception, or background task engine;
- no replacement for governing instructions, native permission prompts,
  sandboxing, UAC, or operating-system access control.
