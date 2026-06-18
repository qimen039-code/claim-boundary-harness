# Deployment Risk Patterns

Use this guide when adapting Agent Memory Lane Harness into an agent runtime.

The WorkBuddy case shows the core deployment risk: copying the harness files is not the same as wiring the harness into the execution path. If the agent runtime does not call the gate before the protected action, the harness remains advisory for that action.

This document is intentionally version-neutral. Agent clients change hook names, config locations, environment variables, and tool schemas. Treat every product-specific integration as unverified until it passes the local acceptance tests below.

## Deployment Levels

| Level | What is wired | What it can enforce |
| --- | --- | --- |
| L0 instruction only | Root instructions such as `AGENTS.md`, `CLAUDE.md`, or workspace rules | Soft behavior contract only. Useful but not a hard stop. |
| L1 advisory control plane | Intake router, memory/search/claim gates called by the agent or user | Structured decisions and receipts. Hard only if the caller obeys them. |
| L2 selective hard gates | Pre-task, pre-tool, command wrapper, or final-answer hook for critical boundaries | Can block the paths that actually pass through the hook or wrapper. |
| L3 tool proxy / in-process middleware | All protected tool execution goes through one policy function or proxy | Stronger runtime enforcement for covered tools. Bypass paths still matter. |
| L4 sandbox/runtime enforcement | The host runtime or sandbox owns the policy check before execution | Physical blocking for covered execution paths. Requires host/runtime support. |

Most adopters should aim for L1 plus L2. Do not try to wrap every tool call until the selective hard gates are reliable.

## Agent Runtime Families

| Runtime family | Typical integration surface | Main deployment risk | Practical solution |
| --- | --- | --- | --- |
| Instruction-file agents | Workspace rule files, project docs, memory files | The file is present but not loaded by the agent | Ask the agent to report the routing receipt on a test task, and keep a visible root instruction entry. |
| CLI agents with hooks | Pre-prompt, pre-tool, post-tool, stop hooks | Hook exists but is not on the actual execution path | Place the gate at the earliest pre-execution hook and verify a blocked action never reaches the tool. |
| IDE or desktop agents | IDE extension settings, tool executor pipeline, output gate | UI actions, background tasks, or built-in tools bypass the wrapper | Identify every tool execution surface and mark unhooked surfaces as advisory. |
| Custom orchestrators | Python/Node middleware, tool registry, function dispatcher | Policy is called after execution or its result is ignored | Put `runtime_enforcer` before dispatch and raise/return a blocking error on `status: blocked`. |
| Hosted or SaaS agents | Limited settings, system prompts, external tools | No local pre-tool hook is available | Treat the harness as advisory, or move protected actions behind an external proxy you control. |
| Terminal-only assistants | Shell aliases, wrapper scripts, project instructions | Users or tools can call the raw shell directly | Use wrappers for high-risk commands and state clearly that raw shell paths bypass enforcement. |

## Common Deployment Failures And Fixes

