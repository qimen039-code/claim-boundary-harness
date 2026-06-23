#!/usr/bin/env python3
"""Default-off SkillOpt-style cycle runner.

This module generates and gates candidate edits for skills, routers, and
governance files. It never patches the target file. An accepted gate means the
candidate may enter the normal human-reviewed change process.

Attribution boundary: this is an independent lightweight implementation inspired
by the public Microsoft SkillOpt project. It does not vendor SkillOpt code.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "skillopt-cycle/v1"
ALLOWED_SURFACES = {
    "router",
    "ERR",
    "SOL",
    "semantic_anchor",
    "project_router",
    "harness",
    "registry",
    "docs",
    "skill",
}
ALLOWED_SOURCE_TYPES = {
    "local_evidence",
    "external_source_prior",
    "mixed",
}
DEFAULT_REGRESSION_TASKS = [
    "ordinary chat remains low cost",
    "GitHub or currentness task routes to external research",
    "governance or routing update remains a framework-governance change",
    "delete install network permission secret payment actions remain high risk",
    "projectless exploration does not contaminate project memory",
    "small recurring mistakes route to common error corpus before full ERR/SOL",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def date_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def slugify(text: str, limit: int = 36) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text.strip().lower()).strip("-")
    return (slug or "candidate")[:limit].strip("-") or "candidate"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def resolve_inside(root: Path, candidate: str) -> tuple[Path, bool]:
    root_resolved = root.resolve()
    path = Path(candidate)
    if not path.is_absolute():
        path = root_resolved / path
    path_resolved = path.resolve()
    try:
        path_resolved.relative_to(root_resolved)
        return path_resolved, True
    except ValueError:
        return path_resolved, False


def rel_to_root(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def evidence_rows(items: list[str], source_type: str) -> list[dict[str, Any]]:
    tag = "local_test" if source_type == "local_evidence" else "external_source"
    if source_type == "mixed":
        tag = "source_note"
    rows = []
    for idx, item in enumerate(items, start=1):
        rows.append(
            {
                "evidence_id": f"EVID-{idx:03d}",
                "source_tag": tag,
                "summary": item,
                "belief_status": "bounded_claim",
                "confidence": {
                    "label": "medium",
                    "basis": "Provided as cycle input; validation gate has not applied the candidate.",
                    "score_method": "none",
                },
            }
        )
    return rows


def build_candidate(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    root = Path(args.root).resolve()
    target_path, inside = resolve_inside(root, args.target)
    candidate_id = f"SKILLOPT-{date_stamp()}-{slugify(args.proposed_change)}"
    run_dir = Path(args.out_dir).resolve() / candidate_id
    target_file = rel_to_root(root, target_path) if inside else str(target_path)
    regression_tasks = args.regression_task or DEFAULT_REGRESSION_TASKS
    evidence = evidence_rows(args.evidence, args.source_type)

    candidate = {
        "schema_version": SCHEMA_VERSION,
        "kind": "candidate_edit_packet",
        "candidate_id": candidate_id,
        "created_at": utc_now(),
        "cycle_mode": "default_off_periodic",
        "target": {
            "file": target_file,
            "surface": args.surface,
            "must_exist": True,
        },
        "source_type": args.source_type,
        "source_monitoring": {
            "source_tag": "local_test"
            if args.source_type == "local_evidence"
            else "source_note",
            "belief_status": "bounded_claim",
            "confidence": {
                "label": "medium",
                "basis": "Candidate was generated from provided evidence and still requires gate review.",
                "score_method": "none",
            },
            "derived_from": [
                {
                    "type": "user_confirmation"
                    if args.source_type == "local_evidence"
                    else "source_note",
                    "ref_id": row["evidence_id"],
                    "relationship": "synthesized_from",
                    "inherited_boundary": "candidate evidence only; not local validation of the proposed edit",
                }
                for row in evidence
            ],
        },
        "evidence": evidence,
        "proposed_change": {
            "summary": args.proposed_change,
            "patch_hint": args.patch_hint,
        },
        "reason": args.reason,
        "textual_learning_rate": {
            "profile": "default",
            "max_target_files": 1,
            "max_bullets": 3,
            "max_short_sections": 1,
            "allow_global_rewrite": False,
            "allow_protected_region_edit": bool(args.slow_update),
        },
        "protected_regions_checked": bool(args.protected_regions_checked),
        "regression_tasks": regression_tasks,
        "expected_improvement": args.expected_improvement,
        "risk": args.risk,
        "rollback": args.rollback,
        "status": "proposed",
        "gate_result": None,
        "human_approval_required_to_apply": True,
        "slow_update": bool(args.slow_update),
    }
    return candidate, run_dir


def validate_candidate(candidate: dict[str, Any], root: Path) -> dict[str, Any]:
    blocking: list[str] = []
    deferrals: list[str] = []
    warnings: list[str] = []

    def require(condition: bool, issue: str) -> None:
        if not condition:
            blocking.append(issue)

    require(candidate.get("schema_version") == SCHEMA_VERSION, "unsupported_schema")
    require(candidate.get("kind") == "candidate_edit_packet", "wrong_kind")
    require(bool(candidate.get("candidate_id")), "missing_candidate_id")
    require(candidate.get("status") == "proposed", "candidate_status_must_be_proposed")

    target = candidate.get("target") or {}
    target_file = target.get("file")
    surface = target.get("surface")
    require(bool(target_file), "missing_target_file")
    require(surface in ALLOWED_SURFACES, "unsupported_target_surface")

    if target_file:
        target_path, inside = resolve_inside(root, str(target_file))
        if not inside:
            blocking.append("target_file_outside_root")
        elif not target_path.exists():
            blocking.append("target_file_missing")

    source_type = candidate.get("source_type")
    require(source_type in ALLOWED_SOURCE_TYPES, "unsupported_source_type")

    source_monitoring = candidate.get("source_monitoring") or {}
    for field in ("source_tag", "belief_status", "confidence", "derived_from"):
        require(field in source_monitoring, f"missing_source_monitoring_{field}")
    confidence = source_monitoring.get("confidence") or {}
    if confidence.get("score_method") is None:
        blocking.append("missing_score_method")
    if confidence.get("score_method") == "none" and "score" in confidence:
        blocking.append("score_present_when_score_method_none")

    evidence = candidate.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        deferrals.append("missing_evidence")

    proposed = candidate.get("proposed_change") or {}
    if not proposed.get("summary"):
        blocking.append("missing_proposed_change_summary")
    if proposed.get("patch_hint") and len(str(proposed["patch_hint"]).splitlines()) > 20:
        deferrals.append("patch_hint_too_large_for_default_learning_rate")

    tlr = candidate.get("textual_learning_rate") or {}
    if tlr.get("max_target_files") != 1:
        blocking.append("textual_learning_rate_must_target_one_file")
    if tlr.get("allow_global_rewrite"):
        blocking.append("global_rewrite_not_allowed_in_default_cycle")

    if not candidate.get("protected_regions_checked"):
        deferrals.append("protected_regions_not_checked")

    probes = candidate.get("regression_tasks")
    if not isinstance(probes, list) or len(probes) < 3:
        deferrals.append("too_few_regression_tasks")
    elif len(probes) > 10:
        deferrals.append("too_many_regression_tasks_for_default_cycle")

    if not candidate.get("rollback"):
        deferrals.append("missing_rollback_plan")

    risk = candidate.get("risk")
    if risk == "R5":
        deferrals.append("R5_candidate_requires_explicit_human_confirmation")
    elif risk not in {"R1", "R2", "R3", "R4"}:
        warnings.append("risk_label_not_in_reference_set")

    if blocking:
        result = "rejected"
        next_action = "Do not apply. Fix the packet or preserve as a rejected edit."
    elif deferrals:
        result = "deferred"
        next_action = "Collect missing evidence or boundary checks, then rerun validation."
    else:
        result = "accepted"
        next_action = "Candidate may enter the normal human-reviewed change process."

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "gate_report",
        "candidate_id": candidate.get("candidate_id"),
        "created_at": utc_now(),
        "gate_result": result,
        "blocking_issues": blocking,
        "deferred_reasons": deferrals,
        "warnings": warnings,
        "manual_apply_only": True,
        "applied_to_target": False,
        "next_action": next_action,
        "claim_boundary": "Gate result validates packet shape and boundaries only; it does not prove the proposed edit improves behavior until regression probes are actually run.",
    }


def build_source_note(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "source_intake_note",
        "candidate_id": candidate["candidate_id"],
        "created_at": utc_now(),
        "classification": "adapted_rule",
        "source_type": candidate["source_type"],
        "boundary": "External or provided evidence is source-prior unless locally validated by the adopting workspace.",
        "non_adopted_by_default": [
            "third-party optimizer execution",
            "automatic mutation of primary skills",
            "automatic long-term memory writes",
            "replacement of the bounded skill matrix",
        ],
    }


def build_rejected_record(candidate: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "rejected_edit_record",
        "rejected_id": f"REJ-{candidate['candidate_id']}",
        "candidate_id": candidate["candidate_id"],
        "target_surface": candidate.get("target", {}).get("surface"),
        "bad_change_summary": candidate.get("proposed_change", {}).get("summary"),
        "why_rejected": gate.get("blocking_issues") or gate.get("deferred_reasons"),
        "evidence": candidate.get("evidence", []),
        "prevention_rule": "Do not promote candidates that fail schema, boundary, evidence, or regression-probe gates.",
        "date": utc_now(),
    }


def build_slow_update(candidate: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "slow_update_proposal",
        "candidate_id": candidate["candidate_id"],
        "created_at": utc_now(),
        "target": candidate.get("target"),
        "gate_result": gate["gate_result"],
        "promotion_condition": "Require repeated local evidence or explicit approval before applying to primary skill/router files.",
        "review_cadence": "periodic_or_user_requested",
        "status": "open" if gate["gate_result"] != "rejected" else "closed_rejected",
    }


def record_gate(records_dir: Path, candidate: dict[str, Any], gate: dict[str, Any]) -> None:
    result = gate["gate_result"]
    append_jsonl(records_dir / f"{result}.jsonl", gate)
    if result == "rejected":
        append_jsonl(records_dir / "rejected_edit_buffer.jsonl", build_rejected_record(candidate, gate))
    if candidate.get("slow_update"):
        append_jsonl(records_dir / "slow_updates.jsonl", build_slow_update(candidate, gate))


def run_cycle(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    candidate, run_dir = build_candidate(args)
    gate = validate_candidate(candidate, root)
    candidate["gate_result"] = gate["gate_result"]
    probes = [
        {
            "schema_version": SCHEMA_VERSION,
            "kind": "regression_probe",
            "candidate_id": candidate["candidate_id"],
            "probe_id": f"PROBE-{idx:03d}",
            "task": task,
            "expected_boundary": "preserve_or_improve_existing_routing",
        }
        for idx, task in enumerate(candidate["regression_tasks"], start=1)
    ]

    write_json(run_dir / "candidate_edit_packet.json", candidate)
    write_json(run_dir / "gate_report.json", gate)
    write_json(run_dir / "source_intake_note.json", build_source_note(candidate))
    write_jsonl(run_dir / "regression_probe_set.jsonl", probes)
    if not args.no_record:
        record_gate(Path(args.records_dir).resolve(), candidate, gate)

    print(
        json.dumps(
            {
                "status": "pass",
                "candidate_id": candidate["candidate_id"],
                "gate_result": gate["gate_result"],
                "run_dir": str(run_dir),
                "recorded": not args.no_record,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if gate["gate_result"] in {"accepted", "deferred"} else 2


def run_validate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    candidate_path = Path(args.candidate).resolve()
    candidate = load_json(candidate_path)
    gate = validate_candidate(candidate, root)
    write_json(candidate_path.parent / "gate_report.json", gate)
    if not args.no_record:
        record_gate(Path(args.records_dir).resolve(), candidate, gate)
    print(json.dumps(gate, ensure_ascii=False, indent=2))
    return 0 if gate["gate_result"] in {"accepted", "deferred"} else 2


def run_self_test(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    work_dir = (root / args.work_dir).resolve()
    if work_dir.exists():
        shutil.rmtree(work_dir)
    target = work_dir / "dummy-skill.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Dummy Skill\n\n- Existing bounded rule.\n", encoding="utf-8")

    cycle_args = argparse.Namespace(
        root=str(root),
        target=rel_to_root(root, target),
        surface="skill",
        evidence=["Recurring bounded dummy evidence for self-test."],
        source_type="local_evidence",
        proposed_change="Add a bounded regression reminder",
        patch_hint="- Add one regression reminder bullet.",
        reason="Self-test validates candidate generation and gate reporting.",
        expected_improvement="The runner can create and gate a candidate packet.",
        rollback="Discard the candidate packet; no target file is mutated.",
        regression_task=DEFAULT_REGRESSION_TASKS[:3],
        risk="R3",
        protected_regions_checked=True,
        slow_update=False,
        out_dir=str(work_dir / "cycles"),
        records_dir=str(work_dir / "records"),
        no_record=False,
    )
    exit_code = run_cycle(cycle_args)
    summary = {"status": "pass" if exit_code == 0 else "fail", "work_dir": str(work_dir)}
    if not args.keep:
        shutil.rmtree(work_dir)
        summary["cleaned"] = True
    else:
        summary["cleaned"] = False
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Default-off SkillOpt-style candidate-edit cycle runner."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    cycle = sub.add_parser("cycle", help="Create and gate a candidate edit packet.")
    cycle.add_argument("--root", default=".")
    cycle.add_argument("--target", required=True)
    cycle.add_argument("--surface", default="skill", choices=sorted(ALLOWED_SURFACES))
    cycle.add_argument("--evidence", action="append", required=True)
    cycle.add_argument("--source-type", default="local_evidence", choices=sorted(ALLOWED_SOURCE_TYPES))
    cycle.add_argument("--proposed-change", required=True)
    cycle.add_argument("--patch-hint", default="")
    cycle.add_argument("--reason", default="Recurring skill improvement candidate.")
    cycle.add_argument("--expected-improvement", default="Improve recurring routing or skill behavior.")
    cycle.add_argument("--rollback", default="Do not apply the candidate; remove the generated packet.")
    cycle.add_argument("--regression-task", action="append")
    cycle.add_argument("--risk", default="R3")
    cycle.add_argument("--protected-regions-checked", action="store_true")
    cycle.add_argument("--slow-update", action="store_true")
    cycle.add_argument("--out-dir", default=".skillopt/cycles")
    cycle.add_argument("--records-dir", default=".skillopt/records")
    cycle.add_argument("--no-record", action="store_true")
    cycle.set_defaults(func=run_cycle)

    validate = sub.add_parser("validate", help="Validate an existing candidate packet.")
    validate.add_argument("--root", default=".")
    validate.add_argument("--candidate", required=True)
    validate.add_argument("--records-dir", default=".skillopt/records")
    validate.add_argument("--no-record", action="store_true")
    validate.set_defaults(func=run_validate)

    self_test = sub.add_parser("self-test", help="Run a local smoke test.")
    self_test.add_argument("--root", default=".")
    self_test.add_argument("--work-dir", default=".tmp-skillopt-smoke")
    self_test.add_argument("--keep", action="store_true")
    self_test.set_defaults(func=run_self_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
