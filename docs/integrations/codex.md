# Codex Integration Example

This is the smallest Codex-oriented integration pattern for the whiteboard package. The verified behavior is the local script behavior and exit-code contract. Any Codex client update can change launch paths or hook behavior, so re-run the smoke checks after updates.

## Field Status

This page is a generic Codex reference mapping. Keep adopter-specific field
histories, private project names, and solved incident traces outside the public
package. Promote only reusable generic rules, tests, or adapter contracts back
into this repository.

Re-run update smoke checks after Codex client changes. A client update can
change launch paths, instruction loading, hook behavior, bundled runtimes, or
the active shell dialect used by generated commands.

## Instruction Entry

Keep `AGENTS.md` at the workspace root, or copy its microkernel into the instruction file Codex actually reads.

The instruction entry should require:

- run the intake router before nontrivial work;
- read memory meta/index layers before capsule payloads;
- stop for explicit human confirmation before R5 actions;
- downgrade final claims when a gate was skipped or could not run.

## Pre-Task Gate

```powershell
powershell -ExecutionPolicy Bypass -File <HARNESS_ROOT>\harness_runtime_enforcer.ps1 `
  -Stage pre_task `
  -TaskText "<user task>" `
  -Cwd "<workspace root>" `
  -ConstitutionPath "<workspace root>\AGENTS.md"
```

Expected behavior:

- exit `0` with `status: pass` for allowed work;
- exit `2` with `status: blocked` for configured hard stops;
- other exits indicate adapter failure or malformed input.

## Tool-Call Gate

Run the tool proxy before high-risk shell commands:

```powershell
powershell -ExecutionPolicy Bypass -File <HARNESS_ROOT>\harness_tool_proxy.ps1 `
  -Stage pre_tool `
  -TaskText "<user task>" `
  -Cwd "<workspace root>" `
  -ToolName "shell_command" `
  -ToolInputJson '{"command":"git commit -am update"}'
```

If the result exits `2`, the caller should stop and ask for explicit human confirmation. Pass `-HumanConfirmed` only after that confirmation exists for the specific action.

When confirmation must be carried across an adapter boundary, pass
`-HumanConfirmationPermitJson` or `-HumanConfirmationPermitPath` with a
`cbh.r5_human_confirmation_permit.v1` object. The permit must use
`scope: single_event`, match the exact task/tool SHA-256 hashes, and expire
quickly. Pin `-HumanConfirmationPermitUseLedgerPath` or
`CBH_R5_PERMIT_USE_LEDGER` when the host needs a stable replay ledger. Do not
use the permit as a broad approval for later commands.

## Command Wrapper

Use `harness_task_wrapper.ps1` only for command paths that you can actually route through it:

```powershell
powershell -ExecutionPolicy Bypass -File <HARNESS_ROOT>\harness_task_wrapper.ps1 `
  -TaskText "<user task>" `
  -Cwd "<workspace root>" `
  -CommandPath "powershell" `
  -CommandArgs @("-NoProfile","-Command","Get-ChildItem")
```

This wrapper is hard enforcement only if it is the sole command execution path for the protected action. If another shell path bypasses it, that path remains advisory.

## Update Smoke

After Codex updates:

1. Confirm the root instruction entry still loads.
2. Run `validate_policy.ps1`.
3. Run a mixed R3/R4 intake route.
4. Run a blocked R5 tool-proxy check.
5. Run memory isolation on an allowed path and a sibling-prefix blocked path.
