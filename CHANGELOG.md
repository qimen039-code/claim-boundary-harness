# Changelog

All notable public changes should be recorded here.

This project uses `vMAJOR.MINOR.PATCH` version labels while the framework is still early-stage.

## v0.14.9 - 2026-06-21

- Added a temporary Claude Code deployment boundary note: the public package has not yet completed a full Claude Code client deployment validation.
- Pointed Claude Code adopters to the deployment problem examples, troubleshooting runbook, and compatibility manifest when local instruction, hook, wrapper, or denial behavior differs from the reference example.
- Fixed remaining PowerShell policy readers to use explicit UTF-8 decoding so non-ASCII trigger text does not break policy parsing in Windows PowerShell.
- Updated the compatibility manifest template harness version and removed a stale README note that referenced an older receipt-profile smoke-test version.
- Wrapped several fragile long Markdown lines in public docs without changing behavior.

## v0.14.8 - 2026-06-21

- Revised the public design note with clearer engineering tradeoffs, boundary language, and reproduction limits.

## v0.14.7 - 2026-06-21

- Added a public design note for Claim Boundary Harness, covering claim boundaries, meta-first routing, project-scoped memory lanes, receipt-based risk routing, runtime enforcement limits, SkillOpt-style default-off boundaries, deployment pitfalls, and reproduction scope.
- Linked the article from the README documentation index so readers can open a technical explanation rather than only the project homepage.

## v0.14.6 - 2026-06-21

- Clarified the SkillOpt-style training layer activation boundary: it is default-off for ordinary work and should be used only for recurring skill/router improvements, candidate rule edits, rejected-edit review, slow updates, or external skill-optimization intake.
- Added explicit non-use cases so ordinary chat, one-off fixes, memory writes, external fact checks, runtime enforcement, and claim gating do not accidentally route through the optimizer layer.

## v0.14.5 - 2026-06-21

- Renamed the public framework identity to Claim Boundary Harness so the repository name, README headline, and claim-boundary terminology use one consistent concept.
- Refined the public positioning around claim verification, meta-first routing, project-scoped memory lanes, R0-R5 risk receipts, and deployment adapters.
- Prepared the GitHub repository metadata for a shorter, less crowded name and a focused topic set without near-duplicate discovery keywords.

## v0.14.4 - 2026-06-21

- Added concrete deployment problem examples and solution playbooks for instruction loading, hook denial, prompt-state transfer, file-tool false positives, external search, conversation linking, final-claim gating, encoding/recording payloads, PowerShell policy parsing, and client-update drift.
- Updated the README deployment docs pointer to highlight the new agent-facing solution playbooks.

## v0.14.3 - 2026-06-21

- Added `link_intent` to router receipts and adapter contracts for continuation, referenced-conversation lookup, explicit merge, archive, and cross-conversation memory updates.
- Added a conversation-link gate: pre-action runtimes can block with `conversation_link_decision_required` until meta-first lookup and link selection are resolved.
- Updated PowerShell wrapper/proxy/runtime scripts and the WorkBuddy Python adapter so unresolved conversation-link decisions are enforceable on covered execution paths.
- Updated PowerShell policy readers to use explicit UTF-8 decoding so Chinese trigger/config text does not break `ConvertFrom-Json` in Windows PowerShell.
- Clarified that these changes apply to Codex-style local harness installs and other agent runtimes, not only WorkBuddy-style deployments.
- Tightened memory-linking docs with lane-scoped latest lookup, link-depth threshold, append-only link ledger schema, merge redirect semantics, and advisory fallback when no pre-action hook exists.

## v0.14.2 - 2026-06-21

- Added the silent-by-default R0-R5 visibility rule: classification always runs internally, but user-facing replies and prompt-stage hook context expose only action-changing boundaries unless debug/audit is requested.
- Updated the WorkBuddy Python prompt hook to suppress ordinary low-risk route context, emit minimal boundary context only when needed, and expose full route data only for debug receipts.
- Added a memory linking contract for stable memory IDs, `updated_at` timestamps, link-only conversation continuation, explicit merged memories, append-only link ledgers, and index-first fuzzy retrieval.
- Updated conversation memory and global archive templates with `memory_id`, `updated_at`, retrieval terms, semantic anchors, `memory_links.jsonl`, and cold `conversation_index.jsonl` shapes.
- Extended memory routing and meta-index contracts with `link_intent`, continuation/merge/archive edges, timestamp lookup, and path-light registry boundaries.
## v0.14.1 - 2026-06-21

