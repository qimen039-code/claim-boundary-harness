# Project Skill Matrix Registry

A compact index that routes the agent to project-specific skill matrix routers. Keep this file small; put detailed behavior inside each project router skill.

## Default Flow

```text
root AGENTS.md
-> embedded harness intake router
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
