# Doubao Client Adaptation Notes

These notes summarize a local Doubao client adaptation of Claim Boundary
Harness observed on 2026-06-25. They are migration guidance for adopters, not an
official Doubao compatibility certification.

The local adaptation was reported by the operator as deployed and tested
successfully inside the Doubao client. Repository-side review checked the
generated adaptation report, file layout, JSON memory files, helper scripts, and
an operator-provided hard-constraint test record. That review confirms the demo
can operate as a soft plus semi-hard workflow layer, and that the tested Doubao
client surfaced a platform-owned hard confirmation guard for a destructive file
operation. It does not prove broad Doubao compatibility, complete hook coverage,
or Claim Boundary Harness-owned hard enforcement inside Doubao.

## Adaptation Shape

The tested local shape used three effective layers:

1. Soft constraint layer: instruction documents for identity boundaries,
   evidence classification, risk routing, mode switching, output contracts, and
   workflow order.
2. Semi-hard layer: JSON facts and hypotheses stores plus init, derive, lint,
   and repair scripts.
3. Host platform hard guard: in the reviewed local test record, a direct
   deletion command was intercepted and required an `interaction.warn` user
   confirmation path before it could continue. This guard is owned by the
   Doubao platform, not by this repository.

A future Claim Boundary Harness-owned hard layer would still require a formal
client skill, host hook, or equivalent execution-path integration. The observed
platform guard is valuable, but it should be treated as host safety
infrastructure that the adaptation aligns with, not as framework code shipped by
this repository.

This difference is expected. Claim Boundary Harness is designed as a portable
boundary framework, not a promise that every client will expose the same
enforcement surface. In one client it may run as instruction-only guidance; in
another it may combine soft routing with scripts; in Doubao, the reviewed local
case combines the framework's soft and semi-hard layers with a host-owned hard
confirmation guard. The adapter's job is to identify those host capabilities,
align with them, and record downgraded or upgraded surfaces honestly.

This shape is useful for general-purpose chat agents because it does not require
the host to expose a full tool-interception API. The tradeoff is that critical
checks become post-run or workflow-driven instead of host-enforced.

## Verified Local Chain

The reviewed demo contained:

- mode-switching guidance for partner chat versus agent execution;
- an output contract that separates facts, hypotheses, unknowns, risks, and next
  steps;
- a seven-step workflow from boundary confirmation through delivery;
- `facts.json` and `hypotheses.json` memory stores with schema metadata;
- init, derive, lint, and repair scripts;
- paired normal-output and boundary-output examples;
- a hard-constraint test record showing that a direct file deletion attempt was
  forced through `interaction.warn`, and that user refusal stopped the delete.

