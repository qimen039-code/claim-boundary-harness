# Architecture

Agent Memory Lane Harness has four layers.

## 1. Root Microkernel

`AGENTS.md` is the smallest always-on rule set. It asks the agent to classify work before loading large context:

- task type;
- active project lane;
- evidence needs;
- memory boundary;
- risk boundary.

The microkernel should stay short. Put project details elsewhere.

## 2. Embedded Harness

`skills/embedded-harness` contains local scripts:

- `harness_intake_router.ps1`;
- `harness_memory_isolation_gate.ps1`;
- `harness_external_research_gate.ps1`;
- `harness_claim_schema_verifier.ps1`;
- `embedded_harness_policy.json`.

The intake router classifies work into R0-R5 and returns required gates.

The repository also includes adapter examples outside the core skill folder, such as `integrations/workbuddy-python-runtime`. These adapters should be treated as host-specific references. They can reuse the same `embedded_harness_policy.json`, but they do not change the core framework contract unless the adopting runtime actually calls them at the right execution boundary.

The mandatory advisory control plane sits around the router:

```text
routing receipt
-> intake route and cheapest sufficient gate selection
-> event-triggered re-evaluation
-> final claim, memory, version, and verification boundary check
-> selective hard runtime gate only for critical risks
```

The control plane decides whether to use project instructions, a project router, memory retrieval, existing skills/tools/plugins, external research, claim checks, or human confirmation. It should not expand into every memory, every skill, or every tool call by default.

## Router Decision Contract

The router and dynamic decision layer use a compact contract before opening deeper modules:

```text
task_type
target_surface
audience
project_lane
risk_level
semantic_ambiguity
module_need
memory_need
memory_mode
memory_lane
record_intent
external_need
claim_risk
projectization_decision
required_gates
```

This contract keeps the decision layer stronger than a suggestion while avoiding full runtime wrapping. It tells the agent which surface is being touched, who the content is for, whether a term is ambiguous, which module to open, whether memory or external lookup is needed, and whether the final answer needs a claim schema.

The design borrows a few lightweight patterns: separate decision from execution, run prechecks before critical boundaries, route by metadata, reassess on trigger events, preflight likely failure modes, and keep audience/ownership explicit. These are design influences, not proof that this framework is validated in every runtime.

## Receipt Profile Layer

The full receipt schema remains the canonical governance model, but runtime adapters do not need to expose every field on every turn. The router computes the full decision and selects a profile:

- `compact_runtime`: default low-cost output for local agent loops. It carries the fields needed to enforce R5, memory route, external search budget, claim gate, and confirmation.
- `extended_governance`: public repository, local harness, adapter, project memory, semantic ambiguity, memory write, or projectization work.
- `debug_receipt`: full route diagnostics and trigger evidence.

This mirrors a common systems pattern: keep the policy decision point complete, but sample or expand emitted context only when the execution boundary needs it.

See [router-decision-contract.md](router-decision-contract.md).

## Memory Routing Contract

Memory use has its own routed decision:

```text
memory_need
memory_mode
memory_lane
record_intent
projectization_decision
```

This prevents the framework from treating every mistake as permanent memory or every memory mention as a full history read. Common small mistakes can be stored as lightweight CE error-and-solution records. Full ERR/SOL pairs are reserved for explicit self-reflection requests, high-impact incidents, or repeated failures.

See [memory-routing-contract.md](memory-routing-contract.md) and [common-error-corpus.md](common-error-corpus.md).

## Conversation Memory Lane

Projectless long conversations can use a separate conversation memory lane when the router detects explicit checkpoint instructions or durable long-chat signals:

```text
conversation-memory/_META_INDEX.md
-> conversation_state.md or index.json
-> decisions.jsonl / open_loops.jsonl / errors_and_solutions.jsonl / references.jsonl
```

This lane is isolated by conversation or thread id. It can be read by later conversations only through explicit reference, and cross-conversation writes require explicit user instruction. If the work becomes a real project, the router should mark `projectization_decision: emergent_project_candidate` instead of silently mixing conversation memory into project memory.

See [conversation-memory-lane.md](conversation-memory-lane.md).

## Format Layering

The framework uses Markdown for human-facing docs and meta summaries, but machine-owned facts should use structured formats:

```text
Markdown -> public explanation, meta index, short capsules
JSON -> router policy and machine-readable indexes
JSONL -> append-only decisions, open loops, errors, solutions, references
CSV/TSV -> large tabular matrices
SQLite -> larger queryable local state
```

See [format-layering.md](format-layering.md).

## Cost Control Contract

The framework keeps a complete internal contract but emits only the smallest useful receipt:

```text
R0 -> no explicit receipt
R1/R2 -> compact runtime receipt
R3/R4 -> compact receipt plus triggered fields
R5 / public / archive / persona / memory write / debug -> extended or debug receipt
```

After the initial receipt, event-triggered re-evaluation should emit a delta receipt with changed fields only. A field belongs in the default receipt only if it changes the next action.

See [cost-control-contract.md](cost-control-contract.md).

## Archive And Persona Boundaries

Global archive is optional cold storage. It is checked after active project or conversation memory, not before. Archive defaults to moving or copying source files/directories so provenance stays intact.

Persona state is conversation-only and default-off. It may shape tone inside an ordinary conversation, but it cannot influence factual claims, risk, verification, project boundaries, memory boundaries, external research, claim schema checks, or tests.

See [archive-and-persona-boundaries.md](archive-and-persona-boundaries.md).

## Selective Runtime Enforcement Layer

