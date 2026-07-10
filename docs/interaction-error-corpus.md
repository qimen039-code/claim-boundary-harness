# Interaction Error Corpus

The interaction error corpus is one lane-scoped common-error collection for
tool and UI control mistakes. It prevents keyboard/mouse details from loading
during structured API work while preserving a bounded fallback path between
control surfaces.

## Four Lanes

| Lane | Use when | Typical evidence |
| --- | --- | --- |
| `structured-tool-control` | MCP, API, connector, application-code, or other structured calls are available. | Request/response payload, tool schema, exit or status result. |
| `browser-control` | The task depends on DOM, accessibility, browser state, navigation, or web-session semantics. | DOM/accessibility snapshot, URL, browser action result. |
| `desktop-app-control` | The target is a native app or visual surface without a sufficient structured interface. | Window identity, visual state, application response. |
| `keyboard-mouse-control` | Deterministic input is the last suitable control surface. | Focus target, coordinates or key sequence, post-action state. |

## Retrieval And Fallback

```text
interaction-error-corpus/_META_INDEX.md
-> one matching lane/_INDEX.md
-> at most two matching CE payloads
```

Prefer the highest-semantic surface that can complete the task:

```text
structured tool
-> browser semantics
-> desktop visual control
-> deterministic keyboard/mouse
-> stop or user takeover
```

Do not load this corpus for ordinary tasks. Read one adjacent lane only when a
real fallback changes the control surface. A fallback does not authorize a
broader action, cross a memory lane, or lower R5 confirmation requirements.

## Record Boundary

Keep an issue in its interaction lane when its cause and prevention are
surface-specific. Add a link to the general common-error corpus only when the
same prevention rule applies across multiple tools or surfaces. Upgrade to a
paired `ERR-*` / `SOL-*` record only for high-impact, repeated, dangerous, or
explicitly escalated incidents.

Each record should preserve:

```text
ce_id
lane
symptom
cause
solution_applied
prevention
validation
evidence
adjacent_lane_fallback
upgrade_to_err_sol_when
```

The public templates are synthetic structure examples. Adopters should keep
machine-specific coordinates, account data, private paths, screenshots, and
incident logs in their own local lanes.
