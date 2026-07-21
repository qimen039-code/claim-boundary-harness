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


def test_bilingual_readme_and_local_overlay_template_are_present() -> None:
    readme = read_text("README.md")
    readme_zh = read_text("README_zh.md")
    overlay = json.loads(read_text("skills/embedded-harness/embedded_harness_policy.local.example.json"))
    policy = json.loads(read_text("skills/embedded-harness/embedded_harness_policy.json"))

    assert "[中文版](./README_zh.md) | English" in readme
    assert "[English](./README.md) | 中文" in readme_zh
    assert "v1.0.0" in readme
    assert "v1.0.0" in readme_zh
    assert read_text("VERSION").strip() == "v1.0.0"
    assert overlay["schema"] == "cbh.project_lane_overlay.v1"
    assert policy["local_project_lane_overlay"]["default_filename"] == "embedded_harness_policy.local.json"
    assert "embedded_harness_policy.local.json" in readme
    assert "CBH_PROJECT_LANES_FILE" in readme_zh


def test_citation_notice_are_visible_and_public_report_draft_is_absent() -> None:
    required_files = [
        "CITATION.cff",
        "NOTICE.md",
        "docs/assets/doi-badge.svg",
    ]
    for relative in required_files:
        assert (ROOT / relative).is_file(), relative
    assert not (ROOT / "docs/articles/claim-boundary-harness-technical-report.md").exists()

    readme = read_text("README.md")
    readme_zh = read_text("README_zh.md")
    citation = read_text("CITATION.cff")
    doi_badge = read_text("docs/assets/doi-badge.svg")
    notice = read_text("NOTICE.md")
    license_text = read_text("LICENSE")
    changelog = read_text("CHANGELOG.md")
    manifest = json.loads(read_text("templates/adapter-contract/compatibility.manifest.json"))

    assert "CITATION.cff" in readme
    assert "NOTICE.md" in readme
    assert "10.5281/zenodo.21189879" in readme
    assert "./docs/assets/doi-badge.svg" in readme
    assert "Canonical current release:" in readme
    assert "Earlier tags are historical snapshots" in readme
    assert "claim-boundary-harness-technical-report.md" not in readme
    assert "CITATION.cff" in readme_zh
    assert "NOTICE.md" in readme_zh
    assert "10.5281/zenodo.21189879" in readme_zh
    assert "./docs/assets/doi-badge.svg" in readme_zh
    assert "当前规范版本：" in readme_zh
    assert "更早的 tag 仅为历史快照" in readme_zh
    assert "claim-boundary-harness-technical-report.md" not in readme_zh
    assert "title: \"Claim Boundary Harness: A Model-Facing Capability Harness for LLM Agent Workflows\"" in citation
    assert "qimen039-code" in citation
    assert "version: \"1.0.0\"" in citation
    assert "doi: \"10.5281/zenodo.21189879\"" in citation
    assert "10.5281/zenodo.21189879" in doi_badge
    assert 'role="img"' in doi_badge
    assert "Recommended short attribution" in notice
    assert "submitted arXiv record exists" in notice
    assert "Copyright (c) 2026 qimen039-code" in license_text
    assert "Zenodo DOI trigger release" in changelog
    assert "## v1.0.0 - 2026-07-20" in changelog
    stale_version = "v0." + "14.0"
    assert stale_version not in changelog
    assert manifest["harness_version"] == "v1.0.0"


