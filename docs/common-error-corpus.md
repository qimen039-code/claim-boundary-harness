# Common Error Corpus

The common error corpus stores lightweight execution-error samples. It is for useful recurring mistakes that are worth preserving as agent training material, but not severe enough for a full paired `ERR-*` / `SOL-*` incident.

## When To Use

Use a `CE-*` common error record when:

- the mistake is small but likely to recur;
- it helps future routing or tool-call preflight;
- the user calls it a common error or useful sample;
- the issue is fixed immediately and does not need a full incident pair.

Do not use it for:

- data loss or irreversible action risk;
- public/private exposure mistakes;
- repeated failures after prevention was already recorded;
- user-explicit request for full self-reflection matrix recording.

Those should become paired `ERR-*` / `SOL-*` records.

## CE Record Shape

```text
ce_id:
class:
status:
surface:
symptom:
cause:
prevention:
upgrade_to_err_sol_when:
evidence:
last_reviewed:
```

Recommended classes:

```text
field_schema_error
function_tool_call_error
semantic_routing_error
patch_context_error
powershell_encoding_path_error
git_repo_action_error
```

## Retrieval Chain

```text
common-error-corpus/_META_INDEX.md
-> one class/category row
-> one matching CE-* payload
```

The corpus should stay compact. If it becomes large, split by class indexes before reading payloads.
