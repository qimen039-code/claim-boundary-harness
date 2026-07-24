# Claim Boundary Harness: Claim Boundaries Before Agent Confidence

Coding agents do not usually fail in a clean, obvious way. The uncomfortable failure is quieter: a partial run becomes "validated", a mock becomes "tested", a stale memory is treated as current context, or a hook is described as hard enforcement even though the host still has another execution path.

Claim Boundary Harness started from that observation. It is not another agent runtime. It is a small governance layer that sits before memory lookup, tool execution, and final reporting. The goal is to make an agent decide what kind of claim it is about to make before it makes it.

The project is intentionally plain. It uses instruction files, compact routing receipts, policy JSON, PowerShell/Bash reference gates, and a WorkBuddy-oriented Python adapter. The interesting part is not the stack. It is the boundary placement.

## The Narrow Problem

Most agent harnesses talk about planning, tools, memory, sandboxes, and evals. Those are all useful. In practice, a local coding agent also needs a smaller discipline:

```text
What do I know?
How do I know it?
Which project or conversation owns this context?
Is this enough evidence for the claim I am about to make?
```

Without that discipline, an agent can do many individually reasonable things and still produce a bad outcome. It can load the wrong memory lane. It can skip current-source lookup for versioned facts. It can treat an advisory hook as if it were a sandbox. It can turn one smoke check into a broad validation claim.

Claim Boundary Harness makes those decisions explicit, but tries not to make ordinary tasks expensive.

## The Control Path

The default path is meta-first:

```text
user request
-> L0 microkernel
-> intake router
-> routing receipt
-> one matching gate or index
-> one matching payload
-> final claim boundary review
```

The router is supposed to be cheap enough to run before nontrivial work. It should not open every memory file, every skill, or every project document. It should decide which surface is relevant, then stop expanding.

That is why memory lookup starts from a meta layer:

```text
memory summary or _META_INDEX
-> category index or outer retrieval surface
-> selected capsule or paired record
```

This is slower than guessing, but much cheaper than broad history scans. It also gives the agent a place to notice when it is about to cross a project or conversation boundary.

## Routing Receipts

The routing receipt is the contract between the advisory control plane and any runtime adapter that wants to enforce it.

Important fields include:

```text
task_type
target_surface
audience
project_lane
risk_level
semantic_ambiguity
module_need
memory_need
memory_mode
memory_lane
record_intent
external_need
claim_risk
projectization_decision
conversation_memory_decision
link_intent
receipt_profile
required_gates
```

The names are a little dry on purpose. They are meant to answer operational questions:

- Is this a public-docs edit, a local adapter change, a memory update, or a git action?
- Does this task need project memory, conversation memory, external research, a claim schema, or no extra module?
- Is the final answer allowed to say "validated", or only "smoke checked"?
- Is the runtime expected to block, or is an advisory note enough?

The receipt can stay internal for ordinary work. It should become visible only when the decision changes cost, risk, permission, memory, search, or claim wording.

## R0-R5 Is Additive, Not A Label Game

The risk model is deliberately simple:

```text
R0 ordinary chat
R1 read-only local inspection
R2 reports, handoffs, and documentation artifacts
R3 code, config, governance, routing, trigger, or framework behavior changes
R4 experiments, runtime claims, current facts, external mechanisms, or performance work
R5 delete, submit, publish, install, login, payment, permission, network/proxy, sensitive transfer, or long-term memory writes
```

The important detail is additive routing. "Fix code and run an experiment" should keep both the code-change gate and the experiment/claim gate. "Update docs and push to GitHub" should not be treated as harmless just because the file is Markdown.

This is also why R0-R5 is silent by default. Users do not need a risk label for every small task. They need the agent to stop when a boundary matters.

## Claim Boundaries

The framework separates evidence levels that agents often collapse:

```text
artifact exists
command ran
smoke check passed
local regression passed
repeated run passed
current external source checked
production/runtime path verified
```

