# Claude Code Integration

This page is a reference mapping, not a completed Claude Code deployment
validation. Confirm the exact instruction filename and hook protocol in the
installed client before claiming activation.

Map the root `AGENTS.md` microkernel into the workspace instruction surface,
commonly `CLAUDE.md`, and keep the host model responsible for the user's task.

Minimal instruction intent:

```text
Route nontrivial work before planning.
Read memory meta/index layers before payloads.
Ask for exact user confirmation before R5 actions.
Use source-grounded external research for current public facts.
Keep CBH behavior correction nonblocking and separate from authorization.
```

The advisory Bash router requires `jq`:

```bash
bash <HARNESS_ROOT>/bash/harness_intake_router.sh \
  --task-text "<user task>" --cwd "<workspace root>"
```

The bundled `behavior_correction_hook.py` uses an `allow + updatedInput`
reference protocol. Do not wire it into Claude Code unless the exact installed
version documents compatible updated-input and permission semantics. If that
cannot be verified, use only the instruction/router/context surfaces.

No match, ambiguity, parser failure, or unsupported host protocol must remain a
silent no-op. CBH does not emit deny, freeze the session, create R5 permits, or
replace Claude Code's native permission boundary.

After client updates, recheck the loaded instruction file, router/validator,
memory meta-first behavior, hook payload schema, native permission behavior,
and bypass surfaces. Do not report hard enforcement from repository presence or
reference tests alone.
