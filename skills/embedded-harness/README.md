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

Mandatory advisory control plane:

```text
routing receipt
-> execute the cheapest sufficient route
-> re-evaluate only after trigger events
-> final claim/memory/version boundary check
-> selective runtime hard gate when a critical risk appears
```

Receipt fields: task type, project lane, risk level, required gates, external search need, memory need, claim gate need, and human confirmation need.

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

Scripts:

```powershell
.\harness_intake_router.ps1 -TaskText "fix the build and run benchmark" -Cwd "<PROJECT_ROOT>"
.\harness_runtime_enforcer.ps1 -Stage pre_task -TaskText "fix the build and run benchmark" -Cwd "<PROJECT_ROOT>"
.\harness_tool_proxy.ps1 -Stage pre_tool -TaskText "commit changes" -ToolName "shell_command" -ToolInputJson '{"command":"git commit"}'
.\harness_task_wrapper.ps1 -TaskText "list files" -CommandPath "powershell" -CommandArgs @("-NoProfile","-Command","Get-ChildItem")
.\harness_memory_isolation_gate.ps1 -ProjectLane EXAMPLE_PROJECT -RequestedPath "<PROJECT_ROOT>/.agent-memory/item.md"
.\harness_external_research_gate.ps1 -TaskText "check latest version"
.\harness_claim_schema_verifier.ps1 -ClaimJson '{"claim_type":"architecture_decision","source_type":"local_file","evidence_boundary":"example"}'
```

Runtime hard-stop conditions:

- R5 route without explicit human confirmation.
- Low-confidence route without boundary review.
- Nontrivial task with no available constitution entry.
- High-risk tool call without explicit human confirmation.
- Long-term memory write without explicit user request.
- Final strong claim without claim schema evidence boundary.

Configure `embedded_harness_policy.json` for project lanes, memory roots, trigger terms, and claim phrases.