| ID | Symptom | Likely cause | Fix | Acceptance check |
| --- | --- | --- | --- | --- |
| DEP-001 | The harness files exist but behavior does not change | The agent never loaded the root instruction file | Map `AGENTS.md` to the instruction filename or settings surface the agent actually reads | Ask for a routing receipt on a mixed-risk task and verify the expected gates are named |
| DEP-002 | The router runs, but dangerous tools still execute | The pre-tool hook or wrapper is not in the execution path | Wire the gate into the runtime's earliest pre-execution surface | Run a disposable high-risk command test and confirm it is blocked before execution |
| DEP-003 | The hook runs, returns blocked, but the tool still runs | The host ignores the hook result, exit code, or denial schema | Use the host-supported denial format and exit code; if unsupported, mark the path advisory | Confirm logs show both hook invocation and blocked tool suppression |
| DEP-004 | A command wrapper works in tests but not during agent use | The agent uses another shell, terminal, or internal tool executor | Identify the actual executor and move the wrapper there | Compare wrapper logs with the agent's real tool calls |
| DEP-005 | `PreToolUse` routing is wrong or loses context | The pre-tool event lacks the original user prompt | Store prompt/session state at prompt submit time and reload it in pre-tool checks | Verify the pre-tool log contains the original task text, not only `R5` or a compact receipt field |
| DEP-006 | Hook command fails only on Windows or only on macOS/Linux | Shell, quoting, executable bit, path separator, `bash` availability, or Python launcher differs | Use explicit shell invocation, quote workspace paths, and expose `PYTHON_BIN` or equivalent; on Windows use `cmd.exe` wrappers when Bash is unavailable | Run the hook command from the same shell the agent uses |
| DEP-007 | The adapter passes unit tests but not inside the agent | Tests cover the decision layer, not the host hook pipeline | Add one end-to-end blocked-action test inside the actual agent runtime | Confirm the protected action never happens, not just that the adapter returned `blocked` |
| DEP-008 | Logs are missing or permission errors appear | Log directory is treated as a file, blocked by sandbox policy, or outside the workspace | Use a workspace-local log directory and create it before enforcement | Verify the JSONL event file is written after both pass and block cases |
| DEP-009 | Memory isolation appears to work but cross-project data leaks | Memory roots are broad, symbolic paths are unresolved, or the agent reads memory before the gate | Use resolved absolute roots and run memory isolation before payload reads | Test allowed root, sibling-prefix blocked root, and cross-lane blocked root |
| DEP-010 | Final answer still overclaims weak evidence | The claim gate lacks the actual final response body | Pass final text into the final-answer gate, or downgrade final claims when final text cannot be checked | Test a final sentence containing a strong claim and confirm it blocks or is downgraded |
| DEP-011 | External research rules are skipped for current facts | Search gate is advisory and not connected to dynamic re-evaluation | Trigger search gate on currentness, version, GitHub, legal, policy, price, or release-date claims | Ask for a latest/current version claim and verify the route demands external evidence |
| DEP-012 | Hooks stop working after a client update | Client paths, hook names, bundled runtimes, or config schema changed | Run adapter smoke tests after every client update before trusting enforcement | Use the update smoke checklist in `docs/adoption.md` |
| DEP-013 | Public repository examples leak local settings | Local hook configs or personal paths were committed | Keep product-specific local settings out of the public package; publish templates only | Scan docs and examples for local paths, private project names, and credential-like fields |
| DEP-014 | Everything becomes slow after adoption | The adapter wraps every tool call or loads all memory/skills by default | Keep L0/L1 cheap and use event-triggered expansion; hard-wrap only critical risks | Compare ordinary read-only task latency before and after adoption |
| DEP-015 | `--fail-open` remains enabled | Setup diagnostics were left in production mode | Remove fail-open flags after first-time hook setup | Force a hook-runner error and confirm high-risk pre-tool calls fail closed |
| DEP-016 | Human confirmation becomes too broad | A confirmation flag is reused for future actions | Bind confirmation to the current concrete action only | Confirm a second destructive action still requires a fresh confirmation |
| DEP-017 | Built-in background actions bypass gates | The agent performs background indexing, auto-fixes, or hidden commands outside tool hooks | Identify background execution surfaces and mark unhooked surfaces advisory | Check runtime logs during startup, indexing, and automatic actions |
| DEP-018 | Tool input parsing misses dangerous commands | The command is nested under a tool-specific field not parsed by the adapter | Update the adapter to inspect the actual tool schema used by the host | Capture one real tool event JSON and verify hard patterns are detected |
| DEP-019 | Hook runner logs `codec can't encode character '\ud...'` | Host stdin JSON decoded to lone UTF-16 surrogate values, then output/logging writes them as Unicode | Sanitize hook payloads before routing and log/output writes; prefer ASCII-escaped hook output | Replay a captured hook payload with `\udcac` or `\udc80` and confirm routing still returns context |
| DEP-020 | Pre-tool blocking works, but the agent says it did not proactively route the task | Only the tool-stage hook is wired, or the prompt-stage hook failed before adding route context | Wire `UserPromptSubmit` or equivalent prompt-stage hook to store the original prompt and inject compact route context | Start a normal task and confirm the agent receives a compact routing receipt before tool planning |

