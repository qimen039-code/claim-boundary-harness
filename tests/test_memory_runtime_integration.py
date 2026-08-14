from __future__ import annotations

import sys
from pathlib import Path


HARNESS = Path(__file__).resolve().parents[1] / "skills" / "embedded-harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from memory_runtime_bridge import bind_memory_query_to_workfile  # noqa: E402
from semantic_memory import append_memory_record, build_memory_record  # noqa: E402
from task_continuity import new_task_capsule  # noqa: E402
from task_continuity_workfile import (  # noqa: E402
    append_cumcwork_snapshot,
    rehydrate_cumcwork,
)


def _event(event_id: str, event_type: str, **payload: object) -> dict[str, object]:
    return {
        "schema": "cbh.task_event.v1",
        "event_id": event_id,
        "type": event_type,
        "observed_at": "2026-08-14T00:00:00Z",
        "task_key": "public-memory-runtime-integration",
        **payload,
    }


def test_v3_selection_is_bound_to_workfile_and_rehydrates_after_restart(
    tmp_path: Path,
) -> None:
    store = tmp_path / "memory-v3"
    append_memory_record(
        store,
        build_memory_record(
            record_id="CE-PUBLIC-V3-INTEGRATION-001",
            memory_class="common_error",
            lane_id="PUBLIC-TEST",
            lane_kind="project",
            owner_skill="test",
            observed_at="2026-08-14T00:00:00Z",
            state="active",
            current_status="verified_solution",
            confidence={"label": "high", "basis": "synthetic verifier"},
            query_types=["history_reason"],
            candidate_label="public v3 integration memory",
            summary="A selected record survives a workfile restart.",
            retrieval_terms=["public v3 integration memory"],
            facets={"surface": ["test"]},
            content={
                "event_summary": "Synthetic public integration event.",
                "details": "Selected through meta and bound to one task workfile.",
                "applicable_boundaries": ["test"],
                "non_applicable_boundaries": ["production claim"],
                "evidence_boundary": "synthetic test only",
            },
        ),
    )
    route = {
        "memory_need": "index_only",
        "memory_source_hints": [
            {
                "lane": "public-test",
                "root_path": str(store),
                "isolation": "exact_test_lane",
            }
        ],
        "action_bindings": [
            {
                "action": "retrieve_matching_memory",
                "completion_evidence": "selected_record_id_and_provenance",
            }
        ],
    }
    capsule = new_task_capsule(
        route,
        _event(
            "start",
            "task_observed",
            objective="Recall public v3 integration memory",
            intent_kind="new_task",
            purpose="Verify task-local memory continuity",
            acceptance_criteria=[
                {"id": "memory-bound", "text": "Selected memory ID survives restart"}
            ],
        ),
    )
    workfile = tmp_path / "task.cumcwork"
    append_cumcwork_snapshot(
        workfile,
        capsule,
        expected_head_sha256=None,
        expected_work_revision=0,
    )

    receipt = bind_memory_query_to_workfile(
        workfile,
        expected_host_task_key_sha256=capsule["host_task_key_sha256"],
        route=route,
        prompt="CE-PUBLIC-V3-INTEGRATION-001",
        event_id="memory-selected",
        query_type="history_reason",
    )

    assert receipt["selected_record_ids"] == ["CE-PUBLIC-V3-INTEGRATION-001"]
    assert receipt["work_revision"] == 2
    assert receipt["durable_memory_written"] is False
    restarted = rehydrate_cumcwork(
        workfile,
        expected_host_task_key_sha256=capsule["host_task_key_sha256"],
    )
    working_set = restarted["active_capsule"]["memory_working_set"]
    assert working_set["selected_record_ids"] == ["CE-PUBLIC-V3-INTEGRATION-001"]
    assert working_set["query_type"] == "history_reason"
    assert working_set["query_basis"] == "global_goal"
    assert working_set["bound_goal_revision"] == capsule["goal_revision"]
