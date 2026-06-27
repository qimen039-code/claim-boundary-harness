# Changelog

All notable public changes should be recorded here.

This project uses `vMAJOR.MINOR.PATCH` version labels while the framework is still early-stage.

## Unreleased

- Added a skill lifecycle contract with `skill_lifecycle_profile`, active-frame loading, release-receipt handoff, and reactivation from current source files instead of stale compressed skill fragments.

## v0.17.0 - 2026-06-27

- Added source-preserving memory write granularity rules so durable capsules stay context-complete instead of becoming isolated short fragments.
- Added a no-dependency hybrid memory retrieval contract: meta-first filtering, original-language lexical channels, optional lexical ranking, and explicit non-adoption of database/vector semantic-memory cores.
- Added routed `hybrid_retrieval_profile` and `memory_write_profile` fields across the PowerShell router, WorkBuddy Python adapter, policy contract, templates, and regression tests so these capabilities are executable route decisions rather than only documentation.
- Added a bounded content-reading contract for source-shape identification, structure-map fallback, source context headers, progressive evidence windows, and unread-zone verification debt.
- Added middle-safe evidence layout rules for evidence inventories, original-window dual anchors, segment-level conclusion cards, adjacent multi-hop evidence clusters, key-evidence reminders, position-risk markers, and bounded middle rereads when head/tail anchors cannot support a strong claim.
- Added reading trigger profiles so the routing or decision layer can select baseline, evidence-window, middle-safe, or full-audit reading instead of enabling every strategy on every source read.
- Connected the new memory-writing, hybrid-retrieval, and content-reading contracts into the architecture overview, cost-control guidance, README layout, doctor required-file checks, acceptance cases, and pytest documentation-contract coverage.
- Added release-preparation routing coverage so publish/release readiness, release audit, and 发布前/发布准备/发布整理 tasks route as R3 governance/docs work while submit/commit/push wording remains only an R5 candidate unless an actual git action is requested.
- Extended the WorkBuddy adapter manifest and documentation for optional quality-reference, domain source-tier, claim-artifact, and external-model JSON-filler surfaces. These remain default-off, advisory/source-prior, and unverified until a host version tests them.
- Added attribution for the Doubao built-in finance and market-analysis skill artifacts that informed those optional contract-boundary patterns, with an explicit no-code/no-template/no-proprietary-schema copying boundary.
- Added transferable Doubao client adaptation notes covering soft and semi-hard deployment, downgraded enforcement surfaces, script-chain checks, UTF-8 console requirements, and attribution boundaries.
- Clarified the Doubao notes with an operator-provided local hard-constraint test: a destructive delete path was forced through the platform-owned `interaction.warn` confirmation surface, so the adaptation should align with host safety guards without claiming framework-owned hard enforcement.
- Documented the portability principle that different clients may legitimately provide different enforcement strengths; adapters should map, align, test, and disclose those host-specific surfaces instead of pretending every deployment has identical hard gates.
- Added a README field-use boundary listing Codex, WorkBuddy, and Doubao as the only currently locally tested adaptation/deployment surfaces, while keeping other clients as unverified reference paths.
- Added a public common-issues-and-solutions playbook for classified adaptation, CI, memory-ledger, attribution, R5-permit, and shell-startup issue classes.

## v0.16.0 - 2026-06-25

- Promoted the release line for the conversation-ledger, TOML policy-authoring, and full-lane trigger work into a larger compatibility update.
- Extended WorkBuddy adapter coverage around prompt routing, command-tool hard gates, Stop/final checks, conversation-link blocking, host-provided transcript extraction, and single-event R5 confirmation permits.
- Added WorkBuddy hook-runner regression coverage for replayed `cbh.r5_human_confirmation_permit.v1` permits, not only the in-process runtime path.
- Clarified release-facing WorkBuddy boundaries: local adapter tests and one local hook deployment observation are not a broad WorkBuddy compatibility certification.
- Updated the adapter compatibility manifest version to match the release line.

## v0.15.3 - 2026-06-24

- Added a conversation-ledger contract, templates, and Codex JSONL ledger builder that link raw host sessions to project or conversation memory through session, turn, segment, time-anchor, and evidence-ref records.
- Added low-cost Codex ledger maintenance modes: stat-first `doctor`, stale-only `refresh`, bounded-window `resolve`, and boundary-oriented `auto` checks so stale or missing ledgers can be detected without waiting for the user to name the problem.
- Preserved the meta-summary and event/domain capsule design by generating `capsules.jsonl` as a derivative classification view over segments and evidence refs.
- Added structured conversation full-lane trigger groups so context loss, durable decisions, open loops, and artifact/code-change clusters can promote a projectless long chat beyond the old coarse signal-count threshold.
- Added a short-lived `cbh.r5_human_confirmation_permit.v1` path for one exact R5 or hard-tool event, with task/tool hash matching and `single_event` scope.
- Added a lightweight TOML policy authoring layer for high-churn R5, full-lane, and permit sections, plus a compiler/checker that keeps the runtime JSON as the adapter-facing source.
- Added routing support for the `conversation_ledger` target surface and `conversation_ledger_index` module need, with PowerShell and WorkBuddy regression coverage.
- Fixed the Bash router helper so CI smoke checks no longer hit a Bash nameref self-reference warning during trigger collection.
- Normalized the `Where It Can Be Used` README list punctuation for consistency.

