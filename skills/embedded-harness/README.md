# Embedded Agent Harness

A low-cost control layer for agent workflows. It routes each task through only the gates it needs: intake classification, project/memory isolation, external research triggers, and claim-schema checks.

Default chain:

```text
root AGENTS.md microkernel
-> deterministic intake router
-> optional project router / project AGENTS / project memory
-> memory meta summary / category index / matching capsule, if memory is needed
-> optional executable project harness gates
-> final claim and memory boundary check
```

Design boundaries:

- Risk rules are additive: keep the highest risk label, but return the union of all gates matched by the task.
- `R4` includes `R3` change and claim gates, plus external research and verification gates.
- If no deterministic risk rule matches but the text looks like a nontrivial task, the router sets `fallback_model_judgment_recommended=true` rather than silently treating it as high-confidence `R0`.
- `GLOBAL` memory is manual-only by default.
- Memory retrieval is meta-first: read `_META_INDEX.md`, a memory summary, or a router manifest before opening category indexes or capsule payloads.
- These scripts are advisory runtime checks, not sandbox-level hard enforcement.

Mandatory memory retrieval chain:

```text
meta summary / _META_INDEX / router manifest
-> category index / point index / outer_retrieval_surface
-> matching capsule / ERR-* / SOL-* payload
```

Scripts:

```powershell
.\harness_intake_router.ps1 -TaskText "fix the build and run benchmark" -Cwd "<PROJECT_ROOT>"
.\harness_memory_isolation_gate.ps1 -ProjectLane EXAMPLE_PROJECT -RequestedPath "<PROJECT_ROOT>/.agent-memory/item.md"
.\harness_external_research_gate.ps1 -TaskText "check latest version"
.\harness_claim_schema_verifier.ps1 -ClaimJson '{"claim_type":"architecture_decision","source_type":"local_file","evidence_boundary":"example"}'
```

Configure `embedded_harness_policy.json` for project lanes, memory roots, trigger terms, and claim phrases.
