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

## Project Lane Isolation

For multi-project use, create one lane per project in the harness policy and one registry entry per project in `PROJECT_SKILL_MATRIX_REGISTRY.md`.

Each lane should have its own:

- project instruction entry;
- memory roots;
- optional project router;
- incident records;
- retrieval log.

Shared rules should stay in the whiteboard core. Project-specific rules should stay inside the project lane. This keeps separate projects usable across new conversations without mixing unrelated memory, progress, or failure records.