A smoke check is useful. It is just not the same as broad validation. A public benchmark is useful. It is still source-prior until the adopting environment reproduces or gates it locally.

The final claim gate exists to keep those distinctions intact. It does not make the project more sophisticated; it prevents the answer from sounding more certain than the evidence.

## Memory Lanes

The memory design follows the same boundary rule.

Project memory belongs to a project. Conversation memory belongs to a conversation. A global archive is cold storage, not active context. Common operational mistakes can go into a common error corpus. Higher-impact or repeated failures can become paired error/solution records.

New conversations that continue old ones should use link-only continuation by default. They create their own lane and point back to the older one. They do not rewrite the older lane unless the user explicitly asks for a merge.

This is not mainly about storage format. It is about preventing a useful memory system from becoming a source of contamination.

## Advisory Control Plane And Native Host Boundaries

This was one of the sharper deployment lessons.

A harness receipt can route risk, memory, evidence, or review work, but it does
not create physical enforcement. Permission and sandbox enforcement remain on
the native host surfaces that actually own execution.

```python
candidate = harness.behavior_correction_gate(tool_input)
if candidate.is_exact_match and candidate.verifier_passed:
    return allow_with_updated_input(candidate.updated_input)
return no_output_original_input_unchanged()
```

The behavior-correction hook is deliberately narrow, stateless, and
nonblocking. It may rewrite one exactly matched current input only after its
mechanical verifier passes. Ambiguity, no match, module failure, or verifier
failure leaves the original input unchanged. Risk authorization, long-term
memory writes, unresolved links, and strong claims continue through the
instruction, evidence, and native-host boundaries that own them.

This matters because "self-improving" systems can become noisy quickly. Too many generated skills can make ownership unclear and routing less reliable. The training layer is subordinate to the skill matrix: it proposes candidate edits, regression probes, gate reports, or rejected-edit records. It does not mutate primary rules without an accepted gate result and required approval.

## Deployment Notes

The repository includes deployment playbooks because most harness failures are integration failures.

Some examples:

- the instruction file exists but the agent never loads it;
- the pre-tool hook is configured, but the host never consumes its updated-input protocol;
- the pre-tool hook receives a tool payload but not the original user task;
- a correction matcher rewrites documentation text instead of the current executable input;
- a final answer says "validated" even though no claim schema was checked;
- a Windows PowerShell reader decodes policy JSON with the wrong encoding;
- a client update changes the launcher path, hook schema, or bundled runtime.

These are not edge cases. They are the kinds of failures that decide whether a governance layer is actually connected.

## Reproduction Scope

The public package currently carries lightweight checks, not a full production test matrix.

Recent local checks for the reference package included:

- WorkBuddy-oriented Python adapter unittest suite passes locally;
- embedded harness policy validation: `status: pass`;
- JSON/JSONL parse checks for repository examples;
- `git diff --check`;
- public-sensitive-string scanning to reduce accidental leakage.

Those checks support a narrow claim: the checked reference package is internally consistent on the tested setup. They do not prove that every host agent, operating system, hook schema, or production workflow is supported.

## What To Reuse

If you are adapting the framework, the reusable parts are:

- the meta-first lookup rule;
- the routing receipt shape;
- the additive R0-R5 risk model;
- the claim boundary vocabulary;
- project and conversation memory isolation;
- link-only continuation;
- task-local, nonblocking behavior correction;
- deployment smoke checks that prove the exact host lifecycle consumes a verified rewrite.

The exact scripts are reference implementations. Replace them if your runtime has a better native hook, middleware, policy engine, or sandbox surface.

## Suggested Listing Description

> Claim Boundary Harness - A meta-first governance harness for coding agents focused on claim verification, project-scoped memory lanes, R0-R5 risk receipts, and adapter deployment playbooks. Reference framework with local Codex and WorkBuddy-oriented smoke checks; not a production-validated universal runtime.

## Repository

- GitHub: https://github.com/qimen039-code/claim-boundary-harness
- License: MIT
