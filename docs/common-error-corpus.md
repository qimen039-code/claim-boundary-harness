# Common Error Corpus

The common error corpus stores lightweight execution error-and-solution samples. It is for useful recurring mistakes that are worth preserving as agent training material, including the applied solution and validation, but not severe enough for a full paired `ERR-*` / `SOL-*` incident.

For public, reusable issue classes collected during framework adaptation and
release work, see [common-issues-and-solutions.md](common-issues-and-solutions.md).
Keep private local incidents in lane-scoped `CE-*` records instead of publishing
machine-specific logs or paths.

## When To Use

Use a `CE-*` common error record when:

- the mistake is small but likely to recur;
- it helps future routing or tool-call preflight;
- the user calls it a common error or useful sample;
- the issue is fixed immediately and the solution can be recorded without needing a full incident pair.

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
solution_applied:
prevention:
validation:
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
