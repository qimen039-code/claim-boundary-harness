---
name: skillopt-training-layer
description: Offline SkillOpt-style candidate-edit and validation layer for a bounded agent skill matrix. Use when optimizing or consolidating recurring skill improvements without replacing the existing multi-skill control plane.
---

# SkillOpt-Style Training Layer

This skill is an auxiliary optimization layer. It does not replace the runtime skill matrix.

The runtime matrix stays responsible for routing, memory isolation, external research triggers, claim boundaries, and high-risk stops. This layer only proposes and gates candidate improvements to those surfaces.

## Source And Attribution

This public skill adapts ideas from the public SkillOpt project:

- source: `https://github.com/microsoft/SkillOpt`
- project page: `https://microsoft.github.io/SkillOpt/`
- license observed on 2026-06-18: MIT License, Copyright (c) 2026 Microsoft Corporation
- local classification: `adapted_rule`

This file does not vendor SkillOpt code or copy its implementation. It translates selected public mechanisms into this framework's control plane: validation-gated skill updates, candidate-edit packets, rejected-edit buffers, textual learning-rate limits, and slow-update proposals.

If future work copies SkillOpt source code, substantial documentation text, examples, or executable components, include the upstream MIT copyright and permission notice with the copied material, pin the upstream version or commit, and preserve a rollback or yank path before publishing.

For the broader source ledger, see `../../docs/influences-and-attribution.md`.

## Scope

Use this layer for:

- offline or bounded consolidation of recurring skill, router, harness, and workflow lessons;
- SkillOpt-style candidate generation from completed tasks, failure patterns, or rollout reviews;
- validation-gated proposals before changing routers, memory contracts, semantic anchors, or project skills;
- rejected-edit records that prevent bad rule changes from recurring;
- slow-update proposals that need repeated evidence before adoption.

Do not use this layer for:

- replacing a multi-skill matrix with one composite skill;
- writing long-term memory directly;
- mutating primary routers without an explicit gate result and human approval when required;
- running third-party optimizer code by default;
- treating external benchmark claims as local validation.

## Invocation

Use this layer when a task asks to:

- optimize, train, benchmark, consolidate, or validate a skill;
- produce candidate edits rather than immediately changing a primary skill;
- review rejected skill edits;
- apply textual learning-rate limits;
- propose a slow update;
- absorb a public skill-optimization mechanism as a local rule rather than executable code.

## Executable External Module

This repository includes an optional, default-off runner:

```bash
python tools/skillopt/skillopt_cycle.py --help
```

Use it only for periodic skill or router maintenance, not ordinary task
execution. The runner creates:

- `candidate_edit_packet.json`;
- `gate_report.json`;
- `source_intake_note.json`;
- `regression_probe_set.jsonl`;
- local `.skillopt/records/*.jsonl` ledgers.

The runner never patches the target skill or router file. `accepted` means the
candidate may enter the normal human-reviewed change process. It does not mean
the proposed change has been applied or behavior-validated.

Runtime details: `../../docs/skillopt-runtime.md`.

## Architecture Boundary

Recommended chain:

```text
user task
-> root microkernel and intake router
-> existing skill matrix selects scope and boundary
-> this layer drafts candidate edits only when useful
-> validation gate accepts, rejects, or defers each candidate
-> accepted candidates may be applied through the normal change process
```

Do not invert this order. The optimizer is subordinate to the matrix.

## Candidate Edit Packet

Every candidate should preserve:

```text
candidate_id:
target_file:
target_surface: router | ERR | SOL | semantic_anchor | project_router | harness | registry | docs
source_type: local_evidence | external_source_prior | mixed
evidence:
proposed_change:
reason:
textual_learning_rate:
protected_regions_checked:
regression_tasks:
expected_improvement:
risk:
rollback:
status: proposed | accepted | rejected | deferred
gate_result:
```

Rules:

- One candidate should change one conceptual behavior.
- Prefer small edits over broad rewrites.
- Do not mix routing changes, semantic-anchor changes, and memory writes in one candidate.
- Do not mark a candidate accepted without a gate result or explicit approval.
- If a candidate changes governance or routing rules, treat it as a framework-governance change.
- If a candidate changes claims about validation, experiments, current facts, or external mechanisms, route it through external research and claim boundaries before adoption.
- If a candidate writes memory or touches install, delete, permission, network, secret, or payment surfaces, stop for explicit human confirmation.

## Textual Learning Rate

Default edit budget:

- one target file per candidate;
- up to three bullets or one short section per candidate;
- no broad rename or global rewrite;
- no edits inside protected slow-update regions unless the candidate is explicitly a slow-update proposal.

Raise the budget only for an explicit migration, cleanup, or full rewrite.

## Validation Gate

Before accepting a candidate:

```text
candidate edit
-> inspect target file and nearby routing rules
-> choose a small regression probe set
-> verify the candidate improves or preserves expected routing
-> verify no boundary regression: memory isolation, high-risk stops, external research trigger, claim boundary
-> accept, reject, or defer
```

Useful probes include:

- ordinary chat stays low-cost;
- GitHub or currentness requests trigger external research;
- governance or routing updates remain framework-governance changes;
- delete, install, network, permission, secret, or payment actions remain high-risk stops;
- projectless exploration does not contaminate project memory;
- small recurring mistakes route to a common error corpus before full paired incident records.

Gate outcomes:

- `accepted`: candidate may be applied through the normal change process.
- `rejected`: preserve the bad edit pattern and rejection reason.
- `deferred`: evidence is insufficient; keep as source-prior or hypothesis.

## Rejected Edit Buffer

Rejected candidates should preserve:

```text
rejected_id:
candidate_id:
target_surface:
bad_change_summary:
why_rejected:
evidence:
prevention_rule:
date:
```

Do not silently discard rejected edits when they reveal a recurring risk.

## Slow Update

Use slow updates for:

- recurring cross-session route failures;
- stable user semantic corrections;
- repeated tool-call failure patterns;
- durable external mechanism absorption;
- benchmark-backed skill improvements.

Slow updates require repeated local evidence or explicit approval. They should be staged as candidates first.

## External Mechanism Intake

Classify SkillOpt-like sources as:

- `fact`: repository metadata, license, release notes, source tree facts, or quoted docs;
- `source_prior`: reported benchmark results or project claims not locally reproduced;
- `adapted_rule`: a mechanism translated into this framework, such as validation gates or rejected-edit buffers;
- `hypothesis`: plausible improvement not yet tested;
- `unverified_implementation_path`: executable adoption path not yet reviewed;
- `not_applicable`: mechanism that conflicts with local boundaries.

Adopted mechanism classes:

- validation-gated skill update;
- candidate edit packet;
- rejected edit buffer;
- textual learning rate;
- slow update;
- separation of runtime matrix from offline optimizer.

Not adopted by default:

- third-party optimizer execution;
- automatic mutation of primary skills;
- automatic memory writes;
- replacement of bounded skills with one composite skill;
- external benchmark claims as local validation.

## Output Contract

Produce one of:

1. `candidate_edit_packet`: a bounded proposed change.
2. `gate_report`: accepted, rejected, or deferred with evidence.
3. `source_intake_note`: source-prior mechanism classification.
4. `regression_probe_set`: prompts or checks used to validate candidate behavior.

If the task asks to apply an edit, first ensure the risk level and approval requirements are satisfied.

## Guardrails

- The existing multi-skill matrix is the runtime authority.
- This layer is a candidate generator and validator, not an autonomous maintainer.
- Do not optimize away explicit boundaries for convenience.
- Do not collapse specialized skills into one composite skill.
- Do not write memory just because a candidate looks useful.
- Do not claim local validation without local gate evidence.