## v0.15.2 - 2026-06-24

- Added a generic existing-file local-patch rule: ordinary change, update, fix, sync, or adapt requests should modify only the necessary anchored section unless the user explicitly asks for a full-file rewrite or replacement.
- Added adoption guidance for protecting existing instruction, memory, config, and policy files from accidental full-file regeneration.
- Fixed a narrow router miss where Chinese public-repository rule synchronization phrasing could route as ordinary R0 chat instead of R3 governance/docs change.
- Added a regression case for public repository rule synchronization routing.

## v0.15.0 - 2026-06-23

- Hardened PowerShell runtime parity with original task text and explicit risk-level overrides, schema-aware command-tool scanning, policy-backed hard-tool patterns, and safer project-lane path boundary checks.
- Tightened claim schema checks with enumerated source types, source references for source-backed claims, enumerated evidence boundaries, and stronger evidence requirements for final validation wording.
- Reduced noisy fallback routing by keeping short unclassified prompts cheap while reserving boundary review for medium fallback matches or long unclassified tasks.
- Added WorkBuddy hook-state locking and atomic state writes to reduce cross-session prompt-state overwrite risk.
- Updated smoke tests, pytest contract checks, and adoption notes for the runtime parity and claim-boundary behavior.

## v0.14.27 - 2026-06-23

- Added `tools/cbh_doctor.py`, a read-only adoption diagnostic for package files, policy shape, PowerShell router probes, selective tool-proxy blocking, and Bash/jq availability.
- Added pytest contract checks for automatically verifiable `TC-xxx` routing cases, tool-proxy blocking, doctor execution, and machine-readable credits.
- Added `CREDITS.toml` as a machine-readable companion to the public influences and attribution document.

## v0.14.26 - 2026-06-23

- Added R5 candidate/context routing so high-risk words are recorded before being promoted to hard R5 actions.
- Added PowerShell and Bash smoke coverage for R5 documentation context, Chinese submit/report phrasing, Chinese delete/release actions, and paths with spaces.
- Kept package-manager distribution as a non-goal; no npm or pip distribution layer was added.

## v0.14.25 - 2026-06-23

- Extended the policy validator to check that `belief_trace_summary.current_status` stays synchronized with `belief_status` when reusable memory examples or templates include both fields.
- Added the same lightweight invariant check to the Bash reference validator when `jq` and Bash are available.

## v0.14.24 - 2026-06-23

- Added a trigger-promotion gate so one-off task wording does not become long-lived router policy.
- Removed README-specific simplification terms from the R3 trigger list; generic edit and documentation rules continue to route those tasks.

## v0.14.23 - 2026-06-23

- Reworded public changelog entries so release notes describe user-facing documentation changes without internal maintenance phrasing.
- Replaced colloquial public-documentation routing triggers with neutral wording.

## v0.14.22 - 2026-06-23

- Reworded metadata field lists so GitHub line wrapping does not leave punctuation separated from inline field names.
- Applied the same field-list wording style across README, adoption-facing docs, templates, and embedded-harness notes.

## v0.14.21 - 2026-06-23

- Reworked the README opening section with a compact overview, fast-path table, and shorter project-difference summary.
- Condensed the adoption notes on the README into a shorter reality-check section that links to the detailed adoption and deployment-risk docs.
- Made the WorkBuddy hook runner emit readable Unicode JSON by default while retaining a UTF-8 fallback for stdout encoding failures.
- Added routing coverage for README overview restructuring and similar public-documentation edits through the existing generic edit path.

## v0.14.20 - 2026-06-23

- Added an explicit attribution section to the Static Knowledge Layer, clarifying that it adapts the established pattern of repository manuals, project wikis, and close-to-code knowledge bases without vendoring a specific upstream wiki implementation.
- Tightened `docs/memory-meta-index-contract.md` for static knowledge and source-monitoring constraints: `_STATIC_KNOWLEDGE_INDEX.md`, `static_knowledge`, `static_knowledge_page`, `promotion_reason`, and `decay_reason`.
- Updated the static knowledge index template so lifecycle, retention, promotion, and decay fields are visible at the index layer.

## v0.14.19 - 2026-06-23

- Added an optional Static Knowledge Layer for wiki-style project manuals, including indexed templates for project maps, entry points, conventions, and interface notes.
- Routed static knowledge lookups through `static_knowledge_index` and `static_knowledge_index_gate` so project manuals stay index-first and `source_prior` by default.
- Added `source_tag: static_knowledge` and `static_knowledge_page` provenance language to the source-monitoring schema.
- Updated README, architecture, adoption, reproduction, CI smoke checks, and adapter tests to cover the static knowledge layer without making it a memory backend.

