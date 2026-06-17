---
name: troubleshooting-skill-matrix
description: Router skill for a project-neutral agent self-improvement matrix. Use when routing semantic anchors, paired error records, paired solution records, external mechanism intake, or project router manifest rules.
---

# Troubleshooting Skill Matrix Router

This router coordinates four components:

1. `troubleshooting-skill-matrix`: this router.
2. `agent-error-memory`: records agent-caused execution or process errors.
3. `bug-solution-memory`: records practical solutions and validation paths.
4. `shared-semantic-anchors`: records user-confirmed meanings and boundaries.
5. `embedded-harness`: low-cost intake, memory isolation, external research, and claim gates.

## Invocation

Use this router when a task involves:

- recording or retrieving a reusable incident;
- updating an error/solution memory pair;
- semantic anchor definitions;
- project router manifest design;
- external mechanism intake;
- deciding whether an existing skill/tool/plugin should be used.

## Retrieval Workflow

```text
request
-> read memory_summary / _META_INDEX / router manifest first
-> scan the compact point index
-> select matching ERR/SOL/anchor by retrieval surface
-> read only the selected payload
-> apply to the current task
```

If no meta layer exists yet, use this router manifest and the compact point index as the temporary meta layer. Do not scan every point payload before choosing by retrieval surface.

## Recording Workflow

```text
solved incident
-> add one ERR-* point if the agent caused or exposed a process error
-> add one SOL-* point for the solution
-> cross-link both IDs
-> add semantic anchors only when the user explicitly defines a reusable meaning
```

## Current Bound Points

No real incident records are included in this whiteboard version.

| Error point | Solution point | Use when |
| --- | --- | --- |
| `ERR-EXAMPLE-YYYY-MM-DD` | `SOL-EXAMPLE-YYYY-MM-DD` | Replace with a real solved incident after adoption. |

## External Mechanism Intake

Classify outside material as:

- `reference_only`: useful idea, no execution.
- `adapted_rule`: translated into local policy/router/point records.
- `executable_tool`: requires explicit approval, pinned source/version, integrity review when practical, permission declaration, and rollback path.

Do not copy third-party mechanisms into execution by default.
