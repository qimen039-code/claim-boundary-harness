# Agent Memory Lane Harness

Agent Memory Lane Harness is a meta-first whiteboard framework for routing coding-agent work through project-scoped memory lanes, lightweight guardrails, claim checks, and paired improvement records.

Current version: `v0.7.0`

Formerly: Agent Harness Skill Tree.

It is not tied to one agent runtime. It is a neutral starting point that can be mapped into any agent that can read workspace instructions, run local scripts, use command or skill folders, or call hooks before tools.

## Important Adoption Notes

- **Codex field-use boundary:** this framework has been tried in one private Codex-based project workflow. That early use suggests the routing chain can persist across new conversations when the root instruction file, harness policy, project registry, and skill tree are installed, but it has not yet been broadly validated across many projects or many agent runtimes.
- **Independent project lanes:** separate projects can run separate local chains. With clear global routing boundaries, each project keeps its own instructions, memory roots, and progress records, which reduces silent memory bleed and cross-project contamination.
- **Mandatory advisory control plane:** nontrivial tasks must create a lightweight routing receipt, re-evaluate only on trigger events, and final-check claim/memory/search boundaries without wrapping every tool call.
- **Source-grounded search and learning:** current facts, GitHub/open-source review, unfamiliar mechanisms, and anti-closed-door-invention tasks are split into official-source search, repository inspection, general web cross-check, source-grounded intake, and local validation.
- **Selective hook/wrapper/tool proxy runtime:** only critical boundaries such as R5, high-risk tools, low-confidence routes, long-term memory writes, and final strong claims need hard stops.
- **Meta-first memory retrieval:** memory lookup is not a direct file dive. The required chain is meta summary or `_META_INDEX`, then category or point index, then only the matching capsule or paired record.
- **No continuous skill generation by default:** the framework does not keep creating new skills automatically. Too many self-generated skills can pollute project boundaries, weaken routing discipline, and make it unclear which rule owns a task. Reusable knowledge should instead be added to a clearly registered skill knowledge library, reference pack, or tool content pack, then routed explicitly.
- **Sanitized whiteboard examples:** This public repository was sanitized before publication. Private records, local project details, machine paths, and real incident history from the original working setup are not included. The included examples are synthetic records used only to help agents and adopters understand how to adapt the framework: routing, layered memory indexes, project memory capsules, paired error/solution records, claim boundaries, and client-update drift handling.
- **Reference adapters are early:** the main scripts are PowerShell, and the four core gates also have Bash counterparts under `skills/embedded-harness/bash`. Bash scripts require `jq`. The repository also includes an experimental WorkBuddy-oriented Python runtime adapter under `integrations/workbuddy-python-runtime`. These adapters have not been fully tested across devices, operating systems, client versions, or real production loops; they are reference starting points.
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
-> mandatory advisory control plane
-> lightweight routing receipt
-> event-triggered re-evaluation
-> only needed gates
-> project instructions and memory boundary
-> execution
-> final answer with evidence limits
-> optional paired error and solution records
```

## What It Implements

- **Root microkernel**: the small always-on rule set for language, evidence, risk, memory boundaries, and high-risk stops.
- **Intake router**: deterministic R0-R5 task classification.
- **Mandatory advisory control plane**: routing receipt, event-triggered dynamic review, and final boundary checks for skill/tool/plugin/search/memory/claim-gate decisions.
- **Governance/routing update handling**: framework-rule, trigger-term, routing-rule, decision-matrix, and dynamic-evaluation edits are treated as R3 changes even when they are documentation-only.
- **Selective runtime enforcer scripts**: hook, wrapper, and tool-proxy entry points that return nonzero only at configured hard-stop boundaries when called by the adopting runtime. They are truly mandatory only when they are the sole execution path for the relevant agent action.
- **Search and learning decision matrix**: routes public facts, GitHub repository evidence, general web cross-checks, external mechanism intake, and local validation boundaries.
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
+-- AGENTS.md
+-- CHANGELOG.md
+-- PROJECT_SKILL_MATRIX_REGISTRY.md
+-- VERSION
+-- docs/
|   +-- adoption.md
|   +-- architecture.md
|   +-- examples.md
|   +-- integrations/
|   +-- non-goals.md
|   +-- reproduction.md
+-- integrations/
|   +-- workbuddy-python-runtime/
+-- examples/
|   +-- sample-routing.md
|   +-- memory-capsule-examples.md
|   +-- memory-library-demo/
+-- skills/
|   +-- agent-error-memory/
|   +-- bug-solution-memory/
|   +-- embedded-harness/
|   |   +-- bash/
|   |   +-- validate_policy.ps1
|   |   +-- harness_runtime_enforcer.ps1
|   |   +-- harness_task_wrapper.ps1
|   |   +-- harness_tool_proxy.ps1
|   +-- shared-semantic-anchors/
|   +-- troubleshooting-skill-matrix/
+-- templates/
    +-- project/
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

Integration examples are intentionally small and conservative:

- [docs/integrations/codex.md](docs/integrations/codex.md)
- [docs/integrations/claude-code.md](docs/integrations/claude-code.md)
- [docs/integrations/workbuddy.md](docs/integrations/workbuddy.md)
- [integrations/workbuddy-python-runtime/README.md](integrations/workbuddy-python-runtime/README.md)

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

## Mandatory Advisory Control Plane

For nontrivial tasks, the framework requires a low-cost control plane:

```text
routing receipt
-> execute the cheapest sufficient route
-> event-triggered re-evaluation
-> final claim, memory, version, and verification boundary check
-> selective runtime hard gate only for critical risks
```

The routing receipt should decide:

- task type and active lane;
- risk level and required gates;
- project instructions or project router;
- memory retrieval and memory isolation;
- an existing skill, tool, plugin, or adapter;
- external research for current or drift-prone facts;
- claim-schema or evidence-boundary checks;
- human confirmation for high-risk actions.

Re-evaluation is event-triggered, not continuous. Trigger events include new evidence, missing files, tool errors, scope changes, user corrections, cross-project terminology, version/currentness claims, GitHub/open-source mechanism intake, cost escalation, risk escalation, strong claims, R5 actions, or memory writes.

This control plane is mandatory, but it is not a reason to load every skill, every memory file, or wrap every tool call. If the control plane is skipped or cannot be completed, the final answer must say so and must not present the result as fully verified.

## Mandatory Search And Learning Decision Matrix

The framework treats external research as a routed workflow, not a vague instruction to search. Use this matrix when the task involves current facts, public products, policy, law, price, version, release data, GitHub/open-source repositories, unfamiliar mechanisms, architecture comparison, or avoiding closed-door invention.

| Route | Use when | Boundary |
| --- | --- | --- |
| Official / authority source search | Drift-prone public facts such as product, institution, policy, law, price, version, release date, or named role | Prefer official or authority sources first; cross-check when practical. |
| GitHub / open-source repository search | Repository intent, source tree, release notes, issues, changelog, license, project activity, or examples | Separate README claims, code facts, release or issue evidence, and license boundaries. |
| General web cross-check | Ecosystem trend, mechanism comparison, third-party guide, community experience, or uncertain public claim | Use independent sources when practical; mark source limits when not. |
| Source-grounded learning intake | Learn-from-open-source tasks, external mechanism review, architecture comparison, or anti-closed-door-invention work | Build a source ledger and classify material before adapting it. |
| Local validation route | Strong adoption, success, performance, or compatibility claims | Require local files, scripts, tests, reproduction, or a concrete evidence chain. |

Outside material should be classified as `fact`, `source_prior`, `hypothesis`, `inspiration`, `unverified_implementation_path`, or `not_applicable`. Reading external material can guide the work, but it is not local validation by itself.

## Mandatory Meta-First Memory Lookup

For nontrivial memory retrieval, the framework requires this order:

```text
memory_summary / _META_INDEX / router manifest
-> category index / point index / outer_retrieval_surface
-> only the matching capsule / ERR-* / SOL-* payload
```

This rule is important because direct deep reads recreate the same context-bloat problem that the framework is meant to prevent. If a project has not adopted a meta index yet, use the smallest available top-level index as a temporary meta layer, note the adaptation gap, and do not scan the whole memory tree unless the task is explicitly a full audit.

## Field Use Note

This framework has been tried in one private Codex-based project workflow. Once the root instruction file, harness policy, project registry, and skill tree are in place, that early use suggests new conversations can continue to follow the same routing chain instead of rediscovering the workflow from scratch.

This is not yet broad field validation. The public package has not been battle-tested across many projects, many operators, or many agent runtimes.

The PowerShell, Bash, and WorkBuddy Python adapters are also not complete compatibility claims. They were adapted and smoke-tested from one local device environment. The Bash scripts were exercised through Git Bash on Windows rather than a real macOS/Linux machine, and the WorkBuddy Python adapter was unit-tested as a standalone decision layer rather than proven as a hard-wired WorkBuddy execution-loop integration.

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

Validate the policy after editing it:

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\embedded-harness\validate_policy.ps1
```

