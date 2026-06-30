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
| `CE-PUBLIC-2026-06-26-01` | `semantic_routing_error` | Release-preparation wording such as "prepare release", "发布前", "发布准备", or "发布整理" routes too low as read-only review while nearby submit/commit wording is only a non-promoted R5 candidate. | The router treated ambiguous release wording as semantic ambiguity or read-only inspection instead of governance/docs readiness work, and relied on later human/model reassessment to recover the R3 boundary. | Add release-preparation and release-audit phrases to R3 routing triggers; keep submit/commit/push as R5 candidates unless an actual git/release action is requested; add a regression case for release prep with submit/push explicitly not executed. | `TC-005d` covers release-preparation audit as R3 with non-promoted submit/push R5 candidate. |
| `CE-PUBLIC-2026-06-27-01` | `git_repo_action_error` | A question about "previously published PRs" is answered by checking only the current repository, missing PRs opened from the same account in external repositories. | The lookup scope was silently narrowed to the active repository instead of resolving whether the user meant current-repo PRs, author-owned PRs, or cross-repository publication PRs. | For ambiguous PR/publication questions, check current repository PRs first, then author-scoped open and closed PRs across GitHub when the wording refers to prior publication. State the searched scope explicitly. | `gh pr list` on the current repository returned no PRs, while author-scoped `gh search prs` found two open external publication PRs. |
| `CE-PUBLIC-2026-06-27-02` | `function_tool_call_error` | GitHub CLI or REST checks fail before returning useful data because flags or methods are assumed incorrectly, such as using `gh api` form fields with the wrong request method or `gh search prs --state all`. | CLI subcommands have different accepted state values and `gh api -f` can alter request behavior unless the HTTP method is explicit. | Prefer command-specific help or known-good patterns for non-routine GitHub queries. Use `gh api -X GET` for read-only REST calls with form parameters, and split PR search into `--state open` and `--state closed` when `all` is unsupported. | The corrected `gh api -X GET .../pulls -f state=all` returned successfully, and split `gh search prs --state open/closed` found the expected PR state. |
| `CE-PUBLIC-2026-06-29-01` | `causal_attribution_error` | A local formation path, single case, or field observation is written as a mechanism definition, universal effect, or validated causal result. | The draft mixed empirical records with mechanism properties and causal proof, often by using broad wording such as solved, caused, always, or all agents without scope limits. | Use `observation_scope_gate` for global or historical questions and `causal_attribution_gate` for final text. Classify the statement as `mechanism_property`, `empirical_record`, `causal_hypothesis`, or `validated_causality`; keep privacy/release decisions in the separate public/private boundary gate. | Router and final-claim tests cover observation-scope routing plus final causal overclaim blocking while allowing scoped empirical or hypothesis wording. |
| `CE-PUBLIC-2026-06-29-02` | `semantic_routing_error` | A memory-bank or long-term-memory status check under a known project cwd routes as `PROJECTLESS` or promotes to R5 even though the request is read-only. | Machine-local project roots were not present in the active policy, and long-term-memory terms were treated too much like direct actions instead of context-required candidates. | Load private project roots through `embedded_harness_policy.local.json` or `CBH_PROJECT_LANES_FILE`; keep public policy clean; demote long-term-memory wording in read/status contexts while preserving R5 for real memory writes. | `TC-004d` covers read/status memory wording as non-R5, and `TC-031a` covers local project-lane overlay preservation. |
| `CE-PUBLIC-2026-06-30-01` | `semantic_routing_error` | A read-only self-check of public docs remains R1 after the task selects a README/docs edit, or an explicit "commit and push" instruction is treated as documentation context. | The router protected against false positives from docs/rule/check wording, but did not give enough priority to selected edit paths or explicit git-action phrases. | Keep pure self-checks as R1, but reclassify self-check-plus-edit tasks as R3. Promote explicit commit-and-push phrases to R5 unless they are explicitly negated as not executed. | `TC-008a` keeps read-only self-check as R1, `TC-008b` promotes self-check-plus-update to R3, and `TC-004e`/`TC-004f` promote explicit commit-and-push phrasing to actionable R5. |

## Feedback Loop Trial Entries

The first public CE feedback-loop trial applies to the 2026-06-27 records above:

- `CE-PUBLIC-2026-06-27-01`: prediction is that future publication-PR checks should state lookup scope and include author-scoped open/closed PR lookup when current-repo lookup is insufficient. Verification starts as `pending`.
- `CE-PUBLIC-2026-06-27-02`: prediction is that future non-routine GitHub CLI/API queries should use read-only method checks and split unsupported `all` states into accepted state queries. Verification starts as `pending`.

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
release prep publish preparation 发布前 发布准备 发布整理 route R3 submit push not executed
github pr scope current repository author scoped cross repository publication prs
gh api get method state all gh search prs open closed cli flag mismatch
causal attribution observation scope empirical record causal hypothesis validated causality all agents hallucination drift
self-check README docs R1 R3 dynamic reevaluation commit and push 提交推送 explicit git action
```

## Upgrade Boundary

Keep these entries as public `CE-*` style records while the issue is small,
fixed, and reusable. Upgrade to paired `ERR-*` / `SOL-*` records when:

- the same prevention rule fails again;
- a current release or current head is broken;
- a public/private boundary is crossed;
- a hard gate allows a dangerous action without the expected confirmation; or
- the user explicitly asks for a full incident record.
