# Architecture

Agent Harness Skill Tree has four layers.

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