On Bash environments with `jq`:

```bash
bash ./skills/embedded-harness/bash/validate_policy.sh
bash ./skills/embedded-harness/bash/harness_intake_router.sh --task-text "fix the script and run benchmark" --cwd "/path/to/project"
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
- blocked memory isolation for a sibling prefix path;
- trigger word-boundary and negation checks;
- external research trigger checks;
- external research negation checks;
- claim schema verification;
- policy validation;
- Bash smoke checks when `jq` is available;
- WorkBuddy Python adapter unit tests as a standalone decision layer;
- package content scan for local project terms and sensitive field names.

See [docs/reproduction.md](docs/reproduction.md) for commands and expected results.

## Recommended First Customizations

- Rename `EXAMPLE_PROJECT` to your project lane.
- Replace placeholder memory roots.
- Add one project instruction file under `templates/project/`.
- Keep the error and solution memory files empty until a real solved incident exists.
- Add only user-confirmed semantic anchors.
- Add wrapper or hook integration only after the basic scripts run in your environment.
- Review [docs/non-goals.md](docs/non-goals.md) before adding packaging, dashboards, broad comparison tables, or community-maintenance boilerplate.

## Versioning

Every public repository update should update:

- `VERSION`
- `CHANGELOG.md`
- the `Current version` line in this README

Use `vMAJOR.MINOR.PATCH` labels:

- `PATCH`: wording, docs, examples, or small trigger-rule updates.
- `MINOR`: new reusable templates, gates, adapters, or framework behaviors.
- `MAJOR`: breaking changes to the framework layout, rule contract, or adoption surface.

## Limitations

This is a foundation package, not a complete safety system.

- The scripts are not a hard sandbox.
- A blocked result only works when the calling agent or wrapper honors it.
- A wrapper is truly mandatory only if it is the only command or tool execution path for the agent action it protects. If users or tools can bypass it, the framework remains advisory for that path.
- Most gates are intentionally advisory: they return structured decisions for the caller to honor. They become real interception only on execution paths where `harness_task_wrapper.ps1`, `harness_tool_proxy.ps1`, or an equivalent hook is the only way the agent can run the protected action.
- The trigger lists are intentionally small and should be tuned.
- The memory format is a template, not a database.
- Different agents need different adapter files and launch methods.
- The WorkBuddy Python adapter is experimental and is not a complete WorkBuddy compatibility guarantee.
- Bash/macOS/Linux support is a reference path until it is tested on the target machine and shell.
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
