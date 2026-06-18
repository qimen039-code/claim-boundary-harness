# Changelog

All notable public changes should be recorded here.

This project uses `vMAJOR.MINOR.PATCH` version labels while the framework is still early-stage.

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
- Current framework name: Agent Memory Lane Harness.
- Includes meta-first memory retrieval, project-scoped memory lanes, synthetic examples, whiteboard templates, and paired error/solution record shapes.
