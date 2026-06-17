# Examples

## Example 1: Mixed Code And Benchmark Task

Input:

```text
fix the script and run benchmark
```

Expected route:

- risk label: `R4`;
- triggered risks: `R4`, `R3`;
- required gates include change contract, claim gate, external research gate, and verification gate.

## Example 2: Vague Project Task

Input:

```text
handle this project issue
```

Expected route:

- risk label: `R0`;
- confidence: low;
- fallback review recommended.

The point is not to treat vague work as safe. The router marks uncertainty so the agent should do a small boundary review.

## Example 3: Memory Boundary Check

Input:

```text
Project lane: EXAMPLE_PROJECT
Requested path: C:\path\to\project\.agent-memory\note.md
```

Expected route:

- status: pass;
- reason: requested path is inside active project memory roots.

## Example 4: Strong Claim Check

If a final answer says a result is validated without a claim record, the claim verifier should block it. Add a claim object with source type and evidence boundary before making strong claims.

## Example 5: Project Memory Capsule

See [../examples/memory-capsule-examples.md](../examples/memory-capsule-examples.md) for a synthetic project memory capsule. The important properties are:

- one active lane owns the record;
- the retrieval surface is short and searchable;
- source and evidence boundaries are explicit;
- applicable and non-applicable boundaries are both present;
- cross-project reuse requires explicit user intent.

## Example 6: Paired Error And Solution Records

The same example file includes `ERR-EXAMPLE-CLIENT-DRIFT-001` and `SOL-EXAMPLE-CLIENT-DRIFT-001`.

The pair shows why solved incidents should not become vague advice. The error record preserves the failure condition; the solution record preserves the investigation order, fix path, rollback, validation, caveats, and future reuse rule.

## Example 7: Bounded Skill Addition

The framework does not continuously generate active skills. When reusable knowledge is helpful but does not need a new execution capability, store it in a project memory capsule, paired incident record, reference pack, or examples folder. Promote it to a new skill only when repeated use, narrow scope, and clear non-applicable boundaries make the extra active capability worth the routing cost.

## Example 8: Layered Memory Library

See [../examples/memory-library-demo/_META_INDEX.md](../examples/memory-library-demo/_META_INDEX.md) for a complete synthetic library.

The retrieval path is mandatory:

```text
read _META_INDEX.md
-> choose governance, memory_hierarchy, external_references, or raw_logs
-> read only that category _INDEX.md
-> open only the matching capsule
```

This keeps memory lookup cheap and prevents a single summary file from becoming a second hidden conversation history.
