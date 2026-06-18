# Adoption Guide

Use this guide to adapt the whiteboard core to your own agent environment.

## Step 1: Choose The Instruction Entry

Every agent has a different way to load workspace rules. Map `AGENTS.md` into the file or settings surface that your agent actually reads.

Do not add product-specific adapter files to the shared core unless you want to maintain that adapter.

## Step 2: Configure Project Lanes

Edit `skills/embedded-harness/embedded_harness_policy.json`:

- replace `EXAMPLE_PROJECT`;
- replace `C:\\path\\to\\project`;
- replace memory roots;
- tune trigger terms.

Then copy `templates/project/memory-library` into the project memory root and keep the layered layout:

```text
_META_INDEX.md
governance/_INDEX.md
memory_hierarchy/_INDEX.md
external_references/_INDEX.md
raw_logs/_INDEX.md
```

Do not collapse the library into one large summary file. The point of the meta index is to select the category first, then open only the relevant category index and capsule.

Make this lookup order mandatory in the adopting agent instructions:

```text
_META_INDEX.md or equivalent meta summary
-> one category index
-> one matching capsule
```

If the agent cannot confirm that it read the meta layer first, treat the memory result as incomplete rather than authoritative.

Use [memory-meta-index-contract.md](memory-meta-index-contract.md) as the recommended field shape. The important part is not the exact Markdown formatting; it is the ability to select by lane, scope, category, record type, status, retrieval terms, applicability, linked modules, linked records, and review freshness before opening a payload.

## Step 3: Register The Skill Folders

If your agent supports skills or commands, register these folders:

- `skills/embedded-harness`;
- `skills/troubleshooting-skill-matrix`;
- `skills/agent-error-memory`;
- `skills/bug-solution-memory`;
- `skills/shared-semantic-anchors`.

If your agent does not support skills, keep them as normal workspace files and reference them from the root instruction entry.

## Step 4: Wire Runtime Checks

At minimum, run the intake router before nontrivial work.

Stronger setups can run:

- memory isolation before reading or writing project memory;
- external research gate before current source claims;
- claim schema verifier before final strong claims;
- high-risk checks before tool calls.

Also make the advisory control plane mandatory:

1. Create a lightweight routing receipt for nontrivial work: task type, target surface, audience, lane, risk, semantic ambiguity, module need, memory need, memory mode, memory lane, record intent, external need, claim risk, projectization decision, and required gates.
2. Re-evaluate only after trigger events: new evidence, missing files, tool errors, scope changes, user corrections, cross-project terminology, currentness/version claims, GitHub/open-source mechanism intake, risk/cost escalation, strong claims, R5 actions, or memory writes.
3. Final-check claim scope, memory scope, version metadata, and unresolved verification debt.

Do not make this expensive by default. The control plane should choose the cheapest sufficient route and should not wrap every tool call.

Use [router-decision-contract.md](router-decision-contract.md) as the field contract for router and dynamic-decision adapters. The contract can be implicit for obvious low-risk work, but should be explicit for R3 or higher work, public-facing changes, memory writes, high-risk actions, and audited decisions.

Use [memory-routing-contract.md](memory-routing-contract.md) when wiring memory writes. Start with common error corpus records for small reusable mistakes and upgrade to paired ERR/SOL records only when the issue is explicit, high-impact, or repeated.

For selective runtime hard stops, route only critical boundaries through these entry points:

```text
pre-task hook -> skills/embedded-harness/harness_runtime_enforcer.ps1
tool-call proxy -> skills/embedded-harness/harness_tool_proxy.ps1
command wrapper -> skills/embedded-harness/harness_task_wrapper.ps1
final-answer gate -> skills/embedded-harness/harness_runtime_enforcer.ps1 -Stage final
```

Do not replace your normal agent launcher until the scripts pass local smoke checks. Start with high-risk blocking, final-claim checks, and memory-write checks. Keep ordinary tool calls on the advisory control plane unless you have a reason to harden them. Keep a fallback path so a bad adapter can be disabled without losing workspace access.

