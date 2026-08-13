from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import tomllib


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "skills" / "embedded-harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from task_continuity import (  # noqa: E402
    apply_task_event,
    build_dynamic_reminders,
    build_task_capsule_context,
    decide_task_continuity,
    initialize_task_capsule,
    new_task_capsule,
    page_result,
    plan_transport,
    process_worker_request,
)


def event(event_id: str, event_type: str, **payload: object) -> dict[str, object]:
    return {
        "schema": "cbh.task_event.v1",
        "event_id": event_id,
        "type": event_type,
        "observed_at": "2026-08-13T00:00:00Z",
        **payload,
    }


def write_route() -> dict[str, object]:
    return {
        "edit_operation_profile": "in_place_patch",
        "memory_mode": "none",
        "tool_surface_need": "local_filesystem",
        "action_bindings": [],
    }


def test_short_answer_only_question_stays_dormant() -> None:
    decision = decide_task_continuity(
        {
            "edit_operation_profile": "read_only",
            "memory_mode": "none",
            "tool_surface_need": "none",
            "action_bindings": [],
        },
        event("answer:1", "task_observed", objective="什么是检索增强生成？"),
    )

    assert decision == {
        "schema": "cbh.task_continuity_decision.v1",
        "decision": "dormant",
        "reasons": [],
        "source_event_ids": ["answer:1"],
        "host_delivery": "not_needed",
    }


def test_existing_active_capsule_uses_contract_continue_decision() -> None:
    route = write_route()
    capsule = new_task_capsule(
        route,
        event("start:1", "task_observed", objective="修复文件"),
    )
    decision = decide_task_continuity(
        route,
        event("observe:2", "task_observed", objective="继续修复"),
        capsule,
    )
    assert decision["decision"] == "continue"


def test_first_substantive_event_is_applied_when_capsule_is_created() -> None:
    capsule, transition = initialize_task_capsule(
        write_route(),
        event(
            "write:first",
            "write_result_received",
            objective="写入并验证文件",
            acceptance_id="write_applied",
            postcondition_satisfied=False,
        ),
    )
    assert transition is not None
    assert capsule["lifecycle"] == "VERIFYING"
    assert capsule["acceptance_criteria"][0]["status"] == "inferred"
    assert "write:first" in capsule["applied_event_ids"]


def test_plan_progress_refreshes_next_action_without_claiming_verification() -> None:
    capsule = new_task_capsule(
        write_route(),
        event("plan:start", "task_observed", objective="实现并验证功能"),
    )
    transition = apply_task_event(
        capsule,
        event(
            "plan:update",
            "progress_snapshot",
            acceptance_criteria=[
                {"id": "plan-0", "text": "实现功能", "status": "inferred"},
                {"id": "plan-1", "text": "运行验证", "status": "unknown"},
            ],
            current_step="运行验证",
            next_action="运行验证",
        ),
    )
    updated = transition["capsule"]
    assert updated["lifecycle"] == "ACTIVE"
    assert updated["next_action"] == "运行验证"
    assert not updated["verified_completed"]
    assert any(item["text"] == "实现功能" for item in updated["inferred_progress"])


def test_retired_capsule_cannot_be_reactivated_by_a_late_event() -> None:
    capsule = new_task_capsule(
        write_route(),
        event(
            "retire:start",
            "task_observed",
            objective="完成一个动作",
            acceptance_criteria=[{"id": "done", "text": "done"}],
        ),
    )
    verified = apply_task_event(
        capsule,
        event(
            "retire:verify",
            "verifier_completed",
            acceptance_id="done",
            postcondition_satisfied=True,
            retire_if_complete=True,
        ),
    )["capsule"]
    late = apply_task_event(
        verified,
        event("retire:late", "candidate_selected", next_action="must not run"),
    )
    assert late["capsule"]["lifecycle"] == "RETIRED"
    assert late["changed"] is False
    assert late["event_outcome"] == "retired_ignored"


def test_host_task_identity_prevents_cross_task_event_contamination() -> None:
    capsule = new_task_capsule(
        write_route(),
        event("identity:start", "task_observed", task_key="thread-a", objective="修改 A"),
    )
    with pytest.raises(ValueError, match="task_identity_mismatch"):
        apply_task_event(
            capsule,
            event("identity:wrong", "tool_dispatched", task_key="thread-b"),
        )