- Hardened the WorkBuddy Python hook runner with bounded nested text extraction so host-provided recording transcripts can be routed while raw media blobs, bytes, base64 strings, and arbitrary recording files remain ignored.
- Added Stop/final hook enforcement to the WorkBuddy hook runner so strong final validation claims can be blocked when final text is available before display.
- Narrowed command-risk scanning to command-capable tools and command fields, reducing false positives when Write/Edit payloads merely contain high-risk words as documentation text.
- Added UTF-8 defaults to the WorkBuddy Bash and `cmd.exe` hook wrappers for Windows Git Bash and mixed-shell non-ASCII prompt handling.
- Expanded WorkBuddy and generic deployment guidance with command-tool matcher recommendations, transcript payload checks, final-answer hook checks, nested-JSON/claim-file handoff advice, and new acceptance tests.

## v0.14.0 - 2026-06-18

- Added a lightweight declarative governance contract for adapter stage support, decision vocabulary, denial semantics, payload safety, and cost boundaries.
- Added a version compatibility management guide for runtime/client version drift, hook schema drift, wrapper-path drift, tested denial behavior, bypass surfaces, and opt-in repair boundaries.
- Added compact JSON templates for `governance.contract.json` and `compatibility.manifest.json` under `templates/adapter-contract/`.
- Added a lightweight GitHub Actions smoke workflow that runs representative reproduction checks and the WorkBuddy Python adapter tests on push, pull request, or manual dispatch.
- Documented the leverage-first improvement rule: absorb external mechanisms only when they reduce ambiguity, improve adapter verification, or close a real deployment gap without increasing ordinary-task cost.
- Linked the new contract and manifest into the architecture, adoption guide, deployment risk guide, and README.

## v0.13.1 - 2026-06-18

- Fixed the WorkBuddy Python hook runner so stdin JSON containing lone UTF-16 surrogate escapes is sanitized before routing, state writes, log writes, or hook output.
- Made hook output ASCII-escaped and added surrogate-safe JSONL event logging to prevent malformed host payload text from disabling `UserPromptSubmit` active routing.
- Added a Windows `cmd.exe` hook wrapper for WorkBuddy deployments where `bash` is not available on PATH.
- Added regression tests for surrogate-safe hook routing and log writes.
- Expanded WorkBuddy deployment guidance and the generic deployment-risk runbook with prompt-stage active routing and malformed hook-payload diagnostics.

## v0.13.0 - 2026-06-18

- Added a public SkillOpt-style training layer that stages skill improvements as candidate edits, validation-gate reports, rejected-edit records, and slow-update proposals without replacing the bounded multi-skill matrix.
- Added SkillOpt source attribution and MIT license boundary notes while keeping the integration as `adapted_rule` rather than vendored code or executable adoption.
- Registered the training layer in the public skill matrix registry and routed SkillOpt-style mechanism absorption through the troubleshooting matrix.

## v0.12.0 - 2026-06-18

- Added Conversation Memory Lane for long-running projectless conversations, with isolated per-conversation memory, explicit cross-conversation write rules, and mandatory meta-first retrieval.
- Added a blank conversation-memory template with `_META_INDEX.md`, human state summary, machine index, and JSONL record families for decisions, open loops, errors/solutions, and references.
- Added a format-layering strategy that separates human-facing Markdown from machine-owned JSON/JSONL/CSV/SQLite-style records to reduce fragile Markdown table and long-line patching.
- Added a cost-control contract with routing field budgets, action-relevant field rules, delta receipts, and active-context ceilings.
- Added archive and persona boundaries: optional global archive stays cold and defaults to move/copy operations, while persona state is conversation-only and cannot affect factual or work decisions.
- Added blank global-memory-archive and conversation-only persona templates.
- Updated router policy and PowerShell, Bash, and Python intake adapters to emit `conversation_memory_decision`, `current_conversation` lane routing, and conversation checkpoint signals.
- Added WorkBuddy Python adapter regression tests for explicit conversation memory, checkpoint candidates, ordinary chat skip behavior, and projectization precedence.

## v0.11.1 - 2026-06-18