The framework becomes hard runtime only for selected critical boundaries when an adopting agent routes execution through the runtime entry scripts:

```text
pre-task hook
-> harness_runtime_enforcer.ps1
-> task route, dynamic evaluation, constitution check

tool-call proxy
-> harness_tool_proxy.ps1
-> high-risk tool-call check

command wrapper
-> harness_task_wrapper.ps1
-> route check before command execution

final-answer gate
-> harness_runtime_enforcer.ps1 -Stage final
-> claim schema check for strong claims; PowerShell callers may pass actual response text with -FinalText
```

Hard-stop conditions:

- R5 without explicit human confirmation.
- Low-confidence route without boundary review.
- Nontrivial task with no available constitution entry.
- High-risk tool call without explicit human confirmation.
- Long-term memory write without explicit user request.
- Final strong claim without claim schema evidence boundary.

Ordinary tool calls should stay on the advisory control plane. This is not a sandbox. If an agent bypasses the hook, wrapper, or tool proxy, the scripts cannot stop it.

The wrapper is truly mandatory only when it is the agent's sole command execution path for the protected action. If a user, client feature, or separate tool path can bypass the wrapper, the framework remains advisory for that path.

Most gates are advisory by design: they return structured decisions that the caller must actively honor. Only paths configured to run through `harness_task_wrapper.ps1`, `harness_tool_proxy.ps1`, or an equivalent hook before execution become real interception points.

## Search And Learning Decision Matrix

External research is split into route types so the agent does not treat all outside lookup as the same operation:

| Route | Evidence surface | Output |
| --- | --- | --- |
| Official / authority source search | official docs, public notices, policy, law, price, version, release date, named role | current fact with source boundary |
| GitHub / open-source repository search | README, source tree, release notes, issues, changelog, license, examples | repository-grounded evidence with reuse boundary |
| General web cross-check | independent articles, tutorials, ecosystem notes, community reports | cross-checked public context with source limits |
| Source-grounded learning intake | external mechanism, external architecture comparison, learn-from-open-source task | source ledger plus classification labels |
| Local validation route | local files, scripts, tests, reproduction, smoke checks | local evidence boundary for strong claims |

The learning classifier uses these labels:

```text
fact
source_prior
hypothesis
inspiration
unverified_implementation_path
not_applicable
local_validated
```

This keeps external learning useful without letting it become an unsupported local success claim.

## 3. Skill Tree

The skill tree has a router and three ledgers:

- `troubleshooting-skill-matrix`: routes incidents, anchors, and project manifests.
- `agent-error-memory`: stores agent-caused process errors.
- `bug-solution-memory`: stores solution patterns.
- `shared-semantic-anchors`: stores user-confirmed meanings and boundaries.

The ledgers start empty in this whiteboard package.

## 4. Project Templates

`templates/project` contains a project instruction file and a memory-library skeleton. Each adopting project should copy and edit these templates instead of placing private project content into the shared core.

## Layered Memory Library

Project memory is intentionally not a single flat summary file. A flat file is cheap at first, but it becomes another overloaded history blob as records grow. The mandatory retrieval path is:

```text
memory-library/_META_INDEX.md
-> choose one category
-> category/_INDEX.md
-> open only the matching capsule
```

Do not skip the meta index. If a project has no meta index yet, use the smallest available top-level index or router manifest as a temporary meta layer and mark the missing layer as an adoption gap.

The default categories are:

- `governance`: project rules, decision records, boundaries, and operating contracts.
- `memory_hierarchy`: reusable memory capsules, active context, progress notes, and supersession chains.
- `external_references`: source notes, outside mechanisms, citations, and adoption boundaries.
- `raw_logs`: raw or near-raw observations that should not be treated as final memory.

Each category index should keep records small and searchable:

```text
ID | Type | Status | Summary | Retrieval Terms | Applies | Not Applies | Linked Modules | Linked Records | Supersedes | Superseded By
```

Recommended status values:

- `ACTIVE`: currently preferred record.
- `SUPERSEDED_BY:<ID>`: replaced by a newer record.
- `DEPRECATED`: retained for audit value but not used as current guidance.
- `TEMPLATE`: example or placeholder only.

When a new capsule replaces an old one, update both sides: the old row should point to `SUPERSEDED_BY:<ID>`, and the new row should declare `Supersedes`. This keeps long-horizon memory auditable without forcing the agent to reread old records on every task.

See [../examples/memory-library-demo/_META_INDEX.md](../examples/memory-library-demo/_META_INDEX.md) for a synthetic end-to-end example.

For the full recommended index fields and retrieval budget, see [memory-meta-index-contract.md](memory-meta-index-contract.md).

## Routing Model

```text
R0 ordinary response
R1 read-only inspection
R2 durable artifact
R3 code or config change
R4 experiment, runtime, or current source work
R5 high-risk action requiring confirmation
```

Routing is additive. A task can match R3 and R4 at the same time. The router keeps the highest label and returns all required gates.

## Boundary

The harness is advisory unless connected to a wrapper or hook system. It produces structured decisions, but the caller must honor them.

Even after hook or wrapper integration, enforcement is limited to paths that actually invoke the scripts. Use local smoke checks after agent client updates because launch paths, hook behavior, and bundled runtimes can change.

Do not treat this layer as a hard sandbox. If an agent still has a direct execution route that bypasses the wrapper or tool proxy, the hard stop degrades back to advisory for that route.

The published adapters are not complete compatibility certifications. PowerShell, Bash, and WorkBuddy Python paths must be smoke-tested in the target device, shell, client version, and hook or loop surface before any hard-enforcement claim is made.
