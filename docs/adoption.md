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

## Step 5: Keep The Core Clean

The whiteboard core should not contain private project content. Add project rules, real memory capsules, and solved incident records inside the adopting project only.

Use the public demo records as shape examples only. They are synthetic and are not claims about your environment.

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
