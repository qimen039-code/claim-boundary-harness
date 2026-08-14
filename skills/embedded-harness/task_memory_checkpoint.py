"""Promote one completed task snapshot into durable semantic memory.

Preparation is read-only and returns a hash-bound candidate.  Promotion is a
separate, synchronous caller-owned action: append the canonical v3 record,
validate the store, and prove that the exact record is immediately searchable.
No background queue, authority, raw evidence, or hidden reasoning is created.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from semantic_memory import (
    append_memory_record,
    build_memory_record,
    check_memory_store,
    search_memory_store,
    validate_memory_record,
)
from task_continuity_workfile import rehydrate_cumcwork


CANDIDATE_SCHEMA = "cbh.task_memory_checkpoint_candidate.v1"
PROMOTION_RECEIPT_SCHEMA = "cbh.task_memory_checkpoint_promotion_receipt.v1"
SUPPORTED_LANES = {"conversation", "project"}
MEMORY_CLASS_BY_LANE = {
    "conversation": "conversation_event",
    "project": "project_event",
}
MAX_TEXT = 1_200
MAX_LIST = 8
_EVIDENCE_REF_FIELDS = {
    "source_id",
    "source_type",
    "source_kind",
    "original_path",
    "resolved_path",
    "artifact_path",
    "line",
    "line_sha256_16",
    "sha256",
    "status",
    "test_id",
    "verification",
    "evidence_boundary",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _bounded_text(value: Any, limit: int = MAX_TEXT) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _bounded_items(values: Any, *, fields: Sequence[str]) -> list[dict[str, Any]]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    result: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        item = {
            field: _copy(value[field])
            for field in fields
            if value.get(field) is not None
        }
        if item:
            result.append(item)
        if len(result) >= MAX_LIST:
            break
    return result


def _evidence_ref(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    result = {
        key: _copy(value[key])
        for key in _EVIDENCE_REF_FIELDS
        if value.get(key) is not None
    }
    if not result or not any(
        result.get(key)
        for key in ("source_id", "sha256", "artifact_path", "original_path", "resolved_path")
    ):
        return None
    return result


def _candidate_hash(candidate: Mapping[str, Any]) -> str:
    return _sha256(
        {key: _copy(value) for key, value in candidate.items() if key != "candidate_sha256"}
    )


def _eligibility_reasons(capsule: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if capsule.get("schema") != "cbh.task_capsule.v1":
        reasons.append("invalid_task_capsule")
    if capsule.get("lifecycle") != "RETIRED":
        reasons.append("task_not_retired")
    retirement = capsule.get("retirement")
    if not isinstance(retirement, Mapping) or retirement.get("outcome") != "completed":
        reasons.append("task_not_completed")
    criteria = capsule.get("acceptance_criteria")
    if (
        not isinstance(criteria, Sequence)
        or isinstance(criteria, (str, bytes))
        or not criteria
        or any(
            not isinstance(item, Mapping) or item.get("status") != "verified"
            for item in criteria
        )
    ):
        reasons.append("acceptance_not_fully_verified")
    if capsule.get("remaining_work"):
        reasons.append("remaining_work_present")
    if capsule.get("semantic_review_required") is True:
        reasons.append("semantic_review_required")
    if capsule.get("blocking_condition"):
        reasons.append("blocking_condition_present")
    if capsule.get("unresolved_failures"):
        reasons.append("unresolved_failures_present")
    if not _bounded_text(capsule.get("objective")):
        reasons.append("task_objective_missing")
    last_event = capsule.get("last_event")
    if not isinstance(last_event, Mapping) or not _bounded_text(last_event.get("observed_at"), 80):
        reasons.append("task_observed_at_missing")
    return list(dict.fromkeys(reasons))


def _retrieval_terms(capsule: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for value in (capsule.get("objective"), capsule.get("purpose")):
        text = _bounded_text(value, 320)
        if text:
            values.append(text)
    for item in capsule.get("required_outputs") or []:
        if isinstance(item, Mapping):
            text = _bounded_text(item.get("text"), 240)
            if text:
                values.append(text)
    return list(dict.fromkeys(values))[:MAX_LIST]


def _record_id(capsule: Mapping[str, Any], lane_id: str, lane_kind: str) -> str:
    identity = {
        "capsule_id": capsule.get("capsule_id"),
        "lane_id": lane_id,
        "lane_kind": lane_kind,
    }
    return f"MEM-TASK-{_sha256(identity)[:24].upper()}"


def _build_record(
    capsule: Mapping[str, Any],
    *,
    workfile: Path,
    work_state: Mapping[str, Any],
    lane_id: str,
    lane_kind: str,
    owner_skill: str | None,
) -> dict[str, Any]:
    last_event = capsule["last_event"]
    observed_at = _bounded_text(last_event.get("observed_at"), 80)
    objective = _bounded_text(capsule.get("objective"))
    capsule_sha256 = _sha256(capsule)
    source_id = f"cumcwork:{capsule.get('capsule_id')}"
    evidence_refs: list[dict[str, Any]] = [
        {
            "source_id": source_id,
            "source_kind": "task_workfile_snapshot",
            "original_path": str(Path(workfile).resolve()),
            "head_sha256": work_state.get("head_sha256"),
            "work_revision": work_state.get("work_revision"),
            "capsule_sha256": capsule_sha256,
            "evidence_boundary": "hash-bound operational task state",
        }
    ]
    for value in capsule.get("evidence_refs") or []:
        item = _evidence_ref(value)
        if item is not None and item not in evidence_refs:
            evidence_refs.append(item)
    selected_ids = list(
        dict.fromkeys(
            str(value)
            for value in (
                (capsule.get("memory_working_set") or {}).get("selected_record_ids")
                if isinstance(capsule.get("memory_working_set"), Mapping)
                else []
            )
            if str(value).strip()
        )
    )[:MAX_LIST]
    record_id = _record_id(capsule, lane_id, lane_kind)
    return build_memory_record(
        record_id=record_id,
        memory_class=MEMORY_CLASS_BY_LANE[lane_kind],
        lane_id=lane_id,
        lane_kind=lane_kind,
        owner_skill=owner_skill,
        observed_at=observed_at,
        state="historical",
        current_status="completed_task_checkpoint",
        confidence={
            "label": "bounded_high",
            "basis": "all_task_acceptance_items_verified",
            "scope": "task_completion_state_not_external_fact_truth",
        },
        query_types=["history_reason"],
        candidate_label=_bounded_text(objective, 180),
        summary=_bounded_text(objective, 480),
        retrieval_terms=_retrieval_terms(capsule),
        facets={
            "capsule_id": [str(capsule.get("capsule_id") or "")],
            "goal_revision": [str(capsule.get("goal_revision") or 0)],
            "task_outcome": ["completed"],
            "lane_kind": [lane_kind],
        },
        content={
            "event_summary": objective,
            "details": {
                "purpose": _bounded_text(capsule.get("purpose")),
                "declared_required_outputs": _bounded_items(
                    capsule.get("required_outputs"), fields=("id", "text", "status")
                ),
                "verified_acceptance_criteria": _bounded_items(
                    capsule.get("acceptance_criteria"), fields=("id", "text", "status")
                ),
                "stop_condition": _bounded_text(capsule.get("stop_condition"), 800),
                "last_postcondition": _bounded_text(capsule.get("last_postcondition"), 800),
                "retirement": _bounded_items(
                    [capsule.get("retirement")], fields=("outcome", "reason")
                ),
            },
            "applicable_boundaries": [
                "completed task history in the exact declared lane",
                "future history_reason retrieval",
            ],
            "non_applicable_boundaries": [
                "not execution authority",
                "not hidden reasoning",
                "not raw tool output",
                "not sufficient evidence for external factual claims",
            ],
            "evidence_boundary": (
                "Verified completion state from one hash-bound task capsule; open linked "
                "evidence before reusing external factual claims."
            ),
        },
        edges=[{"type": "derived_from", "target_id": value} for value in selected_ids],
        evidence_refs=evidence_refs[:MAX_LIST],
        source_tag="task_checkpoint_promotion",
        belief_status="verified_task_completion",
        source_monitoring={
            "mode": "hash_bound_workfile_snapshot",
            "last_checked_at": observed_at,
            "source_id": source_id,
            "head_sha256": work_state.get("head_sha256"),
        },
        entity_id=f"task:{capsule.get('host_task_key_sha256')}",
        slot="completed_task_checkpoint",
    )


def prepare_task_checkpoint_candidate(
    path: Path,
    *,
    expected_host_task_key_sha256: str,
    lane_id: str,
    lane_kind: str,
    owner_skill: str | None = None,
) -> dict[str, Any]:
    """Read one exact workfile and return a non-writing promotion candidate."""

    if lane_kind not in SUPPORTED_LANES:
        raise ValueError("unsupported_task_checkpoint_lane_kind")
    if not str(lane_id).strip():
        raise ValueError("task_checkpoint_lane_id_required")
    state = rehydrate_cumcwork(
        Path(path),
        expected_host_task_key_sha256=expected_host_task_key_sha256,
    )
    if state.get("status") != "clean":
        raise ValueError(f"cumcwork_not_clean:{state.get('status')}")
    capsule = state.get("latest_capsule")
    if not isinstance(capsule, Mapping):
        raise ValueError("task_checkpoint_capsule_missing")
    reasons = _eligibility_reasons(capsule)
    record = None
    if not reasons:
        record = _build_record(
            capsule,
            workfile=Path(path),
            work_state=state,
            lane_id=str(lane_id).strip(),
            lane_kind=lane_kind,
            owner_skill=owner_skill,
        )
    base = {
        "schema": CANDIDATE_SCHEMA,
        "status": "eligible" if record is not None else "rejected",
        "reason_codes": reasons or ["completed_task_checkpoint_eligible"],
        "source": {
            "capsule_id": capsule.get("capsule_id"),
            "capsule_sha256": _sha256(capsule),
            "workfile_path": str(Path(path).resolve()),
            "workfile_head_sha256": state.get("head_sha256"),
            "work_revision": state.get("work_revision"),
            "host_task_key_sha256": expected_host_task_key_sha256,
        },
        "target": {
            "lane_id": str(lane_id).strip(),
            "lane_kind": lane_kind,
            "memory_class": MEMORY_CLASS_BY_LANE[lane_kind],
            "owner_skill": owner_skill,
        },
        "record": record,
        "durable_memory_written": False,
        "searchable_ready": False,
        "derivation_mode": "synchronous_inline_on_explicit_promotion",
        "background_queue_used": False,
        "raw_evidence_opened": False,
        "authority_granted": False,
        "boundary": (
            "Preparation is read-only. The caller must own the exact lane and memory-write "
            "decision before separately invoking promotion."
        ),
    }
    return {**base, "candidate_sha256": _candidate_hash(base)}


def promote_task_checkpoint_to_memory(
    candidate: Mapping[str, Any],
    *,
    store_root: Path,
    expected_candidate_sha256: str,
) -> dict[str, Any]:
    """Synchronously append and verify one exact eligible checkpoint candidate."""

    if not isinstance(candidate, Mapping) or candidate.get("schema") != CANDIDATE_SCHEMA:
        raise ValueError("invalid_task_checkpoint_candidate")
    actual_hash = _candidate_hash(candidate)
    if (
        not expected_candidate_sha256
        or candidate.get("candidate_sha256") != expected_candidate_sha256
        or actual_hash != expected_candidate_sha256
    ):
        raise ValueError("task_checkpoint_candidate_hash_mismatch")
    if candidate.get("status") != "eligible" or not isinstance(candidate.get("record"), Mapping):
        return {
            "schema": PROMOTION_RECEIPT_SCHEMA,
            "status": "rejected",
            "reason_codes": list(candidate.get("reason_codes") or ["candidate_not_eligible"]),
            "candidate_sha256": expected_candidate_sha256,
            "canonical_status": "not_written",
            "search_index_status": "not_applicable",
            "durable_memory_written": False,
            "searchable_ready": False,
            "derivation_mode": "synchronous_inline",
            "background_queue_used": False,
            "raw_evidence_opened": False,
            "authority_granted": False,
        }
    record = _copy(candidate["record"])
    validate_memory_record(record)
    target = candidate.get("target")
    owner = record.get("owner")
    if not isinstance(target, Mapping) or not isinstance(owner, Mapping):
        raise ValueError("task_checkpoint_target_binding_missing")
    if (
        target.get("lane_id") != owner.get("lane_id")
        or target.get("lane_kind") != owner.get("lane_kind")
        or target.get("memory_class") != record.get("memory_class")
        or target.get("owner_skill") != owner.get("skill_id")
    ):
        raise ValueError("task_checkpoint_target_binding_mismatch")
    append_receipt = append_memory_record(Path(store_root), record)
    store_check = check_memory_store(Path(store_root))
    search = search_memory_store(
        Path(store_root),
        str(record["record_id"]),
        query_type="history_reason",
        limit=1,
    )
    searchable_ready = (
        store_check.get("status") == "pass"
        and search.get("selected_record_ids") == [record["record_id"]]
    )
    return {
        "schema": PROMOTION_RECEIPT_SCHEMA,
        "status": (
            "searchable_ready" if searchable_ready else "durable_written_verification_failed"
        ),
        "candidate_sha256": expected_candidate_sha256,
        "record_id": record["record_id"],
        "record_sha256": record["record_sha256"],
        "append_status": append_receipt.get("status"),
        "canonical_status": "durable",
        "search_index_status": "ready" if searchable_ready else "verification_failed",
        "store_check_status": store_check.get("status"),
        "durable_memory_written": append_receipt.get("status") == "appended",
        "record_already_present": append_receipt.get("status") == "unchanged",
        "searchable_ready": searchable_ready,
        "derivation_mode": "synchronous_inline",
        "background_queue_used": False,
        "raw_evidence_opened": False,
        "authority_granted": False,
        "store_root": str(Path(store_root).resolve()),
    }


def _load_object(*, file_path: str | None, json_text: str | None) -> dict[str, Any]:
    value = (
        json.loads(Path(file_path).read_text(encoding="utf-8-sig"))
        if file_path
        else json.loads(str(json_text))
    )
    if not isinstance(value, dict):
        raise ValueError("task_checkpoint_input_must_be_object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "promote"))
    parser.add_argument("--workfile")
    parser.add_argument("--host-task-key-sha256")
    parser.add_argument("--lane-id")
    parser.add_argument("--lane-kind", choices=sorted(SUPPORTED_LANES))
    parser.add_argument("--owner-skill")
    candidate_group = parser.add_mutually_exclusive_group()
    candidate_group.add_argument("--candidate-file")
    candidate_group.add_argument("--candidate-json")
    parser.add_argument("--expected-candidate-sha256")
    parser.add_argument("--store-root")
    args = parser.parse_args()
    if args.operation == "prepare":
        if not all((args.workfile, args.host_task_key_sha256, args.lane_id, args.lane_kind)):
            parser.error("prepare requires workfile, host task key, lane id, and lane kind")
        result = prepare_task_checkpoint_candidate(
            Path(args.workfile),
            expected_host_task_key_sha256=args.host_task_key_sha256,
            lane_id=args.lane_id,
            lane_kind=args.lane_kind,
            owner_skill=args.owner_skill,
        )
    else:
        if not (args.candidate_file or args.candidate_json):
            parser.error("promote requires a candidate file or candidate JSON")
        if not args.expected_candidate_sha256 or not args.store_root:
            parser.error("promote requires expected candidate SHA-256 and store root")
        result = promote_task_checkpoint_to_memory(
            _load_object(file_path=args.candidate_file, json_text=args.candidate_json),
            store_root=Path(args.store_root),
            expected_candidate_sha256=args.expected_candidate_sha256,
        )
    print(_canonical_json(result))
    return 0 if result.get("status") not in {"rejected", "durable_written_verification_failed"} else 1


__all__ = [
    "CANDIDATE_SCHEMA",
    "PROMOTION_RECEIPT_SCHEMA",
    "prepare_task_checkpoint_candidate",
    "promote_task_checkpoint_to_memory",
]


if __name__ == "__main__":
    raise SystemExit(main())
