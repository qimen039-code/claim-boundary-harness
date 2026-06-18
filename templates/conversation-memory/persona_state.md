# Conversation-Only Persona State

```yaml
status: TEMPLATE
scope: current_conversation_only
default_enabled: false
may_affect: tone, pacing, roleplay_style
must_not_affect: facts, risk, verification, project_boundary, memory_boundary, claim_schema, external_research
```

## Boundary

Persona state is optional and conversation-local.

It must not be copied into global memory, project memory, archive capsules, or user operating preferences unless the user explicitly requests a bounded export.

## Current Conversation Style

No persona state is configured in this template.

## Do Not Infer

- Do not infer personality from work requests.
- Do not infer motives from correction style.
- Do not let persona state change evidence or verification rules.
