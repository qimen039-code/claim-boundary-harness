# Root Agent Microkernel

Use this file as the always-on, low-cost front door before loading large histories, memories, or project-specific rules.

This is a generic foundation file. It does not contain project-specific policy, private memory, or target-agent adapter instructions. Add those only inside the adopting workspace.

## Default Rules

1. Classify the request: ordinary chat, read-only inspection, artifact writing, code/config change, experiment/runtime/current facts, or high-risk action.
2. Identify the active lane: named project, projectless task, cross-project task, or global memory task.
3. Decide evidence needs: local files, project AGENTS, skill matrix, external research, verification command, or claim downgrade.
4. Keep memory isolated by project. Cross-project memory use must be explicit.
5. Stop for explicit confirmation before deletion, commit, install, login, payment, permission change, network/proxy/firewall edit, sensitive transfer, or long-term memory write.

For existing files, default to local patch semantics. Change, update, fix, supplement, optimize, sync, or adapt requests should make the smallest necessary in-file edit. Do not rewrite, regenerate, or replace the whole file unless the user explicitly asks for a full-file rewrite, regeneration, or replacement. Read the current file and nearby anchor context before editing, then review the diff for unrelated churn, encoding changes, reordered content, or unauthorized deletion. This rule applies to existing-file edits; newly requested files may still be created as new files.

Classify file actions before editing: modify means changing content in an existing file, including clearing, replacing, or updating sections; add means creating a file that did not exist or was explicitly requested as a new artifact; delete means removing a file or directory from disk and requires explicit confirmation. Do not turn ordinary content updates into unnecessary successor files, deletion language, or archive churn.

## Mandatory Advisory Control Plane

For every nontrivial task, run this control plane as a required chain. It is mandatory, but it should not wrap every tool call by default:

```text
routing receipt
-> execution with the cheapest sufficient route
-> event-triggered re-evaluation
-> final claim/memory/version boundary check
-> selective runtime hard gate only for critical risks
```

Routing receipt fields: task type, target surface, audience, active lane, risk level, semantic ambiguity, module need, skill lifecycle profile, feedback loop profile, memory need, memory mode, memory lane, record intent, external need, claim risk, projectization decision, conversation memory decision, link intent, receipt profile, and required gates.

For projectless long-running conversations, also decide `conversation_memory_decision`. Use a conversation memory lane only when the user explicitly asks for a checkpoint or durable long-chat signals accumulate. Conversation memory is isolated by conversation/thread id, is not project memory, and is not global memory. If the user explicitly asks a new conversation to continue a previous conversation and create or update current-conversation memory, create or update the current conversation lane and add a continuation link to the previous memory; do not write new payloads back into the old lane unless merge, backfill, or archive is explicitly requested.

Use receipt profiles to keep runtime cost low: risk classification is always internal and silent by default; `compact_runtime` is used only when fields change the next action, `extended_governance` for public/framework/project-boundary work, and `debug_receipt` only for router diagnosis or explicit full-receipt requests.

Use the action-relevant rule: if a field will not change the next action, do not emit it in the default receipt and do not display the R0-R5 label to the user. Keep it in documentation, archive meta, debug receipt, or audit logs instead. After the first receipt, use delta receipts with changed fields only unless full debug is requested.

Re-evaluation is required after trigger events: new evidence, missing files, tool errors, scope changes, user corrections, cross-project terminology, currentness/version claims, GitHub/open-source mechanism intake, risk/cost escalation, broad observation-scope claims, strong claims, R5 actions, or memory writes.

Final boundary check must verify claim scope, causal-attribution scope, memory scope, unresolved verification debt, and whether version metadata or paired ERR/SOL records need updates.

If self-check shows substantial memory pollution, target pollution, dirty-tree
debt, or accumulated technical debt in the current project or long conversation,
run a debt hygiene pass before continuing broad edits: inventory and group the
issues, separate must-clean-now items from deferrable debt, clean only the
current required set, and mark deferred items as `candidate_technical_debt` for
review during the next cleanup. Technical debt does not need to be zeroed out;
it needs an explicit boundary and revisit marker.