Local script checks passed after forcing UTF-8 stdout:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python scripts\lint_claims.py --facts memory\facts.json --hypotheses memory\hypotheses.json --output test-output-boundary.md --strict
python scripts\derive_claims.py --facts memory\facts.json --output facts-derived.json
python scripts\repair_claims.py --facts memory\facts.json --hypotheses memory\hypotheses.json --dry-run
python scripts\init_memory.py --task "adapter verification" --task-id "doubao-local-check" --output memory-new
```

On Windows, the UTF-8 setting is part of the deployment contract. Without it,
emoji or non-ASCII status output can fail under a GBK console with
`UnicodeEncodeError`.

## Downgraded Or Substituted Surfaces

Different clients may land the same framework with different enforcement
strengths. Treat the table below as an adapter map, not as a weakness by itself.
The important requirement is that every substituted surface states who owns the
enforcement and what has actually been tested.

| Claim Boundary Harness surface | Doubao local adaptation | Status |
| --- | --- | --- |
| Runtime pre-tool hard gate | Instruction/risk-routing document plus host-owned `interaction.warn` for at least one destructive command path | Partial host hard guard observed; not Claim Boundary Harness-owned enforcement |
| R0-R5 router receipt | Mode and risk-routing rules in the prompt/docs | Partially substituted |
| Final claim gate | `lint_claims.py` post-check over selected output files | Downgraded to post-run validation |
| Project/conversation memory lanes | `facts.json` and `hypotheses.json` stores | Partial; no automatic lane router or raw-session ledger |
| Skill lifecycle profile | Instruction/script convention for listing-only, active-frame, release-receipt, and reactivation behavior | Partial; large rendered skill cleanup depends on host context management support |
| Hybrid retrieval profile | Instruction/script convention that can require meta-first plus bounded original-language matching before reading facts or hypotheses | Partial; no tested automatic route field unless the local adapter adds it |
| Memory write granularity profile | Schema/lint convention requiring context-complete facts and hypotheses before durable reuse | Partial; post-run or workflow-level unless wired before memory writes |
| Memory feedback loop | Optional `feedback_loop` field inside fact, hypothesis, CE, or decision records for memory -> prediction -> verification -> calibration | Partial; advisory payload convention only, not a host hard gate |
| Raw session ledger | Not implemented in the reviewed demo | Missing |
| R5 single-event permit | Doubao user confirmation may block or allow some destructive commands | Host-owned confirmation exists for the tested delete path; no replay-protected Claim Boundary Harness permit |
| External research gate | Evidence-tier labels and output contract | Partial; no automatic authority/GitHub search trigger |
| Claim-artifact renderer/checker | Init/derive/lint/repair scripts | Partial; no render payload verifier |
| Domain quality rubric | Not implemented as a generic layer | Future optional surface |

The most important boundary is enforcement authority. A script that reports
warnings is useful, but it is not equivalent to a host that blocks a tool call
before execution. The local Doubao test record does show a host block for one
destructive command path. Keep that claim narrow until the exact client version,
command classes, refusal semantics, and bypass paths have been tested.

## Lint Boundary

The reviewed linter is useful as a smoke check, but adopters should not treat
its score as the fact source. In the local review, a boundary-formatted output
and a weaker normal output both passed strict mode with warnings, and the weaker
normal output received a higher score because the linter did not fully penalize
missing boundary labels.

Use lint output as:

- a formatting and schema signal;
- a prompt-regression detector;
- an advisory final-review aid.

Do not use it as:

- proof that every factual claim is true;
- proof that hypotheses were not promoted into facts;
- proof that the Claim Boundary Harness layer owns hard runtime enforcement.

If an adopter wants a stronger linter, add checks for required section coverage,
missing fact/hypothesis/unknown labels, source-to-claim consistency, and
unsupported certainty language.

## Transferable Deployment Recipe

1. Start with a soft instruction pack. Keep identity, evidence, risk, mode, and
   output-contract documents separate so the client can load only what it needs.
2. Add a visible mode boundary. General chat can stay flexible, but execution
   mode should require evidence labels, unknowns, risk review, and next steps.
3. Split raw facts from hypotheses. Facts require direct evidence. Hypotheses
   require evidence basis and verification steps. Unknowns should remain
   explicit instead of being filled by plausible text.
4. Generate derived facts from raw facts only. Do not hand-edit derived values.
5. Keep repair mechanical. A repair script may add missing fields or normalize
   schema shape; it must not invent evidence or fill unknown data.
6. If the client has a skill or command workflow, add a route-visible field
   equivalent to `skill_lifecycle_profile`: listing-only while idle, active
   frame while executing, release receipt after the phase, and reactivation
   from current source files.
7. If the client has a memory workflow, add route-visible fields equivalent to
   `hybrid_retrieval_profile` and `memory_write_profile`. Treat them as
   meta-first retrieval and write-shape selectors, not as proof that claims are
   true.
8. If reusable memory records are meant to prevent repeated mistakes, preserve
   optional `feedback_loop` fields. Treat predictions as hypotheses until later
   evidence verifies them, and do not create a per-task token ledger for this
   field.
9. Run lint after important outputs and before publishing strong claims. Treat
   warnings as review debt, not as a validated pass.
10. Test the host's own hard guard with a harmless disposable file before relying
   on it. Record whether the client requires `interaction.warn`, whether user
   refusal stops execution, and which command classes are covered.
11. Record unsupported or host-owned hard-gate surfaces in the compatibility
   manifest as advisory, partial, host-owned, or unverified.
12. Keep attribution and source boundaries explicit when the adaptation was
   inspired by local client artifacts or other non-GitHub sources.

## Acceptance Checklist

Before calling a Doubao-style deployment successful, verify:

- the client actually loads the instruction pack in the target chat or agent
  workspace;
- execution-mode answers show facts, hypotheses, unknowns, risks, and next
  steps when the task is nontrivial;
- `facts.json` and `hypotheses.json` parse as JSON and keep raw facts separate
  from derived facts;
- derive, lint, repair, and init scripts run on the target machine;
- memory lookup guidance preserves meta-first retrieval and uses hybrid
  matching only as an enhancement over bounded fact/hypothesis candidates;
- durable fact or hypothesis writes are context-complete and avoid orphan
  fragments before derived reuse;
- optional `feedback_loop` predictions remain hypotheses until later evidence
  verifies them;
- Windows consoles use UTF-8 output or the scripts avoid emoji status output;
- normal-output and boundary-output examples demonstrate a meaningful behavior
  difference;
- README or operator docs match the current file layout and script workflow;
- the platform hard guard is tested on a disposable destructive operation, such
  as deleting a temporary file, without touching user data;
- the test records whether `interaction.warn` or an equivalent confirmation
  surface is required before the destructive command can proceed;
- user refusal is confirmed to stop execution for the tested path;
- no broad hard-enforcement claim is made unless each relevant action class has
  been smoke-tested in the exact client version and workspace mode.

## Attribution Boundary

This adaptation was informed in part by locally inspected Doubao built-in
finance and market-analysis skill artifacts. See
[Influences And Attribution](../influences-and-attribution.md). The reference is
source-prior only. This repository does not copy Doubao code, prompt text,
templates, proprietary schemas, data-source lists, or finance-domain rules.
