# Common Error Corpus Meta Index

status: TEMPLATE
lane: EXAMPLE_COMMON_ERROR_CORPUS

| CE ID | Class | Status | Retrieval terms | Applies | Solution summary | Upgrade boundary |
| --- | --- | --- | --- | --- | --- | --- |
| `CE-EXAMPLE-YYYY-MM-DD` | patch_context_error | TEMPLATE | apply_patch, context mismatch | A patch is rejected because context does not match current file text. | Re-read target lines, apply smaller hunks, then verify the edit landed. | Upgrade if repeated after target-line reread or if it causes wrong edits. |

If a CE payload includes `feedback_loop`, keep only a compact state hint in
this index, such as `feedback_loop: pending` or `feedback_loop: matched`.
