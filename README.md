# Agent Harness Skill Tree

Agent Harness Skill Tree is a whiteboard framework for routing agent work through lightweight guardrails, project memory boundaries, claim checks, and paired improvement records.

It is not tied to one agent runtime. It is a neutral starting point that can be mapped into any agent that can read workspace instructions, run local scripts, use command or skill folders, or call hooks before tools.

## Important Adoption Notes

- **Codex field use:** this framework has been used smoothly in a Codex-based workflow. After the root instruction file, harness policy, project registry, and skill tree are installed, new conversations can keep following the same routing chain instead of rediscovering the workflow from scratch.
- **Independent project lanes:** separate projects can run separate local chains. With clear global routing boundaries, each project keeps its own instructions, memory roots, and progress records, which reduces silent memory bleed and cross-project contamination.
- **Meta-first memory retrieval:** memory lookup is not a direct file dive. The required chain is meta summary or `_META_INDEX`, then category or point index, then only the matching capsule or paired record.
- **No continuous skill generation by default:** the framework does not keep creating new skills automatically. Too many self-generated skills can pollute project boundaries, weaken routing discipline, and make it unclear which rule owns a task. Reusable knowledge should instead be added to a clearly registered skill knowledge library, reference pack, or tool content pack, then routed explicitly.
- **Sanitized whiteboard examples:** This public repository was sanitized before publication. Private records, local project details, machine paths, and real incident history from the original working setup are not included. The included examples are synthetic records used only to help agents and adopters understand how to adapt the framework: routing, layered memory indexes, project memory capsules, paired error/solution records, claim boundaries, and client-update drift handling.
- **PowerShell-only reference scripts:** the included scripts are PowerShell because the original working environment was Windows. Other operating systems have not been adapted or tested here. The design is portable, but Bash, Python, Node, or native hook adapters should be written and validated by users on their own target systems.
- **Agent client updates require re-adaptation:** Codex, Claude Code, and other agent clients may change paths, launchers, hook behavior, skill loading, or bundled runtimes after updates. Re-run adapter checks and smoke tests after client updates so stale paths do not silently disable the harness.

## What Problem It Solves

Modern coding agents often fail in the same places:

- They start working before deciding task risk.
- They load too much history, or the wrong project history.
- They mix memories from unrelated projects.
- They overstate partial runs as proven results.
- They skip current source checks for versioned or fast-changing facts.
- They repeat old mistakes because solved incidents are not stored in a reusable shape.
- Their instruction files, skills, and local checks are not connected into one clear path.

This project gives those pieces a simple shared structure.

```text
user request
-> root microkernel
-> intake router R0-R5
-> only needed gates
-> project instructions and memory boundary
-> execution
-> final answer with evidence limits
-> optional paired error and solution records
```

## What It Implements

- **Root microkernel**: the small always-on rule set for language, evidence, risk, memory boundaries, and high-risk stops.
- **Intake router**: deterministic R0-R5 task classification.
- **Additive routing**: if a task matches more than one risk type, it keeps the highest risk label and returns the union of needed gates.
- **Memory isolation gate**: prevents accidental cross-project memory use unless the user clearly asks for it.
- **External research gate**: detects currentness signals such as latest, current, version, release, GitHub, and official sources.
- **Claim schema verifier**: blocks strong claims unless the claim has enough source and evidence boundary metadata.
- **Skill tree router**: routes semantic anchors, paired incident records, and project router manifests.
- **Paired improvement records**: one error record plus one solution record for each solved recurring incident.
- **Layered project memory library**: a meta index points to category indexes, and category indexes point to individual capsules.
- **Whiteboard templates**: empty project memory categories, project instructions, semantic anchors, and error/solution ledgers.

## Repository Layout

```text
.
├── AGENTS.md
├── PROJECT_SKILL_MATRIX_REGISTRY.md
├── docs/
│   ├── adoption.md
│   ├── architecture.md
│   ├── examples.md
│   └── reproduction.md
├── examples/
│   ├── sample-routing.md
│   ├── memory-capsule-examples.md
│   └── memory-library-demo/
├── skills/
│   ├── agent-error-memory/
│   ├── bug-solution-memory/
│   ├── embedded-harness/
│   ├── shared-semantic-anchors/
│   └── troubleshooting-skill-matrix/
└── templates/
    └── project/
```

## Where It Can Be Used

This framework can be adapted to agents that support one or more of these surfaces:

- workspace instruction files;
- project instruction files;
- command or skill folders;
- local script execution;
- tool-call hooks;
- project memory folders;
- wrapper scripts around the agent process.

