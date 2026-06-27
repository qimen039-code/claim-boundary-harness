from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_new_memory_and_reading_contracts_are_indexed() -> None:
    required_docs = [
        "docs/memory-feedback-loop-trial.md",
        "docs/memory-write-granularity-contract.md",
        "docs/hybrid-memory-retrieval-contract.md",
        "docs/content-reading-contract.md",
        "docs/skill-lifecycle-contract.md",
    ]
    for relative in required_docs:
        assert (ROOT / relative).is_file(), relative

    readme = read_text("README.md")
    architecture = read_text("docs/architecture.md")
    doctor = read_text("tools/cbh_doctor.py")
    test_cases = read_text("docs/test-cases.md")

    for relative in required_docs:
        name = Path(relative).name
        assert name in readme
        assert name in architecture
        assert relative in doctor

    assert "TC-032" in test_cases
    assert "TC-036" in test_cases


def test_memory_feedback_loop_trial_is_optional_and_template_visible() -> None:
    trial = read_text("docs/memory-feedback-loop-trial.md")
    schema = read_text("docs/source-monitoring-memory-schema.md")
    common_error_doc = read_text("docs/common-error-corpus.md")
    common_error_template = read_text("templates/common-error-corpus/CE-EXAMPLE-YYYY-MM-DD.md")
    project_meta = read_text("templates/project/memory-library/_META_INDEX.md")
    manifest = json.loads(read_text("templates/adapter-contract/compatibility.manifest.json"))
    workbuddy_doc = read_text("docs/integrations/workbuddy.md")
    doubao_doc = read_text("docs/integrations/doubao.md")

    for text in [trial, schema, common_error_doc, common_error_template, project_meta]:
        assert "feedback_loop" in text

    assert "not a task-cost ledger" in trial
    assert "not a per-task token ledger" in read_text("docs/architecture.md")
    assert "status: pending" in common_error_template
    assert manifest["memory_feedback_loop"]["field_name"] == "feedback_loop"
    assert manifest["memory_feedback_loop"]["advisory_only"] is True
    assert manifest["memory_feedback_loop"]["does_not_create_task_cost_ledger"] is True
    assert "feedback_loop" in workbuddy_doc
    assert "feedback_loop" in doubao_doc


def test_conversation_templates_expose_reading_profiles() -> None:
    conversation_index = json.loads(read_text("templates/conversation-memory/index.json"))
    ledger_index = json.loads(read_text("templates/conversation-ledger/domain_index.json"))

    for payload in [conversation_index, ledger_index]:
        policy = payload["content_reading_policy"]
        assert policy["profile_selected_by"] == "routing_or_decision_layer"
        assert policy["default_profile"] == "baseline"
        assert policy["available_profiles"] == [
            "baseline",
            "evidence_window",
            "middle_safe",
            "full_audit",
        ]
        assert "conditional_triggers" in policy
        assert "middle_safe_layout" in policy

    middle_safe = conversation_index["content_reading_policy"]["middle_safe_layout"]
    assert middle_safe["dual_anchor"] == "inventory_plus_original_window"
    assert middle_safe["head_tail_middle_reread_gate"]["enabled"] is True
    assert middle_safe["head_tail_middle_reread_gate"]["action"] == "bounded_middle_reread_around_structural_anchors"


def test_memory_profiles_are_routed_and_template_visible() -> None:
    policy = json.loads(read_text("skills/embedded-harness/embedded_harness_policy.json"))
    conversation_index = json.loads(read_text("templates/conversation-memory/index.json"))
    manifest = json.loads(read_text("templates/adapter-contract/compatibility.manifest.json"))

    receipt_fields = policy["router_decision_contract"]["receipt_fields"]
    assert "skill_lifecycle_profile" in receipt_fields
    assert "hybrid_retrieval_profile" in receipt_fields
    assert "memory_write_profile" in receipt_fields
    assert policy["router_decision_contract"]["skill_lifecycle_profile_values"] == [
        "none",
        "listing_only",
        "active_frame_required",
        "release_receipt_required",
        "reactivate_from_receipt",
    ]
    assert policy["router_decision_contract"]["hybrid_retrieval_profile_values"] == [
        "none",
        "meta_first_hybrid_enhancement",
        "meta_first_hybrid_required",
    ]
    assert policy["router_decision_contract"]["memory_write_profile_values"] == [
        "none",
        "context_complete_required",
        "strict_capsule_required",
    ]

    assert conversation_index["hybrid_retrieval_profile_default"] == "meta_first_hybrid_required"
    assert conversation_index["content_plane"]["memory_write_profile_default"] == "context_complete_required"
    assert manifest["skill_lifecycle"]["receipt_schema"] == "cbh.skill_release_receipt.v1"
    assert manifest["skill_lifecycle"]["reactivation_reads_current_source_files"] is True
    assert manifest["memory_feedback_loop"]["prediction_is_hypothesis_until_verified"] is True
    assert manifest["memory_retrieval_result"]["hybrid_retrieval_is_meta_first_enhancement"] is True
    assert manifest["memory_write_granularity"]["strict_capsules_reject_orphan_fragments"] is True


def test_skill_release_receipt_template_is_reactivation_ready() -> None:
    receipt = json.loads(read_text("templates/skill-lifecycle/skill_release_receipt.json"))

    assert receipt["schema"] == "cbh.skill_release_receipt.v1"
    for field in [
        "skill_id",
        "status",
        "completed_steps",
        "current_stage",
        "artifact_paths",
        "evidence_refs",
        "open_loops",
        "resume_entry",
        "last_used_at",
        "ttl_policy",
    ]:
        assert field in receipt
    assert "SKILL.md" in receipt["resume_entry"]
