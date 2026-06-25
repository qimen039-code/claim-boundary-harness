# Common Issues And Solutions

This page records reusable issue classes found while adapting, publishing, and
testing Claim Boundary Harness. It is a public field playbook, not a private
incident log and not proof that a client is broadly certified.

Use this page for transferable problem shapes. Use the common error corpus
template for local or private `CE-*` records, and upgrade to paired `ERR-*` /
`SOL-*` records only when an issue is repeated, high-impact, or explicitly
requested as a full incident.

## Current Classified Issues

| ID | Class | Symptom | Likely cause | Solution | Validation |
| --- | --- | --- | --- | --- | --- |
| `CE-PUBLIC-2026-06-25-01` | `git_repo_action_error` | GitHub notifications show failed smoke checks even after later commits look healthy. | Notifications are per workflow run. Older failed runs stay unread after a later commit fixes the issue. | Compare run number, head SHA, branch, and current head before patching. Inspect failed job logs only when the current head or latest relevant run fails. | `gh run list` showed old failures followed by later successful runs; the current-head smoke run passed. |
| `CE-PUBLIC-2026-06-25-02` | `powershell_encoding_path_error` | Windows PowerShell smoke checks fail with parser-looking errors such as a missing string terminator in a `.ps1` file. | Windows PowerShell 5.1 can misread UTF-8 scripts without the expected encoding marker, especially when non-ASCII content is present. | Save Windows PowerShell-targeted scripts in a 5.1-safe UTF-8 form or run under a UTF-8-capable `pwsh` path, then keep a Windows smoke check. | A later Windows smoke run passed after the script encoding/path was corrected. |
| `CE-PUBLIC-2026-06-25-03` | `function_tool_call_error` | Bash smoke checks fail under `set -euo pipefail` with circular nameref warnings. | A helper used a nameref or local variable name that referenced itself after refactoring. | Rename the local reference variables and keep trigger collection free of self-referential namerefs. | Ubuntu Bash smoke checks passed after the helper was adjusted. |
| `CE-PUBLIC-2026-06-25-04` | `client_adapter_boundary_error` | A client adaptation appears to enforce destructive-action confirmation, but the enforcement belongs to the host client rather than this framework. | Some clients provide their own hard-confirmation UI or safety layer; the harness can align with it but does not own that surface. | Document the guard as host-owned, map which harness checks are soft, semi-hard, or hard in that client, and list bypass surfaces. | Doubao notes now state the destructive delete confirmation path is platform-owned and locally observed, not a universal framework-owned hard gate. |
| `CE-PUBLIC-2026-06-25-05` | `attribution_boundary_error` | External client artifacts or public projects inspire useful patterns, but publishing risks implying copied code, copied proprietary schema, or uncredited influence. | Source intake was mixed with implementation planning before a source ledger and attribution boundary were written. | Record the source, date, usable pattern, non-usable boundary, and no-code/no-template/no-proprietary-schema rule before publishing. | `CREDITS.toml`, the attribution doc, and tests include the client artifact reference boundary. |
| `CE-PUBLIC-2026-06-25-06` | `semantic_routing_error` | Conversation-ledger summaries or compact memory summaries are treated as factual source material. | A derived navigation summary was mistaken for an evidence source. | Treat ledger summaries as navigation only. Recover exact wording, decisions, diffs, tests, R5 confirmations, and external claims through evidence references back to raw sessions or artifacts. | The README and ledger contract describe the ledger as derived and preserve evidence-reference lookup. |
| `CE-PUBLIC-2026-06-25-07` | `git_repo_action_error` | A one-time user confirmation for a high-risk action is reused or described ambiguously. | The confirmation was treated as a general permission rather than an exact event permit. | Use the established term `single-event R5 permit`: one exact task/tool event, hash-bound, recorded after use, and not replayable. | Runtime and WorkBuddy adapter tests cover replayed permit denial. |
| `CE-PUBLIC-2026-06-25-08` | `powershell_encoding_path_error` | Local commands print shell-profile or version-manager startup errors while the requested command still exits successfully. | A user shell profile or tool manager failed during process startup; the repository command itself did not fail. | Separate shell startup noise from command exit status. Use `-NoProfile` for automation when appropriate, and repair the profile outside the repository only with explicit local-environment approval. | The affected GitHub, git, and test commands completed with exit code `0`; no repository patch was required. |
| `CE-PUBLIC-2026-06-25-09` | `field_schema_error` | A quality score or linter prefers a less careful response over a claim-boundary response. | The checker measures surface format or style, not truth, provenance, or validation strength. | Treat advisory scores as schema or style smoke only. Never use them as the fact source for a final claim. | Final claim promotion still requires claim schema, source boundary, and local validation evidence. |

## Retrieval Terms

Use these terms to find the right issue class without reading every record:

```text
github smoke old notification current head
windows powershell utf-8 bom parser terminator
bash nameref circular reference set -euo pipefail
host-owned hard guard client adapter bypass surface
external artifact attribution source ledger no-code boundary
conversation ledger summary evidence refs raw session
single-event R5 permit replay denial
shell profile startup noise no-profile
advisory score linter not fact source
```

## Upgrade Boundary

Keep these entries as public `CE-*` style records while the issue is small,
fixed, and reusable. Upgrade to paired `ERR-*` / `SOL-*` records when:

- the same prevention rule fails again;
- a current release or current head is broken;
- a public/private boundary is crossed;
- a hard gate allows a dangerous action without the expected confirmation; or
- the user explicitly asks for a full incident record.
