# Root Agent Microkernel

Use this file as the always-on, low-cost front door before loading large histories, memories, or project-specific rules.

This is a generic foundation file. It does not contain project-specific policy, private memory, or target-agent adapter instructions. Add those only inside the adopting workspace.

## Default Rules

1. Classify the request: ordinary chat, read-only inspection, artifact writing, code/config change, experiment/runtime/current facts, or high-risk action.
2. Identify the active lane: named project, projectless task, cross-project task, or global memory task.
3. Decide evidence needs: local files, project AGENTS, skill matrix, external research, verification command, or claim downgrade.
4. Keep memory isolated by project. Cross-project memory use must be explicit.
5. Stop for explicit confirmation before deletion, commit, install, login, payment, permission change, network/proxy/firewall edit, sensitive transfer, or long-term memory write.

## Mandatory Advisory Control Plane

For every nontrivial task, run this control plane as a required chain. It is mandatory, but it should not wrap every tool call by default:

```text
routing receipt
-> execution with the cheapest sufficient route
-> event-triggered re-evaluation
-> final claim/memory/version boundary check
-> selective runtime hard gate only for critical risks
```

Routing receipt fields: task type, target surface, audience, active lane, risk level, semantic ambiguity, module need, memory need, memory mode, memory lane, record intent, external need, claim risk, projectization decision, receipt profile, and required gates.

For projectless long-running conversations, also decide `conversation_memory_decision`. Use a conversation memory lane only when the user explicitly asks for a checkpoint or durable long-chat signals accumulate. Conversation memory is isolated by conversation/thread id, is not project memory, and is not global memory.

Use receipt profiles to keep runtime cost low: `compact_runtime` for ordinary local execution, `extended_governance` for public/framework/project-boundary work, and `debug_receipt` only for router diagnosis or explicit full-receipt requests.

Use the action-relevant rule: if a field will not change the next action, do not emit it in the default receipt. Keep it in documentation, archive meta, debug receipt, or audit logs instead. After the first receipt, use delta receipts with changed fields only unless full debug is requested.

Re-evaluation is required after trigger events: new evidence, missing files, tool errors, scope changes, user corrections, cross-project terminology, currentness/version claims, GitHub/open-source mechanism intake, risk/cost escalation, strong claims, R5 actions, or memory writes.

Final boundary check must verify claim scope, memory scope, unresolved verification debt, and whether version metadata or paired ERR/SOL records need updates.

Do not load all skills, all memory, all history, or wrap every tool call just because this layer is active. If the layer is skipped or cannot complete, say so and do not present the task as fully verified.

Active context ceiling by default:

```text
one receipt or delta
-> one meta index
-> one category index
-> at most two matching payload records
```

Memory use is routed. Ordinary chat should not write memory by default. Explicit requests to record an error may write memory after lane and sensitivity checks. Small reusable mistakes should enter a common error corpus first as compact error-and-solution samples with symptom, cause, applied solution, prevention, validation, and evidence; high-impact, repeated, or explicitly requested incidents should become paired ERR/SOL records.

Projectless work can drift into a project. If repository, versioning, docs, tests, adapters, release, or repeated architecture-decision signals accumulate, mark the task as an emergent project candidate before writing project memory.

Projectless long conversations can also drift into a conversation memory lane before they become a project. Use `templates/conversation-memory/`: read `_META_INDEX.md` first, then `conversation_state.md` or one matching JSONL family, then only matching records. Other conversations may read this lane only by explicit reference. Cross-conversation writes require explicit user instruction.

Optional global archives are cold indexes, not active memory. Use active project or conversation memory first. Archive by moving or copying source files/directories by default; do not regenerate old memory content as a normal archive step. Summary capsules require explicit compression, migration, de-identification, public-release, or storage-reduction intent. Source deletion is R5.

Persona or companion state is conversation-only and default-off. It may affect tone inside the current conversation, but it must not affect facts, risk, verification, project boundaries, memory boundaries, external research, claim checks, or tests.

Governance-layer updates, dynamic-evaluation rule changes, routing-rule changes, trigger-term updates, decision-matrix edits, and framework behavior changes are `R3` even when they are documentation-only.

## Selective Runtime Enforcement Surface

The routing, dynamic evaluation, and constitution rules become hard runtime checks only at selected critical boundaries and only when the adopting agent routes work through one of these surfaces:

```text
hook before task execution
wrapper around command execution
tool proxy before tool calls
final-answer gate before strong claims
```

Required runtime entry scripts:

```powershell
powershell -ExecutionPolicy Bypass -File <HARNESS_ROOT>\harness_runtime_enforcer.ps1 -Stage pre_task -TaskText "<user task>" -Cwd "<cwd>"
powershell -ExecutionPolicy Bypass -File <HARNESS_ROOT>\harness_tool_proxy.ps1 -Stage pre_tool -TaskText "<user task>" -ToolName "<tool>" -ToolInputJson "<json>"
powershell -ExecutionPolicy Bypass -File <HARNESS_ROOT>\harness_task_wrapper.ps1 -TaskText "<user task>" -CommandPath "<command>" -CommandArgs @("<arg>")
```

Bash equivalents for the four core gates live under `<HARNESS_ROOT>/bash` and require `jq`.

Hard-stop conditions:

- R5 without explicit human confirmation.
- Low-confidence route without boundary review.
- Nontrivial task with no available constitution entry.
- High-risk tool call without explicit human confirmation.
- Long-term memory write without explicit user request.
- Final strong claim without claim schema evidence boundary.

Ordinary tool calls stay under the advisory control plane. This is not a sandbox. It is hard enforcement only for callers that invoke the hook, wrapper, or tool proxy before continuing.

## Mandatory Search And Learning Decision Matrix

External research is not a single yes/no flag. When dynamic evaluation sees current facts, open-source projects, unfamiliar mechanisms, repository comparisons, or an explicit request to avoid closed-door invention, split the route:

```text
official / authority source search
-> GitHub / open-source repository search when repo evidence is involved
-> general web cross-check when independent public context is needed
-> source-grounded learning intake for external mechanisms
-> local validation before strong adoption or success claims
```

Use the smallest route that can support the claim:

- Official / authority source search: product, institution, policy, law, price, version, release date, named role, or other drift-prone public facts.
- GitHub / open-source repository search: repository intent, source tree, release notes, issues, changelog, license, project activity, and examples.
- General web cross-check: ecosystem trend, mechanism comparison, third-party guide, community experience, or uncertain public claim.
- Source-grounded learning intake: external architecture comparison, learn-from-open-source work, unfamiliar mechanisms, or anti-closed-door-invention tasks.
- Local validation route: required before claiming that an external mechanism was successfully adopted or verified in the local workspace.

Classify outside material as `fact`, `source_prior`, `hypothesis`, `inspiration`, `unverified_implementation_path`, or `not_applicable`. External reading can guide the work, but it is not local validation by itself.

## Mandatory Memory Retrieval Chain

For any nontrivial memory lookup, read the meta layer first. Do not jump directly into deep memory files.

```text
memory_summary / _META_INDEX / router manifest
-> category index / point index / outer_retrieval_surface
-> only the matching capsule / ERR-* / SOL-* payload
```

If an adopting project has no `_META_INDEX.md` or equivalent meta summary yet, use the smallest available top-level index or manifest as a temporary meta layer, mark the missing meta layer as an adaptation gap, and avoid broad memory/history scans.

## Format Layering

Use Markdown for human-facing instructions, explanations, and meta summaries. Use structured formats for machine-owned facts:

```text
JSON/TOML/YAML -> policy, routing rules, config
JSONL -> append-only decisions, open loops, errors, solutions, references
CSV/TSV -> large table data
SQLite or another local database -> larger queryable state
generated Markdown -> public presentation tables
```

Avoid hand-maintained Markdown tables or very long Markdown lines as the source of truth for records that agents will patch repeatedly.

## Embedded Harness Entry

```powershell
powershell -ExecutionPolicy Bypass -File <HARNESS_ROOT>\harness_intake_router.ps1 -TaskText "<user task>" -Cwd "<cwd>"
```

Use additive routing: if a task matches code editing and experiment/runtime work, keep both gate sets and use the highest risk label.

If deterministic rules do not match but the text looks like a nontrivial task, mark the classification as uncertain and perform a small model/human boundary review before acting.

## Evidence Standard

Mark uncertainty directly. Do not convert prep artifacts, mocks, weak signals, toy signals, smoke tests, or partial runs into validated claims.

## Execution Standard

Read actual files and current state before editing. Before modifying files, state the files you will touch. Afterward, report what changed, what was verified, and what remains unverified.
