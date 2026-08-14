from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


HARNESS = Path(__file__).resolve().parents[1] / "skills" / "embedded-harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from memory_runtime_bridge import bind_memory_query_to_workfile  # noqa: E402
from task_continuity import new_task_capsule, process_worker_request  # noqa: E402
from task_continuity_workfile import append_cumcwork_snapshot, rehydrate_cumcwork  # noqa: E402


def _load_checkpoint_module():
    path = HARNESS / "task_memory_checkpoint.py"
    assert path.is_file(), "task_memory_checkpoint consumer is not implemented"
    spec = importlib.util.spec_from_file_location("task_memory_checkpoint", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _event(event_id: str, event_type: str, **payload: object) -> dict[str, object]:
    return {
        "schema": "cbh.task_event.v1",
        "event_id": event_id,
        "type": event_type,
        "observed_at": "2026-08-14T10:00:00Z",
        "task_key": "checkpoint-integration-thread",
        **payload,
    }


def _route(store: Path | None = None) -> dict[str, object]:
    route: dict[str, object] = {
        "memory_need": "index_only",
        "action_bindings": [
            {
                "action": "retrieve_matching_memory",
                "completion_evidence": "selected_record_id_and_provenance",
            }
        ],
    }
    if store is not None:
        route["memory_source_hints"] = [
            {
                "lane": "checkpoint-test",
                "root_path": str(store),
                "isolation": "exact_test_lane",
            }
        ]
    return route


def _retired_workfile(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    capsule = new_task_capsule(
        _route(),
        _event(
            "checkpoint:start",
            "task_observed",
            objective="修复记忆闭环并验证新任务可准确召回",
            purpose="让已验证的任务结果形成可追溯的长期历史",
            intent_kind="new_task",
            required_outputs=[
                {"id": "runtime-loop", "text": "运行时记忆闭环", "status": "unknown"}
            ],
            acceptance_criteria=[
                {"id": "loop-verified", "text": "新任务能检索并绑定已完成任务记录"}
            ],
        ),
    )
    capsule["plan_steps"] = [
        {"id": "private-plan", "text": "PRIVATE_PLAN_MARKER", "status": "completed"}
    ]
    capsule["raw_tool_output"] = "RAW_SECRET_MARKER"
    capsule["authority"] = {"granted": True, "source": "UNTRUSTED_AUTHORITY_MARKER"}
    workfile = tmp_path / "completed-task.cumcwork"
    append_cumcwork_snapshot(
        workfile,
        capsule,
        expected_head_sha256=None,
        expected_work_revision=0,
    )
    completed = process_worker_request(
        {
            "op": "observe",
            "route_receipt": _route(),
            "task_event": _event(
                "checkpoint:verified",
                "verifier_completed",
                acceptance_id="loop-verified",
                postcondition_satisfied=True,
                postcondition="端到端检索和工作集绑定已验证",
                evidence_refs=[
                    {
                        "source_id": "test:checkpoint-verifier",
                        "sha256": "a" * 64,
                        "status": "original_verified",
                        "raw_output": "RAW_EVIDENCE_MARKER",
                    }
                ],
            ),
            "capsule": None,
            "workfile": {"path": str(workfile)},
        }
    )
    assert completed["capsule"]["lifecycle"] == "RETIRED"
    return workfile, completed["capsule"]


def test_completed_task_checkpoint_promotes_synchronously_and_next_task_binds_it(
    tmp_path: Path,
) -> None:
    checkpoint = _load_checkpoint_module()
    workfile, retired = _retired_workfile(tmp_path)
    store = tmp_path / "conversation-memory-v3"

    candidate = checkpoint.prepare_task_checkpoint_candidate(
        workfile,
        expected_host_task_key_sha256=retired["host_task_key_sha256"],
        lane_id="CONVERSATION-CHECKPOINT-TEST",
        lane_kind="conversation",
        owner_skill="test",
    )

    assert candidate["status"] == "eligible"
    assert candidate["durable_memory_written"] is False
    assert candidate["searchable_ready"] is False
    assert candidate["background_queue_used"] is False
    serialized = json.dumps(candidate, ensure_ascii=False, sort_keys=True)
    assert "PRIVATE_PLAN_MARKER" not in serialized
    assert "RAW_SECRET_MARKER" not in serialized
    assert "RAW_EVIDENCE_MARKER" not in serialized
    assert "UNTRUSTED_AUTHORITY_MARKER" not in serialized

    promoted = checkpoint.promote_task_checkpoint_to_memory(
        candidate,
        store_root=store,
        expected_candidate_sha256=candidate["candidate_sha256"],
    )

    assert promoted["status"] == "searchable_ready"
    assert promoted["canonical_status"] == "durable"
    assert promoted["search_index_status"] == "ready"
    assert promoted["derivation_mode"] == "synchronous_inline"
    assert promoted["background_queue_used"] is False
    assert promoted["durable_memory_written"] is True

    duplicate = checkpoint.promote_task_checkpoint_to_memory(
        candidate,
        store_root=store,
        expected_candidate_sha256=candidate["candidate_sha256"],
    )
    assert duplicate["status"] == "searchable_ready"
    assert duplicate["append_status"] == "unchanged"
    assert duplicate["durable_memory_written"] is False
    assert (store / "records.jsonl").read_text(encoding="utf-8").count("\n") == 1

    next_capsule = new_task_capsule(
        _route(store),
        _event(
            "next:start",
            "task_observed",
            objective="回顾修复记忆闭环并验证新任务可准确召回",
            purpose="继续使用已完成任务的可靠历史",
            intent_kind="new_task",
            acceptance_criteria=[
                {"id": "history-bound", "text": "历史记录进入当前工作集"}
            ],
        ),
    )
    next_workfile = tmp_path / "next-task.cumcwork"
    append_cumcwork_snapshot(
        next_workfile,
        next_capsule,
        expected_head_sha256=None,
        expected_work_revision=0,
    )
    bound = bind_memory_query_to_workfile(
        next_workfile,
        expected_host_task_key_sha256=next_capsule["host_task_key_sha256"],
        route=_route(store),
        prompt=promoted["record_id"],
        event_id="next:memory-bound",
        query_type="history_reason",
    )
    assert bound["selected_record_ids"] == [promoted["record_id"]]
    restarted = rehydrate_cumcwork(
        next_workfile,
        expected_host_task_key_sha256=next_capsule["host_task_key_sha256"],
    )
    assert restarted["active_capsule"]["memory_working_set"]["selected_record_ids"] == [
        promoted["record_id"]
    ]

    current_capsule = new_task_capsule(
        _route(store),
        _event(
            "current:start",
            "task_observed",
            objective="检查当前记忆状态，不复用历史任务结果",
            purpose="验证查询意图隔离",
            intent_kind="new_task",
            acceptance_criteria=[
                {"id": "current-filtered", "text": "历史 checkpoint 不进入 current_state"}
            ],
        ),
    )
    current_workfile = tmp_path / "current-state-task.cumcwork"
    append_cumcwork_snapshot(
        current_workfile,
        current_capsule,
        expected_head_sha256=None,
        expected_work_revision=0,
    )
    current_bound = bind_memory_query_to_workfile(
        current_workfile,
        expected_host_task_key_sha256=current_capsule["host_task_key_sha256"],
        route=_route(store),
        prompt=promoted["record_id"],
        event_id="current:memory-filtered",
        query_type="current_state",
    )
    assert current_bound["selected_record_ids"] == []


def test_incomplete_or_ambiguous_task_is_rejected_without_writing(tmp_path: Path) -> None:
    checkpoint = _load_checkpoint_module()
    capsule = new_task_capsule(
        _route(),
        _event(
            "active:start",
            "task_observed",
            objective="尚未完成的任务",
            intent_kind="new_task",
            semantic_review_required=True,
            acceptance_criteria=[{"id": "pending", "text": "仍需验证"}],
        ),
    )
    workfile = tmp_path / "active-task.cumcwork"
    append_cumcwork_snapshot(
        workfile,
        capsule,
        expected_head_sha256=None,
        expected_work_revision=0,
    )

    candidate = checkpoint.prepare_task_checkpoint_candidate(
        workfile,
        expected_host_task_key_sha256=capsule["host_task_key_sha256"],
        lane_id="CONVERSATION-CHECKPOINT-TEST",
        lane_kind="conversation",
        owner_skill="test",
    )

    assert candidate["status"] == "rejected"
    assert set(candidate["reason_codes"]) >= {
        "task_not_retired",
        "acceptance_not_fully_verified",
        "semantic_review_required",
    }
    assert candidate["record"] is None
    assert candidate["durable_memory_written"] is False
    assert not (tmp_path / "rejected-memory-v3").exists()


def test_candidate_hash_and_lane_binding_are_checked_before_write(tmp_path: Path) -> None:
    checkpoint = _load_checkpoint_module()
    workfile, retired = _retired_workfile(tmp_path)
    candidate = checkpoint.prepare_task_checkpoint_candidate(
        workfile,
        expected_host_task_key_sha256=retired["host_task_key_sha256"],
        lane_id="PROJECT-CHECKPOINT-TEST",
        lane_kind="project",
        owner_skill="test",
    )
    tampered = json.loads(json.dumps(candidate, ensure_ascii=False))
    tampered["record"]["owner"]["lane_id"] = "WRONG-LANE"
    store = tmp_path / "tampered-store"

    try:
        checkpoint.promote_task_checkpoint_to_memory(
            tampered,
            store_root=store,
            expected_candidate_sha256=candidate["candidate_sha256"],
        )
    except ValueError as exc:
        assert str(exc) == "task_checkpoint_candidate_hash_mismatch"
    else:
        raise AssertionError("tampered task checkpoint candidate was accepted")
    assert not store.exists()

    owner_tampered = json.loads(json.dumps(candidate, ensure_ascii=False))
    owner_tampered["target"]["owner_skill"] = "wrong-owner"
    owner_tampered["candidate_sha256"] = checkpoint._candidate_hash(owner_tampered)
    owner_store = tmp_path / "owner-tampered-store"
    try:
        checkpoint.promote_task_checkpoint_to_memory(
            owner_tampered,
            store_root=owner_store,
            expected_candidate_sha256=owner_tampered["candidate_sha256"],
        )
    except ValueError as exc:
        assert str(exc) == "task_checkpoint_target_binding_mismatch"
    else:
        raise AssertionError("owner-skill target mismatch was accepted")
    assert not owner_store.exists()
