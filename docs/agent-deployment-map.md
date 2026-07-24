# Agent Self-Deployment Map

This is the required pre-deployment map for an agent installing or adapting
Claim Boundary Harness (CBH). Read it before copying files, editing a host
configuration, or claiming that a capability is active.

## Core Rule

Do not copy the repository wholesale. Select one declared deployment profile,
stage its exact files, map them to the real host surfaces, and verify every
claimed capability. Repository presence is not deployment evidence.

```text
read this map
-> inspect real host instruction / model-loop / hook surfaces
-> select one deployment profile
-> stage the exact runtime bundle and keep its receipt
-> initialize deployment-local lane/config state from public templates
-> wire only supported host surfaces
-> run policy, behavior, and host-lifecycle checks
-> claim only capabilities whose receipts pass
```

## Component Classes

### A. Required Runtime Core

| Component | Purpose | Required when |
| --- | --- | --- |
| `AGENTS.md` | low-cost microkernel and risk/memory/claim/tool boundaries | every deployment |
| `skills/embedded-harness/embedded_harness_policy.json` | compiled runtime policy | every scripted or adapter deployment |
| `harness_intake_router.ps1` | deterministic route receipt | PowerShell/Codex direct-script profile |
| `harness_action_consumer.py` | bounded memory context and task-local correction receipt | memory retrieval or full model-loop integration |
| `harness_memory_isolation_gate.ps1` | project-lane path receipt | PowerShell memory reads/writes |
| `harness_external_research_gate.ps1` | external-evidence route receipt | external/current fact routing |
| `harness_claim_schema_verifier.ps1` | claim/evidence-boundary receipt | PowerShell claim validation |

The Bash directory is a reference equivalent for advisory core gates and
requires `bash` plus `jq`. Deploy it only when that target shell is real and
tested.

### B. Behavior-Correction Closure

Deploy this set as one unit; omitting one member invalidates the
profile/hash/verifier chain:

```text
behavior_correction_gate.py
behavior_correction_hook.py
behavior_correction_profiles.json
execution_feedback.py
python_inline_write_analysis.py
embedded_harness_policy.json
```

`behavior_correction_source_map.md` is provenance documentation, not a runtime
dependency. The hook is stateless and nonblocking: one accepted, mechanically
verified current-input rewrite or silent no-op. It does not grant permission,
deny, freeze, write memory, or mutate policy.

### C. Host Adapter Components

| Profile | Required adapter surface | Boundary |
| --- | --- | --- |
| `codex-local-minimal` | root instruction, compiled policy, direct gates, action consumer, correction closure | hook activation still requires the exact installed Codex lifecycle |
| `workbuddy-hook-minimal` | WorkBuddy Python package, wrappers, compiled policy, correction closure | default prompt advisory; PreToolUse disabled until host-protocol verification |
| `workbuddy-loop-integration-sdk` | hook profile plus agent-loop contract, action consumer, compatibility manifest | host consumes every action and returns a complete receipt |

Do not mix adapter claims. A passing WorkBuddy unit test does not prove Codex,
Claude Code, or another host loaded the same lifecycle surface.

### D. Build And Maintenance Files

These maintain or validate a deployment, but are not always runtime files:

```text
embedded_harness_policy.authoring.toml
compile_policy_from_toml.py
validate_policy.ps1
tools/cbh_doctor.py
tests/
integrations/workbuddy-python-runtime/tests/
```

Keep the TOML authoring source and compiler together in a source checkout. The
runtime consumes generated JSON; do not hand-edit both and let them drift.

### E. Documentation / Review Only

These explain, reproduce, cite, or review the framework and are excluded from
minimal runtime bundles by default:

```text
README*.md
docs/** (this map must still be read before deployment)
examples/**
paper/**
research/**
CHANGELOG.md
CITATION.cff
NOTICE.md
```

They remain required in a public source release, but copying them into an agent
runtime does not activate capabilities.

## Deployment Procedure

1. Inspect the exact host version and its real instruction, model-loop,
   updated-input, permission, and sandbox surfaces.
2. Run the bundle builder with `--list`; review the resolved file list.
3. Stage one profile into an empty directory and retain
   `cbh-deployment-receipt.json`.
4. Map the root instruction entry and compiled policy.
5. Initialize project/memory roots and lane state from the published templates
   through a deployment-local overlay.
6. Keep prompt routing advisory unless a real host loop consumes its actions.
7. Enable correction only if the host accepts the declared updated-input
   protocol without bypassing native permission checks.
8. Run the compiler check, validator, doctor, profile tests, and one real
   host-lifecycle smoke test.
9. Record `checked_available`, `checked_missing`, or `checked_blocked` for each
   host capability; do not infer activation from files alone.

## Minimum Acceptance Matrix

| Claim | Required evidence |
| --- | --- |
| instruction active | a fresh task demonstrates that the root microkernel loaded |
| router active | route receipt from the deployed path |
| memory retrieval active | selected record with lane, source, and provenance returned to the model |
| model-loop integration active | complete host-owned action-consumption receipt |
| correction active | known historical regression rewritten, verifier passes, invariants preserved |
| correction fallback active | no-match and forced verifier/module failure both produce silent no-op |
| WorkBuddy PreToolUse active | exact target version confirms rewrite plus native permission semantics |
| client compatibility current | checks rerun after client or hook-configuration changes |

If any row lacks evidence, downgrade it to advisory, reference-only, or
unverified. Do not silently remove required components to make a smaller
bundle; update a named deployment profile and its tests instead.