@pytest.mark.parametrize(
    ("route", "task_event", "reason"),
    [
        (write_route(), event("write:1", "task_observed", objective="修改 README"), "write_intent"),
        (
            {
                "edit_operation_profile": "read_only",
                "tool_surface_need": "browser",
                "action_bindings": [],
            },
            event("tool:1", "task_observed", objective="检查这个网页"),
            "tool_required",
        ),
        (
            {"edit_operation_profile": "read_only", "action_bindings": []},
            event("long:1", "task_observed", objective="分三阶段完成并持续验证", multi_stage=True),
            "multi_stage_task",
        ),
        (
            {"edit_operation_profile": "read_only", "action_bindings": []},
            event("resume:1", "task_observed", objective="继续之前未完成的任务", resume=True),
            "task_resume",
        ),
    ],
)
def test_write_tool_long_and_resume_tasks_arm(
    route: dict[str, object], task_event: dict[str, object], reason: str
) -> None:
    decision = decide_task_continuity(route, task_event)

    assert decision["decision"] == "arm"
    assert reason in decision["reasons"]
    assert decision["host_delivery"] == "ready"


def test_runtime_reasons_are_declared_by_the_policy_contract() -> None:
    authoring = tomllib.loads(
        (HARNESS / "embedded_harness_policy.authoring.toml").read_text(encoding="utf-8")
    )
    declared = set(
        authoring["router_decision_contract"]["task_continuity_contract"][
            "activation_reasons"
        ]
    )
    probes = [
        (write_route(), event("reason:write", "task_observed", objective="修改文件")),
        ({"tool_surface_need": "web"}, event("reason:tool", "task_observed", objective="检查网页")),
        ({}, event("reason:multi", "task_observed", objective="分阶段完成", multi_stage=True)),
        ({}, event("reason:resume", "task_observed", objective="继续", resume=True)),
        ({}, event("reason:long", "task_observed", objective="执行", long_running=True)),
        ({}, event("reason:open", "task_observed", objective="任务", open_loops=["x"])),
        ({}, event("reason:prior", "task_observed", objective="任务", prior_failure=True)),
        ({}, event("reason:explicit", "task_observed", objective="任务", continuity_requested=True)),
    ]
    emitted: set[str] = set()
    for route, task_event in probes:
        emitted.update(decide_task_continuity(route, task_event)["reasons"])
    capsule = new_task_capsule(write_route(), event("reason:active", "task_observed", objective="修改"))
    emitted.update(decide_task_continuity({}, event("reason:next", "task_observed", objective="任务"), capsule)["reasons"])
    assert emitted <= declared
    assert declared <= emitted


def test_write_capsule_requires_both_application_and_verification() -> None:
    observed = event(
        "write:observed",
        "task_observed",
        objective="更新配置并确认解析成功",
        acceptance_criteria=[
            {"id": "write_applied", "text": "目标写入已应用"},
            {"id": "write_verified", "text": "写入结果已验证"},
        ],
    )
    capsule = new_task_capsule(write_route(), observed)
    assert capsule["lifecycle"] == "ARMED"

    active = apply_task_event(
        capsule,
        event("write:selected", "candidate_selected", next_action="应用最小补丁"),
    )["capsule"]
    assert active["lifecycle"] == "ACTIVE"

    applied = apply_task_event(
        active,
        event(
            "write:result",
            "write_result_received",
            outcome="completed",
            acceptance_id="write_applied",
            postcondition_satisfied=True,
        ),
    )["capsule"]
    assert applied["lifecycle"] == "VERIFYING"
    assert [item["id"] for item in applied["verified_completed"]] == ["write_applied"]
    assert [item["id"] for item in applied["remaining_work"]] == ["write_verified"]

    verified = apply_task_event(
        applied,
        event(
            "write:verified",
            "verifier_completed",
            outcome="completed",
            acceptance_id="write_verified",
            postcondition_satisfied=True,
            retire_if_complete=True,
        ),
    )["capsule"]
    assert verified["lifecycle"] == "RETIRED"
    assert verified["remaining_work"] == []