- Added a deployment risk-pattern guide that generalizes the WorkBuddy hook issue into reusable failure modes and fixes for instruction-file agents, CLI hook agents, IDE agents, custom orchestrators, hosted agents, and wrapper-only setups.
- Added an agent-facing troubleshooting runbook that tells adopters what to inspect, where to inspect it, what result to expect, and how to localize failures across instruction loading, direct gate execution, hook shell setup, hook payloads, host block semantics, bypass paths, memory/search/final-claim surfaces, and client drift.
- Added a mainstream agent deployment checklist and minimal acceptance tests for instruction loading, pre-tool hard blocking, bypass surfaces, memory isolation, current-fact routing, final-claim checks, and client-update drift.
- Clarified in the public README and adoption guide that hard enforcement is path-specific: a gate blocks only the execution path that invokes it and honors the blocked result.

## v0.11.0 - 2026-06-18

- Added a WorkBuddy hook runner that reads WorkBuddy/CodeBuddy hook JSON from stdin, stores the original prompt at `UserPromptSubmit`, and calls the runtime enforcer at `PreToolUse`.
- Added a Bash-compatible WorkBuddy hook wrapper so command-hook environments can call the Python adapter without patching the installed WorkBuddy application.
- Documented the WorkBuddy enforcement boundary: a hook-wired `PreToolUse` path can hard-block with `permissionDecision: deny` and exit code `2`, while any host path that bypasses the hook remains advisory.
- Added WorkBuddy hook deployment guidance, setup checks, and regression tests for prompt-state capture, high-risk tool denial, and low-risk tool pass-through.

## v0.10.2 - 2026-06-18

- Fixed WorkBuddy Python adapter logging so `log_dir` writes to `workbuddy_harness_events.jsonl` inside the directory instead of treating the directory itself as a file.
- Added `original_task_text` and explicit `risk_level` handling to keep pre-tool enforcement from losing the original task evidence after a compact pre-task receipt.
- Expanded WorkBuddy hard-tool detection to include Unix `rm -rf` / `rm -fr` style destructive commands.
- Added regression tests for the three WorkBuddy deployment defects.

## v0.10.1 - 2026-06-18

- Reworked the README opening around the concrete failure mode of weak evidence being overstated as validated.
- Added a compact Mermaid architecture diagram near the top of the README so adopters can see the routing, memory, search, claim, and selective hard-gate flow quickly.
- Prepared repository discoverability metadata through focused GitHub topics.

## v0.10.0 - 2026-06-18

- Added receipt profiles so the router can compute the full governance decision internally while exposing a compact runtime receipt by default.
- Added `compact_runtime`, `extended_governance`, and `debug_receipt` profile semantics to policy and adapters.
- Updated PowerShell, Bash reference, and WorkBuddy Python intake routers to emit `receipt_profile`, `compact_receipt`, and `profile_reason`.
- Added WorkBuddy Python tests for compact local R5 receipts, public governance expansion, and debug receipt routing.
- Grounded the change in lightweight external patterns: policy-decision separation, admission-style hard stops, telemetry-style sampling, and lifecycle middleware hooks.

## v0.9.2 - 2026-06-18

- Restored stricter R5 English trigger coverage for ordinary `delete`, `remove`, `commit`, `push`, and related high-risk wording.
- Added `-FinalText` support to the PowerShell runtime enforcer so final-answer hard gates can scan the actual response text for strong claim phrases.
- Fixed PowerShell routing receipt array handling so a single semantic ambiguity term does not merge with `governance_or_change_surface`.
- Re-verified that active and public policies still retain mandatory advisory control-plane, selective hard runtime gates, external research gate, claim gate, and meta-first memory retrieval rules.

## v0.9.1 - 2026-06-18

- Clarified that common error corpus records are error-and-solution samples, not error-only notes.
- Added `solution_applied` and `validation` to the CE record shape in docs, templates, and harness policy.
- Updated public templates so lightweight CE records preserve the applied fix before escalation to paired ERR/SOL records.

## v0.9.0 - 2026-06-18

- Added a memory routing contract for `memory_mode`, `memory_lane`, `record_intent`, and `projectization_decision`.
- Added projectization drift detection for projectless conversations that accumulate durable project signals.
- Added a common error corpus template for lightweight CE records before escalation to paired ERR/SOL records.
- Updated intake adapters to emit the new memory routing fields.

## v0.8.0 - 2026-06-18

