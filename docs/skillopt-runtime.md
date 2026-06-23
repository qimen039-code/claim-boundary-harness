# SkillOpt-Style External Runtime Module

The SkillOpt-style layer is a default-off, periodic module for improving skills,
routers, and governance files from accumulated evidence. It is not part of the
always-on runtime path, and it does not patch primary skill files by itself.

Use it when an operator explicitly asks to optimize, train, consolidate, or
review recurring skill behavior.

## Attribution Boundary

This module is an independent lightweight implementation inspired by the public
Microsoft SkillOpt project:

- https://github.com/microsoft/SkillOpt
- https://microsoft.github.io/SkillOpt/

Absorbed ideas include candidate skill edits, validation-gated updates, rejected
edit buffers, textual learning-rate limits, and slow/meta update boundaries.
This repository does not vendor Microsoft SkillOpt code, benchmark code,
training loops, model backends, dashboards, or datasets.

Treat SkillOpt benchmark claims and upstream behavior as source-prior until
locally reproduced. This module only proves that this repository can generate
and gate candidate packets; it does not prove that a candidate improves the
target skill until the listed regression probes are run after a normal reviewed
edit.

For the broader source ledger, see
[influences-and-attribution.md](influences-and-attribution.md).

## Why Not Vendor Upstream SkillOpt By Default

Directly using Microsoft SkillOpt is compatible with this project, but it should
be an optional upstream adapter rather than copied into the core repository by
default.

Reasons:

- upstream SkillOpt is a full optimizer stack with its own package, model
  backends, benchmarks, training loop, docs, and optional dashboard;
- adopters may need API keys, model-provider configuration, dependency
  installation, and benchmark data before running it;
- vendoring upstream code would make this repository responsible for license
  notices, security updates, version pinning, dependency drift, and rollback;
- upstream benchmark results remain source-prior for this framework until an
  adopting workspace reproduces or gates them locally;
- the default whiteboard package should stay small enough to copy into agent
  workspaces without installing a full optimizer.

The recommended direct-integration path is:

```text
install or clone Microsoft SkillOpt outside this repository
-> run upstream SkillOpt in its own environment
-> export the candidate skill artifact or evaluation result
-> convert that artifact into this repository's candidate_edit_packet
-> run this repository's validation gate
-> apply only through the normal reviewed change process
```

If an adopter wants to vendor, submodule, or package upstream SkillOpt code, pin
the upstream version or commit, preserve the MIT license notice, document the
dependency and API-key boundary, and keep a rollback/yank path. That is an
explicit integration decision, not the default whiteboard baseline.

## What It Does

The module creates a bounded cycle:

```text
evidence or completed-task observation
-> candidate_edit_packet
-> validation gate
-> accepted / deferred / rejected record
-> optional slow_update_proposal
-> normal human-reviewed change process
```

The executable entry point is:

```bash
python tools/skillopt/skillopt_cycle.py --help
```

The main command is `cycle`:

```bash
python tools/skillopt/skillopt_cycle.py cycle \
  --target skills/skillopt-training-layer/SKILL.md \
  --surface skill \
  --evidence "Recurring route failure or completed-task observation." \
  --proposed-change "Add one bounded rule for the recurring failure." \
  --protected-regions-checked
```

By default it writes generated runtime artifacts under `.skillopt/`:

```text
.skillopt/
  cycles/<candidate_id>/
    candidate_edit_packet.json
    gate_report.json
    source_intake_note.json
    regression_probe_set.jsonl
  records/
    accepted.jsonl
    deferred.jsonl
    rejected.jsonl
    rejected_edit_buffer.jsonl
    slow_updates.jsonl
```

`.skillopt/` is local runtime output and is intentionally ignored by Git.

## Gate Meaning

`accepted` means the candidate packet has enough structure, evidence, target
boundary, rollback, and regression probes to enter the normal change process.
It does not mean the target file was modified. It does not prove behavioral
improvement until the listed probes are actually run against the applied edit.

`deferred` means the candidate is plausible but missing evidence, protected
region review, rollback, or regression coverage.

`rejected` means the packet violates a hard boundary such as missing schema,
unsupported target surface, target outside the repository root, missing target
file, or a learning-rate violation.

## Why It Is External

This module is intentionally outside the always-on router. Skill improvement is
a periodic maintenance activity, not a cost paid by every task. Keeping it
external preserves the harness core:

- ordinary work stays low cost;
- the runtime skill matrix remains the authority;
- candidate changes are reviewable artifacts;
- rejected edits are preserved instead of silently retried;
- accepted candidates still require the normal approval and change process.

## Smoke Test

Run the built-in smoke test from the repository root:

```bash
python tools/skillopt/skillopt_cycle.py self-test
```

The test creates a temporary candidate cycle, validates it, records the gate
result under a temporary local directory, and removes that directory unless
`--keep` is passed.