## v0.14.18 - 2026-06-23

- Added read-only completion/status review triggers so phrases such as "review whether this is complete" or "还有什么没做完" do not fall through as R0 ordinary chat.
- Mirrored scope-reassessment gate handling in the WorkBuddy Python adapter so composite/status-review routing matches the policy-backed PowerShell router.
- Added a regression test case for completion/status review routing.

## v0.14.17 - 2026-06-23

- Added `docs/test-cases.md` with reference acceptance cases for routing, claim boundaries, memory lanes, adapter/runtime checks, shell robustness, and SkillOpt-style cycles.
- Added composite-task and scope-reassessment routing rules so multi-intent requests keep the highest risk level and union of required gates instead of being under-routed by the first narrow phrase.
- Updated public status language for Codex and WorkBuddy: Codex has extended private use observations, and WorkBuddy has one local hook deployment confirmation while remaining non-certified across versions.

## v0.14.16 - 2026-06-23

- Added a practical innovation summary to the README so readers can quickly see the concrete value of claim boundaries, memory-lane linking, metadata-bearing retrieval, low-cost routing, selective hard gates, source-grounded learning, and periodic skill improvement.
- Clarified that borrowed mechanisms remain attributed while the repository's contribution is the composed boundary contract and runnable reference package.

## v0.14.15 - 2026-06-23

- Clarified the memory-lane innovation in the README: project, conversation, common-error, and archive lanes can be linked through metadata and ledgers while payload writes stay lane-scoped by default.
- Added a stronger public explanation of meta-first memory lookup, link-only continuation, explicit merge boundaries, and metadata-bearing retrieval results.

## v0.14.14 - 2026-06-23

- Added a default-off executable SkillOpt-style external module at `tools/skillopt/skillopt_cycle.py` for periodic candidate-edit generation, validation gating, rejected-edit records, and slow-update proposals.
- Added SkillOpt runtime templates under `templates/skillopt/` and a smoke-testable runtime guide in `docs/skillopt-runtime.md`.
- Added `docs/influences-and-attribution.md` to separate project contributions from public GitHub and engineering-pattern influences.
- Updated README, reproduction checks, registry wording, and CI smoke workflow so the SkillOpt-style layer is described as an optional executable module rather than only a document.

## v0.14.13 - 2026-06-23

- Added a hook capture point matrix for prompt, tool, compaction, and stop/final stages without turning every tool call into a hard wrapper.
- Added a retrieval-result boundary requiring memory retrieval outputs to carry source, provenance, belief state, confidence, and score-method metadata instead of returning unbounded text snippets.
- Added optional lifecycle metadata for reusable memory capsules: `stage`, `retention_policy`, `last_accessed_at`, `promotion_reason`, and `decay_reason`.
- Added explicit memory command semantics for recall, remember, forget, recap, handoff, session-history, and commit-context style requests.
- Clarified that full memory backends and automatic cross-agent shared memory are optional adopter choices, not part of the default whiteboard core.

## v0.14.12 - 2026-06-22

- Added plural Chinese/English explicit-recording triggers so phrases such as "record these issues" and "记录这几个问题" route to memory recording instead of falling through as no-memory work.
- Hardened the WorkBuddy Python runtime tests for Windows/Codex sandbox environments where `tempfile.TemporaryDirectory()` can create directories with unusable ACLs.
- Added a regression test for plural Chinese issue-recording phrasing.

## v0.14.11 - 2026-06-22

- Added a source-monitoring memory schema for capsules, covering `source_tag` `belief_status` `confidence` `derived_from` `source_monitoring` `belief_trace` `belief_trace_summary`.
- Clarified that `belief_status` is a verification-process state and `confidence` is the evidence strength for assigning that state, not a naked probability score.
- Added conditional capsule rules for `score` / `score_method`, synthesized provenance, correction evidence, rejected capsules, novelty adapter boundaries, and trace compression.
- Updated project, conversation, global archive, and demo memory templates to expose compact source-monitoring fields through meta-first indexes.
- Tightened conversation-memory routing so explicit current/local conversation memory updates route to the conversation-memory surface and current-conversation lane instead of being swallowed by broader private/local rule wording.

## v0.14.10 - 2026-06-22

- Removed the former-name line from the README so the public homepage presents Claim Boundary Harness as a new, focused project identity.
- Added a compact Start Here guide near the top of the README so readers can quickly choose the overview, architecture, adoption, deployment, or example path.

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
- Added a format-layering strategy that separates human-facing Markdown from machine-owned JSON/JSONL/CSV and non-semantic operational records to reduce fragile Markdown table and long-line patching.
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
- Updated repository metadata with focused GitHub topics.

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
