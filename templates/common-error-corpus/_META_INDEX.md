# Common Error Corpus Meta Index

status: TEMPLATE
lane: EXAMPLE_COMMON_ERROR_CORPUS

| CE ID | Class | Status | Retrieval terms | Applies | Upgrade boundary |
| --- | --- | --- | --- | --- | --- |
| `CE-EXAMPLE-YYYY-MM-DD` | patch_context_error | TEMPLATE | apply_patch, context mismatch | A patch is rejected because context does not match current file text. | Upgrade if repeated after target-line reread or if it causes wrong edits. |
