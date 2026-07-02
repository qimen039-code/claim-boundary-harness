# Claim Boundary Harness: External Cognition Governance for Agent Workflows

Draft technical report for possible arXiv submission.

Version: v0.19.0

Repository: https://github.com/qimen039-code/claim-boundary-harness

## Abstract

Agent workflows increasingly depend on long-running context, local tools,
memory files, project instructions, and host-specific adapters. These systems
often fail not because the base model cannot reason, but because claims,
memories, risks, and execution surfaces are not kept separate enough. A smoke
check is reported as validation, a stale summary is treated as current evidence,
or a soft instruction is described as a hard gate.

Claim Boundary Harness (CBH) is a lightweight external cognition governance
framework for agent workflows. It does not replace the host model and does not
require a new model, vector database, or universal runtime. Instead, it defines
a set of small contracts: route the task before expansion, keep memory lanes
isolated, preserve evidence provenance, downgrade claims that lack support,
record reusable corrections, and disclose whether a runtime can actually honor
a blocking decision. This report describes the framework, its reference
implementation, its tested boundaries, and its limitations. The evidence is
engineering-oriented rather than experimental: CBH is presented as a framework
and reference package, not as a completed benchmark result or a proof that
hallucination has been solved.

## 1. Introduction

Modern coding agents can read files, edit code, call tools, search external
sources, and carry large context windows. The practical difficulty is that these
abilities do not automatically produce stable epistemic boundaries. An agent
can perform a useful local check and then overstate the result. It can retrieve
the right memory and still lose the source boundary. It can follow a safety
instruction in one host client and fail in another because the second host does
not call the same hook.

CBH starts from a modest premise: before an agent acts or reports, it should
know what kind of claim it is about to make, which memory lane owns the context,
what evidence is available, and whether the runtime can enforce the relevant
boundary. The framework is therefore not a planning system, a safety sandbox, or
a semantic-memory backend. It is a governance layer for the smaller decisions
that usually sit between user intent and model output.

The design goal is to keep this layer cheap enough to use in ordinary work. CBH
uses compact routing receipts, meta-first memory lookup, source-monitoring
fields, bounded evidence windows, and selective hard gates. It tries to avoid
the common failure mode where an agent framework becomes a growing pile of
active prompts, summaries, and skills that eventually pollutes the context it
was meant to improve.

## 2. Problem Statement

The failure cases targeted by CBH are narrow but common:

- a single smoke check is described as broad validation;
- a mock, partial run, or prepared artifact is reported as a completed result;
- memory from one project or conversation silently influences another;
- an old summary survives after its source evidence is obsolete;
- the agent relies on internal knowledge when current external facts are needed;
- a hook returns a denial, but the host runtime continues through a bypass path;
- repeated small mistakes never become reusable lessons.

These are not only model-quality problems. Many are boundary-placement
problems. The agent needs a place to decide whether it is doing ordinary chat,
read-only inspection, documentation, code or governance change, runtime or
external-fact work, or a high-risk action. It also needs a place to preserve the
difference between source-prior information, bounded claims, local validation,
conflicts, and rejected or superseded records.

## 3. Framework Overview

CBH uses a low-cost control path:

```text
user task
-> L0 microkernel
-> intake router
-> routing receipt
-> selected memory/search/reading/claim gate
-> execution
-> final boundary review
```

The router is additive rather than mutually exclusive. A task can be both a
documentation change and a release action; a code edit can also require runtime
verification; an external source can be useful without becoming local proof.
The route determines how much context to open and which boundary checks matter.

The core contracts are:

- **Claim boundary.** Claims must not be stronger than their evidence. Artifact
  existence, command execution, smoke checks, regression tests, repeated runs,
  current external sources, and production-path verification are different
  evidence levels.
- **Memory continuity.** Project memory, conversation memory, common-error
  records, static knowledge, and global archives are separate lanes. They may
  link to each other, but they do not silently merge payloads.
- **Risk routing.** R0-R5 labels describe ordinary chat through high-risk
  actions. The labels are operational gates, not user-facing ceremony.
- **Correction accumulation.** Reusable mistakes can become compact common-error
  records or paired incident and solution records. Improvements are bounded,
  reviewable, and rejectable.
- **Adapter disclosure.** A gate is hard only on paths where the host runtime
  calls the gate and honors the result. Otherwise it remains advisory.

## 4. Memory And Retrieval

CBH's memory design is not "save everything." It is a lane-and-link model. Each
lane should expose a meta index before deeper payloads are opened:

```text
memory summary or _META_INDEX
-> category index or point index
-> selected capsule or paired record
```

Reusable memory records carry source-monitoring fields such as `source_tag`,
`derived_from`, `belief_status`, `confidence`, `source_monitoring`,
`lifecycle`, and `belief_trace_summary`. These fields are not proof that a
claim is true. They preserve how the claim was obtained, what supports it, and
what should happen if the source changes.

The framework deliberately avoids making a vector database or SQL store the
default semantic-memory core. Lexical and structural retrieval can still be
useful, but it is bounded by lane and meta-index selection first. This is
especially important for multilingual content: code and schema fields can stay
in English for interoperability, while memory content should preserve the
original language when that language carries the original meaning.

