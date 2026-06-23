# Non-Goals

These items are intentionally out of scope for the whiteboard package. They can be added by downstream adopters, but they should not be treated as missing P0 work.

| Non-goal | Reason |
| --- | --- |
| Package-manager distribution | The framework should stay copyable, inspectable, and easy to adapt while the rule contract is still early. |
| Python or Node script ports | PowerShell and Bash cover the current reference surfaces. More ports would increase drift until adoption contracts stabilize. |
| Community boilerplate such as contribution templates or stale automation | Useful for mature projects, but not needed to validate the harness chain itself. |
| Monitoring dashboards | The current package is a local gate and memory-lane framework, not an operations monitoring system. |
| Full memory backend or shared memory server | The core defines routing, source boundaries, and lane isolation. Downstream adopters may connect a database, vector search, graph search, MCP memory tool, or server, but that backend is not part of the default whiteboard core. |
| Automatic cross-agent memory sharing | Shared recall is useful only after lane IDs, source-monitoring fields, and explicit cross-lane rules are in place. Default sharing would weaken the project-isolation goal. |
| Large compatibility database | The compatibility manifest should describe the adapter at hand, not become a global matrix of every agent runtime and version. |
| Every-turn compatibility scanning | Compatibility checks are for setup, client updates, hook or wrapper edits, failed smoke tests, or explicit audits. Running them on ordinary tasks would waste context and latency. |
| Promotion material or repository-topic tuning | Discovery work should not drive core architecture changes. |
| Full test matrix | The public core keeps only a lightweight smoke workflow. Downstream adopters should add deeper tests for their runtime. |
| Full comparison table against other frameworks | Short positioning is enough here. Large comparisons become stale and invite unsupported claims. |

Before adding any of these, define the owner, maintenance cost, validation path, and whether the addition belongs in the public core or an adopter-specific fork.
