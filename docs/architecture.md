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
-> claim schema check for strong claims
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
ID | Record Type | Status | Summary | Retrieval Terms | Supersedes | Superseded By
```

Recommended status values:

- `ACTIVE`: currently preferred record.
- `SUPERSEDED_BY:<ID>`: replaced by a newer record.
- `DEPRECATED`: retained for audit value but not used as current guidance.
- `TEMPLATE`: example or placeholder only.

When a new capsule replaces an old one, update both sides: the old row should point to `SUPERSEDED_BY:<ID>`, and the new row should declare `Supersedes`. This keeps long-horizon memory auditable without forcing the agent to reread old records on every task.

See [../examples/memory-library-demo/_META_INDEX.md](../examples/memory-library-demo/_META_INDEX.md) for a synthetic end-to-end example.

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
