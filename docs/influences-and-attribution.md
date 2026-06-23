# Influences And Attribution

Claim Boundary Harness is a composed framework. Some parts are independent
design choices in this repository, and some parts are adapted from public
projects or established engineering patterns. This page keeps that boundary
explicit.

External references are source-prior inputs. They are useful for design,
terminology, and validation ideas, but they do not prove this framework works in
an adopting runtime until local smoke checks pass.

## Public GitHub Influences

| Source | Absorbed or adapted ideas | Boundary |
| --- | --- | --- |
| Microsoft SkillOpt: https://github.com/microsoft/SkillOpt | Candidate skill edits, validation-gated updates, rejected-edit buffers, textual learning-rate limits, slow/meta update boundaries, and a deployable skill-artifact mindset. | This repository does not vendor SkillOpt code, training loops, datasets, benchmark harnesses, model backends, dashboard code, or benchmark claims. `tools/skillopt/skillopt_cycle.py` is an independent lightweight cycle runner. Direct upstream use should be an optional external adapter or separate install. |
| rohitg00/agentmemory: https://github.com/rohitg00/agentmemory | Lifecycle hook coverage, explicit memory command semantics, memory retrieval metadata pressure, and client-update hook drift concerns. | This repository does not require an external memory backend, memory server, vector database, automatic cross-agent shared memory, or automatic memory mutation. Project, conversation, common-error, and archive lanes remain isolated. |
| LanNguyenSi/harness: https://github.com/LanNguyenSi/harness | Declarative control-plane vocabulary, adapter compatibility thinking, evidence-ledger and policy/enforcement separation ideas. | This repository does not require its manifest format, CLI, Rego-like policy layer, generated runtime config, or always-on hook enforcement. |
| epicsagas/epic-harness: https://github.com/epicsagas/epic-harness | Hook health, pipeline state, multi-tool harness framing, and self-improvement as a staged maintenance concern. | This repository does not adopt always-on self-evolution, autonomous spec-to-PR behavior, or unified memory as the default. |
| ChatBotKit template-node-agent-cli-js: https://github.com/chatbotkit/template-node-agent-cli-js | Tool schema, CLI-agent structure, and structured command-output inspiration. | This repository does not depend on ChatBotKit or its SDK. |

## Established Pattern Influences

| Pattern | Absorbed idea | Boundary |
| --- | --- | --- |
| Policy decision point / policy enforcement point separation | Keep routing decisions separate from actual execution or blocking. | This is not a complete policy engine and does not become a sandbox unless the adopting runtime honors the gate. |
| Admission-control style hooks | Check critical actions before persistence or execution. | Only critical risks should be hard-gated; ordinary tools stay low cost. |
| Append-only ledgers | Keep decision, error, solution, and rejected-edit records auditable. | Records are lightweight files, not a database by default. |
| Structured provenance | Carry source, confidence, and derivation fields with reusable memory. | Provenance fields do not make a claim true; they preserve the evidence boundary. |
| Meta-first retrieval | Read summaries and indexes before opening deep payloads. | This is a retrieval discipline, not a guarantee of semantic correctness. |
| Project manuals and wiki-style knowledge bases | Keep stable module maps, commands, conventions, and interface notes close to the repository. | Static notes are source-prior orientation aids until checked against files, tests, or other evidence. |

## Project Contributions

The repository's own contribution is the combined boundary contract and runnable
whiteboard package:

- a claim-boundary vocabulary that separates source-prior, bounded claim,
  local validation, conflict, and rejection states;
- a low-cost router receipt that decides memory, external search, skill,
  claim, and runtime-gate needs before opening larger context;
- project, conversation, common-error, and archive memory lanes with explicit
  cross-lane boundaries;
- retrieval-result requirements that carry `source_tag`, `derived_from`,
  `belief_status`, structured `confidence`, and `score_method`;
- an optional static knowledge layer that adapts wiki-style project manuals into
  indexed, source-prior, claim-bounded agent context;
- selective hard gates that apply only when an adopting runtime actually calls
  the hook, wrapper, or tool proxy;
- a default-off external SkillOpt-style cycle runner that generates and gates
  candidate skill improvements without mutating primary skills.

Those contributions are a composition and adaptation layer, not a claim that
each underlying mechanism was invented here.
