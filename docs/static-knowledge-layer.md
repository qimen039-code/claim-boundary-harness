# Static Knowledge Layer

The Static Knowledge Layer is an optional, wiki-style project manual for agents.
It stores stable project facts that are useful for navigation, but it does not
replace project memory, conversation memory, source-monitoring capsules, or claim
verification.

## Influence And Attribution

This layer adapts the established engineering pattern of repository manuals,
project wikis, and close-to-code knowledge bases. It does not vendor or require a
specific upstream wiki implementation. The contribution here is the boundary
contract: index-first lookup, `source_tag: static_knowledge`, `belief_status:
source_prior`, and claim-boundary promotion only after local evidence.

See [influences-and-attribution.md](influences-and-attribution.md) for the
project's broader distinction between borrowed patterns and this repository's
composition layer.

Use it for:

- module maps and ownership notes;
- entry points and common commands;
- interface and data-shape notes;
- repository conventions;
- environment assumptions that are safe to document;
- links to project memory indexes, source ledgers, or test commands.

Do not use it for:

- private operator history;
- unresolved conversation state;
- raw logs or large transcripts;
- secrets, credentials, or local-only paths;
- validation claims that have not gone through the claim boundary;
- automatic always-on skill rewrites.

## Position In The Framework

```text
root instructions
-> intake router
-> static knowledge index when the task needs project navigation
-> one selected static page
-> claim boundary before using the page as evidence
```

The layer is static and low-cost. It should be read only when the router sees a
project-navigation need such as "where is the entry point?", "which command runs
tests?", "what is the module map?", or "what convention should this file follow?"

It is not a general memory backend. A project can have both:

- a memory library for decisions, incidents, source monitoring, and evolving
  state;
- a static knowledge layer for stable manuals and navigation.

## Retrieval Rule

Read the static index first. Do not scan every page.

```text
templates/static-knowledge-layer/_STATIC_KNOWLEDGE_INDEX.md
-> selected page such as project-map.md or entrypoints-and-commands.md
-> optional memory capsule or test result only when the selected page points to it
```

When a selected static note leaves the layer and is returned to an agent, include
the same boundary metadata used by memory retrieval:

```json
{
  "source_tag": "static_knowledge",
  "derived_from": [
    {
      "type": "static_knowledge_page",
      "ref_id": "SKL-PROJECT-MAP",
      "relationship": "distilled_from",
      "inherited_boundary": "source_prior until reviewed against repository files"
    }
  ],
  "belief_status": "source_prior",
  "confidence": {
    "label": "unverified",
    "basis": "Selected from the static knowledge index; no local file or test check has been run."
  },
  "score_method": "none"
}
```

If the agent confirms a static note against repository files or tests, the claim
may be promoted in a separate capsule or result record. Do not silently overwrite
the static page's source-prior boundary.

## Update Rule

Static pages are maintainer-owned documentation. They may be updated by explicit
maintenance tasks, release work, or adapter setup. They should not be rewritten
automatically on every run.

Each page should keep:

- stable `knowledge_id`;
- `status`;
- `last_reviewed`;
- `source_tag: static_knowledge`;
- `belief_status`;
- retrieval terms;
- applies/does-not-apply boundaries.

Use append-only memory records for volatile decisions. Use static pages for
stable maps that a new agent needs to orient itself quickly.
