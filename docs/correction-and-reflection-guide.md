# Correction And Reflection Guide

This guide explains how to use the framework's correction and reflection loop
without turning it into always-on self-rewriting.

## Goal

Small execution mistakes should become compact reusable lessons. Major failures,
route-policy changes, dangerous actions, and public/private boundary decisions
still need human review.

## Default Loop

```text
mistake observed
-> classify the issue
-> record the smallest useful lesson
-> verify the applied fix
-> add a feedback_loop only when future behavior can be checked
-> upgrade only if the issue repeats or becomes high impact
```

## What The Agent May Auto-Record

An adopting runtime may let the agent write a lane-scoped `CE-*` common-error
record without waiting for the operator when all conditions are true:

- the mistake is small, concrete, and already fixed;
- the cause and prevention rule are clear;
- the record includes symptom, cause, solution, prevention, validation, and
  evidence;
- the record stays in the current project or conversation lane;
- no private logs, credentials, personal data, or host-specific secrets are
  published;
- the record does not change routing policy, trigger lists, runtime gates, or
  public docs by itself.

Good examples:

- wrong CLI flag or API method;
- stale notification mistaken for current failure;
- shell profile startup noise mistaken for command failure;
- encoding or path issue with a known fix;
- small patch-context or schema mistake that was corrected and verified.

## What Needs Human Review

Human review is required before:

- changing router rules, trigger lists, decision-layer policy, or runtime gates;
- publishing a new public issue record, README claim, release note, or adapter
  compatibility statement;
- upgrading a CE record to paired `ERR-*` / `SOL-*`;
- recording data loss, security exposure, private/public boundary mistakes, or
  dangerous tool execution;
- creating broad memory links, cross-project merges, or deletion/forgetting
  actions;
- treating a feedback-loop prediction as verified.

## When To Upgrade

Keep an issue as `CE-*` while it is small, fixed, and reusable. Upgrade to
paired `ERR-*` / `SOL-*`, a router regression, or a policy change when:

- the same prevention rule fails again;
- the issue caused or nearly caused data loss, public/private exposure, or an
  unsafe R5 action;
- the issue is a route/decision-layer flaw rather than a one-off execution
  mistake;
- the user explicitly asks for full self-reflection or incident recording.

## Feedback Loop Use

Use `feedback_loop` only for records that should predict and check future
behavior. It is not a user-facing "always predict" feature. It is the internal
habit of using reusable memory well: when a selected CE record, ERR/SOL pair,
capsule, or decision record exists to prevent recurrence, the agent should check
what the record expects, verify the current behavior against that expectation,
and calibrate if the expectation fails.

```text
prediction: what should happen next time
verification: what actually happened
calibration: whether to keep, weaken, strengthen, or upgrade the rule
```

A prediction is a hypothesis. It is not evidence that the behavior is fixed.
The operator may explicitly ask to run the loop or correct its result, but
ordinary task execution should not expose prediction scaffolding unless it
changes the action, risk, memory, or claim boundary.
Use `feedback_loop_profile` to keep the cost bounded: lookup hints and record
candidates stay compact; prevention review and explicit cycles may open the
selected payload.

## Human Work In This Framework

The operator should focus on:

- judging high-impact incidents;
- approving public-facing records and release claims;
- deciding whether a route mistake needs policy/test changes;
- confirming R5 actions and single-event permits;
- resolving project-lane or cross-conversation boundaries.

The agent should handle:

- recording small fixed mistakes as CE records when policy allows;
- reusing CE records during future preflight checks;
- proposing, not silently applying, policy or router improvements;
- marking verification debt when a lesson is not yet proven.

## Non-Goals

This guide does not authorize:

- recording every mistake as permanent memory;
- using ledger summaries as fact sources;
- auto-patching primary rules or skills;
- treating self-reflection notes as validation evidence;
- replacing human confirmation for R5 actions.
