# Skill Lifecycle Contract

Skill files should behave like routed working sets, not permanent context
furniture. The framework keeps idle skills cheap, activates only the selected
skill body and support files, then releases large skill text after the skill
phase ends while preserving a compact receipt for audit and reactivation.

This contract is mandatory for skill-layer work in adopting runtimes. It is a
context-management contract, not a promise that every host can physically delete
previous conversation messages. If the host supports context garbage collection,
release the large rendered skill body. If it does not, write the receipt and use
it as the compaction and reactivation anchor.

## Profiles

The router or dynamic decision layer exposes `skill_lifecycle_profile`:

| Profile | Use when | Required behavior |
| --- | --- | --- |
| `none` | No skill-layer work is selected. | Do not load skill bodies. |
| `listing_only` | The task only needs discovery, routing, or capability selection. | Use skill name, short description, meta-summary, route tags, and activation condition only. |
| `active_frame_required` | A selected skill must guide the current work. | Load `SKILL.md` and only the referenced files needed for the current step. |
| `release_receipt_required` | A skill phase has ended, the task shifts away from that skill, or token pressure/compaction risk appears. | Replace the large skill body with a compact `skill_release_receipt` where the host supports it; otherwise write the receipt for compression and future turns. |
| `reactivate_from_receipt` | A later turn needs the skill again after release or compaction. | Use `skill_id` and `resume_entry` to reload the current source files, not stale compressed fragments. |

This is a lifecycle profile. It does not authorize tool calls, memory writes, or
claim promotion by itself.

## Required Receipt

Every released skill phase should leave a compact receipt:

```json
{
  "schema": "cbh.skill_release_receipt.v1",
  "skill_id": "embedded-harness",
  "skill_version_or_hash": "optional-source-hash",
  "status": "released",
  "completed_steps": [
    "route classified",
    "policy validated"
  ],
  "current_stage": "release verification",
  "artifact_paths": [
    "docs/report.md",
    "test-output.json"
  ],
  "evidence_refs": [
    "pytest:94 passed",
    "gh_run:28273659275"
  ],
  "open_loops": [
    "Bash local surface not verified on this Windows host"
  ],
  "resume_entry": "Read SKILL.md routing section, then docs/router-decision-contract.md if route fields are involved.",
  "last_used_at": "2026-06-27T09:30:00+08:00",
  "ttl_policy": "release after phase ends unless the next turn needs the same skill"
}
```

Required fields:

- `skill_id`
- `status`
- `completed_steps`
- `current_stage`
- `artifact_paths`
- `evidence_refs`
- `open_loops`
- `resume_entry`
- `last_used_at`
- `ttl_policy`

`resume_entry` must be actionable. Avoid vague text such as "continue the
previous skill." Say which source file, section, command, artifact, or evidence
window should be reopened.

## Lifecycle Order

```text
skill name / meta-summary / activation tags
-> route selects skill_lifecycle_profile
-> active frame loads SKILL.md and selected support files
-> execute bounded skill phase
-> write skill_release_receipt
-> release large rendered skill body when host supports context GC
-> reactivate from receipt by rereading current source files
```

The receipt is not a fact source. It is a navigation and recovery surface. Facts
still come from files, tests, tool outputs, evidence refs, or memory capsules
with source-monitoring fields.

## TTL Rules

Use the smallest active window that preserves correctness:

| Situation | Recommended TTL |
| --- | --- |
| One-shot skill task completed | Release immediately after final boundary review. |
| Multi-step task continues in the next turn | Keep active until the current phase closes. |
| User shifts to ordinary discussion | Release and retain only the receipt. |
| Token pressure, compaction, or long-context drift appears | Release non-current skills first. |
| The same skill is likely needed repeatedly in a tight loop | Keep active until the loop ends, then release once. |

Do not release a skill before writing the receipt if the skill influenced a
tool call, file edit, memory write, route decision, or claim boundary.

## Non-Goals

This contract does not introduce:

- GUI or exe packaging as a token-saving strategy;
- automatic self-rewriting of skills;
- deletion of audit evidence;
- cross-skill memory pooling;
- reliance on compressed skill fragments as the long-term authority.

The core improvement is not making a skill disappear. It is replacing large,
stale, rendered skill text with a small, auditable, reactivation-ready receipt.