## Agent-Facing Troubleshooting Runbook

When an adopting agent reports "the harness is deployed but it does not behave like a hard gate", do not guess from repository files alone. Check the actual runtime path in this order.

### 1. Confirm The Instruction Entry Is Loaded

Inspect:

- workspace root instruction file, such as `AGENTS.md`, `CLAUDE.md`, or the agent's configured rules file;
- agent settings page or config file that declares instruction paths;
- the first agent response after a test prompt.

Test:

```text
Ask the agent: "Classify this task with the harness routing receipt: edit code, run a benchmark, then commit."
```

Expected:

- the response mentions a routing receipt or equivalent route;
- risk is not treated as ordinary chat;
- R5 actions such as commit require explicit confirmation.

If this fails, fix the instruction entry before debugging hooks.

### 2. Confirm The Gate Works Outside The Agent

Inspect:

- harness root path;
- policy file path;
- Python, PowerShell, Bash, or Node runtime availability;
- adapter logs and standard output.

Test the gate directly from the same workspace:

```text
Run the intake router or runtime enforcer directly with a known high-risk task.
```

Expected:

- allowed tasks return pass;
- high-risk tasks return blocked;
- the gate exits with the documented blocked code when the script supports exit codes.

If direct execution fails, the problem is adapter setup, dependencies, policy JSON, quoting, or file paths. Do not debug the agent hook yet.

### 3. Confirm The Hook Command Runs In The Agent's Real Shell

Inspect:

- hook settings or hook UI;
- the exact command string stored in the agent config;
- the shell used by the hook runner;
- `cwd`, `PATH`, Python launcher, Bash availability, and environment variables exposed inside hooks.

Test:

```text
Run the exact hook command from the same shell style the agent uses.
```

Expected:

- the hook command can import the adapter;
- it can read stdin JSON;
- it can write its log directory;
- it returns the same decision as the direct gate test.

If direct gate works but the hook command fails, the problem is shell quoting, path expansion, missing environment variables, executable permissions, or runtime discovery.

### 4. Capture One Real Hook Event Payload

Inspect:

- hook debug logs;
- the harness JSONL log file;
- event fields such as event name, session id, cwd, tool name, and tool input;
- state file used to preserve the original prompt.
- raw stdin JSON when the hook runner reports decoding or encoding errors.

Expected fields:

```text
hook event name
session id or conversation id
cwd / workspace root
tool name
tool input
original user task or stored prompt state
```

If the payload lacks the original task, add a prompt-stage hook that stores it. If the tool command is nested in an unexpected field, update the adapter to parse that field.

If the payload contains invalid Unicode such as lone surrogate escapes (`\udcac`, `\udc80`), sanitize nested strings before routing, state writes, JSONL logging, or hook output. Do not rely on the host to clean these values.

### 5. Confirm The Host Honors The Blocked Result

Inspect:

- hook return payload;
- process exit code;
- host documentation for deny/block semantics;
- agent runtime logs around the tool call.

Test:

```text
Use a disposable workspace and attempt a known blocked action through the normal agent path.
```

Expected:

```text
hook runs before tool execution
hook returns blocked / deny
hook exits with the host-supported blocked code
tool does not execute
```

If the hook returns blocked but the tool still runs, the issue is not the harness policy. The host is ignoring the hook result, the hook is attached to the wrong event, or that specific tool path bypasses hooks.

### 6. Search For Bypass Paths

Inspect every action surface the agent can use:

- shell command execution;
- file edit tools;
- package installation tools;
- browser or network tools;
- memory read/write tools;
- background indexing or auto-fix tasks;
- built-in commit, deploy, or project-management actions;
- secondary terminals or remote runners.

For each surface, classify it:

```text
hard-gated
advisory only
not covered
unknown, needs test
```

