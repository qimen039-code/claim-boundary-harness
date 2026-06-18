# Local Reproduction

Run these commands from the repository root.

These checks are smoke tests for the reference package, not a full compatibility matrix. The current public package was adapted and checked from one local device environment. Re-run the relevant commands on the exact Windows, macOS/Linux, WorkBuddy, Codex, Claude Code, or other agent runtime you plan to use.

## 0. Policy Validator

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\validate_policy.ps1
```

Expected highlight:

- `status`: `pass`.

## 1. Intake Router

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_intake_router.ps1 -TaskText "fix the script and run benchmark" -Cwd "C:\path\to\project"
```

Expected highlights:

- `project_lane`: `EXAMPLE_PROJECT`;
- `risk_level`: `R4`;
- `triggered_risks`: `R4`, `R3`;
- required gates include `change_contract_gate`, `external_research_gate`, `verification_gate`, and `claim_gate`.

## 2. Fallback Boundary

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_intake_router.ps1 -TaskText "handle this project issue" -Cwd "C:\path\to\other"
```

Expected highlights:

- `classification_confidence`: `low`;
- `fallback_model_judgment_recommended`: `true`.

## 3. Memory Isolation

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_memory_isolation_gate.ps1 -ProjectLane EXAMPLE_PROJECT -RequestedPath "C:\path\to\project\.agent-memory\note.md"
```

Expected highlight:

- `status`: `pass`.

## 3a. Memory Prefix Block

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_memory_isolation_gate.ps1 -ProjectLane EXAMPLE_PROJECT -RequestedPath "C:\path\to\project-evil\.agent-memory\note.md"
```

Expected highlights:

- process exits with code `2`;
- `status`: `blocked`.

## 3b. Trigger Boundary And Negation

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_intake_router.ps1 -TaskText "read installation guide" -Cwd "C:\path\to\other"
```

Expected highlight:

- `matched_risk_triggers` does not include `install`.

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_intake_router.ps1 -TaskText "do not delete anything" -Cwd "C:\path\to\other"
```

Expected highlights:

- `risk_level` is not `R5`;
- `negated_risk_triggers` includes `delete`.

## 4. External Research Trigger

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_external_research_gate.ps1 -TaskText "check latest package version 1.2.3 on GitHub"
```

Expected highlight:

- `needs_external_research`: `true`.
- `recommended_search_modes` includes `github_open_source_repository_search` and `official_authority_source_search`.

## 4-1. External Research Negation

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_external_research_gate.ps1 -TaskText "do not search GitHub"
```

Expected highlights:

- `needs_external_research`: `false`;
- `negated_triggers` includes `GitHub`;
- `recommended_search_modes`: empty.

## 4a. Source-Grounded Learning Route

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_external_research_gate.ps1 -TaskText "learn from an open source mechanism and avoid closed-door invention"
```

Expected highlights:

- `needs_external_research`: `true`;
- `recommended_search_modes` includes `github_open_source_repository_search` and `source_grounded_learning_intake`;
- `learning_classification_labels` includes `source_prior`, `hypothesis`, `inspiration`, `unverified_implementation_path`, and `not_applicable`.

## 4b. Governance Rule Update Route

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_intake_router.ps1 -TaskText "refine the dynamic evaluation decision layer and update routing triggers" -Cwd "C:\path\to\project"
```

Expected highlights:

- `risk_level`: `R3`;
- `matched_risk_triggers` includes `dynamic evaluation`, `decision layer`, or `trigger rule`;
- required gates include `project_context_gate`, `change_contract_gate`, and `claim_gate`.

## 4c. Runtime Enforcer Pass

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_runtime_enforcer.ps1 -Stage pre_task -TaskText "inspect project files" -Cwd (Get-Location).Path
```

Expected highlights:

- `phase`: `runtime_enforcer`;
- `status`: `pass`;
- `constitution_path` points to `AGENTS.md`.

## 4c-1. Local Architecture Maintenance Should Not Force External Research

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_intake_router.ps1 -TaskText "update the local architecture chain and optimize routing logic" -Cwd (Get-Location).Path
```

Expected highlights:

- `risk_level`: `R3`;
- `needs_external_research`: `false`.

## 4d. Tool Proxy Block

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_tool_proxy.ps1 -Stage pre_tool -TaskText "commit changes" -ToolName "shell_command" -ToolInputJson '{"command":"git commit -am update"}' -Cwd (Get-Location).Path
```

Expected highlights:

- process exits nonzero;
- `status`: `blocked`;
- `blocked_reasons` includes `human_confirmation_required_for_R5` or `tool_call_requires_human_confirmation`.

## 5. Claim Schema

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_claim_schema_verifier.ps1 -ClaimJson '{"claim_type":"architecture_decision","source_type":"local_file","evidence_boundary":"whiteboard smoke"}'
```

Expected highlight:

- `status`: `pass`.

## 6. Bash Smoke Checks

Run these only when Bash and `jq` are available.

```bash
bash ./skills/embedded-harness/bash/validate_policy.sh
bash ./skills/embedded-harness/bash/harness_intake_router.sh --task-text "do not delete anything" --cwd "/path/to/other"
bash ./skills/embedded-harness/bash/harness_external_research_gate.sh --task-text "do not search GitHub"
```

Expected highlights:

- policy validator returns `status: pass`;
- intake router records the negated `delete` trigger without direct `R5`;
- external research gate returns `needs_external_research: false`.

## 7. WorkBuddy Python Runtime Adapter

Run this if Python is available:

```bash
python -m unittest discover -s integrations/workbuddy-python-runtime/tests
```

Expected highlight:

- all tests pass.

This validates the standalone Python decision layer only. It does not prove that WorkBuddy has wired the adapter into its internal action execution loop, and it does not prove compatibility across WorkBuddy versions.

## Notes

These tests prove only that the whiteboard scripts and reference adapter functions run and return expected routing decisions. They do not prove that an adopting agent will honor the gates. Hook, wrapper, tool-proxy, or in-process loop integration is required for stronger enforcement.