## 5. Reading And Evidence Windows

Retrieval is not the same as reading. After a candidate file or memory record is
selected, CBH chooses a reading profile. Small tasks may need only a baseline
read. Strong claims, multi-hop evidence, public documentation, or long-context
work can trigger evidence windows, middle-safe reading, or a full audit.

The middle-safe profile exists because long contexts can hide important
evidence away from the beginning and end of the window. CBH therefore supports
evidence inventories, original-window anchors, per-window conclusion cards,
adjacent multi-hop evidence, key evidence reminders near strong claims, and a
position-risk marker. This does not solve model attention behavior. It gives the
agent a procedure for noticing when it has not read enough to support a strong
claim.

## 6. Runtime Enforcement

CBH distinguishes advisory control from hard runtime enforcement. The same
policy can be embedded in a prompt, a local script, a hook, a wrapper, or a
client adapter, but the enforcement strength depends on the host.

```text
advisory instruction
< hook called and honored
< wrapper around the execution path
< host-level denial with no bypass
```

The reference implementation includes PowerShell gates, Bash reference gates,
a WorkBuddy-oriented Python adapter, and client-specific notes. The important
claim is limited: hard enforcement exists only on covered paths. If a host
client does not expose a tool hook or ignores denial results, CBH cannot pretend
to be a sandbox.

The Doubao adaptation attempt is an example of this boundary. A prepared native
skill package and dated chat/workspace demo existed, but the inspected desktop
client did not persistently load the custom skill in a later new chat and did
not expose a usable custom skill/tool registration path. The correct status is
therefore failed persistent adaptation, with possible single-chat advisory use,
not completed client support.

## 7. Reference Implementation

The public repository includes:

- root and project instruction contracts;
- policy files and authoring TOML;
- PowerShell and Bash reference gate scripts;
- a WorkBuddy Python runtime adapter;
- memory and conversation-ledger templates;
- common-error and correction records;
- content-reading, retrieval, feedback-loop, skill-lifecycle, and causal
  attribution contracts;
- smoke and unit tests for checkable surfaces;
- attribution records for public influences and local client artifact
  references.

The package is intentionally plain. It should be possible for another runtime
to replace the scripts with native hooks while preserving the same contracts.

## 8. Evidence Boundary

The current evidence is a set of repository tests, script checks, adapter unit
tests, and operator observations from local use. These support limited claims:
the reference files are internally consistent, selected scripts and tests pass
on the checked machine, and some client adaptation paths have known outcomes.

They do not support broad claims that CBH works in every agent runtime, that it
eliminates hallucination, or that it creates new model capabilities. A more
careful description is that CBH can reduce unchecked claim drift and make
cross-turn or cross-project errors easier to detect, provided the host runtime
actually loads the relevant instructions and honors the relevant gates.

Field observations should remain field observations unless a controlled
comparison is performed. A useful future evaluation would run the same
long-running task chain with no harness, with equivalent static context, and
with the full CBH routing and memory contracts, then compare overclaim rate,
wrong-lane memory use, repeated-error frequency, and bypass disclosure.

## 9. Relation To Prior Work And Influences

CBH is a composed framework. It uses established engineering patterns such as
policy decision/enforcement separation, admission-control hooks, append-only
ledgers, structured provenance, and meta-first retrieval. It also records public
GitHub influences and local client artifact references in `CREDITS.toml` and
`docs/influences-and-attribution.md`.

This report does not claim that every underlying mechanism was invented here.
The contribution is the particular boundary contract and reference package that
connects claim verification, memory continuity, risk routing, correction
accumulation, and adapter disclosure for agent workflows.

## 10. Limitations

CBH has several important limitations:

- it is not a sandbox;
- hard stops require host support;
- routing rules need continued calibration;
- memory templates are not a database or a universal memory system;
- current validation is not a large controlled benchmark;
- client behavior can change after updates;
- public documentation must not expose private local formation paths;
- the framework can still be misused if adopters treat source-prior records as
  proof.

These limitations are not incidental. They are part of the claim boundary. The
framework is useful only if its own documentation follows the same evidence
rules it asks agents to follow.

## 11. Conclusion

Claim Boundary Harness proposes a small external governance layer for agent
workflows. Its central idea is simple: make the agent route risk, memory,
evidence, and enforcement before it acts or reports. The reference
implementation shows one way to make that idea concrete with local files,
scripts, templates, adapters, tests, and public attribution records.

The project should be read as a framework and engineering artifact, not as a
final experimental result. Its value is in giving agents and operators a shared
set of boundaries: what is known, where it came from, which lane owns it, what
can be claimed, and whether the runtime can actually enforce the decision.

## References

- Claim Boundary Harness repository:
  https://github.com/qimen039-code/claim-boundary-harness
- Claim Boundary Harness influences and attribution record:
  `docs/influences-and-attribution.md`
- Claim Boundary Harness citation metadata:
  `CITATION.cff`
- Nelson F. Liu et al. "Lost in the Middle: How Language Models Use Long
  Contexts." arXiv:2307.03172.
