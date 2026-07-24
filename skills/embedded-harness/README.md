# Embedded Agent Harness

A low-cost, model-facing control and context layer for agent workflows. It
routes each task through only the capabilities it needs, then returns compact
context and boundary receipts to the host model agent. The model still plans,
uses tools, handles errors, and writes the final answer.

Default chain:

```text
root AGENTS.md microkernel
-> deterministic intake router
-> mandatory advisory control plane
-> lightweight routing receipt
-> event-triggered re-evaluation
-> optional project router / project AGENTS / project memory
-> static knowledge index / selected manual page, if project navigation is needed
-> memory meta summary / category index / matching capsule, if memory is needed
-> bounded action consumer context returned to the model agent
-> optional nonblocking current-candidate correction
-> final claim and memory boundary check
```

Design boundaries:

- Risk rules are additive: keep the highest risk label, but return the union of all gates matched by the task.
- R5 trigger terms are candidates first. The router promotes them to R5 only when context shows an actionable delete, git, install, login, permission, network/proxy, sensitive-transfer, or memory-write operation.
- `R4` includes `R3` change and claim gates, plus external research and verification gates.
- If no deterministic risk rule matches, fallback review is reserved for medium-length text with fallback terms or long unclassified text. Short ordinary questions stay cheap R0 unless another rule fires.
- `GLOBAL` memory is manual-only by default.
- The mandatory advisory control plane is required for nontrivial tasks: create a lightweight routing receipt, re-evaluate only on trigger events, and re-check claim/memory/version boundaries before final output.
- R0-R5 classification always runs internally but stays silent by default in user-facing surfaces. Expose only action-changing boundaries; `debug_receipt` is for route diagnosis or explicit full-receipt requests.
- Receipt profiles keep runtime cost low: `compact_runtime` is used only when fields change the next action, `extended_governance` expands for public/framework/project-boundary work, and `debug_receipt` is only for route diagnosis or explicit full-receipt requests.
- Do not wrap every tool call. Invoke correction only for a current candidate whose surface and profile can be mechanically identified.
- Memory retrieval is meta-first: read `_META_INDEX.md`, a memory summary, or a router manifest before opening category indexes or capsule payloads.
- `memory_source_hints` bind retrieval to exact active roots. `harness_action_consumer.py` promotes exact record or anchor matches into compact model context; bounded weaker candidates are returned to the host model for semantic reranking and do not demote an exact match into mandatory manual review.
- `action_bindings` describe work for the host model agent. They do not make CBH an autonomous task runner and are not completion evidence until the matching model/tool path returns a receipt.
- Static knowledge retrieval is index-first: read `_STATIC_KNOWLEDGE_INDEX.md` before opening a project manual page, and treat static notes as `source_tag: static_knowledge` / `belief_status: source_prior` until checked.
- `behavior_correction_gate.py` returns a task-local receipt; `behavior_correction_hook.py` may return one verified `allow + updatedInput` rewrite for an accepted deterministic profile.
- Ambiguity, verifier failure, unsupported host protocol, registry failure, or no match leaves the event unchanged. Correction never grants permission, denies, freezes, stores approval state, writes memory, or mutates policy.
- Most gates remain advisory structured decisions that the host model interprets under its governing instructions and native security boundary.
- Machine-local project roots should be loaded from `embedded_harness_policy.local.json` or `CBH_PROJECT_LANES_FILE`, not committed into the public runtime policy.

Mandatory advisory control plane:

```text
routing receipt
-> execute the cheapest sufficient route
-> re-evaluate only after trigger events
-> final claim/memory/version boundary check
-> optional nonblocking correction when a verified recurrence profile matches
```

Receipt fields: task type, target surface, audience, project lane, risk level, semantic ambiguity, module need, memory need, memory mode, memory lane, memory source hints, action bindings, record intent, external need, claim risk, projectization decision, conversation memory decision, link intent, receipt profile, and required gates. Runtime adapters can expose `compact_runtime` by default and expand only for governance or debug cases.

If this control plane cannot be completed, the final response must say so and must not present the result as fully verified.

Mandatory search and learning decision matrix:

```text
official / authority source search
-> GitHub / open-source repository search when repo evidence is involved
-> general web cross-check when independent public context is needed
-> source-grounded learning intake for external mechanisms
-> local validation before strong adoption or success claims
```

Use this matrix when a task mentions current facts, latest versions, public products, policies, prices, laws, GitHub, open-source repositories, unfamiliar mechanisms, external architecture comparisons, or avoiding closed-door invention.
Do not treat local architecture maintenance as external research unless it includes external comparison or open-source learning.
Classify outside material as `fact`, `source_prior`, `hypothesis`, `inspiration`, `unverified_implementation_path`, or `not_applicable`.
Do not upgrade external reading into local validation unless local evidence, tests, reproduction, or a concrete project-specific proof path exists.

Mandatory memory retrieval chain:

```text
meta summary / _META_INDEX / router manifest
-> category index / point index / outer_retrieval_surface
-> matching capsule / ERR-* / SOL-* payload
```

Recommended meta index fields: lane, scope, category, record type, status, retrieval terms, applies-when, does-not-apply-when, linked modules, linked records, and last-reviewed marker. Default lookup should open at most one meta index, one category index, and two payload records unless the task explicitly asks for a full audit or migration.

Memory recording is routed separately from memory reading. Use `common_error_corpus` for lightweight recurring error-and-solution samples with symptom, cause, applied solution, prevention, validation, and evidence. Use paired `ERR-*` / `SOL-*` records for explicit, repeated, or high-impact self-reflection incidents.

Reusable memory capsules should carry source-monitoring fields: `source_tag` `belief_status` `confidence` `derived_from` `source_monitoring` `lifecycle` `belief_trace_summary`. The router decides whether memory is needed; the capsule schema preserves the source and status boundary after the route chooses to write or update memory.

Memory retrieval results used as reusable context should return these fields with the selected snippet: `source_tag` `derived_from` `belief_status` `confidence` `score_method`. If no numeric score was computed, use `score_method: none` and omit `score`.

Scripts:

```powershell
.\harness_intake_router.ps1 -TaskText "fix the build and run benchmark" -Cwd "<PROJECT_ROOT>"
python .\harness_action_consumer.py --route-json '<ROUTE_JSON>' --prompt '<USER_TASK>'
python .\behavior_correction_gate.py --list-profiles
python .\behavior_correction_hook.py < pretool-event.json
.\validate_policy.ps1
.\harness_memory_isolation_gate.ps1 -ProjectLane EXAMPLE_PROJECT -RequestedPath "<PROJECT_ROOT>/.agent-memory/item.md"
.\harness_external_research_gate.ps1 -TaskText "check latest version"
.\harness_claim_schema_verifier.ps1 -ClaimJson '{"claim_type":"architecture_decision","source_type":"local_file","source_ref":"README.md","evidence_boundary":"whiteboard_smoke"}'
```

Policy authoring:

```powershell
python .\compile_policy_from_toml.py --check
python .\compile_policy_from_toml.py --output .\embedded_harness_policy.json
```

`embedded_harness_policy.authoring.toml` is for human-maintained high-churn
sections. `embedded_harness_policy.json` remains the runtime source consumed by
PowerShell, Bash, and Python adapters.

R5 confirmation is intentionally outside the correction hook. The model agent
must follow its governing instructions, and the host's native security boundary
remains authoritative for actual execution.

Bash counterparts:

```bash
bash ./bash/validate_policy.sh
bash ./bash/harness_intake_router.sh --task-text "fix the build and run benchmark" --cwd "<PROJECT_ROOT>"
bash ./bash/harness_memory_isolation_gate.sh --project-lane EXAMPLE_PROJECT --requested-path "<PROJECT_ROOT>/.agent-memory/item.md"
bash ./bash/harness_external_research_gate.sh --task-text "check latest version"
bash ./bash/harness_claim_schema_verifier.sh --claim-json '{"claim_type":"architecture_decision","source_type":"local_file","source_ref":"README.md","evidence_boundary":"whiteboard_smoke"}'
```

Bash scripts require `jq`. They are reference adapters, not a package-manager distribution.

The experimental WorkBuddy-oriented Python adapter lives outside this skill folder at `../../integrations/workbuddy-python-runtime`. It reuses `embedded_harness_policy.json` but is not part of the core PowerShell/Bash script surface.

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | Gate completed, returned a nonblocking receipt, or performed a silent no-op. |
| Other | Standalone diagnostic/runtime error; never an authorization decision. |

Gate statuses:

| Status | Meaning |
| --- | --- |
| `pass` | The advisory check completed without an issue. |
| `correction_candidate` | A task-local profile matched and declares its required verifier. |
| `cross_reference_allowed` | Memory path is outside the active lane, but explicit cross-reference allowance was provided. |

Behavior correction has no hard-stop state. It either emits one mechanically
verified current-input rewrite or leaves the event unchanged.

Configure `embedded_harness_policy.authoring.toml` for high-churn trigger and threshold sections, then keep `embedded_harness_policy.json` synchronized for runtime use. Machine-local project lanes and memory roots should live in a private `embedded_harness_policy.local.json` overlay or the path named by `CBH_PROJECT_LANES_FILE`; use `embedded_harness_policy.local.example.json` as the shape. Promote trigger terms only for recurring routing classes that change gates or boundaries; keep one-off task wording out of long-lived policy.

## Limitations

- This harness is not a hard sandbox.
- Most gate results are caller-honored by default.
- The correction hook is nonblocking and cannot substitute for host authorization or sandboxing.
- Published adapters are local smoke-test references, not complete cross-device or cross-client compatibility guarantees.
