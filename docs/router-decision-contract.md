# Router Decision Contract

The router and dynamic decision layer are the front door of the framework. They must stay cheap enough to run on every nontrivial task, but precise enough to decide which deeper module is worth opening.

## Contract

For any nontrivial task, produce or internally satisfy this minimal receipt before doing expensive work:

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
receipt_profile
required_gates
```

Field meanings:

| Field | Purpose |
| --- | --- |
| `task_type` | Classify ordinary chat, read-only inspection, documentation, code/config change, runtime/current-fact work, or high-risk action. |
| `target_surface` | Name the surface being changed or consulted: public docs, local harness, project memory, skill matrix, tool call, adapter, git action, or private rule. |
| `audience` | Separate public users, local maintainer, project-only operator, or current chat. |
| `project_lane` | Keep memory and project instructions scoped to one lane unless cross-project work is explicit. |
| `risk_level` | Use additive R0-R5 routing; keep the highest risk and union of gates. |
| `semantic_ambiguity` | Mark terms that could mean multiple actions, such as update, record, publish, call, route, memory, or skill. |
| `module_need` | Decide whether to use no module, project router, semantic anchors, skill matrix, memory meta index, external research gate, claim verifier, or runtime hard gate. |
| `memory_need` | Decide whether memory is unnecessary, meta-only, index-only, capsule-level, or paired ERR/SOL retrieval. |
| `memory_mode` | Decide whether memory should be skipped, read, written, or updated. |
| `memory_lane` | Decide whether the memory action belongs to a current project, emergent project candidate, common error corpus, self-reflection matrix, global inbox, or no lane. |
| `record_intent` | Decide whether there is no record request, explicit user request, inferred reusable error, or projectization review. |
| `external_need` | Decide whether external lookup is unnecessary, official-source, GitHub/open-source, general cross-check, source-grounded learning, or local validation. |
| `claim_risk` | Decide whether the final answer contains an operational note, a weak claim, or a strong factual claim needing schema evidence. |
| `projectization_decision` | Decide whether projectless work is still not a project, belongs to a current project, or should be treated as an emergent project candidate. |
| `receipt_profile` | Decide whether to expose a compact runtime receipt, expanded governance receipt, or debug receipt. |
| `required_gates` | List the concrete gates to run or honor. |

## Receipt Profiles

The router should compute the full decision internally, then expose the smallest useful surface:

| Profile | Use when | Expose |
| --- | --- | --- |
| `compact_runtime` | Default local runtime, single-user agents, ordinary R1-R5 checks where no public/private or governance ambiguity exists. | Risk, gates, memory mode/lane, external need, claim risk, human confirmation need. |
| `extended_governance` | Public docs, local harness, adapters, project memory, semantic ambiguity, memory writes, projectization drift, or audience-boundary work. | Full governance receipt fields. |
| `debug_receipt` | Router debugging, misroute analysis, or user asks for full receipt. | Full receipt plus matched/negated triggers, confidence, and profile reasons. |

This keeps WorkBuddy-like local adapters cheap while preserving the full whiteboard schema for migration, audits, and public framework work.

## Low-Cost Rule

Do not load all skills, all memory, or all history because this contract exists. The preferred expansion order is:

```text
L0 microkernel
-> router decision contract
-> one matching project or skill entry
-> one needed gate
-> one needed index
-> only matching payload
```

If the receipt is obvious from the current request, it can stay implicit. If the task is R3 or higher, boundary-sensitive, or likely to be audited later, keep the receipt explicit in logs or a task note.

## Dynamic Re-Evaluation Triggers

Re-run the contract when any of these appears:

```text
new evidence
missing file
tool error
scope change
user correction
cross-project term
public/internal audience ambiguity
version/currentness claim
GitHub or open-source mechanism
cost or risk escalation
before a strong factual claim
before R5 action
before long-term memory write
```

## Source-Grounded Influences

This contract adapts several established ideas as lightweight design influences:

| Influence | Absorbed mechanism | Boundary |
| --- | --- | --- |
| Open Policy Agent | Separate the decision point from the execution/enforcement path. | This framework is not OPA and does not require Rego. |
| Kubernetes admission control | Run checks before critical persistence or execution boundaries. | Only selected hard gates should intercept; ordinary tools stay cheap. |
| OpenTelemetry sampling | Control emitted detail to balance usefulness and overhead. | Receipt profiles are not telemetry sampling; they only decide how much routing context to expose. |
| LangChain middleware | Use lifecycle hooks or wrap-style interception for cross-cutting concerns. | The framework stays runtime-neutral and does not require LangChain. |
| LlamaIndex and Haystack routers | Select a candidate tool, route, or retrieval path from metadata instead of opening everything. | Router output is a control receipt, not an autonomous success claim. |
| OODA loop | Reassess when the situation changes. | Reassessment is trigger-based, not continuous deliberation. |
| Cynefin-style sensemaking | Match response style to context uncertainty. | The public contract uses simple fields instead of complex domain taxonomy. |
| FMEA | Think about likely failure modes before changing a process. | Only high-risk or repeated failure modes need detailed records. |
| RACI-style role clarity | Separate public, local maintainer, project, and current-chat audiences. | The framework does not add organization-heavy role management. |

External references are source-prior design inputs. They do not prove this framework works in a target agent until the adopting environment runs local smoke checks.