def test_memory_feedback_loop_trial_is_optional_and_template_visible() -> None:
    trial = read_text("docs/memory-feedback-loop-trial.md")
    schema = read_text("docs/source-monitoring-memory-schema.md")
    meta_contract = read_text("docs/memory-meta-index-contract.md")
    routing_contract = read_text("docs/memory-routing-contract.md")
    common_error_doc = read_text("docs/common-error-corpus.md")
    common_error_template = read_text("templates/common-error-corpus/CE-EXAMPLE-YYYY-MM-DD.md")
    project_meta = read_text("templates/project/memory-library/_META_INDEX.md")
    conversation_meta = read_text("templates/conversation-memory/_META_INDEX.md")
    manifest = json.loads(read_text("templates/adapter-contract/compatibility.manifest.json"))
    workbuddy_doc = read_text("docs/integrations/workbuddy.md")
    doubao_doc = read_text("docs/integrations/doubao.md")

    for text in [trial, schema, common_error_doc, common_error_template, project_meta]:
        assert "feedback_loop" in text

    for text in [schema, project_meta, conversation_meta]:
        assert "source_validity_dependency" in text

    assert "Conflict Resolution Policy" in schema
    assert "source invalidation" in read_text("docs/architecture.md")
    assert "lane_state" in meta_contract
    assert "frozen_readonly" in routing_contract
    assert "not a task-cost ledger" in trial
    assert "per-task token ledger" in read_text("docs/architecture.md")
    assert "status: pending" in common_error_template
    assert manifest["memory_feedback_loop"]["field_name"] == "feedback_loop"
    assert manifest["memory_feedback_loop"]["advisory_only"] is True
    assert manifest["memory_feedback_loop"]["host_hard_stop_gate"] is False
    assert manifest["memory_feedback_loop"]["internalized_on_reusable_memory_selection"] is True
    assert manifest["memory_feedback_loop"]["does_not_create_task_cost_ledger"] is True
    assert manifest["memory_feedback_loop"]["profile_controls_cost"] is True
    assert manifest["memory_feedback_loop"]["feedback_loop_profile_values"] == [
        "none",
        "index_hint",
        "record_candidate",
        "prevention_review",
        "explicit_cycle",
    ]
    assert manifest["memory_integrity_policy"]["recency_is_context_not_truth"] is True
    assert manifest["memory_integrity_policy"]["source_invalidity_cascade_blocks_validated_retrieval"] is True
    assert manifest["memory_integrity_policy"]["lane_state_values"] == [
        "active",
        "frozen_readonly",
        "cleared",
    ]
    assert manifest["memory_integrity_policy"]["frozen_readonly_excluded_from_default_retrieval_and_writes"] is True
    assert manifest["observation_and_causal_attribution"]["public_private_boundary_is_separate"] is True
    assert manifest["observation_and_causal_attribution"]["blocks_ordinary_local_causal_reasoning"] is False
    assert "feedback_loop" in workbuddy_doc
    assert "feedback_loop" in doubao_doc
    assert "causal-attribution" in trial
    assert "does not prove causality" in trial


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
    assert "feedback_loop_profile" in receipt_fields
    assert "hybrid_retrieval_profile" in receipt_fields
    assert "memory_write_profile" in receipt_fields
    assert "debt_hygiene_gate" in policy["router_decision_contract"]["module_need_values"]
    assert "debt_hygiene_rule" in policy["router_decision_contract"]
    assert "candidate_technical_debt" in read_text("docs/router-decision-contract.md")
    assert "candidate_technical_debt" in read_text("docs/cost-control-contract.md")
    assert policy["router_decision_contract"]["skill_lifecycle_profile_values"] == [
        "none",
        "listing_only",
        "active_frame_required",
        "release_receipt_required",
        "reactivate_from_receipt",
    ]
    assert policy["router_decision_contract"]["feedback_loop_profile_values"] == [
        "none",
        "index_hint",
        "record_candidate",
        "prevention_review",
        "explicit_cycle",
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
    assert conversation_index["lane_state"] == "active"
    assert conversation_index["lane_state_policy"]["allowed_values"] == [
        "active",
        "frozen_readonly",
        "cleared",
    ]
    assert conversation_index["memory_integrity_policy"]["conflict_resolution"] == "scope_and_confidence_before_recency"
    assert conversation_index["memory_integrity_policy"]["recency_is_context_not_truth"] is True
    assert manifest["skill_lifecycle"]["receipt_schema"] == "cbh.skill_release_receipt.v1"
    assert manifest["skill_lifecycle"]["reactivation_reads_current_source_files"] is True
    assert manifest["memory_feedback_loop"]["prediction_is_hypothesis_until_verified"] is True
    assert manifest["tool_surface_discovery"]["checks_before_fallback_to_shell_or_raw_web"] is True
    assert "tool_surface_need" in manifest["tool_surface_discovery"]["field_names"]
    assert "tool_surface_need" in read_text("integrations/workbuddy-python-runtime/README.md")
    assert "preferred_call_surface" in read_text("docs/integrations/workbuddy.md")
    assert manifest["observation_and_causal_attribution"]["attribution_levels"] == [
        "mechanism_property",
        "empirical_record",
        "causal_hypothesis",
        "validated_causality",
    ]
    assert "global_task_context_gate" in policy["router_decision_contract"]["issue_prevention_gates"]
    assert "global_task_context_gate" in read_text("docs/router-decision-contract.md")
    assert "global task context" in read_text("README.md")
    assert "局部因果先看任务全貌" in read_text("README_zh.md")
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
