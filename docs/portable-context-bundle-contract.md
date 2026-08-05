# Portable Context Bundle Contract

A portable context bundle packages existing CBH navigation, capsule, source,
and optional payload files so they can be moved or registered without losing
lane ownership, provenance, lifecycle, or validation boundaries.

It does not create a new memory lane, semantic-memory backend, graph store,
vector store, agent runtime, or per-task validation service. The receiving
workspace still decides whether the bundle is merely available, eligible for
retrieval, or active as current guidance.

The public manifest template is
[`templates/portable-context-bundle/manifest.json`](../templates/portable-context-bundle/manifest.json).

## Package Boundary

A bundle may contain:

- a `_META_INDEX.md` or equivalent outer retrieval surface;
- bounded capsule, decision, reference, or link records;
- source and evidence references;
- optional payload files when the owner explicitly includes them;
- the manifest and cached structural-validation result.

Raw transcripts, secrets, private local paths, binary caches, and unrelated
lane payloads are excluded by default. Packaging does not change a record's
`belief_status`, evidence strength, or release eligibility.

## Manifest Responsibilities

The manifest binds:

- `bundle_id`, schema, creation time, and source attribution;
- the owning lane and permitted write root;
- each included file's relative path, role, required flag, and SHA-256;
- upstream source references and source-validity dependencies;
- lifecycle state and activation criteria;
- compatibility requirements;
- validation triggers, cached hashes, and the previous structural result;
- runtime non-goals.

All content paths are bundle-relative. Importers must reject absolute paths,
parent traversal, and paths whose resolved target escapes the selected bundle
or lane root. This is a narrow data-integrity check; it must not register a
general tool deny hook, freeze a session, or create approval state.

## Lifecycle

The bundle uses transport state without replacing record lifecycle:

```text
offline -> registered -> active
                    \-> frozen_readonly
                    \-> retired
```

- `offline`: present as a portable artifact but not indexed locally.
- `registered`: manifest and allowed roots are known; payload is not current
  guidance by registration alone.
- `active`: the adopting lane explicitly selected the bundle for retrieval.
- `frozen_readonly`: preserved for audit or comparison and excluded from
  default writes.
- `retired`: no longer eligible for active retrieval but still traceable.

These states do not override capsule-level `raw_observation`,
`working_memory`, `capsule`, `quarantined`, or `archive` states.

## Event-Driven Validation

Validation runs only on a state-changing or claim-changing event:

1. bundle creation;
2. bundle import;
3. activation as current guidance;
4. manifest, source, or payload hash drift;
5. use as support for a strong factual claim.

Ordinary index lookup, ordinary capsule reads, and reuse with unchanged hashes
must reuse the cached structural result. They do not trigger a new full scan.
Structural validation checks manifest shape, relative paths, required files,
declared hashes, and lane binding. Semantic revalidation is narrower: it opens
only the source evidence needed for activation or the current strong claim.

A cached `pass` proves only that the declared package structure matched at the
recorded hashes. It does not prove that capsule claims are true, current, safe,
or applicable to a new lane.

## Import And Activation

Use this minimum sequence:

```text
read manifest
-> resolve destination lane and root
-> validate relative paths and declared hashes
-> register as inactive
-> activate only after lane, source-validity, and compatibility checks
-> reuse cached validation until a declared trigger changes
```

Cross-lane import creates a new lane-owned registration or an explicit link;
it does not silently merge source payloads or inherit write authority.

## External Design Boundary

TrustGraph Context Cores are a source-prior influence for portable packaging
and explicit load state. CBH adapts the mechanism to its existing capsule,
lane, and source-validity model. It does not adopt TrustGraph's graph/vector
payload requirements, dataflow runtime, or user-interface workflow.