Exit code contract:

- `0`: gate passed, or returned a non-blocking status.
- `2`: gate returned `blocked`; stop unless a human explicitly confirms the current action.
- other: runtime error, missing dependency, malformed input, or adapter failure.

Status contract:

- `pass`: no blocking issue found.
- `blocked`: required boundary, evidence, or confirmation is missing.
- `cross_reference_allowed`: memory path is outside the active lane but was explicitly allowed as a cross-reference.

For Bash environments, use the scripts under `skills/embedded-harness/bash`. They require `jq` and share the same `embedded_harness_policy.json`.

For hosts that own an in-process Python agent loop, `integrations/workbuddy-python-runtime` is a small reference adapter. It reuses the same policy file and exposes Python functions for routing, memory isolation, claim checks, and runtime enforcement decisions. It is not automatically wired into WorkBuddy or any other client. Hard enforcement requires the host to call the function before action execution and to stop on `status: blocked`.

Adapter validation is local by default. Do not claim PowerShell, Bash/macOS/Linux, or WorkBuddy Python compatibility until you have run the relevant smoke checks on the target device and client version.

## Step 4a: Configure Search And Learning Routes

Tune `search_and_learning_decision_matrix` and `external_research_triggers` in `skills/embedded-harness/embedded_harness_policy.json`.

Use separate routes for:

- official or authority source checks for drift-prone public facts;
- GitHub or open-source repository inspection for repository claims and reuse boundaries;
- general web cross-checks for ecosystem context and uncertain public claims;
- source-grounded learning intake for external mechanisms and external architecture comparison;
- local validation before claiming adoption, success, performance, or compatibility.

For external mechanism intake, write a compact source ledger before adapting anything:

```text
source
date checked
claim or mechanism
classification label
applicable boundary
non-applicable boundary
risk
validation path
adoption decision
```

Recommended labels are `fact`, `source_prior`, `hypothesis`, `inspiration`, `unverified_implementation_path`, `not_applicable`, and `local_validated`. Reserve `local_validated` for evidence produced in the adopting workspace.

## Step 5: Keep The Core Clean

The whiteboard core should not contain private project content. Add project rules, real memory capsules, and solved incident records inside the adopting project only.

Use the public demo records as shape examples only. They are synthetic and are not claims about your environment.

## Step 6: Keep Versions In Sync

When publishing changes to an adopted copy or fork, update the version metadata in the same change:

- `VERSION`;
- `CHANGELOG.md`;
- any README line that displays the current version.

Use `vMAJOR.MINOR.PATCH` labels. For early framework work, keep `MAJOR` at `0` until the layout and adoption contract are stable.

## Project Lane Isolation

For multi-project use, create one lane per project in the harness policy and one registry entry per project in `PROJECT_SKILL_MATRIX_REGISTRY.md`.

Each lane should have its own:

- project instruction entry;
- memory roots;
- optional project router;
- incident records;
- retrieval log.

Shared rules should stay in the whiteboard core. Project-specific rules should stay inside the project lane. This keeps separate projects usable across new conversations without mixing unrelated memory, progress, or failure records.

## After Agent Client Updates

Agent clients may change executable locations, bundled runtime paths, skill discovery behavior, or hook launch environments across releases. After a client update, re-run the local smoke checks before trusting the chain.

Recommended update check:

1. Confirm the root instruction entry is still loaded.
2. Confirm the intake router still runs.
3. Confirm skill or command folders are still discoverable.
4. Confirm hook or wrapper paths still point to existing files.
5. Confirm project memory roots still pass the isolation gate.
6. Run one mixed-risk route, one memory check, one source-check trigger, and one claim check.

If an agent supports wrapper scripts, keep a small client-health script near the adapter layer. That script should detect path drift and report issues first. Automatic repair should be opt-in because client config files are part of the user's local environment.

## Non-Goals

Before expanding the framework, review [non-goals.md](non-goals.md). Package-manager distribution, broad dashboards, promotion work, large comparison tables, and full test matrices are intentionally excluded from the whiteboard core.
