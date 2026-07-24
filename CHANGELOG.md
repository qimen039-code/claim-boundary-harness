# Changelog

All notable public changes should be recorded here.

This project uses `vMAJOR.MINOR.PATCH` version labels.

## Unreleased

Target main-branch version: `v1.1.0` (not yet tagged).

- Replaced the retired CBH-owned runtime deny/permit/Stop chain with a
  stateless, nonblocking behavior-correction lifecycle.
- Added mechanically verified current-input correction profiles with silent
  no-op on ambiguity, verifier failure, or no match.
- Connected tool-surface routing and bounded action consumption to task-local
  correction receipts while preserving host-model task ownership.
- Updated the WorkBuddy reference bridge to advisory-by-default behavior;
  optional PreToolUse rewriting requires explicit host-protocol verification.
- Kept execution authorization with governing instructions and the host's
  native security boundary; CBH correction does not grant permission.

## v1.0.0 - 2026-07-20

- Re-centered CBH as a model-facing capability harness: the host LLM agent
  retains task planning, semantic judgment, tool use, recovery, and final-answer
  ownership; CBH compiles bounded context and verifies selected boundaries.
- Added route-declared `memory_source_hints`, explicit retrieval/research action
  bindings, and a lightweight action consumer that promotes exact indexed
  anchors into provenance-bearing model context without being demoted by weaker
  candidates from a compound natural-language request.
- Added current-conversation source discovery even when another memory family is
  the primary route, closing the last-mile gap between candidate recall and the
  model's selected context.
- Extended the WorkBuddy Agent Loop contract with model-owned memory-context
  retrieval, exact source hints, and deployment-profile support while keeping
  the default hook chain to `UserPromptSubmit` plus `PreToolUse`.
- Made WorkBuddy `Stop` enforcement opt-in after host compatibility validation;
  final-stage checks no longer reapply pre-execution confirmation or permit
  gates, and denial output uses the host's suppressible reason shape.
- Promoted the public release line and all exact version anchors to `v1.0.0`.

## v0.20.3 - 2026-07-11

- Added deterministic skill safety/redundancy audit and first-principles route
  profiles with source, PowerShell, and WorkBuddy parity plus negative and
  long-middle pressure tests.
- Added a machine-readable WorkBuddy Agent Loop action contract and host-owned
  consumption receipt validation so hook-only advisory fields cannot be
  mistaken for executed host behavior.
- Added minimal WorkBuddy and Codex deployment profiles plus a non-destructive
  bundle builder that excludes papers, articles, research material, examples,
  and development tests by default.
- Clarified hook-only capability boundaries and preserved exact redundancy
  trigger anchors across authoring, source, and active policy surfaces.
- Removed the bundled SkillOpt-style implementation from the public package;
  adopters may install Microsoft SkillOpt separately, while local/private
  optimization tooling remains outside CBH release surfaces.

## v0.20.2 - 2026-07-10

- Added the Research Triage Three Questions method for deciding whether a
  research or evaluator problem should follow a mechanical-verifier,
  verifier-audit, governance, or mixed path.
- Added a WorkBuddy bridge that converts verified host or conversation approval
  into one exact, expiring, non-replayable R5 tool-event permit.
- Added primary-goal and consolidated-verification boundaries to avoid
  non-blocking execution expansion and repeated unchanged smoke checks.
- Added one interaction error corpus with isolated structured-tool, browser,
  desktop-app, and keyboard/mouse lanes plus bounded fallback.
- Tightened the CE boundary so only fixed, validated, reusable, source-grounded
  small mistakes remain CE records; severe or repeated incidents use ERR/SOL.

## v0.20.1 - 2026-07-09

- Added a model-facing local LLM adapter brief for OpenAI-compatible local
  deployments, including GLM-5.2 and DeepSeek-V4 profile notes, capability
  probing, advisory/proxy/tool/full-host modes, and R5/claim/memory boundaries.

## v0.20.0 - 2026-07-09

- Added linked-surface synchronization checks so policy/router changes are
  reviewed against related docs, tests, adapters, active Codex surfaces, and
  WorkBuddy integration instead of being patched as isolated local edits.
- Added a novel-recurrence candidate gate for similar-but-different failures
  that miss existing gates, keeping the first pass lightweight while preserving
  escalation paths for global context, causal review, feedback-loop, memory, or
  R5 boundaries.
- Tightened Codex and WorkBuddy routing around global-context, causal,
  feedback-loop, common-error, memory-linking, read-depth, and edit-operation
  profiles while keeping Bash unchanged unless explicitly requested.

## v0.19.11 - 2026-07-09

- Added tool-surface discovery routing for Codex native skills, plugins,
  connectors, and platform-specific MCP/app tools so agents check available
  surfaces before falling back to shell or raw web.

## v0.19.10 - 2026-07-08

- Tightened router classification for skill/security/redundancy audit requests
  so skill safety, hidden-risk, token-bloat, and merge-candidate reviews route
  through the skill matrix and change-contract gate instead of defaulting to
  ordinary chat.

## v0.19.9 - 2026-07-08

- Added `global_task_context_gate` for local causal diagnosis and narrow edits
  that need upstream goal, lane, status, file-map, or workflow context before
  root-cause or patch claims.

## v0.19.8 - 2026-07-08

- Added issue-prevention gates for exact anchors, current/status table evidence,
  unknown memory references, hallucination-detection anchoring, public/private
  publication surfaces, log-grounded self-reports, root-cause cleanup, and
  memory-lane ownership.
- Added public common-issue entries and acceptance cases for the new prevention
  gates.

## v0.19.7 - 2026-07-07

- Added a routed `first_principles_profile` for constraint-first implementation decisions.
- Added a public common-issue entry for overusing or skipping first-principles constraint checks.

## v0.19.6 - 2026-07-07

- Added a memory-first unknown-reference rule for user-mentioned prior context that is not present in the active conversation.
- Added a public common-issue entry for answering from guesses when local memory lookup should happen first.

## v0.19.5 - 2026-07-06

- Added a log-grounded self-report rule for agent descriptions of prior actions.
- Clarified file action semantics so in-place edits are not treated as add/delete events.
- Added a formal-surface hygiene rule to keep assistant-facing memos out of public, runtime, and rule surfaces.

## v0.19.4 - 2026-07-06

- Tightened the public/private boundary so public materials stay generic and do not include private project traces, even when sanitized.
- Replaced maintainer-local field-use wording and private project examples with adopter-local validation boundaries.
- Added shell dialect drift to the compatibility refresh triggers.

## v0.19.3 - 2026-07-04

- Published a Zenodo DOI trigger release after enabling the repository in Zenodo.
- Updated citation, README, compatibility, and version metadata to `v0.19.3`.
- Reduced stale-version exposure in the public changelog by keeping older release
  detail out of the current branch documentation surface.

## Historical Notes

Earlier pre-DOI and intermediate release notes remain available through Git
history and prior tags when explicitly needed for audit. They are intentionally
not expanded in the current public documentation surface so external readers
and search tools do not treat stale early-stage wording as the current
framework description.
