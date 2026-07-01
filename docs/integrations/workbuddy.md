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

The most practical public deployment is a three-layer hook chain:

```text
UserPromptSubmit hook
-> workbuddy_harness.hook_runner stores the original prompt and route context
PreToolUse hook for command tools
-> workbuddy_harness.hook_runner calls runtime_enforcer
-> blocked decision returns permissionDecision: deny and exits with code 2
Stop hook
-> workbuddy_harness.hook_runner checks final strong claims before display
```

That gives the harness a real pre-tool interception point without editing WorkBuddy internals.

`UserPromptSubmit` is required for active routing. If only `PreToolUse` is wired, the runtime can still block high-risk tools, but the agent may not preserve the original task state before planning. Ordinary low-risk prompt-stage classifications stay silent; boundary-changing classifications inject minimal context.

Prefer a command-tool matcher such as `Bash|PowerShell` for the first hard `PreToolUse` deployment. A broad `*` matcher can pass file-edit payloads through the hard command gate; documentation or patch content may contain words such as `delete`, `permission`, or `rm -rf` without being an attempted command. If you want to gate file tools too, add a separate file-tool policy that understands that tool's schema instead of reusing command-pattern matching on raw file content.

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

Add hook commands through the hook/settings surface supported by your WorkBuddy version. Some WorkBuddy/CodeBuddy builds run command hooks through a Bash-compatible shell; for those, use the included Bash wrapper. On Windows builds where `bash` is not available, use the included `cmd.exe` wrapper instead.

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
        "matcher": "Bash|PowerShell",
        "hooks": [
          {
            "type": "command",
            "command": "AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT=\"$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime\" bash \"$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime/scripts/workbuddy-hook.sh\" --stage pre_tool --constitution-path \"$CODEBUDDY_PROJECT_DIR/AGENTS.md\" --log-dir \"$CODEBUDDY_PROJECT_DIR/.harness-logs\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT=\"$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime\" bash \"$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime/scripts/workbuddy-hook.sh\" --stage final --constitution-path \"$CODEBUDDY_PROJECT_DIR/AGENTS.md\" --log-dir \"$CODEBUDDY_PROJECT_DIR/.harness-logs\""
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

Windows `cmd.exe` wrapper shape:

```json
{
  "type": "command",
  "command": "cmd.exe /c \"\"%CODEBUDDY_PROJECT_DIR%\\integrations\\workbuddy-python-runtime\\scripts\\workbuddy-hook.cmd\" --stage user_prompt --constitution-path \"%CODEBUDDY_PROJECT_DIR%\\AGENTS.md\" --log-dir \"%CODEBUDDY_PROJECT_DIR%\\.harness-logs\"\""
}
```

Set `PYTHON_BIN` to the intended Python executable when plain `python` is not the runtime you want.

Use WorkBuddy's own hook review UI or hook inspection command after editing settings. Some builds may not expose a visible `/hooks` UI; in that case, inspect the documented project or user settings JSON surface for your version and edit it only after the user/operator has approved that configuration change. Hook settings are version-specific, so confirm the exact path and review behavior for your installed WorkBuddy build.

The Bash and `cmd.exe` wrappers set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` by default. Keep those settings when routing Chinese prompts or other non-ASCII text through Windows Git Bash or mixed Windows shells.

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

This adapter has been verified as a standalone Python decision layer and has one local WorkBuddy hook deployment reported as running normally with this package.

This is still not a broad WorkBuddy compatibility certification. It has not been fully tested across WorkBuddy versions, operating systems, permission modes, or production agent loops.

Before relying on it:

1. Confirm the WorkBuddy version and hook or loop surface.
2. Confirm the adapter loads the intended `embedded_harness_policy.json`.
3. Run the unit tests.
4. Wire either the hook runner or the in-process function before action execution.
5. Test an allowed tool call, an R5 command, a valid then replayed single-event permit, a memory-boundary violation, and a strong-claim final check.

When wiring a pre-tool hook after a pre-task router, preserve the original task text. Passing only a compact field such as `risk_level` can remove the task evidence that the runtime enforcer needs for routing. The Python adapter accepts `original_task_text` and an explicit `risk_level` override for this case.

If event logging is enabled, pass `log_path` for a concrete JSONL file or `log_dir` for a directory. `log_dir` mode writes to `workbuddy_harness_events.jsonl` inside that directory.

The hook runner also stores `workbuddy_hook_state.json` in the log directory so `PreToolUse` can use the original `UserPromptSubmit` text instead of routing from a compact field such as `R5`.

Conversation-memory continuation, merge, archive, and cross-conversation update tasks require a resolved link decision before the first protected tool call. The adapter blocks unresolved cases with `conversation_link_decision_required`; after meta-first lookup and link selection are complete, pass `conversation_link_resolved=True` to the in-process function or `--conversation-link-resolved` to the hook runner.

For R5 or hard-tool confirmation across hook stages, pass
`human_confirmation_permit_json` / `human_confirmation_permit_path` to the
in-process function or `--human-confirmation-permit-json` /
`--human-confirmation-permit-path` to the hook runner. The permit must be a
`cbh.r5_human_confirmation_permit.v1` object with `scope: single_event`, an
unexpired timestamp, and task/tool SHA-256 hashes for the exact event. Use
`human_confirmation_permit_use_ledger_path` or
`--human-confirmation-permit-use-ledger-path` to pin the replay ledger used to
block the same permit/task/tool combination after it passes. A broad session
confirmation should still be treated as unsafe.

For nested claim payloads, prefer a file-based claim handoff such as `--ClaimFile` in the PowerShell reference scripts or a JSON file path in custom adapters. Passing deeply nested JSON directly through multiple shells is fragile because each shell has different quote and escape rules.

## Optional Quality Reference And Claim Artifacts

The current WorkBuddy Python adapter implements routing, skill lifecycle
profile output, memory isolation, hybrid retrieval profile output, memory write
granularity profile output, R5/runtime gates, conversation-link blocking, and
final claim checks. It does not implement a full quality-reference layer or a
claim-artifact renderer.

`hybrid_retrieval_profile` and `memory_write_profile` are decision fields, not
new host-owned hard gates. A WorkBuddy-compatible loop can use them to choose
meta-first hybrid lookup and context-complete write shape before opening memory
payloads or writing capsules. If the host only injects route context but does
not own memory reads/writes, record those fields as advisory in the compatibility
manifest.

`feedback_loop` is a router/decision gate plus memory payload convention, not a
host hard-stop gate. If a WorkBuddy-compatible loop selects or writes CE records,
memory capsules, paired incidents, or decision records, it can preserve optional
memory -> prediction -> verification -> calibration fields and require the loop
when those reusable records are used for recurrence prevention. Predictions
remain hypotheses until later evidence verifies them, and failed predictions
should calibrate the record or promote it to a paired incident. Do not create a
per-task token or consumption ledger only to support this field.
Use `feedback_loop_profile` to choose cost: `index_hint` and
`record_candidate` stay compact; `prevention_review` and `explicit_cycle` may
open selected payloads.

`skill_lifecycle_profile` is also a decision field. A WorkBuddy-compatible loop
can use it to keep idle skills listing-only, open an active frame for selected
skill phases, and write a `skill_release_receipt` when the phase ends. Releasing
large rendered skill text requires host context management support; without
that support, keep the profile advisory and preserve the receipt for compaction
and reactivation.

The optional surfaces below were informed in part by the non-GitHub client artifact reference recorded in [Influences And Attribution](../influences-and-attribution.md): Doubao built-in finance and market-analysis skills inspected locally on 2026-06-25. That reference is source-prior only; this repository does not copy Doubao code, prompts, templates, proprietary schemas, or finance-domain rules.

If an adopting WorkBuddy loop adds those surfaces, keep them separate from hard runtime gates:

- `domain_aesthetic_rubric` records are advisory quality references. They can describe domain-specific output dimensions, bands, examples, and failure modes, but they must not block tool execution by themselves.
- `domain_source_tier_catalog` records are source-prior evidence metadata. They can tell the agent which source classes are strong, weak, trace-only, or disallowed for a domain, but they are not fact sources.
- Claim-artifact contracts should pass through file paths or compact JSON objects, not deeply nested shell-escaped JSON. Raw evidence refs, URLs, tool outputs, or artifacts remain the fact sources; summaries and ledgers are navigation.
- External-model delivery modes should treat the model as a structured JSON filler only when the host has deterministic render or verify scripts. Blocking issues should be path-scoped; advisory issues should not trigger unbounded repair loops.

Record support for these optional surfaces in `templates/adapter-contract/compatibility.manifest.json`. Leave each field `unverified` until the exact WorkBuddy host version, hook payload, and renderer or verifier have been tested.

## Recording And Transcript Payloads

The adapter does not decode raw audio or read private recording files by itself. Recording support means the hook runner can route text that the host already extracted from a recording payload.

If your WorkBuddy build sends recording or audio attachments, make sure the prompt-stage hook payload exposes one of these text fields:

```text
transcript
transcription
caption
content
message
text
```

The hook runner recursively extracts bounded text from those fields and ignores raw media blobs, bytes, base64 strings, and binary data. Acceptance test:

```text
Send a voice/recording prompt whose transcript asks for a known R5 action.
Expected: UserPromptSubmit additionalContext reports `human_confirmation=required`, and PreToolUse later uses the stored transcript as the original task.
```

If the host only passes a file path or binary audio blob, add a host-side transcription step first. Do not make the harness adapter responsible for opening arbitrary recording files unless your runtime has a separate privacy and permission policy for that.

## Hook Payload Encoding

Some host builds can pass stdin JSON that contains lone UTF-16 surrogate escapes such as `\udcac` or `\udc80`. These are invalid Unicode scalar values after JSON decoding and can break Python output or JSONL logging if they are written with `ensure_ascii=False`.

The hook runner sanitizes those values to `<invalid-surrogate>` before routing, state writes, log writes, and hook output. If you still see errors such as:

```text
'utf-8' codec can't encode character '\udcac'
'utf-8' codec can't encode character '\udc80'
```

check these surfaces in order:

1. The installed hook command is running the current adapter version.
2. `UserPromptSubmit` and `PreToolUse` both point to the same adapter root.
3. The hook output is ASCII-escaped or otherwise surrogate-safe.
4. The log writer sanitizes nested payload values before `json.dumps(... ensure_ascii=False)`.
5. The WorkBuddy client was restarted or reloaded after hook/settings changes.

## Stop Hook And Final Claims

Wire a `Stop` or final-answer hook when the host exposes the final response before display. The hook runner calls `runtime_enforcer(stage="final", final_text=...)`; strong phrases such as broad validation or verification claims must have a claim schema or the final hook returns a blocked result. The same final path also checks high-risk causal attribution patterns, such as broad mechanism-effect claims, time-range stability assertions, single-sample generalizations, or origin-path wording used as a mechanism definition.

If your WorkBuddy build does not let hooks inspect or block final text, keep final-claim and causal-attribution enforcement as self-downgrade rules in the root instruction file and mark that final surface as advisory in the compatibility manifest.

## Smoke Test

```bash
python -m unittest discover -s integrations/workbuddy-python-runtime/tests
```