If an agent only reads instruction files, this framework acts as a soft workflow contract. If an agent also supports hooks or wrappers, the gate scripts can become stronger runtime checks.

## Why Skills Are Bounded

This framework treats skills as routed, reviewable capabilities rather than an unlimited self-growing pile. The default chain is:

```text
small root rules
-> task risk route
-> selected project lane
-> selected skill or knowledge pack
-> execution and claim boundary
-> optional paired improvement record
```

New skills should be created only when they remove real repeated work and have a clear scope, owner, retrieval surface, and non-applicable boundary. Routine facts, solved incidents, examples, and reference notes can live in memory capsules or knowledge packs without becoming new active skills.

## Mandatory Meta-First Memory Lookup

For nontrivial memory retrieval, the framework requires this order:

```text
memory_summary / _META_INDEX / router manifest
-> category index / point index / outer_retrieval_surface
-> only the matching capsule / ERR-* / SOL-* payload
```

This rule is important because direct deep reads recreate the same context-bloat problem that the framework is meant to prevent. If a project has not adopted a meta index yet, use the smallest available top-level index as a temporary meta layer, note the adaptation gap, and do not scan the whole memory tree unless the task is explicitly a full audit.

## Field Use Note

This framework has been used smoothly in a Codex-based workflow. Once the root instruction file, harness policy, project registry, and skill tree are in place, new conversations can continue to follow the same routing chain instead of rediscovering the workflow from scratch.

It also supports independent project lanes. After global routing boundaries are configured, each project can keep its own instructions, memory roots, and incident records. That makes it possible to run separate local chains for separate projects without silent memory bleed, cross-project contamination, or unrelated progress records being mixed together.

## Concrete Examples

The package includes synthetic examples that show the intended record shapes without exposing any private project history:

- [examples/sample-routing.md](examples/sample-routing.md): routing examples for mixed risk and vague tasks.
- [examples/memory-capsule-examples.md](examples/memory-capsule-examples.md): project memory capsule, paired error/solution records, claim boundary record, and client-update drift record.
- [examples/memory-library-demo/_META_INDEX.md](examples/memory-library-demo/_META_INDEX.md): layered memory library demo using meta index, category indexes, capsule status, and supersession.
- [docs/examples.md](docs/examples.md): expected gate behavior and how to interpret examples.

## Quick Start

1. Copy this package into a new workspace.
2. Open `AGENTS.md` and keep only the rules that match your workflow.
3. Edit `skills/embedded-harness/embedded_harness_policy.json`.
4. Replace `EXAMPLE_PROJECT` and `C:\\path\\to\\project` with your project lane and memory roots.
5. Register the skill folders using whatever skill or command mechanism your agent supports.
6. Run the intake router before nontrivial work.

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\harness_intake_router.ps1 -TaskText "fix the script and run benchmark" -Cwd "C:\path\to\project"
```

After any agent client update, re-check the adapter surface before relying on the chain:

```text
1. Confirm the root instruction file is still loaded.
2. Confirm command, skill, hook, or wrapper paths still exist.
3. Run the intake router on a mixed-risk task.
4. Run the memory isolation gate on an allowed and a blocked path.
5. Run a claim verifier smoke check before publishing strong factual claims.
```

## Local Reproduction

The whiteboard package was smoke-tested locally with:

- intake routing for a mixed fix plus benchmark task;
- fallback classification for vague project work;
- memory isolation for an example project memory folder;
- external research trigger checks;
- claim schema verification;
- package content scan for local project terms and sensitive field names.

See [docs/reproduction.md](docs/reproduction.md) for commands and expected results.

## Recommended First Customizations

- Rename `EXAMPLE_PROJECT` to your project lane.
- Replace placeholder memory roots.
- Add one project instruction file under `templates/project/`.
- Keep the error and solution memory files empty until a real solved incident exists.
- Add only user-confirmed semantic anchors.
- Add wrapper or hook integration only after the basic scripts run in your environment.

## Limitations

This is a foundation package, not a complete safety system.

- The scripts are not a hard sandbox.
- A blocked result only works when the calling agent or wrapper honors it.
- The trigger lists are intentionally small and should be tuned.
- The memory format is a template, not a database.
- Different agents need different adapter files and launch methods.
- There are likely missing cases, rough edges, and workflows we have not considered.

## Feedback Welcome

If you try this in another agent runtime, a different operating system, or a different project workflow, feedback is welcome. Useful feedback includes:

- unclear rules;
- missing risk categories;
- better trigger terms;
- better memory capsule shape;
- examples of hook integration;
- failure cases where the router chose the wrong path.

The goal is a simple reusable chain that helps agents stay scoped, honest, and easier to audit.