def test_success_without_semantic_postcondition_is_only_inferred() -> None:
    capsule = new_task_capsule(
        {"tool_surface_need": "shell", "edit_operation_profile": "read_only"},
        event(
            "tool:observed",
            "task_observed",
            objective="检查项目状态",
            acceptance_criteria=[{"id": "status_checked", "text": "项目状态已核对"}],
        ),
    )
    capsule = apply_task_event(
        capsule,
        event("tool:dispatch", "tool_dispatched", next_action="运行状态检查"),
    )["capsule"]

    transition = apply_task_event(
        capsule,
        event(
            "tool:result",
            "tool_result_received",
            outcome="completed",
            acceptance_id="status_checked",
            postcondition_satisfied=False,
        ),
    )

    assert transition["capsule"]["verified_completed"] == []
    assert [item["id"] for item in transition["capsule"]["inferred_progress"]] == [
        "status_checked"
    ]
    assert transition["capsule"]["lifecycle"] == "VERIFYING"


def test_duplicate_event_is_idempotent() -> None:
    capsule = new_task_capsule(
        write_route(),
        event("dup:observed", "task_observed", objective="修改一个文件"),
    )
    first = apply_task_event(capsule, event("dup:event", "tool_dispatched"))
    second = apply_task_event(first["capsule"], event("dup:event", "tool_dispatched"))

    assert first["changed"] is True
    assert second["changed"] is False
    assert second["capsule"] == first["capsule"]


def test_unchanged_failure_reminder_is_deduplicated_by_revision() -> None:
    capsule = new_task_capsule(
        {"tool_surface_need": "shell", "edit_operation_profile": "read_only"},
        event("failure:observed", "task_observed", objective="执行并验证命令"),
    )
    transition = apply_task_event(
        capsule,
        event(
            "failure:repeat",
            "unchanged_dispatch_repeated",
            subject_signature="a" * 64,
            error_class="parser_error",
        ),
    )
    first = build_dynamic_reminders(transition["capsule"], transition)
    second = build_dynamic_reminders(first[0]["capsule_snapshot"], transition)

    assert len(first) == 1
    assert first[0]["trigger"] == "unchanged_dispatch_repeated"
    assert second == []


def test_continuity_never_creates_or_consumes_authority() -> None:
    capsule = new_task_capsule(
        write_route(),
        event("auth:observed", "task_observed", objective="执行受保护写入"),
    )
    transition = apply_task_event(
        capsule,
        event(
            "auth:pending",
            "verifier_pending",
            blocking_condition="pending_user_confirmation",
        ),
    )

    assert transition["capsule"]["lifecycle"] == "VERIFYING"
    assert transition["capsule"]["blocking_condition"] == "pending_user_confirmation"
    assert transition["capsule"]["authority"] == {
        "granted": False,
        "consumed": False,
        "source": "none",
    }


def test_text_transport_pages_round_trip_and_binds_cursor() -> None:
    payload = "甲乙丙丁" * 40
    plan = plan_transport(
        None,
        {"kind": "text", "original_chars": len(payload), "original_items": 1},
        {"max_chars": 37, "max_items": 10},
    )
    pages: list[str] = []
    cursor = None
    while True:
        page = page_result(payload, plan, cursor)
        pages.append(page["content"])
        if page["next_cursor"] is None:
            break
        cursor = page["next_cursor"]

    rebuilt = "".join(pages)
    assert rebuilt == payload
    assert hashlib.sha256(rebuilt.encode("utf-8")).hexdigest() == page["full_result_sha256"]
    assert all(len(part) <= 37 for part in pages)

    with pytest.raises(ValueError, match="cursor_result_hash_mismatch"):
        page_result(payload, plan, {"result_sha256": "0" * 64, "next_char": 1})


