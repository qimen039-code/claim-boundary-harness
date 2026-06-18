# Claude Code Integration Example

This example maps the same whiteboard chain into a Claude Code-style workspace. The verified behavior is the local script behavior and exit-code contract. Validate the exact instruction filename and hook surface in your installed client before treating the gates as hard runtime.

## Instruction Entry

Claude Code commonly uses a workspace instruction file such as `CLAUDE.md`. Map the root `AGENTS.md` content into that file, or keep a short `CLAUDE.md` that points the agent to the harness entry files.

Minimal instruction text:

```text
Before nontrivial work, run the embedded harness intake router.
Use project-scoped memory lanes only.
For memory retrieval, read the meta summary or _META_INDEX first, then one category index, then one matching capsule.
For R5 actions, stop and ask for explicit human confirmation.
For current public facts, repository review, or external mechanism learning, use the external research gate and source-grounded route.
```

## Pre-Task Check

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File <HARNESS_ROOT>\harness_runtime_enforcer.ps1 `
  -Stage pre_task `
  -TaskText "<user task>" `
  -Cwd "<workspace root>" `
  -ConstitutionPath "<workspace root>\CLAUDE.md"
```

Bash with `jq`:

```bash
bash <HARNESS_ROOT>/bash/harness_intake_router.sh \
  --task-text "<user task>" \
  --cwd "<workspace root>"
```

## R5 Confirmation

Do not pass a human-confirmed flag for broad classes of future work. Confirmation should bind to the concrete action in the current turn, such as a specific delete, commit, install, login, permission change, network/proxy/firewall edit, private-value transfer, or long-term memory write.

## Hook Boundary

If Claude Code can call a pre-tool or command hook in your environment, place `harness_runtime_enforcer.ps1` or `harness_tool_proxy.ps1` before the protected action. If it cannot, keep the harness as a mandatory advisory control plane and state the limitation before strong claims.

The wrapper is hard only if all protected command execution goes through it. If normal tool calls can bypass the wrapper, the gate cannot enforce that path.

## Update Smoke

After Claude Code updates:

1. Confirm `CLAUDE.md` or the configured instruction file still loads.
2. Run the policy validator.
3. Run the intake router on a mixed edit plus runtime task.
4. Run an R5 command check and confirm exit `2`.
5. Re-check the memory meta-first instruction with a small synthetic memory library.
