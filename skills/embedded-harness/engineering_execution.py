"""Bounded engineering-execution receipts for CBH.

The reversible deep-module isolation probe adapts the deletion thought
experiment, and the two-adapter seam criterion is adapted directly, from the
public ``mattpocock/skills`` ``codebase-design`` skill.  Tracer-bullet delivery
and invocation topology are local CBH execution profiles.  Every profile
remains advisory and task-local: this module does not execute tools, mutate
code, grant authority, or persist state.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Any


SCHEMA = "cbh.engineering_execution_receipt.v1"
DELIVERY_TRACE_SCHEMA = "cbh.delivery_trace.v1"
MODULE_DEPTH_SCHEMA = "cbh.module_depth_probe.v1"
INVOCATION_SCHEMA = "cbh.invocation_envelope.v1"
ADAPTER_SEAM_SCHEMA = "cbh.adapter_seam_receipt.v1"

PROFILE_VALUES = (
    "tracer_bullet_plan",
    "deep_module_review",
    "skill_invocation_topology",
    "adapter_seam_review",
)

_STEP_STATUS = {"completed", "in_progress", "pending", "unknown"}
_SLICE_KIND = {"expand", "migrate", "contract", "delivery", "unspecified"}
_REQUEST_ORIGINS = {"user", "model", "host", "automation", "unknown"}
_RUNTIME_INVOKERS = {
    "user_cli",
    "model_tool",
    "host_hook",
    "adapter",
    "automation",
    "unknown",
}
_ORCHESTRATION_OWNERS = {"user", "model", "host", "automation", "unknown"}


def _list(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def _text(value: Any, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _cycle_issues(dependencies: Mapping[str, list[str]]) -> list[str]:
    visited: set[str] = set()
    active: list[str] = []
    issues: list[str] = []

    def visit(node: str) -> None:
        if node in active:
            start = active.index(node)
            issue = "cycle:" + "->".join([*active[start:], node])
            if issue not in issues:
                issues.append(issue)
            return
        if node in visited:
            return
        active.append(node)
        for dependency in dependencies.get(node, []):
            if dependency in dependencies:
                visit(dependency)
        active.pop()
        visited.add(node)

    for node in dependencies:
        visit(node)
    return issues


def build_delivery_trace(plan_steps: Any) -> dict[str, Any]:
    """Build a vertical-slice frontier without turning CBH into a scheduler."""

    normalized: list[dict[str, Any]] = []
    graph_issues: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(_list(plan_steps)):
        item = raw if isinstance(raw, Mapping) else {"text": raw}
        step_id = _text(item.get("id") or f"step-{index + 1}", 160)
        if not step_id:
            graph_issues.append(f"missing_step_id:{index}")
            continue
        if step_id in seen:
            graph_issues.append(f"duplicate_step_id:{step_id}")
            continue
        seen.add(step_id)
        status = _text(item.get("status") or "unknown", 32).lower()
        slice_kind = _text(item.get("slice_kind") or "unspecified", 32).lower()
        blocked_by = list(
            dict.fromkeys(_text(value, 160) for value in _list(item.get("blocked_by")))
        )
        normalized.append(
            {
                "id": step_id,
                "text": _text(item.get("text") or item.get("step") or step_id, 800),
                "status": status if status in _STEP_STATUS else "unknown",
                "slice_kind": slice_kind if slice_kind in _SLICE_KIND else "unspecified",
                "blocked_by": [value for value in blocked_by if value],
            }
        )

    if not normalized:
        return {
            "schema": DELIVERY_TRACE_SCHEMA,
            "status": "insufficient_evidence",
            "migration_phase": "UNSPECIFIED",
            "steps": [],
            "blocking_edges": [],
            "frontier_step_ids": [],
            "graph_issues": graph_issues or ["plan_steps_missing"],
            "authority_granted": False,
        }

    by_id = {item["id"]: item for item in normalized}
    dependencies = {item["id"]: item["blocked_by"] for item in normalized}
    for item in normalized:
        for dependency in item["blocked_by"]:
            if dependency not in by_id:
                graph_issues.append(f"dangling_dependency:{dependency}->{item['id']}")
    graph_issues.extend(_cycle_issues(dependencies))
    graph_issues = list(dict.fromkeys(graph_issues))

    blocking_edges = [
        {
            "from": dependency,
            "to": item["id"],
            "satisfied": bool(
                dependency in by_id and by_id[dependency]["status"] == "completed"
            ),
        }
        for item in normalized
        for dependency in item["blocked_by"]
    ]
    frontier = (
        []
        if graph_issues
        else [
            item["id"]
            for item in normalized
            if item["status"] in {"pending", "in_progress", "unknown"}
            and all(by_id[dep]["status"] == "completed" for dep in item["blocked_by"])
        ]
    )

    incomplete_kinds = {
        item["slice_kind"] for item in normalized if item["status"] != "completed"
    }
    if all(item["status"] == "completed" for item in normalized):
        phase = "COMPLETE"
    elif "expand" in incomplete_kinds:
        phase = "EXPAND"
    elif "migrate" in incomplete_kinds:
        phase = "MIGRATE"
    elif "contract" in incomplete_kinds:
        phase = "CONTRACT"
    else:
        phase = "UNSPECIFIED"

    return {
        "schema": DELIVERY_TRACE_SCHEMA,
        "status": "semantic_review_required" if graph_issues else "ready",
        "migration_phase": phase,
        "steps": normalized,
        "blocking_edges": blocking_edges,
        "frontier_step_ids": frontier,
        "graph_issues": graph_issues,
        "authority_granted": False,
    }


_DEPTH_SIGNAL_FIELDS = (
    "narrow_interface",
    "hides_complexity",
    "owns_independent_policy",
    "multiple_independent_callers",
)
_ISOLATION_FIELD = "isolation_eliminates_complexity"
_LEGACY_DELETION_FIELD = "deletion_simplifies_system"


def build_module_depth_probe(evidence: Any) -> dict[str, Any]:
    """Evaluate a reversible freeze/isolation probe without mutating runtime state."""

    source = evidence if isinstance(evidence, Mapping) else {}
    values = {
        field: _bool_or_none(source.get(field)) for field in _DEPTH_SIGNAL_FIELDS
    }
    isolation_value = _bool_or_none(source.get(_ISOLATION_FIELD))
    legacy_value = _bool_or_none(source.get(_LEGACY_DELETION_FIELD))
    legacy_input_used = isolation_value is None and legacy_value is not None
    if isolation_value is None:
        isolation_value = legacy_value
    values[_ISOLATION_FIELD] = isolation_value
    missing = [field for field, value in values.items() if value is None]
    if missing:
        verdict = "insufficient_evidence"
    else:
        depth_signals = sum(
            bool(values[field])
            for field in (
                "narrow_interface",
                "hides_complexity",
                "owns_independent_policy",
                "multiple_independent_callers",
            )
        )
        if depth_signals >= 3 and values[_ISOLATION_FIELD] is False:
            verdict = "deep_module"
        elif depth_signals <= 1 and values[_ISOLATION_FIELD] is True:
            verdict = "shallow_module"
        else:
            verdict = "mixed_evidence"
    return {
        "schema": MODULE_DEPTH_SCHEMA,
        "verdict": verdict,
        "evidence": values,
        "missing_evidence": missing,
        "probe_mode": "reversible_freeze_or_temporary_isolation",
        "source_method": "deletion_thought_experiment_adapted_to_reversible_isolation",
        "legacy_deletion_input_used": legacy_input_used,
        "rollback_required": True,
        "audit_receipt_required": True,
        "runtime_isolation_performed": False,
        "execution_boundary": "advisory_evaluator_only_external_executor_must_restore_and_audit",
        "destructive_action_authorized": False,
        "authority_granted": False,
    }


def normalize_invocation_envelope(
    payload: Any,
    *,
    trusted_host_evidence: Any = None,
) -> dict[str, Any]:
    """Separate request origin, actual invoker, orchestrator, and authority."""

    source = payload if isinstance(payload, Mapping) else {}
    request_origin = _text(source.get("request_origin") or "unknown", 64).lower()
    claimed_runtime_invoker = _text(
        source.get("runtime_invoker") or "unknown", 64
    ).lower()
    runtime_invoker = claimed_runtime_invoker
    owner = _text(source.get("orchestration_owner") or "unknown", 64).lower()
    issues: list[str] = []
    if request_origin not in _REQUEST_ORIGINS:
        request_origin = "unknown"
        issues.append("unsupported_request_origin")
    if runtime_invoker not in _RUNTIME_INVOKERS:
        runtime_invoker = "unknown"
        issues.append("unsupported_runtime_invoker")
    if owner not in _ORCHESTRATION_OWNERS:
        owner = "unknown"
        issues.append("unsupported_orchestration_owner")
    if isinstance(source.get("host_evidence"), Mapping):
        issues.append("untrusted_payload_host_evidence_ignored")
    host_evidence = (
        dict(trusted_host_evidence)
        if isinstance(trusted_host_evidence, Mapping)
        else None
    )
    verified = (
        runtime_invoker != "unknown"
        and isinstance(host_evidence, Mapping)
        and _text(host_evidence.get("runtime_invoker"), 64).lower()
        == runtime_invoker
        and bool(_text(host_evidence.get("surface"), 160))
        and bool(_text(host_evidence.get("receipt_ref"), 500))
        and bool(
            re.fullmatch(
                r"[0-9a-f]{64}",
                _text(host_evidence.get("receipt_sha256"), 64).lower(),
            )
        )
    )
    if runtime_invoker != "unknown" and not verified:
        runtime_invoker = "unknown"
        issues.append("unverified_runtime_invoker_claim")
    return {
        "schema": INVOCATION_SCHEMA,
        "request_origin": request_origin,
        "claimed_runtime_invoker": claimed_runtime_invoker,
        "runtime_invoker": runtime_invoker,
        "orchestration_owner": owner,
        "call_surface": _text(source.get("call_surface") or "unknown", 160),
        "execution_owner": _text(source.get("execution_owner") or "unknown", 160),
        "host_evidence": dict(host_evidence) if isinstance(host_evidence, Mapping) else None,
        "issues": issues,
        "authority_granted": False,
    }


def evaluate_adapter_seam(
    receipts: Any,
    *,
    trusted_receipt_hashes: Any = None,
) -> dict[str, Any]:
    """Mark a seam real only after two independent adapters verify one core."""

    candidates: list[dict[str, str]] = []
    rejected: list[str] = []
    trusted_hashes = {
        _text(value, 64).lower()
        for value in _list(trusted_receipt_hashes)
        if re.fullmatch(r"[0-9a-f]{64}", _text(value, 64).lower())
    }
    for index, raw in enumerate(_list(receipts)):
        if not isinstance(raw, Mapping):
            rejected.append(f"receipt_{index}:not_object")
            continue
        adapter_id = _text(raw.get("adapter_id"), 160)
        host_surface = _text(raw.get("host_surface"), 160)
        contract_hash = _text(raw.get("core_contract_sha256"), 64).lower()
        status = _text(raw.get("verification_status"), 32).lower()
        receipt_ref = _text(raw.get("receipt_ref"), 500)
        producer_receipt_sha256 = _text(
            raw.get("producer_receipt_sha256"), 64
        ).lower()
        if not (
            adapter_id
            and host_surface
            and re.fullmatch(r"[0-9a-f]{64}", contract_hash)
            and status == "verified"
            and receipt_ref
            and re.fullmatch(r"[0-9a-f]{64}", producer_receipt_sha256)
        ):
            rejected.append(f"receipt_{index}:incomplete_or_unverified")
            continue
        candidates.append(
            {
                "adapter_id": adapter_id,
                "host_surface": host_surface,
                "core_contract_sha256": contract_hash,
                "verification_status": status,
                "receipt_ref": receipt_ref,
                "producer_receipt_sha256": producer_receipt_sha256,
            }
        )

    candidate_adapter_ids = {item["adapter_id"] for item in candidates}
    candidate_host_surfaces = {item["host_surface"] for item in candidates}
    candidate_contract_hashes = {
        item["core_contract_sha256"] for item in candidates
    }
    candidate_real = (
        len(candidate_adapter_ids) >= 2
        and len(candidate_host_surfaces) >= 2
        and len(candidate_contract_hashes) == 1
    )
    verified = [
        item
        for item in candidates
        if item["producer_receipt_sha256"] in trusted_hashes
    ]
    real = (
        len({item["adapter_id"] for item in verified}) >= 2
        and len({item["host_surface"] for item in verified}) >= 2
        and len({item["core_contract_sha256"] for item in verified}) == 1
    )
    return {
        "schema": ADAPTER_SEAM_SCHEMA,
        "seam_status": "real" if real else ("candidate_real" if candidate_real else "hypothetical"),
        "candidate_adapters": candidates,
        "verified_adapters": verified,
        "rejected_receipts": rejected,
        "required_independent_adapters": 2,
        "real_claim_allowed": real,
        "verification_boundary": "trusted_non_model_producer_receipt_hashes_required",
        "authority_granted": False,
    }


def build_engineering_execution_receipt(
    profiles: Any,
    task_event: Any = None,
    *,
    trusted_host_evidence: Any = None,
    trusted_seam_receipt_hashes: Any = None,
) -> dict[str, Any]:
    """Materialize only the requested engineering profiles."""

    selected = [
        profile
        for profile in dict.fromkeys(_text(value, 80) for value in _list(profiles))
        if profile in PROFILE_VALUES
    ]
    event = task_event if isinstance(task_event, Mapping) else {}
    results: dict[str, Any] = {}
    if "tracer_bullet_plan" in selected:
        results["tracer_bullet_plan"] = build_delivery_trace(event.get("plan_steps"))
    if "deep_module_review" in selected:
        results["deep_module_review"] = build_module_depth_probe(event.get("module_probe"))
    if "skill_invocation_topology" in selected:
        results["skill_invocation_topology"] = normalize_invocation_envelope(
            event.get("invocation"),
            trusted_host_evidence=trusted_host_evidence,
        )
    if "adapter_seam_review" in selected:
        results["adapter_seam_review"] = evaluate_adapter_seam(
            event.get("adapter_receipts"),
            trusted_receipt_hashes=trusted_seam_receipt_hashes,
        )
    return {
        "schema": SCHEMA,
        "profiles": selected,
        "results": results,
        "source_refs": [
            {
                "url": "https://github.com/mattpocock/skills/tree/main/skills/engineering/codebase-design",
                "applies_to": ["deep_module_review", "adapter_seam_review"],
            }
        ],
        "local_profile_ids": ["tracer_bullet_plan", "skill_invocation_topology"],
        "adaptation": "bounded_task_local_advisory_receipts",
        "authority_granted": False,
        "persistence": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build one bounded CBH engineering-execution receipt."
    )
    parser.add_argument(
        "--profile",
        action="append",
        choices=PROFILE_VALUES,
        required=True,
    )
    parser.add_argument(
        "--input-json",
        help="Task-event JSON. If omitted, read one JSON object from stdin.",
    )
    args = parser.parse_args()
    source = args.input_json if args.input_json is not None else sys.stdin.read()
    payload = json.loads(source or "{}")
    if not isinstance(payload, Mapping):
        raise ValueError("input must be a JSON object")
    print(
        json.dumps(
            build_engineering_execution_receipt(args.profile, payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