Do not claim full hard enforcement while any protected action still has an untested or known bypass path.

### 7. Check Memory, Search, And Final-Claim Stages Separately

These are often not the same hook as tool execution.

Inspect:

- memory root resolution and meta-index lookup;
- external research trigger route;
- final answer or output gate;
- whether final text is available before display.

Tests:

```text
Memory: allowed memory path passes, sibling or cross-lane path blocks.
Search: latest/current/GitHub/release-date task routes to external research.
Final claim: strong claim without evidence schema blocks or is downgraded.
```

If these fail while pre-tool blocking works, the tool hook is deployed but the memory/search/final-answer surfaces are not.

### 8. Diagnose By Failure Boundary

Use this decision tree:

| Observation | Boundary | Likely fix |
| --- | --- | --- |
| Direct gate fails | adapter/policy/runtime | Fix dependencies, policy JSON, script path, or shell quoting. |
| Direct gate passes, hook command fails | hook shell/environment | Fix hook command path, env vars, Python/Bash launcher, cwd, or quoting. |
| Hook command passes, agent tool still runs | host integration | Move hook to the pre-execution event or use the host's required denial schema / exit code. |
| One tool blocks, another bypasses | coverage | Wire every protected tool surface or document uncovered paths as advisory. |
| Prompt route is correct, pre-tool route is wrong | state transfer | Store original prompt at prompt-submit time and reload it during pre-tool checks. |
| Tests pass until client update | drift | Re-check client version, hook schema, paths, bundled runtimes, and settings format. |

## Mainstream Agent Checklist

Use this checklist for Codex, Claude Code, WorkBuddy, IDE agents, terminal assistants, and custom agent frameworks.

1. **Instruction entry:** which file or setting is actually read by the agent?
2. **Prompt stage:** is there a prompt-submit or pre-task surface where routing can store the original task?
3. **Tool stage:** is there a pre-tool hook, tool proxy, middleware, or command wrapper that runs before the action?
4. **Block semantics:** does the host support a denial payload, nonzero exit code, raised exception, or policy decision that stops execution?
5. **Bypass surfaces:** can the agent still run shell, file, browser, network, package-manager, or memory actions through another path?
6. **State preservation:** can pre-tool checks access the original user task, cwd, session id, project lane, and receipt?
7. **Final answer surface:** can the final response text be checked before display? If not, require self-downgrade language.
8. **Memory surface:** are memory reads/writes routed through meta-first and lane-isolation checks?
9. **External facts:** are currentness and GitHub/open-source triggers connected to a real research route?
10. **Update drift:** what smoke test runs after the agent client updates?

## Minimal Acceptance Tests

Run these before claiming that the harness is deployed in an agent runtime:

1. **Instruction load test:** ask the agent to classify a mixed-risk task and report a compact routing receipt.
2. **Allowed action test:** run a harmless read-only command through the normal agent path and confirm it proceeds.
3. **Blocked action test:** in a disposable workspace, attempt a known high-risk action and confirm it is stopped before execution.
4. **Bypass test:** try the other tool surfaces the agent can use and document which are hard-gated versus advisory.
5. **Memory isolation test:** test one allowed memory path and one sibling-prefix or cross-lane blocked path.
6. **Current fact test:** ask for a latest/current or GitHub/release claim and confirm the external research route is triggered.
7. **Final claim test:** attempt a strong claim without evidence schema and confirm it blocks or downgrades.
8. **Client update test:** after updating the agent client, re-run tests 1 through 4 at minimum.

## Public Documentation Rule

Public deployment docs should describe reusable setup patterns and templates, not one maintainer's private configuration. Do not publish local settings files, private project paths, real memory records, personal machine paths, credentials, auth values, or screenshots that reveal local state.

When a product-specific behavior has not been tested on the adopter's exact version, say so. Use wording such as:

```text
This adapter was tested as a local decision layer. Hard enforcement depends on your agent runtime honoring the pre-tool hook or wrapper result.
```
