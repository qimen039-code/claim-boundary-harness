# Entry Points And Commands

knowledge_id: `SKL-ENTRYPOINTS`
source_tag: `static_knowledge`
belief_status: `source_prior`
last_reviewed: `YYYY-MM-DD`

## Entry Points

| Task | Entry point | Expected use | Boundary |
| --- | --- | --- | --- |
| Route a task | `skills/embedded-harness/harness_intake_router.ps1` | Build a routing receipt. | Result is a routing decision, not proof of success. |
| Validate policy shape | `skills/embedded-harness/validate_policy.ps1` | Lightweight policy parse check. | Not a full JSON Schema validator. |
| Run adapter tests | `python -m unittest discover -s integrations/workbuddy-python-runtime/tests` | Test the reference Python adapter. | Does not certify host runtime hook behavior. |

## Command Notes

- Confirm paths and shell syntax in the adopting environment.
- Treat this page as source-prior until commands are run locally.

