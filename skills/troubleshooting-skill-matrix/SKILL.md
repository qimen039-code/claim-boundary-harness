---
name: troubleshooting-skill-matrix
description: Router skill for a project-neutral agent self-improvement matrix. Use when routing semantic anchors, paired error records, paired solution records, external mechanism intake, or project router manifest rules.
---

# Troubleshooting Skill Matrix Router

This router coordinates the four-skill core:

1. `troubleshooting-skill-matrix`: this router.
2. `agent-error-memory`: records agent-caused execution or process errors.
3. `bug-solution-memory`: records practical solutions and validation paths.
4. `shared-semantic-anchors`: records user-confirmed meanings and boundaries.

`embedded-harness` is an adjacent low-cost intake, memory-isolation, external-research, claim-gate, and selective-enforcement layer. It is not a fifth core skill.

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

## Mandatory Advisory Control Plane

Use this router under the required advisory control plane:

```text
routing receipt
-> select the smallest needed router/skill/memory surface
-> event-triggered re-evaluation after trigger events
-> final claim/memory/version boundary check
```

Trigger events include new evidence, missing files, tool errors, scope changes, user corrections, cross-project terminology, currentness/version claims, and risk or cost escalation.

Do not load every skill or memory record, and do not wrap every ordinary tool call, because this layer is active. If the layer is skipped or incomplete, the final result must say so.

Router decision contract:

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

Use this contract to decide whether to open this router, semantic anchors, ERR/SOL point indexes, project memory meta indexes, external research gates, claim gates, or runtime hard gates. It must stay low-cost: choose one matching module and one matching index first, then read payloads only when the index says they apply.

Memory routing contract:

- Explicit record requests route to the self-reflection matrix or common error corpus.
- Small reusable mistakes route to common error corpus first as compact error-and-solution samples with symptom, cause, applied solution, prevention, validation, and evidence.
- Full paired ERR/SOL records are reserved for high-impact, repeated, or explicit incidents.
- Projectless work with durable repository/docs/tests/adapter/versioning signals should be marked as an emergent project candidate before memory writes.

Memory meta index contract:

- Required lookup path: memory summary or `_META_INDEX` or router manifest -> one category or point index -> only matching capsule or ERR/SOL payload.
- Recommended index fields: lane, scope, category, record type, status, retrieval terms, applies-when, does-not-apply-when, linked modules, linked records, and last-reviewed marker.
- Default retrieval budget: one meta index, one category or point index, and at most two payload records unless the task explicitly asks for full audit, cleanup, migration, or broad historical review.

## Selective Runtime Enforcement Surfaces

Use these entry points when an adopting runtime supports hooks, wrappers, or tool-call interception:

```text
pre-task hook -> harness_runtime_enforcer.ps1
tool-call proxy -> harness_tool_proxy.ps1
command wrapper -> harness_task_wrapper.ps1
final-answer gate -> harness_runtime_enforcer.ps1 -Stage final
```

These gates are hard only when the caller invokes the runtime entry scripts. They block R5 without human confirmation, low-confidence routes without boundary review, missing constitution entry for nontrivial tasks, high-risk tool calls without confirmation, long-term memory writes without explicit request, and strong final claims without claim schema. Ordinary tool calls stay on the advisory control plane.

## Source-Grounded Search And Learning Workflow

Use this workflow whenever the task asks for current facts, GitHub/open-source review, unfamiliar mechanisms, external architecture comparison, or avoiding closed-door invention:

```text
trigger detected by dynamic evaluation
-> choose search route: official source / GitHub repository / general web cross-check / source-grounded learning
-> build a compact source ledger
-> classify each item: fact, source_prior, hypothesis, inspiration, unverified_implementation_path, or not_applicable
-> map only compatible parts into the local router, semantic anchors, memory capsules, or paired point records
-> keep non-applicable and risk notes
-> require local validation before claiming adoption success
```

For GitHub or open-source projects, inspect the surfaces that match the claim: README for stated intent, source tree for implementation facts, release notes or changelog for version facts, issues/discussions for known failures, and license/provenance for reuse boundaries. If a source cannot be reached or cross-checked, mark the resulting statement as `unverified` or `source_prior`, not as validated.

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
