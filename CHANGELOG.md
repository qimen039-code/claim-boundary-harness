# Changelog

All notable public changes should be recorded here.

This project uses `vMAJOR.MINOR.PATCH` version labels while the framework is still early-stage.

## Unreleased

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