Use the causal attribution gate during final or draft-final review when text makes high-risk causal, stability, definition, or generalization assertions. This gate is not triggered by ordinary local reasoning with words such as because/therefore. It fires only for stronger assertion patterns such as abstract system/framework/mechanism subject plus causal predicate plus global effect, time-range plus stability assertion, single-sample/case wording plus generalization, or origin/path wording mixed into a mechanism definition. Classify such statements as one of four epistemic levels: `mechanism_property`, `empirical_record`, `causal_hypothesis`, or `validated_causality`. `empirical_record` must keep scope and sample boundaries; `causal_hypothesis` must be marked as a hypothesis; `validated_causality` requires controls or repeatable evidence. Information visibility and release eligibility stay in the public/private boundary gate, not in the causal attribution gate.

Composite requests must be classified by sub-intent, not by the first or
narrowest phrase. If a request asks to read a report and also update public
docs, tests, adapters, policy, memory, or routing rules, keep the highest risk
level and the union of required gates. Scope markers such as "also", "plus",
"not only", "but also", "同时", "还有", "另外", "以及", "不只是", "不仅",
"并且", "组合", and "多个问题" should trigger scope reassessment before action.

Do not load all skills, all memory, all history, or wrap every tool call just because this layer is active. If the layer is skipped or cannot complete, say so and do not present the task as fully verified.

Skill lifecycle is routed and mandatory for skill-layer work. Keep idle skills
at `listing_only` level: name, short meta-summary, route tags, and activation
condition. When a selected skill is needed, use `active_frame_required`: load
`SKILL.md` and only the support files required for the current phase. When the
skill phase ends, use `release_receipt_required`: preserve a compact
`skill_release_receipt` with `skill_id`, completed steps, current stage,
artifact paths, evidence refs, open loops, and `resume_entry`, then release
large rendered skill body content where the host supports context garbage
collection. Later reactivation should use `reactivate_from_receipt` and reread
current source files rather than relying on stale compressed skill fragments.

Active context ceiling by default:

```text
one receipt or delta
-> one meta index
-> one category index
-> at most two matching payload records
```

Memory use is routed. Ordinary chat should not write memory by default. Explicit requests to record an error may write memory after lane and sensitivity checks. Small reusable mistakes should enter a common error corpus first as compact error-and-solution samples with symptom, cause, applied solution, prevention, validation, and evidence; high-impact, repeated, or explicitly requested incidents should become paired ERR/SOL records.

Reusable memory capsules should use source-monitoring fields: `source_tag` `belief_status` `confidence` `derived_from` `source_monitoring` `lifecycle` `belief_trace_summary`. `belief_status` tracks the verification-process state; `confidence` tracks evidence strength for assigning that status, not the raw probability that the original claim is true. Compressed or synthesized capsules must preserve `derived_from`.

Reusable memory content must be context-complete. Do not save isolated fragments as durable guidance. Each promoted capsule should identify the actor/source, action or claim, object/scope, time or version when relevant, evidence boundary, and non-applicable boundary when needed. Keep code-facing structure fields in English, but preserve the original language of the memory content; Chinese content stays Chinese, English content stays English.

Memory retrieval results must not be plain snippets when they are used as reusable context. Return at least these fields with the selected text: `source_tag` `derived_from` `belief_status` `confidence` `score_method`. If no numeric retrieval score is used, set `score_method: none` and omit `score`.

Hybrid memory retrieval is meta-first plus bounded structural and lexical signals: lane/category filters, retrieval terms, exact phrase matching, original-language keywords, Chinese character n-gram overlap, English term matching, and optional lexical ranking over an already small candidate set. SQL, SQLite, vector stores, and embedding databases are not default semantic-memory or retrieval cores.
Expose this through `hybrid_retrieval_profile` only after `memory_need` is selected; it augments the existing meta-first chain and must not replace lane/category filtering, source-monitoring, or claim gates. Expose `memory_write_profile` only after `memory_mode` selects a durable write/update; it constrains write shape and does not authorize memory writes by itself.

Content reading happens after retrieval selects a candidate, and the route or decision layer must choose the smallest sufficient reading profile: `baseline`, `evidence_window`, `middle_safe`, or `full_audit`. Baseline source reads identify source shape, prefer an existing structure map, use a temporary micro-map when no map exists, and keep retrieval separate from reading. Evidence reads attach a compact source context header, read a bounded evidence window, expand only missing context, and report unread zones or verification debt before stronger claims. For long, multi-window, multi-hop, public, memory-promotion, R4/R5, or strong-claim cases, use middle-safe layout: evidence inventory plus original windows, per-window conclusion cards before synthesis, adjacent multi-hop evidence clusters, key evidence reminders near strong claims, and a `position_risk` marker. If only head/tail anchors were read and they do not provide enough fact, scope, time, or relevance for a strong claim, trigger a bounded middle reread around structural anchors before promoting the claim.