def test_item_transport_respects_item_and_character_limits() -> None:
    items = [{"id": index, "text": f"item-{index}"} for index in range(11)]
    plan = plan_transport(
        None,
        {"kind": "items", "original_items": len(items), "original_chars": 500},
        {"max_chars": 90, "max_items": 3},
    )
    rebuilt: list[dict[str, object]] = []
    cursor = None
    while True:
        page = page_result(items, plan, cursor)
        rebuilt.extend(page["items"])
        assert len(page["items"]) <= 3
        if page["next_cursor"] is None:
            break
        cursor = page["next_cursor"]

    assert rebuilt == items
    canonical = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == page["full_result_sha256"]


def test_typed_media_payload_is_never_serialized_into_context() -> None:
    secret = "base64-secret-payload"
    plan = plan_transport(
        None,
        {"kind": "items", "original_items": 1, "original_chars": 1000},
        {"max_chars": 1000, "max_items": 10},
    )
    page = page_result(
        [{"type": "image", "mimeType": "image/png", "data": secret}],
        plan,
    )
    serialized = json.dumps(page, ensure_ascii=False)

    assert secret not in serialized
    assert page["items"][0]["inline_payload_omitted_from_text"] is True


def test_model_context_contains_progress_not_chain_of_thought() -> None:
    capsule = new_task_capsule(
        write_route(),
        event("context:observed", "task_observed", objective="修改并验证配置"),
    )
    context = build_task_capsule_context(capsule, [], host_limits={"max_chars": 1800})

    assert context["entry"]["kind"] == "untrusted"
    assert context["control_entry"]["kind"] == "application"
    assert "修改并验证配置" not in context["control_entry"]["value"]
    assert "continue_task_from_evidence_entry" in context["control_entry"]["value"]
    assert "修改并验证配置" in context["entry"]["value"]
    assert "chain-of-thought" not in context["entry"]["value"].lower()
    assert context["char_count"] <= 1800


def test_context_reports_unforwarded_progress_instead_of_silent_list_clipping() -> None:
    capsule = new_task_capsule(
        write_route(),
        event(
            "many:1",
            "task_observed",
            objective="完成多阶段写入",
            acceptance_criteria=[
                {"id": f"criterion-{index}", "text": f"step {index}"}
                for index in range(20)
            ],
        ),
    )
    context = build_task_capsule_context(capsule, [], host_limits={"max_chars": 3_200})
    assert "uncovered_counts" in context["entry"]["value"]
    assert "full_capsule_sha256" in context["entry"]["value"]


def test_pending_dynamic_reminder_is_rendered_on_the_next_supported_turn() -> None:
    capsule = new_task_capsule(
        write_route(),
        event("reminder:start", "task_observed", task_key="thread-a", objective="修改文件"),
    )
    response = process_worker_request(
        {
            "op": "observe",
            "route_receipt": {},
            "task_event": event(
                "reminder:next",
                "task_observed",
                task_key="thread-a",
                objective="继续",
            ),
            "capsule": capsule,
            "pending_reminders": [
                {
                    "schema": "cbh.dynamic_reminder.v1",
                    "trigger": "missing_postcondition",
                    "required_action": "verify the semantic postcondition",
                    "expires_when": "postcondition_verified",
                }
            ],
            "host_limits": {"max_chars": 3000, "max_tokens": 850},
        }
    )
    assert "missing_postcondition" in response["additional_context_entry"]["value"]
    assert "verify the semantic postcondition" in response["additional_context_entry"]["value"]


def test_jsonl_worker_keeps_state_external_and_returns_one_context_entry() -> None:
    request = {
        "id": "worker:1",
        "op": "observe",
        "route_receipt": write_route(),
        "task_event": event("worker:event", "task_observed", objective="修改一个文件"),
        "capsule": None,
        "host_limits": {"max_chars": 1600, "max_items": 20},
    }
    completed = subprocess.run(
        [sys.executable, str(HARNESS / "task_continuity.py"), "--worker-once"],
        input=json.dumps(request, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    response = json.loads(completed.stdout)
    assert response["id"] == "worker:1"
    assert response["result"]["decision"]["decision"] == "arm"
    assert response["result"]["capsule"]["lifecycle"] == "ARMED"
    assert response["result"]["additional_context_entry"]["kind"] == "untrusted"
    assert response["result"]["additional_context_entries"]["control"]["kind"] == "application"
    assert response["result"]["additional_context_entries"]["evidence"]["kind"] == "untrusted"
