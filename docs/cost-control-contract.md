# Cost Control Contract

The framework should keep complete governance internally without making every turn expensive.

The rule is:

```text
complete internal contract
-> silent risk classification by default
-> smallest useful receipt only when behavior changes
-> event-triggered expansion
-> changed fields only after the first receipt
```

## Routing Field Budget

Use fields only when they can change the next action.

| Situation | Default receipt | Rule |
| --- | --- | --- |
| R0 ordinary chat | no explicit receipt | Use the microkernel only; do not display the risk label. |
| R1/R2 local work | usually implicit | Keep classification internal unless local files, claim boundaries, memory, external lookup, or another gate changes the path. |
| R3/R4 work | compact plus triggered fields | Show only the reason that changes execution path, cost, search, verification, memory, or claim behavior. |
| R5, public docs, adapter, memory write, archive, persona, or cross-boundary work | `extended_governance` | Include boundary fields and required gates. |
| Router debugging or audits | `debug_receipt` | Include trigger evidence and full diagnostics. |

Do not put a field in the default receipt only because it exists in the full contract.

## Visibility Rule

R0-R5 classification is always performed internally, but it is silent by default in user-facing replies and prompt-stage hook context.

Expose the smallest necessary explanation only when the classification changes one of these:

- execution path or required gate;
- cost or context expansion;
- permission or human confirmation;
- skill activation, release, or reactivation behavior;
- memory read/write/link/merge/archive behavior;
- hybrid retrieval or memory write granularity profile;
- external search or current-fact verification;
- claim schema or evidence boundary.

When the user asks for debug, audit, route diagnosis, or a full receipt, expose the complete `debug_receipt`. Diagnostic CLI scripts may still print full receipts because their purpose is inspection, not ordinary conversation.

## Action-Relevant Rule

Before adding or emitting a field, ask:

```text
Will this field change the agent's next action?
```

If the answer is no, keep it in one of these places instead:

- documentation;
- archive meta index;
- debug receipt;
- audit log;
- not emitted.

Examples:

| Field type | Default handling |
| --- | --- |
| Risk, required gates, human confirmation | Compact receipt. |
| Memory mode and lane | Compact receipt when memory is involved. |
| Full trigger evidence | Debug receipt. |
| Archive operation provenance | Archive index only. |
| Persona/tone state | Conversation-only file, not work receipt. |
| Historical payload summary | Meta index, not active prompt context. |

## Delta Receipt

For long tasks, do not repeat the full receipt after every tool call.

Use:

```text
initial receipt
-> event trigger
-> delta receipt with changed fields only
-> final boundary review
```

Recommended delta shape:

```json
{
  "event": "tool_error",
  "changed_fields": {
    "risk_level": "R3 -> R4",
    "required_gates_added": ["verification_gate"]
  },
  "reason": "local runtime failure changed the evidence need"
}
```

Use a delta receipt when:

- a tool fails;
- scope changes;
- the user corrects the task;
- currentness or external evidence becomes necessary;
- memory write, archive, persona, or cross-lane behavior appears;
- an R5 action is about to happen.

## Active Context Ceiling

Default active context should contain:

```text
root microkernel
-> current receipt or delta
-> one selected meta index
-> at most one category index
-> at most two matching payload records
```

Broader scans require an explicit audit, migration, cleanup, or debug reason.

## Skill Lifecycle Budget

Skill lifecycle control follows the same budget rule:

```text
skill listing / meta-summary
-> selected active frame
-> only needed SKILL.md sections and support files
-> compact skill_release_receipt
-> release large body when the host supports context GC
-> reactivate by rereading current source files
```

For one-shot skill work, release after the skill phase ends. For tight loops,
keep the active frame until the loop closes, then release once. For ordinary
discussion after a skill task, retain only the receipt. This keeps long
contexts from carrying stale rendered skill bodies while preserving recovery
state and auditability.

Hybrid retrieval does not add a new broad scan by itself. It may only run after
the selected meta/index layer has bounded the lane and category. The profile
changes the matching channels inside that bounded set; it does not authorize
opening all memory payloads.

Memory write granularity also should not increase ordinary-token cost. It is
checked only when `memory_mode` is `write` or `update`, and it rejects short
orphan fragments instead of expanding the route into full-history rewriting.

## Reading Profile Budget

Content reading should use the smallest profile that can support the next
action:

| Profile | Use when | Default budget |
| --- | --- | --- |
| `baseline` | Any nontrivial selected source read. | Source shape, existing map or micro-map, native reading unit, and retrieval/reading boundary only. |
| `evidence_window` | The opened source supports or limits a claim, patch, memory, report, or decision. | One bounded evidence window plus targeted expansion for missing context. |
| `middle_safe` | Long source, multiple windows, multi-hop evidence, public-facing claim, memory promotion, release note, R4/R5 decision, or strong final claim. | Evidence inventory, original-window anchors, per-window conclusion cards, adjacent evidence clusters, key-evidence reminder, and position-risk marker. |
| `full_audit` | Explicit full audit, migration, cleanup, backfill, or exhaustive verification. | Broader reading is allowed, but source headers, skipped-zone notes, and claim limits still apply. |

Do not enable `middle_safe` or `full_audit` merely because the source is
interesting. They are escalation profiles selected by the route or decision
layer.

## Non-Goals

Cost control does not remove governance. It decides when governance is active, visible, or archived.

Do not reduce cost by skipping:

- R5 confirmation;
- meta-first memory lookup;
- claim boundaries for strong claims;
- external research for current or drift-prone facts;
- project/conversation/global memory isolation.