- Added a router decision contract for target surface, audience, semantic ambiguity, module selection, memory route, external route, claim risk, and required gates.
- Added a memory meta index contract with multi-axis index fields, default retrieval budgets, missing-meta behavior, and category row shape.
- Grounded the router and decision-layer update in lightweight policy-decision, admission-control, router, sensemaking, failure-mode, and responsibility-boundary patterns without adding heavy runtime overhead.
- Updated PowerShell, Bash, and WorkBuddy Python intake adapters for the new receipt fields; PowerShell and Python were smoke-tested locally, while Bash parity was edited but not executed in this update because Bash was not available on the current PATH.

## v0.7.1 - 2026-06-18

- Cleaned non-user-facing process details from public README and AGENTS content while keeping public version metadata visible.

## v0.7.0 - 2026-06-18

- Published the WorkBuddy-oriented Python runtime adapter under `integrations/workbuddy-python-runtime`.
- Clarified that PowerShell, Bash, and WorkBuddy Python adapters are early reference adapters, not complete cross-device, cross-version, or production-loop validation claims.
- Added local unit-test coverage for the WorkBuddy Python decision layer while keeping hard WorkBuddy loop integration as an adopter responsibility.

## v0.6.1 - 2026-06-18

- Tightened the Codex field-use wording to describe early private use in one Codex-based project workflow, not broad multi-project or multi-agent validation.
- Clarified that the advisory control plane is caller-honored by default and becomes blocking only on execution paths that actually invoke the hook, wrapper, or tool-proxy gates.

## v0.6.0 - 2026-06-17

- Fixed memory isolation path-prefix handling so a sibling path such as `project-evil` does not pass as `project`.
- Added reparse-point aware path resolution checks for the PowerShell memory isolation gate.
- Split trigger rules into `en` and `zh` groups while keeping deterministic matching across both groups.
- Added English trigger word-boundary checks and simple negation handling so phrases such as `do not delete` do not directly count as high-risk action requests.
- Added Bash counterparts for the four core gates under `skills/embedded-harness/bash`; Bash scripts require `jq`.
- Added lightweight PowerShell and Bash policy validators.
- Added Codex and Claude Code integration examples, exit-code/status documentation, and explicit non-goals.

## v0.5.0 - 2026-06-17

- Added the mandatory advisory control plane between the root microkernel and selective runtime hard gates.
- Reframed dynamic evaluation as lightweight routing receipts plus event-triggered re-evaluation, not continuous tool-call wrapping.
- Clarified that runtime hard enforcement should stay selective: R5, high-risk tools, low-confidence boundaries, long-term memory writes, and final strong claims.
- Narrowed external architecture search triggers so local architecture maintenance does not automatically require external research.

## v0.4.0 - 2026-06-17

- Added hook/wrapper/tool-proxy runtime enforcement entry scripts.
- Added hard-stop conditions for R5 without confirmation, low-confidence routes without boundary review, missing constitution entry, high-risk tool calls, and strong final claims without claim schema.
- Clarified that runtime enforcement is hard only when adopting agents call the entry scripts before task, tool, or final-answer execution.

## v0.3.1 - 2026-06-17

- Added narrower R3 trigger terms for governance-layer, dynamic-evaluation, routing-rule, trigger-rule, decision-matrix, and framework-behavior updates.
- Clarified that governance and routing edits are R3 changes even when they are documentation-only.

## v0.3.0 - 2026-06-17

- Added the mandatory search and learning decision matrix to the dynamic evaluation layer.
- Split external research into official-source search, GitHub/open-source repository search, general web cross-check, source-grounded learning intake, and local validation.
- Added classification labels for outside material: fact, source_prior, hypothesis, inspiration, unverified implementation path, not_applicable, and local validation.
- Updated the external research gate to return recommended search modes instead of only a yes/no result.
- Clarified that external reading is not local validation by itself.

## v0.2.0 - 2026-06-17

- Made the dynamic evaluation governance layer mandatory for nontrivial tasks.
- Added the required pre-evaluation, runtime re-evaluation, and final boundary-check checkpoints.
- Added explicit decisions for skill/tool/plugin/search/memory/claim-gate use.
- Added failure boundary language for incomplete dynamic evaluation.
- Kept the cost rule: use the cheapest sufficient route and avoid broad memory/skill/history loading.

## v0.1.0 - 2026-06-17

- Added the first explicit public version marker.
- Established the version update rule for future repository changes.
- Initial public framework name: Agent Memory Lane Harness.
- Includes meta-first memory retrieval, project-scoped memory lanes, synthetic examples, whiteboard templates, and paired error/solution record shapes.
