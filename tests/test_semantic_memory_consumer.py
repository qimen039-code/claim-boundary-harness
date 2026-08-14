from __future__ import annotations

import sys
from pathlib import Path


HARNESS = Path(__file__).resolve().parents[1] / "skills" / "embedded-harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from harness_action_consumer import build_action_consumption  # noqa: E402
from semantic_memory import append_memory_record, build_memory_record  # noqa: E402


def _record(record_id: str, *, label: str, details: str) -> dict[str, object]:
    return build_memory_record(
        record_id=record_id,
        memory_class="common_error",
        lane_id="TEST",
        lane_kind="project",
        owner_skill="test",
        observed_at="2026-08-14T00:00:00Z",
        state="active",
        current_status="verified_solution",
        confidence={"label": "high", "basis": "test verifier"},
        query_types=["current_state", "history_reason"],
        candidate_label=label,
        summary=label,
        retrieval_terms=[label, "shared parser surface"],
        facets={"surface": ["test"]},
        content={
            "event_summary": label,
            "details": details,
            "applicable_boundaries": ["test"],
            "non_applicable_boundaries": ["other"],
            "evidence_boundary": "test verifier",
        },
    )


def _route(store: Path) -> dict[str, object]:
    return {
        "memory_need": "index_only",
        "memory_source_hints": [
            {
                "lane": "test",
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


def test_exact_v3_match_materializes_only_selected_payload(tmp_path: Path) -> None:
    store = tmp_path / "memory-v3"
    append_memory_record(
        store,
        _record("CE-V3-EXACT-001", label="精确测试记忆", details="ONLY-THIS-PAYLOAD"),
    )
    append_memory_record(
        store,
        _record(
            "CE-V3-UNRELATED-002",
            label="无关测试记忆",
            details="UNRELATED-PAYLOAD-MUST-STAY-CLOSED",
        ),
    )

    receipt = build_action_consumption(_route(store), prompt="CE-V3-EXACT-001")

    assert [item["record_id"] for item in receipt["selected_records"]] == [
        "CE-V3-EXACT-001"
    ]
    selected = receipt["selected_records"][0]
    assert selected["source_tag"] == "local_memory_write"
    assert selected["navigation_only"] is False
    assert selected["path"].endswith("records.jsonl")
    assert "精确测试记忆" in receipt["additional_context"]
    assert "ONLY-THIS-PAYLOAD" not in receipt["additional_context"]
    assert "UNRELATED-PAYLOAD-MUST-STAY-CLOSED" not in receipt["additional_context"]


def test_weak_v3_match_stays_meta_only_when_payload_is_unavailable(tmp_path: Path) -> None:
    store = tmp_path / "memory-v3"
    append_memory_record(
        store,
        _record(
            "CE-V3-WEAK-001",
            label="PowerShell 解析候选",
            details="PAYLOAD-MUST-STAY-CLOSED",
        ),
    )
    (store / "records.jsonl").replace(store / "records.unavailable")

    receipt = build_action_consumption(_route(store), prompt="PowerShell parser")

    assert receipt["status"] == "semantic_review_required"
    assert [item["record_id"] for item in receipt["selected_records"]] == [
        "CE-V3-WEAK-001"
    ]
    assert receipt["selected_records"][0]["navigation_only"] is True
    assert "PAYLOAD-MUST-STAY-CLOSED" not in receipt["additional_context"]
