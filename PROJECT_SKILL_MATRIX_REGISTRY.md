# Project Skill Matrix Registry

A compact index that routes the agent to project-specific skill matrix routers. Keep this file small; put detailed behavior inside each project router skill.

## Default Flow

```text
root AGENTS.md
-> embedded harness intake router
-> mandatory advisory control plane
-> this registry
-> project router or project AGENTS
-> memory meta summary, category index, and matching capsule only when needed
-> executable gates only when needed
```

## Mandatory Memory Retrieval Chain

Memory lookup must follow this order:

```text
meta summary / _META_INDEX / router manifest
-> category index / point index / outer_retrieval_surface
-> matching capsule or paired point payload
```

Do not open deep memory files, all project notes, or all incident payloads before the meta/index layer has routed the request. If a project is still flat, treat its top-level index as the temporary meta layer and record that the project memory layout should be upgraded.

## Mandatory Advisory Control Plane

Nontrivial tasks must run the control plane before loading project-specific context, during execution when trigger events appear, and before final output. It should not wrap every tool call by default.

Required decisions:

- task type and active lane;
- current risk level and escalation triggers;
- whether project instructions, a project router, memory retrieval, existing skills/tools/plugins, external research, claim gates, or human confirmation are needed.

The control plane should produce a lightweight routing receipt: task type, project lane, risk level, required gates, external search need, memory need, claim gate need, and confirmation need.

Runtime trigger events include new evidence, missing files, tool errors, scope changes, user corrections, cross-project terminology, currentness/version claims, GitHub/open-source mechanism intake, cost escalation, risk escalation, strong claims, R5 actions, and memory writes.

Use the cheapest sufficient route. Do not load all project memory, all skills, all history, or wrap every tool call just because this governance layer is active.

Governance-layer updates, dynamic-evaluation rule changes, routing-rule changes, trigger-term updates, decision-matrix edits, and framework behavior changes are `R3` even when they are documentation-only. A missed route should be fixed with the narrowest useful trigger term rather than a broad catch-all.

## Selective Runtime Enforcement Layer

Routing, dynamic evaluation, and constitution governance should be enforced through hook/wrapper/tool-proxy entry points when a runtime can call them:

```text
pre-task hook -> harness_runtime_enforcer.ps1
tool-call proxy -> harness_tool_proxy.ps1
command wrapper -> harness_task_wrapper.ps1
final-answer gate -> harness_runtime_enforcer.ps1 -Stage final
```

Hard-stop states: R5 without human confirmation, low-confidence route without boundary review, missing constitution entry for a nontrivial task, high-risk tool call without confirmation, long-term memory write without explicit request, and strong final claim without claim schema. Ordinary tool calls stay under the advisory control plane. If a client cannot call these scripts before execution, the layer remains advisory for that client.

## Mandatory Search And Learning Decision Matrix

When a task needs public facts, open-source repository evidence, external mechanism learning, or anti-closed-door-invention review, choose the appropriate search and learning route:

| Route | Use when | Required boundary |
| --- | --- | --- |
| Official / authority source search | product, institution, policy, law, price, version, release date, named role, or other drift-prone public fact | Prefer official or authority sources first, then cross-check when practical. |
| GitHub / open-source repository search | repository, release, issue, license, changelog, source tree, project activity, examples | Separate README claims, source-code facts, release/issue evidence, and license boundaries. |
| General web cross-check | ecosystem trend, mechanism comparison, third-party guide, community experience, or uncertain public claim | Use independent sources when practical; mark source limits when not. |
| Source-grounded learning intake | external mechanism, external architecture comparison, learn-from-open-source work, or anti-closed-door-invention task | Build a source ledger and classify material as fact, source_prior, hypothesis, inspiration, unverified implementation path, or not_applicable. |
| Local validation route | adopting a mechanism, making a strong claim, or reporting success | Do not upgrade to locally validated without local files, scripts, tests, reproduction, or a concrete evidence chain. |

Outside material can supply completion ideas, boundary control, engineering constraints, validation methods, failure lessons, or non-applicable examples. It must not replace the active project objective or be presented as local validation by itself.

## Registered Routers

| Scope | Path or trigger | Router skill / file | Status | Notes |
| --- | --- | --- | --- | --- |
| Shared troubleshooting | agent errors, tool failures, skill matrix updates, reusable incidents | `skills/troubleshooting-skill-matrix/SKILL.md` | active | Routes to semantic anchors and paired ERR/SOL ledgers. |
| Embedded harness | nontrivial task intake, memory isolation, external research trigger, claim schema | `skills/embedded-harness/README.md` | active | Low-cost deterministic entry route. |
| Example project | `<PROJECT_ROOT>`, `EXAMPLE_PROJECT` | `<PROJECT_ROOT>/AGENTS.md` or a future project router skill | template | Replace with real project details after adoption. |

## Project Router Manifest Contract

Each project router should declare:

- scope
- capabilities
- permission declaration
- risk level and escalation triggers
- default invocation mode
- human-confirmation requirements
- linked point sets
- memory meta summary and category index roots
- external mechanism intake rules
- provenance and rollback policy for executable content
