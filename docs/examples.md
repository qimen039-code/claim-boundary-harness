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
Requested path: C:\path\to\project\.agent-memory\memory-item.md
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

## Example 9: Source-Grounded Learning Intake

Input:

```text
review this open-source harness idea and see whether we should absorb it
```

Expected route:

- risk label: `R4`;
- external research required;
- recommended search modes include GitHub/open-source repository search and source-grounded learning intake;
- output should classify findings as `fact`, `source_prior`, `hypothesis`, `inspiration`, `unverified_implementation_path`, or `not_applicable`;
- no claim of local validation until the mechanism is tested or otherwise verified in the adopting workspace.

Minimum source ledger shape:

```text
source | checked date | mechanism | label | applicable boundary | non-applicable boundary | risk | validation path | adoption decision
```

## Example 10: Governance Rule Update

Input:

```text
refine the dynamic evaluation decision layer and update routing triggers
```

Expected route:

- risk label: `R3`;
- required gates include project context, change contract, and claim gate;
- if the deterministic router misses this pattern, record the miss as a routing-rule gap and add the narrowest useful trigger terms.

## Example 11: Runtime Tool Proxy Block

Input:

```text
Task: commit and push changes
Tool: shell_command
Tool input: {"command":"git commit -am update"}
```

Expected route:

- runtime stage: `pre_tool`;
- status: `blocked`;
- blocked reasons include R5 or high-risk tool call without human confirmation.

The same proxy may pass after explicit human confirmation, but the confirmation should come from the user or adopting runtime policy, not from the agent silently setting a flag.

## Example 12: Advisory Control Plane Without Tool Wrapping

Input:

```text
inspect the local project structure and summarize the relevant files
```

Expected route:

- create a lightweight routing receipt;
- risk label is likely `R1`;
- no tool proxy is needed for ordinary read-only commands;
- final answer should still mention any unverified boundary if the inspection was incomplete.

The control plane is mandatory for nontrivial work, but it should not turn every file read into a hard runtime gate.

## Example 13: Conversation Memory Lane

Input:

```text
checkpoint this conversation so we can continue this conversation later
```

Expected route:

- `conversation_memory_decision`: `create_or_update_current_conversation`;
- `memory_lane`: `current_conversation`;
- `memory_mode`: `write`;
- `record_intent`: `explicit_conversation_memory_request`;
- retrieval must start from `conversation-memory/_META_INDEX.md`.

This is not a project memory write and not a global memory write. Other conversations may read this lane only by explicit reference, and cross-conversation writes require explicit user instruction.

## Example 14: Format Layering

If a record will be edited by agents repeatedly, do not make a large Markdown table the source of truth.

Use:

```text
README explanation -> Markdown
router facts -> JSON
decisions/open loops/errors/references -> JSONL
large matrices -> CSV or generated Markdown
queryable state -> SQLite or another local database
```

## Example 15: Cold Archive Operation

Input:

```text
archive this finished conversation memory lane
```

Expected default operation:

```text
ARCHIVE_MOVE or ARCHIVE_COPY
```

The agent should move or copy the source lane directory/file, update archive indexes, and preserve source references. It should not regenerate the old memory as a new summary file and then delete the original. Summary capsules require explicit compression, migration, de-identification, public-release, or storage-reduction intent.

## Example 16: Conversation-Only Persona

Input:

```text
use a warmer companion style in this chat
```

Expected boundary:

- persona state is current-conversation only;
- default global propagation is off;
- project propagation is off;
- work decisions still use evidence, gates, risk rules, and verification;
- persona cannot affect factual claims, tests, memory boundaries, or external research decisions.

## Example 17: Source-Monitoring Memory Capsule

Input:

```text
turn this external mechanism note into a reusable memory capsule
```

Expected route:

- read the memory meta index first;
- classify the note as source-derived or synthesized before writing;
- write required source-monitoring fields: `source_tag` `belief_status` `confidence` `derived_from`, plus lifecycle metadata;
- keep optional numeric scores out of the core capsule unless an adapter actually computed them;
- mark untested adoption claims as `source_prior` or `bounded_claim`, not `local_validated`.

Minimum capsule fields:

```text
source_tag
belief_status
confidence.label
confidence.basis
derived_from
source_monitoring
lifecycle
belief_trace_summary
```

See [source-monitoring-memory-schema.md](source-monitoring-memory-schema.md) for conditional rules such as `score` / `score_method`, `corrects` requiring correction evidence, and `belief_trace_summary.current_status` matching `belief_status`.

## Example 18: Bounded Memory Retrieval Result

Input:

```text
retrieve the memory that explains this adapter failure
```

Expected returned result:

```json
{
  "memory_id": "MEM-EXAMPLE-001",
  "snippet": "Short selected text only.",
  "source_tag": "memory_capsule",
  "belief_status": "bounded_claim",
  "confidence": {
    "label": "medium",
    "basis": "Status came from a reusable capsule; this retrieval did not rerun local tests."
  },
  "derived_from": [
    {
      "type": "previous_capsule",
      "ref_id": "MEM-EXAMPLE-000",
      "relationship": "distilled_from",
      "inherited_boundary": "source_prior"
    }
  ],
  "score_method": "none"
}
```

A text-only result is not enough for reusable memory. It may help the agent search, but it cannot be used as validated guidance without source and belief-state metadata.