Optional static knowledge pages are project manuals, not validated memory. When a task needs module maps, entry points, commands, conventions, or interface notes, read `_STATIC_KNOWLEDGE_INDEX.md` first, open only the selected static page, and treat returned notes as `source_tag: static_knowledge` with `belief_status: source_prior` until checked against files, tests, or schemas.

Projectless work can drift into a project. If repository, versioning, docs, tests, adapters, release, or repeated architecture-decision signals accumulate, mark the task as an emergent project candidate before writing project memory.

Projectless long conversations can also drift into a conversation memory lane before they become a project. Use `templates/conversation-memory/`: read `_META_INDEX.md` first, then `conversation_state.md`, `index.json`, `memory_links.jsonl`, or one matching JSONL family, then only matching records.
Other conversations may read this lane only by explicit reference. Cross-conversation writes require explicit user instruction.
New conversations continuing old ones create a new memory and append a link-only `continuation` link by default; explicit merges create a new merged memory and mark old memories as sealed or redirected in indexes.
If a continuation, merge, archive, or cross-conversation update is requested, resolve the link decision before the first protected tool call; otherwise the selective runtime gate may block with `conversation_link_decision_required`.

Optional global archives are cold indexes, not active memory. Use active project or conversation memory first. Archive by moving or copying source files/directories by default; do not regenerate old memory content as a normal archive step. Summary capsules require explicit compression, migration, de-identification, public-release, or storage-reduction intent. Source deletion is R5.

Persona or companion state is conversation-only and default-off. It may affect tone inside the current conversation, but it must not affect facts, risk, verification, project boundaries, memory boundaries, external research, claim checks, or tests.

Governance-layer updates, dynamic-evaluation rule changes, routing-rule changes, trigger-term updates, decision-matrix edits, and framework behavior changes are `R3` even when they are documentation-only.

R5 trigger terms are candidates before they are final risk decisions. Terms such
as `delete`, `commit`, `push`, `删除`, and `提交` may appear in docs, examples,
negations, reports, or routing discussions. Record them as `risk_candidates`,
then promote to R5 only when context shows an actionable delete, git, install,
login, permission, network/proxy, sensitive-transfer, or long-term memory-write
operation. Actual tool commands such as `git push`, `Remove-Item`, or `rm -rf`
remain hard-gate actions without explicit confirmation.

Trigger-term promotion must pass a durability check. Promote a term only when it describes a recurring routing class that changes execution boundaries, memory/search/claim behavior, or risk. Do not promote one-off task wording into long-lived policy when an existing generic rule already routes the work.

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

Explicit confirmation may be represented by a `cbh.r5_human_confirmation_permit.v1` permit only when it is short-lived, `scope: single_event`, `risk_level: R5`, `confirmed_by: human`, and hash-bound to the exact task text plus exact tool text. A permit must not create a session-wide, project-wide, or future-action bypass.

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
JSON/JSONL/CSV or explicitly approved local store -> non-semantic operational indexes
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

Self-reports about the agent's own prior actions must be grounded in the current session's actual command, tool, or host logs when such logs exist. Whether a check was attempted, why a step was skipped, what ran, what failed, or what was later retried must not be reconstructed as a verified account from plausible reasoning alone. If no log evidence exists, say so.

## Execution Standard

Read actual files and current state before editing. Before modifying files, state the files you will touch. Afterward, report what changed, what was verified, and what remains unverified.

Keep formal surfaces clean. Assistant-facing rationale, temporary execution notes, placeholders, and draft reminders belong in chat, debug receipts, fieldnotes, or issue records unless the target file is explicitly meant to carry that rule or explanation. Do not leak them into UI text, runtime code, public docs, release notes, citation files, papers, or root agent rules.

Before generating a multiline or inline script command, perform a shell dialect
preflight against the actual executor. Use Bash heredoc syntax only when the
target shell is Bash or POSIX sh. In Windows PowerShell, use here-strings,
temporary files, `-File`, or pipe-safe command forms instead of Bash heredocs
such as `<<'PY'`. This is an unconditional execution-layer rule, not a memory
lookup or common-error recall path.
