# Embedded Agent Harness

A low-cost control layer for agent workflows. It routes each task through only the gates it needs: intake classification, project/memory isolation, external research triggers, and claim-schema checks.

Default chain:

```text
root AGENTS.md microkernel
-> deterministic intake router
-> mandatory advisory control plane
-> lightweight routing receipt
-> event-triggered re-evaluation
-> optional project router / project AGENTS / project memory
-> memory meta summary / category index / matching capsule, if memory is needed
-> selective hard runtime gates only for critical risks
-> final claim and memory boundary check
```

Design boundaries:

- Risk rules are additive: keep the highest risk label, but return the union of all gates matched by the task.
- `R4` includes `R3` change and claim gates, plus external research and verification gates.
- If no deterministic risk rule matches but the text looks like a nontrivial task, the router sets `fallback_model_judgment_recommended=true` rather than silently treating it as high-confidence `R0`.
- `GLOBAL` memory is manual-only by default.
- The mandatory advisory control plane is required for nontrivial tasks: create a lightweight routing receipt, re-evaluate only on trigger events, and re-check claim/memory/version boundaries before final output.
- Do not wrap every tool call by default; use runtime hard gates only for R5, high-risk tool calls, strong final claims, long-term memory writes, and low-confidence boundaries.
- Memory retrieval is meta-first: read `_META_INDEX.md`, a memory summary, or a router manifest before opening category indexes or capsule payloads.
- Runtime enforcement is available through hook/wrapper/tool proxy scripts. A `blocked` JSON result exits nonzero and should stop the caller when these scripts are placed before task or tool execution.
- These scripts cannot stop a caller that bypasses the runtime entry scripts.
- A wrapper is truly mandatory only if it is the agent's only command execution path for the protected action. If another command path bypasses the wrapper, this layer is advisory for that path.
- Most gates are advisory by design: they return structured decisions that the caller must actively honor. Only paths configured to run through `harness_task_wrapper.ps1`, `harness_tool_proxy.ps1`, or an equivalent hook before execution become real interception points.

Mandatory advisory control plane:

```text
routing receipt
-> execute the cheapest sufficient route
-> re-evaluate only after trigger events
-> final claim/memory/version boundary check
-> selective runtime hard gate when a critical risk appears
```

Receipt fields: task type, target surface, audience, project lane, risk level, semantic ambiguity, module need, memory need, memory mode, memory lane, record intent, external need, claim risk, projectization decision, and required gates.

If this control plane cannot be completed, the final response must say so and must not present the result as fully verified.

Mandatory search and learning decision matrix:

```text
official / authority source search
-> GitHub / open-source repository search when repo evidence is involved
-> general web cross-check when independent public context is needed
-> source-grounded learning intake for external mechanisms
-> local validation before strong adoption or success claims
```

Use this matrix when a task mentions current facts, latest versions, public products, policies, prices, laws, GitHub, open-source repositories, unfamiliar mechanisms, external architecture comparisons, or avoiding closed-door invention. Do not treat local architecture maintenance as external research unless it includes external comparison or open-source learning. Classify outside material as `fact`, `source_prior`, `hypothesis`, `inspiration`, `unverified_implementation_path`, or `not_applicable`. Do not upgrade external reading into local validation unless local evidence, tests, reproduction, or a concrete project-specific proof path exists.

Mandatory memory retrieval chain:

```text
meta summary / _META_INDEX / router manifest
-> category index / point index / outer_retrieval_surface
-> matching capsule / ERR-* / SOL-* payload
```

Recommended meta index fields: lane, scope, category, record type, status, retrieval terms, applies-when, does-not-apply-when, linked modules, linked records, and last-reviewed marker. Default lookup should open at most one meta index, one category index, and two payload records unless the task explicitly asks for a full audit or migration.

Memory recording is routed separately from memory reading. Use `common_error_corpus` for lightweight recurring execution samples and paired `ERR-*` / `SOL-*` records for explicit, repeated, or high-impact self-reflection incidents.

Scripts:

```powershell
.\harness_intake_router.ps1 -TaskText "fix the build and run benchmark" -Cwd "<PROJECT_ROOT>"
.\validate_policy.ps1
.\harness_runtime_enforcer.ps1 -Stage pre_task -TaskText "fix the build and run benchmark" -Cwd "<PROJECT_ROOT>"
.\harness_tool_proxy.ps1 -Stage pre_tool -TaskText "commit changes" -ToolName "shell_command" -ToolInputJson '{"command":"git commit"}'
.\harness_task_wrapper.ps1 -TaskText "list files" -CommandPath "powershell" -CommandArgs @("-NoProfile","-Command","Get-ChildItem")
.\harness_memory_isolation_gate.ps1 -ProjectLane EXAMPLE_PROJECT -RequestedPath "<PROJECT_ROOT>/.agent-memory/item.md"
.\harness_external_research_gate.ps1 -TaskText "check latest version"
.\harness_claim_schema_verifier.ps1 -ClaimJson '{"claim_type":"architecture_decision","source_type":"local_file","evidence_boundary":"example"}'
```

Bash counterparts:

```bash
bash ./bash/validate_policy.sh
bash ./bash/harness_intake_router.sh --task-text "fix the build and run benchmark" --cwd "<PROJECT_ROOT>"
bash ./bash/harness_memory_isolation_gate.sh --project-lane EXAMPLE_PROJECT --requested-path "<PROJECT_ROOT>/.agent-memory/item.md"
bash ./bash/harness_external_research_gate.sh --task-text "check latest version"
bash ./bash/harness_claim_schema_verifier.sh --claim-json '{"claim_type":"architecture_decision","source_type":"local_file","evidence_boundary":"example"}'
```

Bash scripts require `jq`. They are reference adapters, not a package-manager distribution.

The experimental WorkBuddy-oriented Python adapter lives outside this skill folder at `../../integrations/workbuddy-python-runtime`. It reuses `embedded_harness_policy.json` but is not part of the core PowerShell/Bash script surface.

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Gate passed, or a non-blocking status was returned. |
| `2` | Gate returned `blocked`; caller should stop unless a human explicitly overrides the action. |
| Other | Runtime error, missing dependency, malformed input, or adapter failure. |

Gate statuses:

| Status | Meaning |
| --- | --- |
| `pass` | The gate did not find a blocking issue. |
| `blocked` | The gate found a boundary violation or missing confirmation. |
| `cross_reference_allowed` | Memory path is outside the active lane, but explicit cross-reference allowance was provided. |

Runtime hard-stop conditions:

- R5 route without explicit human confirmation.
- Low-confidence route without boundary review.
- Nontrivial task with no available constitution entry.
- High-risk tool call without explicit human confirmation.
- Long-term memory write without explicit user request.
- Final strong claim without claim schema evidence boundary.

Configure `embedded_harness_policy.json` for project lanes, memory roots, trigger terms, and claim phrases.

## Limitations

- This harness is not a hard sandbox.
- Most gate results are caller-honored by default.
- Blocking behavior is real only when the adopting agent has no protected execution path that bypasses the wrapper, tool proxy, or hook.
- Published adapters are local smoke-test references, not complete cross-device or cross-client compatibility guarantees.
