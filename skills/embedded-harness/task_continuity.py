"""Task-local continuity, progress, reminder, and transport primitives for CBH.

The module is deliberately process-local and side-effect free except for its
optional JSONL worker entry point.  Callers own the returned capsule and must
send it back with the next event; this module never writes task state to disk.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Any


DECISION_SCHEMA = "cbh.task_continuity_decision.v1"
CAPSULE_SCHEMA = "cbh.task_capsule.v1"
EVENT_SCHEMA = "cbh.task_event.v1"
TRANSITION_SCHEMA = "cbh.task_transition.v1"
REMINDER_SCHEMA = "cbh.dynamic_reminder.v1"
TRANSPORT_SCHEMA = "cbh.transport_plan.v1"
PAGE_SCHEMA = "cbh.transport_page.v1"
WORKER_SCHEMA = "cbh.task_continuity_worker_response.v1"

LIFECYCLES = {"DORMANT", "ARMED", "ACTIVE", "VERIFYING", "RETIRED"}
DEFAULT_MAX_CHARS = 20_000
DEFAULT_MAX_ITEMS = 100
MAX_EVENT_HISTORY = 256
MAX_OBJECTIVE_CHARS = 4_000
MAX_CONTEXT_LIST_ITEMS = 12

_WRITE_PROFILES = {
    "in_place_patch",
    "append_delta",
    "add_new_artifact",
    "section_replace",
    "full_rewrite",
    "supersede_with_link",
    "archive_or_move",
    "delete_record_content",
    "delete_from_disk",
}
_TOOL_ACTIONS = {
    "perform_external_research_route",
    "direct_outcome_first",
    "retrieve_matching_memory",
    "resolve_conversation_link",
    "prepare_task_local_correction_bundle",
}
_WRITE_PROMPT = re.compile(
    r"(?i)(修改|更新|修复|写入|保存|创建|新增|删除|部署|安装|提交|推送|配置|"
    r"\b(?:modify|update|fix|patch|write|save|create|add|delete|deploy|install|commit|push|configure)\b)"
)
_TOOL_PROMPT = re.compile(
    r"(?i)(检查|打开|搜索|运行|执行|验证|抓取|下载|调用|浏览|登录|"
    r"\b(?:inspect|check|open|search|run|execute|verify|fetch|download|browse|login|tool)\b)"
)
_LONG_PROMPT = re.compile(
    r"(?i)(分阶段|多阶段|持续|长程|直到|做完|完成后|然后|并且|继续执行|"
    r"\b(?:multi[- ]stage|long[- ]running|continue until|do not stop|after that|then)\b)"
)
_RESUME_PROMPT = re.compile(r"(?i)(继续|接续|恢复|未完成|中断|\b(?:resume|continue|interrupted)\b)")
_READ_ONLY_PROMPT = re.compile(
    r"(?i)(只读|不要修改|不修改|仅解释|只回答|讨论一下|"
    r"\b(?:read[- ]only|do not modify|explain only|discussion only)\b)"
)
_INLINE_PAYLOAD_KEYS = {"data", "blob", "bytes", "base64"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _copy(value: Any) -> Any:
    return copy.deepcopy(value)


def _bounded_text(value: Any, limit: int = MAX_OBJECTIVE_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[:limit]


def _estimated_tokens(value: str) -> int:
    """Conservative mixed-language estimate for the host's 1000-token entry cap."""

    ascii_chars = sum(1 for char in value if ord(char) < 128)
    non_ascii_chars = len(value) - ascii_chars
    return non_ascii_chars + ((ascii_chars + 2) // 3)


def _event_id(task_event: Mapping[str, Any]) -> str:
    value = task_event.get("event_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("task_event.event_id must be a non-empty string")
    return value


def _event_type(task_event: Mapping[str, Any]) -> str:
    value = task_event.get("type")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("task_event.type must be a non-empty string")
    return value


def _binding_ids(route_receipt: Mapping[str, Any]) -> set[str]:
    bindings = route_receipt.get("action_bindings")
    if not isinstance(bindings, Sequence) or isinstance(bindings, (str, bytes)):
        return set()
    return {
        str(item.get("action"))
        for item in bindings
        if isinstance(item, Mapping) and item.get("action")
    }


def _decision_reasons(
    route_receipt: Mapping[str, Any], task_event: Mapping[str, Any]
) -> list[str]:
    reasons: list[str] = []
    objective = _bounded_text(task_event.get("objective") or task_event.get("prompt"))
    edit_profile = str(route_receipt.get("edit_operation_profile") or "none")
    memory_mode = str(route_receipt.get("memory_mode") or "none")
    tool_surface = str(route_receipt.get("tool_surface_need") or "none")
    event_type = _event_type(task_event)

    explicit_write = bool(task_event.get("write_intent"))
    route_write = edit_profile in _WRITE_PROFILES or memory_mode in {"write", "update"}
    prompt_write = bool(_WRITE_PROMPT.search(objective)) and not bool(
        _READ_ONLY_PROMPT.search(objective)
    )
    if explicit_write or route_write or prompt_write or event_type == "write_result_received":
        reasons.append("write_intent")

    tool_event = event_type in {
        "candidate_selected",
        "preflight_completed",
        "tool_dispatched",
        "tool_result_received",
        "write_result_received",
        "verifier_pending",
        "verifier_completed",
        "unchanged_dispatch_repeated",
        "transport_threshold_crossed",
    }
    route_tool = tool_surface not in {"", "none", "not_required"} or bool(
        _binding_ids(route_receipt) & _TOOL_ACTIONS
    )
    if bool(task_event.get("tool_required")) or tool_event or route_tool or _TOOL_PROMPT.search(objective):
        reasons.append("tool_required")

    if bool(task_event.get("multi_stage")) or _LONG_PROMPT.search(objective):
        reasons.append("multi_stage_task")
    if bool(task_event.get("resume")) or event_type in {"task_interrupted", "continuation_required"} or _RESUME_PROMPT.search(objective):
        reasons.append("task_resume")
    if bool(task_event.get("long_running")):
        reasons.append("long_running_task")
    if bool(task_event.get("open_loops")):
        reasons.append("open_loop")
    if event_type == "unchanged_dispatch_repeated" or bool(task_event.get("prior_failure")):
        reasons.append("prior_failure")
    if task_event.get("continuity_requested") is True:
        reasons.append("explicit_request")
    return list(dict.fromkeys(reasons))


def decide_task_continuity(
    route_receipt: Mapping[str, Any],
    task_event: Mapping[str, Any],
    capsule: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the task-local activation decision without allocating state."""

    if not isinstance(route_receipt, Mapping):
        raise ValueError("route_receipt must be an object")
    if not isinstance(task_event, Mapping):
        raise ValueError("task_event must be an object")
    event_id = _event_id(task_event)
    reasons = _decision_reasons(route_receipt, task_event)
    lifecycle = str(capsule.get("lifecycle")) if isinstance(capsule, Mapping) else None
    if lifecycle in {"ARMED", "ACTIVE", "VERIFYING"}:
        decision = "continue"
        if not reasons:
            reasons = ["existing_active_capsule"]
        host_delivery = "ready"
    elif reasons:
        decision = "arm"
        host_delivery = "ready"
    else:
        decision = "dormant"
        host_delivery = "not_needed"
    return {
        "schema": DECISION_SCHEMA,
        "decision": decision,
        "reasons": reasons,
        "source_event_ids": [event_id],
        "host_delivery": host_delivery,
    }


def _normalize_criteria(
    criteria: Any,
    *,
    write_intent: bool,
    tool_required: bool,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(criteria, Sequence) and not isinstance(criteria, (str, bytes)):
        for index, item in enumerate(criteria):
            if isinstance(item, Mapping):
                criterion_id = _bounded_text(item.get("id") or f"criterion_{index + 1}", 160)
                text = _bounded_text(item.get("text") or item.get("description") or criterion_id, 800)
            else:
                criterion_id = f"criterion_{index + 1}"
                text = _bounded_text(item, 800)
            if criterion_id and text:
                normalized.append({"id": criterion_id, "text": text, "status": "unknown"})
    if normalized:
        return normalized
    if write_intent:
        return [
            {"id": "write_applied", "text": "requested mutation is applied", "status": "unknown"},
            {"id": "write_verified", "text": "mutation postcondition is verified", "status": "unknown"},
        ]
    if tool_required:
        return [
            {"id": "tool_result_observed", "text": "required tool result is observed and checked", "status": "unknown"}
        ]
    return [{"id": "task_goal", "text": "task objective is satisfied", "status": "unknown"}]


def _progress_lists(capsule: dict[str, Any]) -> None:
    criteria = capsule.get("acceptance_criteria") or []
    capsule["verified_completed"] = [
        _copy(item) for item in criteria if item.get("status") == "verified"
    ]
    capsule["inferred_progress"] = [
        _copy(item) for item in criteria if item.get("status") == "inferred"
    ]
    capsule["unknown_progress"] = [
        _copy(item) for item in criteria if item.get("status") == "unknown"
    ]
    capsule["remaining_work"] = [
        _copy(item) for item in criteria if item.get("status") != "verified"
    ]


def _first_remaining(capsule: Mapping[str, Any]) -> Mapping[str, Any] | None:
    values = capsule.get("remaining_work")
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        return next((item for item in values if isinstance(item, Mapping)), None)
    return None


def new_task_capsule(
    route_receipt: Mapping[str, Any], task_event: Mapping[str, Any]
) -> dict[str, Any]:
    """Create one deterministic, process-local ARMED capsule."""

    decision = decide_task_continuity(route_receipt, task_event)
    if decision["decision"] == "dormant":
        raise ValueError("cannot create a capsule for a dormant task")
    objective = _bounded_text(task_event.get("objective") or task_event.get("prompt"))
    event_id = _event_id(task_event)
    task_key = _canonical_json(
        {
            "objective": objective,
            "task_key": task_event.get("task_key"),
            "lane": route_receipt.get("project_lane"),
        }
    )
    task_key_sha256 = _sha256_text(task_key)
    reasons = set(decision["reasons"])
    criteria = _normalize_criteria(
        task_event.get("acceptance_criteria"),
        write_intent="write_intent" in reasons,
        tool_required="tool_required" in reasons,
    )
    capsule: dict[str, Any] = {
        "schema": CAPSULE_SCHEMA,
        "capsule_id": _sha256_text(f"{task_key_sha256}:{event_id}")[:24],
        "task_key_sha256": task_key_sha256,
        "host_task_key_sha256": (
            _sha256_text(str(task_event.get("task_key")))
            if task_event.get("task_key") is not None
            else None
        ),
        "state_version": 1,
        "lifecycle": "ARMED",
        "activation_reasons": decision["reasons"],
        "objective": objective,
        "acceptance_criteria": criteria,
        "constraints": [
            _bounded_text(value, 800)
            for value in (task_event.get("constraints") or [])
            if _bounded_text(value, 800)
        ][:MAX_CONTEXT_LIST_ITEMS],
        "current_stage": _bounded_text(task_event.get("current_stage") or "planning", 160),
        "verified_completed": [],
        "inferred_progress": [],
        "unknown_progress": [],
        "current_step": None,
        "remaining_work": [],
        "next_action": None,
        "next_action_reason": "earliest_incomplete_acceptance_item",
        "blocking_condition": None,
        "last_postcondition": None,
        "unresolved_failures": [],
        "progress_revision": 1,
        "execution_log_cursor": task_event.get("execution_log_cursor"),
        "evidence_refs": list(task_event.get("evidence_refs") or [])[:MAX_CONTEXT_LIST_ITEMS],
        "active_frames": [],
        "transport": {},
        "resume_entry": None,
        "applied_event_ids": [event_id],
        "last_event": {
            "event_id": event_id,
            "type": _event_type(task_event),
            "observed_at": task_event.get("observed_at"),
        },
        "reminder_state": {"emitted": []},
        "authority": {"granted": False, "consumed": False, "source": "none"},
        "persistence": "process_local_only",
    }
    _progress_lists(capsule)
    first = _first_remaining(capsule)
    capsule["next_action"] = first.get("text") if first else None
    return capsule


def initialize_task_capsule(
    route_receipt: Mapping[str, Any], task_event: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Create a capsule and preserve a substantive first event exactly once."""

    if _event_type(task_event) == "task_observed":
        return new_task_capsule(route_receipt, task_event), None
    bootstrap = _copy(task_event)
    bootstrap["event_id"] = f"{_event_id(task_event)}:activation"
    bootstrap["type"] = "task_observed"
    capsule = new_task_capsule(route_receipt, bootstrap)
    transition = apply_task_event(capsule, task_event)
    return transition["capsule"], transition


def _set_criterion_status(
    capsule: dict[str, Any], criterion_id: str | None, status: str
) -> bool:
    if status not in {"verified", "inferred", "unknown"}:
        raise ValueError("invalid progress status")
    criteria = capsule.get("acceptance_criteria") or []
    selected: dict[str, Any] | None = None
    if criterion_id:
        selected = next(
            (item for item in criteria if str(item.get("id")) == criterion_id), None
        )
    if selected is None:
        selected = next((item for item in criteria if item.get("status") != "verified"), None)
    if selected is None or selected.get("status") == status:
        return False
    selected["status"] = status
    return True


def _merge_progress_snapshot(
    capsule: dict[str, Any], task_event: Mapping[str, Any]
) -> bool:
    incoming = task_event.get("acceptance_criteria")
    if not isinstance(incoming, Sequence) or isinstance(incoming, (str, bytes)):
        return False
    normalized = _normalize_criteria(incoming, write_intent=False, tool_required=False)
    if not normalized:
        return False
    for index, item in enumerate(incoming):
        if not isinstance(item, Mapping):
            continue
        status = str(item.get("status") or "unknown")
        normalized[index]["status"] = status if status in {"inferred", "unknown"} else "unknown"
    changed = normalized != capsule.get("acceptance_criteria")
    if changed:
        capsule["acceptance_criteria"] = normalized
    return changed


def _append_unique_failure(capsule: dict[str, Any], task_event: Mapping[str, Any]) -> None:
    signature = _bounded_text(task_event.get("subject_signature"), 128)
    identity = {
        "signature": signature or None,
        "error_class": _bounded_text(task_event.get("error_class") or "unknown", 160),
        "event_id": _event_id(task_event),
    }
    failures = capsule.setdefault("unresolved_failures", [])
    if not any(
        item.get("signature") == identity["signature"]
        and item.get("error_class") == identity["error_class"]
        for item in failures
        if isinstance(item, Mapping)
    ):
        failures.append(identity)
        del failures[MAX_CONTEXT_LIST_ITEMS:]


def apply_task_event(
    capsule: Mapping[str, Any], task_event: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply one event idempotently and return an auditable transition."""

    if not isinstance(capsule, Mapping) or capsule.get("schema") != CAPSULE_SCHEMA:
        raise ValueError("invalid task capsule")
    if str(capsule.get("lifecycle")) not in LIFECYCLES:
        raise ValueError("invalid task capsule lifecycle")
    if not isinstance(task_event, Mapping):
        raise ValueError("task_event must be an object")
    event_id = _event_id(task_event)
    event_type = _event_type(task_event)
    expected_task_key = capsule.get("host_task_key_sha256")
    event_task_key = task_event.get("task_key")
    if (
        expected_task_key is not None
        and event_task_key is not None
        and _sha256_text(str(event_task_key)) != expected_task_key
    ):
        raise ValueError("task_identity_mismatch")
    if capsule.get("lifecycle") == "RETIRED":
        unchanged = _copy(capsule)
        return {
            "schema": TRANSITION_SCHEMA,
            "capsule": unchanged,
            "changed": False,
            "previous_lifecycle": "RETIRED",
            "lifecycle": "RETIRED",
            "progress_delta": [],
            "event_outcome": "retired_ignored",
            "transition_reasons": ["retired_capsule_is_terminal"],
            "event_type": event_type,
        }
    prior_ids = list(capsule.get("applied_event_ids") or [])
    if event_id in prior_ids:
        unchanged = _copy(capsule)
        return {
            "schema": TRANSITION_SCHEMA,
            "capsule": unchanged,
            "changed": False,
            "previous_lifecycle": unchanged["lifecycle"],
            "lifecycle": unchanged["lifecycle"],
            "progress_delta": [],
            "event_outcome": "duplicate_ignored",
            "transition_reasons": ["event_id_already_applied"],
            "event_type": event_type,
        }

    updated = _copy(capsule)
    previous_lifecycle = str(updated["lifecycle"])
    progress_delta: list[str] = []
    reasons: list[str] = []
    updated["applied_event_ids"] = [*prior_ids, event_id]
    updated["last_event"] = {
        "event_id": event_id,
        "type": event_type,
        "observed_at": task_event.get("observed_at"),
        "evidence_refs": list(task_event.get("evidence_refs") or [])[:MAX_CONTEXT_LIST_ITEMS],
    }
    if task_event.get("current_stage"):
        updated["current_stage"] = _bounded_text(task_event["current_stage"], 160)
    if task_event.get("current_step"):
        updated["current_step"] = _bounded_text(task_event["current_step"], 800)
    if task_event.get("next_action"):
        updated["next_action"] = _bounded_text(task_event["next_action"], 800)
        updated["next_action_reason"] = _bounded_text(
            task_event.get("next_action_reason") or "event_declared_next_action", 320
        )
    if task_event.get("blocking_condition") is not None:
        updated["blocking_condition"] = _bounded_text(task_event["blocking_condition"], 400)
    if task_event.get("postcondition") is not None:
        updated["last_postcondition"] = _bounded_text(task_event["postcondition"], 800)
    evidence_refs = [
        _bounded_text(value, 600)
        for value in (task_event.get("evidence_refs") or [])
        if _bounded_text(value, 600)
    ]
    for ref in evidence_refs:
        if ref not in updated["evidence_refs"]:
            updated["evidence_refs"].append(ref)
    updated["evidence_refs"] = updated["evidence_refs"][-MAX_CONTEXT_LIST_ITEMS:]

    if event_type in {"candidate_selected", "preflight_completed", "tool_dispatched"}:
        updated["lifecycle"] = "ACTIVE"
        reasons.append("substantive_action_observed")
    elif event_type in {"tool_result_received", "write_result_received"}:
        satisfied = task_event.get("postcondition_satisfied") is True
        status = "verified" if satisfied else "inferred"
        if _set_criterion_status(
            updated,
            _bounded_text(task_event.get("acceptance_id"), 160) or None,
            status,
        ):
            progress_delta.append(f"criterion_{status}")
        updated["lifecycle"] = "VERIFYING"
        reasons.append("result_requires_acceptance_reconciliation")
    elif event_type == "verifier_pending":
        updated["lifecycle"] = "VERIFYING"
        reasons.append("verifier_pending")
    elif event_type == "verifier_completed":
        satisfied = task_event.get("postcondition_satisfied") is True
        status = "verified" if satisfied else "inferred"
        if _set_criterion_status(
            updated,
            _bounded_text(task_event.get("acceptance_id"), 160) or None,
            status,
        ):
            progress_delta.append(f"criterion_{status}")
        if satisfied:
            updated["blocking_condition"] = None
        updated["lifecycle"] = "VERIFYING"
        reasons.append("verifier_result_observed")
    elif event_type == "unchanged_dispatch_repeated":
        updated["lifecycle"] = "ACTIVE"
        _append_unique_failure(updated, task_event)
        reasons.append("unchanged_failed_dispatch_requires_changed_path")
    elif event_type == "task_interrupted":
        updated["lifecycle"] = "ACTIVE"
        updated["resume_entry"] = {
            "event_id": event_id,
            "current_stage": updated.get("current_stage"),
            "next_action": updated.get("next_action"),
            "remaining_ids": [item.get("id") for item in updated.get("remaining_work", [])],
        }
        reasons.append("task_interrupted_with_open_state")
    elif event_type == "task_abandoned":
        updated["lifecycle"] = "RETIRED"
        reasons.append("task_explicitly_abandoned")
    elif event_type == "task_complete_requested":
        updated["lifecycle"] = "VERIFYING"
        reasons.append("completion_requires_all_acceptance_items")
    elif event_type == "progress_snapshot":
        if _merge_progress_snapshot(updated, task_event):
            progress_delta.append("plan_progress_refreshed")
        updated["lifecycle"] = "ACTIVE"
        reasons.append("observable_plan_progress_refreshed")
    elif event_type in {"stage_exit", "continuation_required", "transport_threshold_crossed"}:
        updated["lifecycle"] = "ACTIVE"
        reasons.append(event_type)
    elif event_type == "task_observed":
        reasons.append("task_observation_refreshed")
    else:
        reasons.append("event_recorded_without_semantic_promotion")

    _progress_lists(updated)
    all_verified = bool(updated["acceptance_criteria"]) and not updated["remaining_work"]
    if event_type in {"verifier_completed", "task_complete_requested", "stage_exit"}:
        if all_verified and task_event.get("retire_if_complete") is True:
            updated["lifecycle"] = "RETIRED"
            updated["next_action"] = None
            updated["next_action_reason"] = "all_acceptance_items_verified"
            reasons.append("all_acceptance_items_verified")
        elif event_type == "task_complete_requested" and not all_verified:
            updated["lifecycle"] = "VERIFYING"

    if updated["lifecycle"] != "RETIRED":
        first = _first_remaining(updated)
        if first is not None and not task_event.get("next_action"):
            updated["next_action"] = first.get("text")
            updated["next_action_reason"] = "earliest_incomplete_acceptance_item"
    updated["progress_revision"] = int(updated.get("progress_revision") or 0) + 1
    return {
        "schema": TRANSITION_SCHEMA,
        "capsule": updated,
        "changed": True,
        "previous_lifecycle": previous_lifecycle,
        "lifecycle": updated["lifecycle"],
        "progress_delta": progress_delta,
        "event_outcome": _bounded_text(task_event.get("outcome") or "observed", 160),
        "transition_reasons": list(dict.fromkeys(reasons)),
        "event_type": event_type,
    }


def reconcile_progress(
    capsule: Mapping[str, Any], evidence_event: Mapping[str, Any]
) -> dict[str, Any]:
    """Compatibility name for applying one evidence-bearing progress event."""

    return apply_task_event(capsule, evidence_event)


def _reminder_candidate(
    capsule: Mapping[str, Any], transition: Mapping[str, Any]
) -> tuple[str, str, str] | None:
    event_type = str(transition.get("event_type") or "")
    last_event = capsule.get("last_event") if isinstance(capsule.get("last_event"), Mapping) else {}
    if event_type == "unchanged_dispatch_repeated":
        failures = capsule.get("unresolved_failures") or []
        signature = failures[-1].get("signature") if failures and isinstance(failures[-1], Mapping) else "unknown"
        return (
            "unchanged_dispatch_repeated",
            f"unchanged_dispatch:{signature}",
            "select a changed, mechanically verified dispatch path before retrying",
        )
    if event_type == "verifier_pending":
        return (
            "verifier_pending",
            f"verifier_pending:{last_event.get('event_id')}",
            "run or obtain the declared verifier before claiming completion",
        )
    if event_type in {"tool_result_received", "write_result_received"} and transition.get(
        "progress_delta"
    ) == ["criterion_inferred"]:
        return (
            "missing_postcondition",
            f"missing_postcondition:{last_event.get('event_id')}",
            "verify the semantic postcondition; command success alone is insufficient",
        )
    if event_type in {"stage_exit", "task_complete_requested"} and capsule.get("remaining_work"):
        return (
            "open_loops_at_stage_exit",
            f"open_loops:{capsule.get('current_stage')}",
            "continue from the earliest incomplete acceptance item or report the blocker",
        )
    if event_type in {"transport_threshold_crossed", "continuation_required"}:
        return (
            "transport_continuation_required",
            f"transport:{last_event.get('event_id')}",
            "continue with the content-bound cursor and preserve the full-result hash",
        )
    return None


def build_dynamic_reminders(
    capsule: Mapping[str, Any], transition: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Emit at most one transition reminder and bind dedupe to the revision."""

    candidate = _reminder_candidate(capsule, transition)
    if candidate is None:
        return []
    trigger, base_key, required_action = candidate
    revision = int(capsule.get("progress_revision") or 0)
    receipt_key = f"{base_key}@{revision}"
    reminder_state = capsule.get("reminder_state")
    emitted = list(reminder_state.get("emitted") or []) if isinstance(reminder_state, Mapping) else []
    if receipt_key in emitted:
        return []
    snapshot = _copy(capsule)
    snapshot["reminder_state"] = {"emitted": [*emitted, receipt_key][-MAX_EVENT_HISTORY:]}
    reminder_id = _sha256_text(f"{snapshot.get('capsule_id')}:{receipt_key}")[:24]
    return [
        {
            "schema": REMINDER_SCHEMA,
            "reminder_id": reminder_id,
            "capsule_id": snapshot.get("capsule_id"),
            "progress_revision": revision,
            "trigger": trigger,
            "scope": "current_task_only",
            "severity": "action_required",
            "dedupe_key": base_key,
            "required_action": required_action,
            "expires_when": "required_action_satisfied_or_task_retired",
            "evidence_refs": list(snapshot.get("evidence_refs") or []),
            "capsule_snapshot": snapshot,
        }
    ]


def _positive_int(value: Any, *, name: str, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def plan_transport(
    capsule: Mapping[str, Any] | None,
    result_shape: Mapping[str, Any],
    host_limits: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan one bounded forwarding envelope; host hard limits only tighten."""

    if not isinstance(result_shape, Mapping):
        raise ValueError("result_shape must be an object")
    limits = host_limits if isinstance(host_limits, Mapping) else {}
    max_chars = min(
        DEFAULT_MAX_CHARS,
        _positive_int(limits.get("max_chars"), name="max_chars", default=DEFAULT_MAX_CHARS),
    )
    max_items = min(
        DEFAULT_MAX_ITEMS,
        _positive_int(limits.get("max_items"), name="max_items", default=DEFAULT_MAX_ITEMS),
    )
    kind = str(result_shape.get("kind") or "canonical_json")
    if kind not in {"text", "items", "canonical_json"}:
        kind = "canonical_json"
    return {
        "schema": TRANSPORT_SCHEMA,
        "profile": "evidence_preserving",
        "mode": kind,
        "max_chars": max_chars,
        "max_items": max_items,
        "host_hard_chars": limits.get("max_chars"),
        "host_hard_items": limits.get("max_items"),
        "mandatory_paths": [
            "schema",
            "objective",
            "acceptance_criteria",
            "unresolved_failures",
            "next_action",
            "full_result_sha256",
            "next_cursor",
        ],
        "capsule_revision": capsule.get("progress_revision") if isinstance(capsule, Mapping) else None,
        "continuation_on_overflow": True,
    }


def _sanitize_for_transport(value: Any) -> Any:
    if isinstance(value, Mapping):
        media = value.get("type") in {"image", "audio", "resource"}
        sanitized: dict[str, Any] = {}
        omitted = False
        for key, item in value.items():
            if key in _INLINE_PAYLOAD_KEYS and (media or isinstance(item, (bytes, bytearray))):
                omitted = True
                continue
            if key in {"image_url", "audio_url"} and isinstance(item, str) and item.startswith("data:"):
                omitted = True
                continue
            sanitized[str(key)] = _sanitize_for_transport(item)
        if omitted:
            sanitized["inline_payload_omitted_from_text"] = True
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize_for_transport(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return {"binary_payload_omitted": True, "sha256": hashlib.sha256(bytes(value)).hexdigest()}
    return value


def _validate_cursor(cursor: Mapping[str, Any] | None, digest: str, mode: str) -> None:
    if cursor is None:
        return
    if not isinstance(cursor, Mapping):
        raise ValueError("cursor must be an object or null")
    if cursor.get("result_sha256") != digest:
        raise ValueError("cursor_result_hash_mismatch")
    if cursor.get("mode") not in {None, mode}:
        raise ValueError("cursor_mode_mismatch")


def page_result(
    normalized_result: Any,
    transport_plan: Mapping[str, Any],
    cursor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Page safe normalized content with a hash-bound continuation cursor."""

    if not isinstance(transport_plan, Mapping) or transport_plan.get("schema") != TRANSPORT_SCHEMA:
        raise ValueError("invalid transport plan")
    max_chars = _positive_int(transport_plan.get("max_chars"), name="max_chars", default=DEFAULT_MAX_CHARS)
    max_items = _positive_int(transport_plan.get("max_items"), name="max_items", default=DEFAULT_MAX_ITEMS)
    safe = _sanitize_for_transport(normalized_result)
    if isinstance(safe, list):
        mode = "items"
        full_text = _canonical_json(safe)
        digest = _sha256_text(full_text)
        _validate_cursor(cursor, digest, mode)
        start = int(cursor.get("next_item") or 0) if cursor else 0
        if start < 0 or start > len(safe):
            raise ValueError("cursor_item_out_of_range")
        page_items: list[Any] = []
        index = start
        while index < len(safe) and len(page_items) < max_items:
            prospective = [*page_items, safe[index]]
            if len(_canonical_json(prospective)) > max_chars:
                if not page_items:
                    raise ValueError("single_item_exceeds_transport_char_limit")
                break
            page_items = prospective
            index += 1
        next_cursor = (
            {"result_sha256": digest, "mode": mode, "next_item": index}
            if index < len(safe)
            else None
        )
        page_text = _canonical_json(page_items)
        return {
            "schema": PAGE_SCHEMA,
            "mode": mode,
            "items": page_items,
            "page_sha256": _sha256_text(page_text),
            "full_result_sha256": digest,
            "original_items": len(safe),
            "forwarded_items": len(page_items),
            "uncovered_items": len(safe) - index,
            "forwarded_chars": len(page_text),
            "next_cursor": next_cursor,
            "complete": next_cursor is None,
        }

    mode = "text"
    full_text = safe if isinstance(safe, str) else _canonical_json(safe)
    digest = _sha256_text(full_text)
    _validate_cursor(cursor, digest, mode)
    start = int(cursor.get("next_char") or 0) if cursor else 0
    if start < 0 or start > len(full_text):
        raise ValueError("cursor_char_out_of_range")
    end = min(len(full_text), start + max_chars)
    content = full_text[start:end]
    next_cursor = (
        {"result_sha256": digest, "mode": mode, "next_char": end}
        if end < len(full_text)
        else None
    )
    return {
        "schema": PAGE_SCHEMA,
        "mode": mode,
        "content": content,
        "page_sha256": _sha256_text(content),
        "full_result_sha256": digest,
        "original_chars": len(full_text),
        "forwarded_chars": len(content),
        "uncovered_chars": len(full_text) - end,
        "next_cursor": next_cursor,
        "complete": next_cursor is None,
    }


def _context_item(item: Any) -> Any:
    if isinstance(item, Mapping):
        return {
            key: item.get(key)
            for key in ("id", "text", "status", "signature", "error_class")
            if item.get(key) is not None
        }
    return _bounded_text(item, 800)


def build_task_capsule_context(
    capsule: Mapping[str, Any],
    reminders: Sequence[Mapping[str, Any]],
    *,
    host_limits: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one bounded model-facing operational context entry."""

    if capsule.get("lifecycle") == "RETIRED":
        return {
            "schema": "cbh.task_capsule_context.v1",
            "entry": None,
            "control_entry": None,
            "char_count": 0,
            "delivery": "not_needed",
        }
    max_chars = min(3_200, _positive_int(
        host_limits.get("max_chars") if isinstance(host_limits, Mapping) else None,
        name="max_chars",
        default=3_200,
    ))
    max_tokens = min(
        900,
        _positive_int(
            host_limits.get("max_tokens") if isinstance(host_limits, Mapping) else None,
            name="max_tokens",
            default=900,
        ),
    )
    full_capsule_sha256 = _sha256_text(
        _canonical_json(_sanitize_for_transport(capsule))
    )
    source_lists = {
        "constraints": list(capsule.get("constraints") or []),
        "verified_completed": list(capsule.get("verified_completed") or []),
        "inferred_progress": list(capsule.get("inferred_progress") or []),
        "remaining_work": list(capsule.get("remaining_work") or []),
        "unresolved_failures": list(capsule.get("unresolved_failures") or []),
    }
    uncovered_counts = {
        name: max(0, len(values) - MAX_CONTEXT_LIST_ITEMS)
        for name, values in source_lists.items()
        if len(values) > MAX_CONTEXT_LIST_ITEMS
    }
    payload = {
        "schema": CAPSULE_SCHEMA,
        "capsule_id": capsule.get("capsule_id"),
        "state_version": capsule.get("state_version"),
        "lifecycle": capsule.get("lifecycle"),
        "progress_revision": capsule.get("progress_revision"),
        "objective": capsule.get("objective"),
        "constraints": source_lists["constraints"][:MAX_CONTEXT_LIST_ITEMS],
        "current_stage": capsule.get("current_stage"),
        "verified_completed": [
            _context_item(item) for item in (capsule.get("verified_completed") or [])[:MAX_CONTEXT_LIST_ITEMS]
        ],
        "inferred_progress": [
            _context_item(item) for item in (capsule.get("inferred_progress") or [])[:MAX_CONTEXT_LIST_ITEMS]
        ],
        "remaining_work": [
            _context_item(item) for item in (capsule.get("remaining_work") or [])[:MAX_CONTEXT_LIST_ITEMS]
        ],
        "current_step": capsule.get("current_step"),
        "next_action": capsule.get("next_action"),
        "next_action_reason": capsule.get("next_action_reason"),
        "blocking_condition": capsule.get("blocking_condition"),
        "last_postcondition": capsule.get("last_postcondition"),
        "unresolved_failures": [
            _context_item(item) for item in (capsule.get("unresolved_failures") or [])[:MAX_CONTEXT_LIST_ITEMS]
        ],
        "full_capsule_sha256": full_capsule_sha256,
        "uncovered_counts": uncovered_counts,
        "resume_entry": capsule.get("resume_entry"),
        "reminders": [
            {
                "trigger": item.get("trigger"),
                "required_action": item.get("required_action"),
                "expires_when": item.get("expires_when"),
            }
            for item in reminders[:4]
        ],
        "boundary": "Operational context only: preserve permissions, verify postconditions, and do not treat this capsule as authority or hidden reasoning.",
    }
    prefix = "CBH task-continuity capsule (task-local, untrusted operational context):\n"
    value = prefix + _canonical_json(payload)
    delivery = "ready"
    if len(value) > max_chars or _estimated_tokens(value) > max_tokens:
        mandatory = {
            "schema": CAPSULE_SCHEMA,
            "capsule_id": capsule.get("capsule_id"),
            "lifecycle": capsule.get("lifecycle"),
            "progress_revision": capsule.get("progress_revision"),
            "objective": capsule.get("objective"),
            "remaining_work": payload["remaining_work"],
            "next_action": capsule.get("next_action"),
            "blocking_condition": capsule.get("blocking_condition"),
            "unresolved_failures": payload["unresolved_failures"],
            "full_capsule_sha256": full_capsule_sha256,
            "uncovered_counts": uncovered_counts,
            "continuation_required": True,
            "boundary": payload["boundary"],
        }
        value = prefix + _canonical_json(mandatory)
        delivery = "continuation_required"
    if len(value) > max_chars or _estimated_tokens(value) > max_tokens:
        identity = {
            "schema": CAPSULE_SCHEMA,
            "capsule_id": capsule.get("capsule_id"),
            "progress_revision": capsule.get("progress_revision"),
            "full_capsule_sha256": full_capsule_sha256,
            "semantic_review_required": True,
        }
        value = prefix + _canonical_json(identity)
        delivery = "semantic_review_required"
    if len(value) > max_chars or _estimated_tokens(value) > max_tokens:
        raise ValueError("mandatory_capsule_identity_exceeds_host_limit")
    first_remaining = _first_remaining(capsule)
    lifecycle = str(capsule.get("lifecycle") or "ACTIVE")
    if lifecycle == "VERIFYING":
        required_action_code = "verify_semantic_postcondition_before_completion"
    elif capsule.get("unresolved_failures"):
        required_action_code = "change_failed_action_then_verify"
    elif capsule.get("blocking_condition"):
        required_action_code = "report_blocker_or_continue_from_evidence"
    else:
        required_action_code = "continue_task_from_evidence_entry"
    control_payload = {
        "schema": "cbh.task_continuity_control.v1",
        "capsule_id": capsule.get("capsule_id"),
        "lifecycle": lifecycle,
        "progress_revision": capsule.get("progress_revision"),
        "required_action_code": required_action_code,
        "earliest_pending_id": first_remaining.get("id") if first_remaining else None,
        "reminder_triggers": [
            str(item.get("trigger"))
            for item in reminders[:4]
            if isinstance(item, Mapping) and item.get("trigger")
        ],
        "evidence_entry": "cbh.task_continuity.evidence",
        "authority_granted": False,
        "boundary": "Use the separate untrusted evidence entry for task text. Preserve permissions and verify postconditions before completion.",
    }
    control_value = (
        "CBH task-continuity control (generated lifecycle codes only):\n"
        + _canonical_json(control_payload)
    )
    if len(control_value) > 1_600 or _estimated_tokens(control_value) > 450:
        raise ValueError("task_continuity_control_exceeds_host_limit")
    return {
        "schema": "cbh.task_capsule_context.v1",
        "entry": {"kind": "untrusted", "value": value},
        "control_entry": {"kind": "application", "value": control_value},
        "char_count": len(value),
        "control_char_count": len(control_value),
        "estimated_tokens": _estimated_tokens(value),
        "delivery": delivery,
    }


def process_worker_request(request: Mapping[str, Any]) -> dict[str, Any]:
    if request.get("op") != "observe":
        raise ValueError("unsupported worker operation")
    route = request.get("route_receipt")
    task_event = request.get("task_event")
    capsule = request.get("capsule")
    if not isinstance(route, Mapping) or not isinstance(task_event, Mapping):
        raise ValueError("route_receipt and task_event must be objects")
    decision = decide_task_continuity(
        route,
        task_event,
        capsule if isinstance(capsule, Mapping) else None,
    )
    transition: dict[str, Any] | None = None
    reminders: list[dict[str, Any]] = []
    pending_reminders = request.get("pending_reminders")
    carried_reminders = (
        [
            {
                key: item.get(key)
                for key in (
                    "schema",
                    "trigger",
                    "required_action",
                    "expires_when",
                    "dedupe_key",
                )
                if item.get(key) is not None
            }
            for item in pending_reminders[:8]
            if isinstance(item, Mapping)
        ]
        if isinstance(pending_reminders, Sequence)
        and not isinstance(pending_reminders, (str, bytes))
        else []
    )
    current: dict[str, Any] | None
    if capsule is None:
        if decision["decision"] != "dormant":
            current, transition = initialize_task_capsule(route, task_event)
        else:
            current = None
    else:
        if capsule.get("lifecycle") == "RETIRED":
            current = _copy(capsule)
        else:
            transition = apply_task_event(capsule, task_event)
            current = transition["capsule"]
            reminders = build_dynamic_reminders(current, transition)
        if reminders:
            current = reminders[-1]["capsule_snapshot"]
            reminders = [
                {key: value for key, value in reminder.items() if key != "capsule_snapshot"}
                for reminder in reminders
            ]
    context = (
        build_task_capsule_context(
            current,
            [*carried_reminders, *reminders],
            host_limits=request.get("host_limits") if isinstance(request.get("host_limits"), Mapping) else None,
        )
        if current is not None
        else {
            "schema": "cbh.task_capsule_context.v1",
            "entry": None,
            "control_entry": None,
            "char_count": 0,
            "delivery": "not_needed",
        }
    )
    return {
        "schema": WORKER_SCHEMA,
        "decision": decision,
        "capsule": current,
        "transition": transition,
        "dynamic_reminders": reminders,
        "additional_context_entry": context["entry"],
        "additional_context_entries": {
            "control": context.get("control_entry"),
            "evidence": context["entry"],
        },
        "transport_receipt": {
            "delivery": context["delivery"],
            "char_count": context["char_count"],
            "estimated_tokens": context.get("estimated_tokens", 0),
        },
        "persistence": "none",
        "authority_granted": False,
    }


def _worker_response(request: Any) -> dict[str, Any]:
    request_id = request.get("id") if isinstance(request, Mapping) else None
    try:
        if not isinstance(request, Mapping):
            raise ValueError("worker request must be an object")
        result = process_worker_request(request)
        return {"id": request_id, "result": result}
    except Exception as exc:  # fail-closed inside worker; host adapter decides fail-open
        return {
            "id": request_id,
            "error": {
                "code": "task_continuity_worker_error",
                "message": str(exc),
            },
        }


def _run_worker_once() -> int:
    request = json.loads(sys.stdin.read())
    sys.stdout.write(json.dumps(_worker_response(request), ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0


def _run_worker_loop() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {
                "id": None,
                "error": {
                    "code": "invalid_json",
                    "message": str(exc),
                },
            }
        else:
            response = _worker_response(request)
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


def main() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--worker", action="store_true")
    modes.add_argument("--worker-once", action="store_true")
    args = parser.parse_args()
    return _run_worker_loop() if args.worker else _run_worker_once()


if __name__ == "__main__":
    raise SystemExit(main())
