# Conventions

knowledge_id: `SKL-CONVENTIONS`
source_tag: `static_knowledge`
belief_status: `source_prior`
last_reviewed: `YYYY-MM-DD`

## Documentation

- Keep public docs free of private project details.
- Separate source-prior notes from local validation results.
- Use synthetic examples in public templates.

## Runtime And Adapter Notes

- A hook is hard enforcement only when the host runtime calls it and honors the
  denial result.
- Wrapper-only setups should document bypass surfaces.
- Client updates require compatibility rechecks.

## Memory Notes

- Read meta indexes before payloads.
- Keep writes lane-scoped by default.
- Use links for cross-lane continuation rather than copying payloads.

