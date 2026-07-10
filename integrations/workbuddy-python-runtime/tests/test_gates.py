from __future__ import annotations

import hashlib
import json
import io
import os
import shutil
import subprocess
import sys
import time
import unittest
import uuid
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import workbuddy_harness.hook_runner as hook_runner  # noqa: E402
from workbuddy_harness import (  # noqa: E402
    claim_schema_verifier,
    flush_logs,
    intake_router,
    load_policy,
    memory_isolation_gate,
    runtime_enforcer,
)


@contextmanager
def writable_test_dir():
    root = ROOT / ".test-tmp"
    path = root / f"case-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        probe = path / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)
        try:
            root.rmdir()
        except OSError:
            pass


class HarnessGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy()
        cls.neutral_cwd = ROOT / ".test-cwd"
        cls.neutral_cwd.mkdir(parents=True, exist_ok=True)
        probe = cls.neutral_cwd / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.neutral_cwd, ignore_errors=True)

    def _route(self, task_text: str, **kwargs: object) -> dict[str, object]:
        kwargs.setdefault("cwd", str(self.neutral_cwd))
        kwargs.setdefault("policy", self.policy)
        return intake_router(task_text, **kwargs)

    def _permit_json(self, task_text: str, tool_text: str, *, scope: str = "single_event") -> str:
        payload = {
            "schema": "cbh.r5_human_confirmation_permit.v1",
            "permit_id": f"PERMIT-{uuid.uuid4().hex}",
            "status": "active",
            "scope": scope,
            "risk_level": "R5",
            "confirmed_by": "human",
            "confirmed_at_utc": "2026-06-25T00:00:00Z",
            "expires_at_utc": "2099-01-01T00:00:00Z",
            "task_sha256": hashlib.sha256(task_text.encode("utf-8")).hexdigest(),
            "tool_sha256": hashlib.sha256(tool_text.encode("utf-8")).hexdigest(),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def test_router_detects_r5_delete(self) -> None:
        route = self._route("delete stale files after review", policy=self.policy)
        self.assertEqual(route["risk_level"], "R5")
        self.assertIn("R5", route["triggered_risks"])

    def test_adapter_manifest_declares_optional_quality_reference_surfaces(self) -> None:
        manifest_path = ROOT.parents[1] / "templates" / "adapter-contract" / "compatibility.manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        quality = manifest["quality_reference"]
        self.assertFalse(quality["default_enabled"])
        self.assertTrue(quality["advisory_only"])
        self.assertFalse(quality["blocks_execution"])
        self.assertTrue(quality["records_are_source_prior"])
        self.assertEqual(quality["domain_aesthetic_rubric_supported"], "unverified")
        self.assertEqual(quality["domain_source_tier_catalog_supported"], "unverified")

        claim_artifacts = manifest["claim_artifact_contracts"]
        self.assertFalse(claim_artifacts["default_enabled"])
        self.assertFalse(claim_artifacts["blocks_ordinary_chat"])
        self.assertTrue(claim_artifacts["requires_original_evidence_refs"])
        self.assertTrue(claim_artifacts["summaries_are_not_fact_sources"])

        causal = manifest["observation_and_causal_attribution"]
        self.assertTrue(causal["default_enabled"])
        self.assertFalse(causal["blocks_ordinary_local_causal_reasoning"])
        self.assertTrue(causal["public_private_boundary_is_separate"])
        self.assertIn("empirical_record", causal["attribution_levels"])

        feedback = manifest["memory_feedback_loop"]
        self.assertEqual(feedback["router_decision_gate_supported"], "unverified")
        self.assertFalse(feedback["host_hard_stop_gate"])
        self.assertTrue(feedback["internalized_on_reusable_memory_selection"])

        external_delivery = manifest["external_model_delivery"]
        self.assertEqual(external_delivery["structured_json_filler_mode_supported"], "unverified")
        self.assertFalse(external_delivery["advisory_issues_trigger_repair"])

    def test_router_detects_plain_commit_and_push_as_r5(self) -> None:
        route = self._route("commit and push the current repository update", policy=self.policy)
        self.assertEqual(route["risk_level"], "R5")
        self.assertIn("commit", route["matched_risk_triggers"].get("R5", []))
        self.assertIn("push", route["matched_risk_triggers"].get("R5", []))

    def test_router_uses_compact_profile_for_plain_local_r5(self) -> None:
        route = self._route("delete old files after explicit review", policy=self.policy)
        self.assertEqual(route["risk_level"], "R5")
        self.assertEqual(route["receipt_profile"], "compact_runtime")
        self.assertTrue(route["compact_receipt"]["human_confirmation_need"])

    def test_router_expands_profile_for_public_governance(self) -> None:
        route = self._route("update public README harness routing rules", policy=self.policy)
        self.assertEqual(route["receipt_profile"], "extended_governance")
        self.assertIn("governance_surface", route["profile_reason"])

    def test_router_uses_debug_profile_when_requested(self) -> None:
        route = self._route("route debug full receipt for this task", policy=self.policy)
        self.assertEqual(route["receipt_profile"], "debug_receipt")

    def test_router_profiles_context_continuity_reading(self) -> None:
        route = self._route("上下文压缩后继续这个长对话，先回顾当前任务源头和全局目标", policy=self.policy)
        self.assertIn("continuity_goal", route["read_semantic_boundary"])
        self.assertEqual(route["read_depth_profile"], "segment_window")
        self.assertEqual(route["edit_operation_profile"], "read_only")

    def test_router_profiles_in_place_update_without_rewrite(self) -> None:
        route = self._route("更新 AGENTS.md 中的记忆规则，不要重写整个文件", policy=self.policy)
        self.assertEqual(route["risk_level"], "R3")
        self.assertIn("change_integrity", route["read_semantic_boundary"])
        self.assertEqual(route["read_depth_profile"], "artifact_output_window")
        self.assertEqual(route["edit_operation_profile"], "in_place_patch")

    def test_router_profiles_filesystem_delete_as_r5(self) -> None:
        route = self._route("删除旧 release 文件夹", policy=self.policy)
        self.assertEqual(route["risk_level"], "R5")
        self.assertEqual(route["edit_operation_profile"], "delete_from_disk")
        self.assertEqual(route["risk_context_decisions"]["R5"]["action_surface"], "actionable_R5")

    def test_router_profiles_negated_delete_as_read_only(self) -> None:
        route = self._route("不要删除任何文件，只检查哪些内容可能需要归档", policy=self.policy)
        self.assertNotEqual(route["risk_level"], "R5")
        self.assertEqual(route["edit_operation_profile"], "read_only")

    def test_router_honors_simple_negation(self) -> None:
        route = self._route("do not delete anything, only inspect files", policy=self.policy)
        self.assertNotEqual(route["risk_level"], "R5")
        self.assertIn("R1", route["triggered_risks"])
        self.assertIn("delete", route["negated_risk_triggers"].get("R5", []))

    def test_router_demotes_memory_status_wording_from_r5(self) -> None:
        route = self._route("只读检查 Example Project Memory Bank 已更新和长期记忆状态，不写入记忆", policy=self.policy)
        self.assertNotEqual(route["risk_level"], "R5")
        self.assertIn("长期记忆", route["risk_candidates"].get("R5", []))
        self.assertEqual(route["risk_context_decisions"]["R5"]["action_surface"], "documentation_or_discussion")

    def test_router_uses_local_project_lane_overlay(self) -> None:
        with writable_test_dir() as root_text:
            root = Path(root_text)
            project = root / "EXAMPLE_PROJECT"
            memory_bank = project / "memory-bank"
            memory_bank.mkdir(parents=True)
            overlay = root / "project_lanes.local.json"
            overlay.write_text(
                json.dumps(
                    {
                        "schema": "cbh.project_lane_overlay.v1",
                        "project_lanes": {"EXAMPLE_PROJECT": [str(project)]},
                        "memory_roots": {"EXAMPLE_PROJECT": [str(memory_bank)]},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"CBH_PROJECT_LANES_FILE": str(overlay)}):
                policy = load_policy()
            route = self._route("只读检查 Memory Bank 已更新和长期记忆状态", cwd=str(project), policy=policy)
        self.assertEqual(route["project_lane"], "EXAMPLE_PROJECT")
        self.assertEqual(route["memory_lane"], "current_project")
        self.assertNotEqual(route["risk_level"], "R5")

    def test_router_marks_project_long_term_memory_write_as_write_mode(self) -> None:
        with writable_test_dir() as root_text:
            root = Path(root_text)
            project = root / "EXAMPLE_PROJECT"
            memory_bank = project / "memory-bank"
            memory_bank.mkdir(parents=True)
            overlay = root / "project_lanes.local.json"
            overlay.write_text(
                json.dumps(
                    {
                        "schema": "cbh.project_lane_overlay.v1",
                        "project_lanes": {"EXAMPLE_PROJECT": [str(project)]},
                        "memory_roots": {"EXAMPLE_PROJECT": [str(memory_bank)]},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"CBH_PROJECT_LANES_FILE": str(overlay)}):
                policy = load_policy()
            route = self._route("写入记忆：记录这个长期记忆修复", cwd=str(project), policy=policy)
        self.assertEqual(route["project_lane"], "EXAMPLE_PROJECT")
        self.assertEqual(route["risk_level"], "R5")
        self.assertEqual(route["memory_lane"], "current_project")
        self.assertEqual(route["memory_mode"], "write")
        self.assertEqual(route["record_intent"], "explicit_user_request")

    def test_router_detects_completion_review_as_read_only_scope_check(self) -> None:
        route = self._route(
            "review whether the memory layer absorption is complete and identify unfinished public or local work",
            policy=self.policy,
        )
        self.assertEqual(route["risk_level"], "R1")
        self.assertIn("scope_reassessment_gate", route["required_gates"])
        self.assertIn("composite_or_scope_reassessment", route["semantic_ambiguity"])

    def test_router_detects_chinese_absorption_status_review_as_composite_change_check(self) -> None:
        route = self._route("所以刚刚做到一半的功能吸纳落地做完了吗，回顾一下还有什么没做完", policy=self.policy)
        self.assertEqual(route["risk_level"], "R3")
        self.assertIn("R1", route["triggered_risks"])
        self.assertIn("scope_reassessment_gate", route["required_gates"])
        self.assertIn("composite_or_scope_reassessment", route["semantic_ambiguity"])

    def test_router_detects_observation_scope_gate(self) -> None:
        route = self._route("从 6 月 15 日以来整体上是否一直更稳定", policy=self.policy)
        self.assertIn("observation_scope_gate", route["required_gates"])
        self.assertIn("observation_scope_required", route["semantic_ambiguity"])
        self.assertIn("observation_scope", route["matched_risk_triggers"])

    def test_router_detects_linked_surface_sync_gate(self) -> None:
        route = self._route(
            "这次 router 和 policy 更新要保持环环相扣，只更新 Codex 和 WorkBuddy，不更新 Bash",
            policy=self.policy,
        )
        self.assertEqual(route["risk_level"], "R4")
        self.assertIn("linked_surface_sync_gate", route["required_gates"])
        self.assertIn("linked_surface_sync_gate", route["semantic_ambiguity"])
        self.assertIn("linked_surface_sync_gate", route["matched_risk_triggers"])

    def test_router_detects_novel_recurrence_candidate_without_heavy_gates(self) -> None:
        route = self._route(
            "这次表现和旧问题不是同一类，但结构相似，可能是新型异常，先标记为候选复发再轻量复评",
            policy=self.policy,
        )
        self.assertIn("novel_recurrence_candidate_gate", route["required_gates"])
        self.assertIn("novel_recurrence_candidate_gate", route["semantic_ambiguity"])
        self.assertIn("novel_recurrence_candidate_gate", route["matched_risk_triggers"])
        self.assertNotIn("global_task_context_gate", route["required_gates"])
        self.assertNotIn("feedback_loop_gate", route["required_gates"])

    def test_router_detects_feedback_loop_gate(self) -> None:
        route = self._route("为这个同类错误加入记忆-预测-验证-校准反馈闭环，观察下次是否复发", policy=self.policy)
        self.assertIn("feedback_loop_gate", route["required_gates"])
        self.assertIn("feedback_loop_required", route["semantic_ambiguity"])
        self.assertIn("feedback_loop", route["matched_risk_triggers"])
        self.assertEqual(route["feedback_loop_profile"], "explicit_cycle")
        self.assertEqual(route["memory_need"], "index_only")

    def test_router_uses_feedback_loop_for_paired_memory(self) -> None:
        route = self._route("查看 ERR-2026-06-29-01 / SOL-2026-06-29-01 这个同类错误的解决记录")
        self.assertIn("feedback_loop_gate", route["required_gates"])
        self.assertIn("feedback_loop_required", route["semantic_ambiguity"])
        self.assertEqual(route["memory_need"], "paired_err_sol")
        self.assertEqual(route["feedback_loop_profile"], "prevention_review")
        self.assertIn("feedback_loop_memory", route["matched_risk_triggers"])

    def test_router_uses_feedback_loop_for_common_error_memory(self) -> None:
        route = self._route("查看 common error 记录并按里面的预防规则继续排查")
        self.assertIn("feedback_loop_gate", route["required_gates"])
        self.assertIn("feedback_loop_required", route["semantic_ambiguity"])
        self.assertEqual(route["memory_need"], "common_error_corpus")
        self.assertEqual(route["memory_mode"], "read")
        self.assertEqual(route["record_intent"], "no_record")
        self.assertEqual(route["feedback_loop_profile"], "prevention_review")
        self.assertIn("feedback_loop_common_error", route["matched_risk_triggers"])

    def test_router_writes_common_error_only_with_record_intent(self) -> None:
        route = self._route("record this error as a common error after the fix is verified")
        self.assertNotIn("feedback_loop_gate", route["required_gates"])
        self.assertEqual(route["memory_need"], "common_error_corpus")
        self.assertEqual(route["memory_mode"], "write")
        self.assertEqual(route["record_intent"], "inferred_reusable_error")
        self.assertEqual(route["feedback_loop_profile"], "record_candidate")

    def test_router_combines_global_context_and_feedback_prevention(self) -> None:
        route = self._route("这个全局问题需要从当前事件发散分析后续可能出现的同类事件，并进行预防，避免再只照顾局部")
        self.assertIn("global_task_context_gate", route["required_gates"])
        self.assertIn("feedback_loop_gate", route["required_gates"])
        self.assertIn("global_task_context_gate", route["semantic_ambiguity"])
        self.assertIn("feedback_loop_required", route["semantic_ambiguity"])
        self.assertEqual(route["feedback_loop_profile"], "explicit_cycle")

    def test_router_detects_static_knowledge_layer_lookup(self) -> None:
        route = self._route("read the project manual and module map before editing", policy=self.policy)
        self.assertIn("R1", route["triggered_risks"])
        self.assertEqual(route["memory_need"], "index_only")
        self.assertIn("static_knowledge_index", route["module_need"])
        self.assertIn("static_knowledge_index_gate", route["required_gates"])

    def test_router_detects_github_external_research(self) -> None:
        route = self._route("compare GitHub open source repositories and learn from them", policy=self.policy)
        self.assertTrue(route["needs_external_research"])
        self.assertIn("external_research", route["matched_risk_triggers"])
        self.assertEqual(route["target_surface"], "public_docs")
        self.assertIn("github_open_source_repository_search", route["external_need"])

    def test_router_requires_external_evidence_for_uncertain_design_discussion(self) -> None:
        route = self._route("我们不确定这个机制有没有成熟方案，需要外部证据后再决定是否吸纳", policy=self.policy)
        self.assertTrue(route["needs_external_research"])
        self.assertIn("external_research", route["matched_risk_triggers"])
        self.assertIn("external_research_gate", route["module_need"])
        self.assertTrue(
            {"general_web_cross_check", "source_grounded_learning_intake"}.intersection(route["external_need"])
        )

    def test_router_receipt_detects_memory_contract_need(self) -> None:
        route = self._route("update routing decision layer and memory meta index contract", policy=self.policy)
        self.assertIn(route["risk_level"], {"R3", "R4"})
        self.assertEqual(route["routing_receipt"]["target_surface"], "local_harness")
        self.assertEqual(route["memory_need"], "index_only")
        self.assertIn("memory_meta_index", route["module_need"])

    def test_router_detects_explicit_error_recording(self) -> None:
        route = self._route("record this error in the self-reflection matrix", policy=self.policy)
        self.assertEqual(route["memory_mode"], "write")
        self.assertEqual(route["memory_lane"], "self_reflection_matrix")
        self.assertEqual(route["record_intent"], "explicit_user_request")

    def test_router_detects_plural_chinese_issue_recording(self) -> None:
        route = self._route("先记录这几个问题，然后继续排查 WorkBuddy", policy=self.policy)
        self.assertIn(route["memory_mode"], {"write", "update"})
        self.assertEqual(route["memory_lane"], "self_reflection_matrix")
        self.assertEqual(route["record_intent"], "explicit_user_request")

    def test_router_detects_projectization_candidate(self) -> None:
        route = self._route("README VERSION CHANGELOG tests adapter repository release", policy=self.policy)
        self.assertEqual(route["projectization_decision"], "emergent_project_candidate")
        self.assertEqual(route["record_intent"], "projectization_review")

    def test_router_detects_explicit_conversation_memory_request(self) -> None:
        route = self._route("checkpoint this conversation so we can continue this conversation later", policy=self.policy)
        self.assertEqual(route["conversation_memory_decision"], "create_or_update_current_conversation")
        self.assertEqual(route["memory_lane"], "current_conversation")
        self.assertEqual(route["memory_mode"], "write")
        self.assertEqual(route["record_intent"], "explicit_conversation_memory_request")
        self.assertIn("conversation_memory_index", route["module_need"])
        self.assertEqual(route["hybrid_retrieval_profile"], "meta_first_hybrid_required")
        self.assertEqual(route["memory_write_profile"], "strict_capsule_required")

    def test_router_detects_continue_previous_conversation_link_intent(self) -> None:
        route = self._route("continue from the previous conversation", policy=self.policy)
        self.assertEqual(route["link_intent"], "continue_from_latest")
        self.assertEqual(route["conversation_memory_decision"], "read_referenced_conversation")
        self.assertEqual(route["memory_lane"], "referenced_conversation")
        self.assertEqual(route["memory_mode"], "read")
        self.assertIn("conversation_link_gate", route["required_gates"])
        self.assertIn("memory_link_ledger", route["module_need"])
        self.assertEqual(route["hybrid_retrieval_profile"], "meta_first_hybrid_required")
        self.assertEqual(route["memory_write_profile"], "none")

    def test_router_detects_continue_previous_and_create_current_memory(self) -> None:
        route = self._route(
            "接续上一段对话记忆，创建此对话新记忆文件并链接上一段对话记忆文件",
            policy=self.policy,
        )
        self.assertEqual(route["link_intent"], "continue_from_latest")
        self.assertEqual(route["conversation_memory_decision"], "create_or_update_current_conversation")
        self.assertEqual(route["memory_lane"], "current_conversation")
        self.assertEqual(route["memory_mode"], "write")
        self.assertEqual(route["record_intent"], "explicit_conversation_memory_request")
        self.assertIn("conversation_link_gate", route["required_gates"])
        self.assertEqual(route["hybrid_retrieval_profile"], "meta_first_hybrid_required")
        self.assertEqual(route["memory_write_profile"], "strict_capsule_required")

    def test_router_detects_conversation_ledger_surface(self) -> None:
        route = self._route(
            "为当前对话建立对话账本，链接 raw session JSONL、segments.jsonl、evidence_refs 和当前对话记忆",
            policy=self.policy,
        )
        self.assertEqual(route["target_surface"], "conversation_ledger")
        self.assertIn("conversation_ledger_index", route["module_need"])
        self.assertEqual(route["hybrid_retrieval_profile"], "meta_first_hybrid_enhancement")
        self.assertEqual(route["memory_write_profile"], "none")

    def test_router_detects_skill_lifecycle_release_and_reactivation(self) -> None:
        route = self._route(
            "skill 调用周期结束后释放大正文并保留 skill release receipt，下次从恢复入口重新激活",
            policy=self.policy,
        )
        self.assertEqual(route["target_surface"], "skill_matrix")
        self.assertIn("skill_matrix", route["module_need"])
        self.assertEqual(route["skill_lifecycle_profile"], "reactivate_from_receipt")

    def test_router_detects_github_tool_surface_discovery(self) -> None:
        route = self._route("查找 GitHub 上 Yuan1z0825/nature-skills 仓库并读取 SKILL.md", policy=self.policy)
        self.assertEqual(route["tool_surface_need"], "plugin_mcp")
        self.assertEqual(route["tool_discovery_status"], "not_checked")
        self.assertEqual(route["plugin_need"], "candidate_discovery_required")
        self.assertEqual(route["preferred_call_surface"], "plugin_or_connector")
        self.assertIn("tool_surface_discovery", route["module_need"])
        self.assertIn("tool_surface_discovery_gate", route["required_gates"])

    def test_router_detects_user_named_plugin_surface(self) -> None:
        route = self._route("[@github] 读取某个仓库的 release 和 Actions 日志", policy=self.policy)
        self.assertEqual(route["tool_discovery_status"], "user_named")
        self.assertEqual(route["plugin_need"], "user_named")
        self.assertEqual(route["preferred_call_surface"], "plugin_or_connector")
        self.assertIn("tool_surface_discovery", route["module_need"])

    def test_router_detects_codex_native_skill_surface(self) -> None:
        route = self._route("帮我分析这个 PDF 并整理文档摘要", policy=self.policy)
        self.assertEqual(route["tool_surface_need"], "native_skill")
        self.assertEqual(route["skill_or_tool_need"], "codex_native_skill")
        self.assertEqual(route["preferred_call_surface"], "native_skill")
        self.assertIn("tool_surface_discovery", route["module_need"])

    def test_router_keeps_local_test_task_on_shell_surface(self) -> None:
        route = self._route("运行本地 pytest 并查看失败日志", policy=self.policy)
        self.assertNotIn("tool_surface_discovery", route["module_need"])
        self.assertEqual(route["tool_surface_need"], "none")
        self.assertEqual(route["tool_discovery_status"], "not_needed")
        self.assertEqual(route["plugin_need"], "none")

    def test_router_detects_explicit_merge_memory_link_intent(self) -> None:
        route = self._route("merge the old conversation memory with this conversation", policy=self.policy)
        self.assertEqual(route["link_intent"], "merge_memories_explicit")
        self.assertEqual(route["record_intent"], "explicit_cross_conversation_update")
        self.assertEqual(route["memory_mode"], "write")
        self.assertIn("conversation_link_gate", route["required_gates"])

    def test_router_detects_conversation_checkpoint_candidate(self) -> None:
        route = self._route(
            "long conversation with open loops, context compression, continue later, unresolved decision, and checkpoint risk",
            policy=self.policy,
        )
        self.assertEqual(route["conversation_memory_decision"], "checkpoint_candidate")
        self.assertEqual(route["memory_lane"], "current_conversation")
        self.assertEqual(route["record_intent"], "conversation_checkpoint")
        self.assertTrue(route["conversation_full_lane_triggered"])
        self.assertIn("compaction_or_context_loss", route["conversation_full_lane_groups"])

    def test_router_does_not_create_conversation_memory_for_plain_chat(self) -> None:
        route = self._route("explain why markdown is common", policy=self.policy)
        self.assertEqual(route["conversation_memory_decision"], "none")
        self.assertEqual(route["memory_lane"], "none")
        self.assertEqual(route["memory_mode"], "none")

    def test_router_projectization_takes_precedence_over_conversation_memory(self) -> None:
        route = self._route("README VERSION CHANGELOG tests adapter repository release long conversation", policy=self.policy)
        self.assertEqual(route["projectization_decision"], "emergent_project_candidate")
        self.assertEqual(route["conversation_memory_decision"], "none")
        self.assertEqual(route["memory_lane"], "emergent_project_candidate")

    def test_memory_gate_blocks_cross_lane_path(self) -> None:
        result = memory_isolation_gate(
            "EXAMPLE_PROJECT",
            r"C:\other\project\memory-bank\capsule.md",
            policy=self.policy,
        )
        self.assertEqual(result["status"], "blocked")

    def test_claim_schema_blocks_missing_source_ref(self) -> None:
        result = claim_schema_verifier(
            claim_json={
                "claim_type": "external_fact",
                "source_type": "external_retrieval",
                "evidence_boundary": "single source",
            },
            policy=self.policy,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("missing_source_ref_for_external_retrieval", result["issues"])

    def test_claim_schema_blocks_causal_attribution_overclaim(self) -> None:
        result = claim_schema_verifier(
            final_text="CBH solved hallucination drift for all agents.",
            policy=self.policy,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "causal_attribution_boundary_required:abstract_system_causal_global_effect",
            result["issues"],
        )

    def test_claim_schema_allows_scoped_causal_hypothesis(self) -> None:
        result = claim_schema_verifier(
            final_text=(
                "In this local sample, this is a causal_hypothesis, not proof: "
                "memory anchors may have reduced this task's drift."
            ),
            policy=self.policy,
        )
        self.assertEqual(result["status"], "pass")

    def test_claim_schema_scope_limiter_is_sentence_local(self) -> None:
        result = claim_schema_verifier(
            final_text=(
                "In this local sample, this is a causal_hypothesis, not proof. "
                "CBH solved hallucination drift for all agents."
            ),
            policy=self.policy,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "causal_attribution_boundary_required:abstract_system_causal_global_effect",
            result["issues"],
        )

    def test_runtime_blocks_hard_tool_without_confirmation(self) -> None:
        decision = runtime_enforcer(
            stage="pre_tool",
            task_text="prepare repository update",
            tool_name="shell",
            tool_input={"command": "git commit -m update"},
            constitution_reviewed=True,
            policy=self.policy,
        )
        self.assertEqual(decision["status"], "blocked")
        self.assertIn("tool_call_requires_human_confirmation", decision["blocked_reasons"])

    def test_runtime_blocks_unix_rm_rf_without_confirmation(self) -> None:
        decision = runtime_enforcer(
            stage="pre_tool",
            task_text="clean temporary build files",
            tool_name="shell",
            tool_input={"command": "rm -rf build"},
            constitution_reviewed=True,
            policy=self.policy,
        )
        self.assertEqual(decision["status"], "blocked")
        self.assertIn("tool_call_requires_human_confirmation", decision["blocked_reasons"])
        self.assertTrue(any("rm" in hit for hit in decision["tool_hard_hits"]))

    def test_runtime_preserves_original_task_text_for_pre_tool(self) -> None:
        decision = runtime_enforcer(
            stage="pre_tool",
            task_text="R5",
            original_task_text="delete stale files after review",
            tool_name="shell",
            tool_input={"command": "echo ok"},
            constitution_reviewed=True,
            policy=self.policy,
        )
        self.assertEqual(decision["route"]["risk_level"], "R5")
        self.assertEqual(decision["task_text_for_route"], "delete stale files after review")
        self.assertEqual(decision["status"], "blocked")
        self.assertIn("human_confirmation_required_for_R5", decision["blocked_reasons"])

    def test_runtime_blocks_unresolved_conversation_link_before_tool(self) -> None:
        decision = runtime_enforcer(
            stage="pre_tool",
            task_text="continue from the previous conversation",
            tool_name="shell",
            tool_input={"command": "echo ok"},
            constitution_reviewed=True,
            policy=self.policy,
        )
        self.assertEqual(decision["status"], "blocked")
        self.assertTrue(decision["conversation_link_required"])
        self.assertIn("conversation_link_decision_required", decision["blocked_reasons"])

    def test_runtime_allows_resolved_conversation_link_before_tool(self) -> None:
        decision = runtime_enforcer(
            stage="pre_tool",
            task_text="continue from the previous conversation",
            tool_name="shell",
            tool_input={"command": "echo ok"},
            conversation_link_resolved=True,
            constitution_reviewed=True,
            policy=self.policy,
        )
        self.assertEqual(decision["status"], "pass")
        self.assertTrue(decision["conversation_link_required"])
        self.assertTrue(decision["conversation_link_resolved"])

    def test_runtime_treats_risk_label_task_text_as_explicit_risk(self) -> None:
        decision = runtime_enforcer(
            stage="pre_tool",
            task_text="R5",
            tool_name="shell",
            tool_input={"command": "echo ok"},
            constitution_reviewed=True,
            policy=self.policy,
        )
        self.assertEqual(decision["route"]["risk_level"], "R5")
        self.assertEqual(decision["explicit_risk_level"], "R5")
        self.assertEqual(decision["status"], "blocked")

    def test_runtime_passes_confirmed_hard_tool_when_constitution_reviewed(self) -> None:
        decision = runtime_enforcer(
            stage="pre_tool",
            task_text="prepare repository update",
            tool_name="shell",
            tool_input={"command": "git commit -m update"},
            human_confirmed=True,
            constitution_reviewed=True,
            policy=self.policy,
        )
        self.assertEqual(decision["status"], "pass")

    def test_runtime_allows_exact_single_event_confirmation_permit(self) -> None:
        with writable_test_dir() as tmp:
            task_text = "prepare repository update"
            tool_text = "shell\ngit commit -m update"
            decision = runtime_enforcer(
                stage="pre_tool",
                task_text=task_text,
                tool_name="shell",
                tool_input={"command": "git commit -m update"},
                human_confirmation_permit_json=self._permit_json(task_text, tool_text),
                human_confirmation_permit_use_ledger_path=str(Path(tmp) / "r5-permit-uses.jsonl"),
                constitution_reviewed=True,
                policy=self.policy,
            )
        self.assertEqual(decision["status"], "pass")
        self.assertFalse(decision["human_confirmed"])
        self.assertTrue(decision["effective_human_confirmed"])
        self.assertEqual(decision["human_confirmation_permit"]["status"], "pass")
        self.assertTrue(decision["human_confirmation_permit"]["consumed"])

    def test_runtime_blocks_replayed_single_event_confirmation_permit(self) -> None:
        with writable_test_dir() as tmp:
            task_text = "prepare repository update"
            tool_text = "shell\ngit commit -m update"
            permit = self._permit_json(task_text, tool_text)
            ledger_path = str(Path(tmp) / "r5-permit-uses.jsonl")
            first = runtime_enforcer(
                stage="pre_tool",
                task_text=task_text,
                tool_name="shell",
                tool_input={"command": "git commit -m update"},
                human_confirmation_permit_json=permit,
                human_confirmation_permit_use_ledger_path=ledger_path,
                constitution_reviewed=True,
                policy=self.policy,
            )
            second = runtime_enforcer(
                stage="pre_tool",
                task_text=task_text,
                tool_name="shell",
                tool_input={"command": "git commit -m update"},
                human_confirmation_permit_json=permit,
                human_confirmation_permit_use_ledger_path=ledger_path,
                constitution_reviewed=True,
                policy=self.policy,
            )
        self.assertEqual(first["status"], "pass")
        self.assertEqual(second["status"], "blocked")
        self.assertIn("permit_already_used", second["human_confirmation_permit"]["issues"])
        self.assertIn("tool_call_requires_human_confirmation", second["blocked_reasons"])

    def test_runtime_blocks_non_single_event_confirmation_permit(self) -> None:
        task_text = "prepare repository update"
        tool_text = "shell\ngit commit -m update"
        decision = runtime_enforcer(
            stage="pre_tool",
            task_text=task_text,
            tool_name="shell",
            tool_input={"command": "git commit -m update"},
            human_confirmation_permit_json=self._permit_json(task_text, tool_text, scope="session"),
            constitution_reviewed=True,
            policy=self.policy,
        )
        self.assertEqual(decision["status"], "blocked")
        self.assertIn("permit_not_single_event_scoped", decision["human_confirmation_permit"]["issues"])
        self.assertIn("tool_call_requires_human_confirmation", decision["blocked_reasons"])

    def test_runtime_ignores_non_command_tool_content_for_hard_tool_patterns(self) -> None:
        decision = runtime_enforcer(
            stage="pre_tool",
            task_text="inspect repository docs",
            tool_name="Write",
            tool_input={
                "file_path": "notes.md",
                "content": "Document the words delete, permission, and rm -rf as examples only.",
            },
            constitution_reviewed=True,
            policy=self.policy,
        )
        self.assertEqual(decision["status"], "pass")
        self.assertEqual(decision["tool_hard_hits"], [])

    def test_runtime_blocks_final_strong_claim_text(self) -> None:
        decision = runtime_enforcer(
            stage="final",
            task_text="report result",
            final_text="This is validated and verified successfully.",
            constitution_reviewed=True,
            policy=self.policy,
        )
        self.assertEqual(decision["status"], "blocked")
        self.assertIn("claim_schema_verifier_blocked", decision["blocked_reasons"])

    def test_flush_logs_appends_default_file_inside_log_dir(self) -> None:
        with writable_test_dir() as tmp:
            result = flush_logs(log_dir=tmp, events=[{"phase": "test", "status": "pass"}])
            log_path = Path(result["path"])
            self.assertEqual(log_path.name, "workbuddy_harness_events.jsonl")
            self.assertEqual(log_path.parent, Path(tmp))
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["written"], 1)
            self.assertTrue(log_path.exists())

    def test_flush_logs_sanitizes_lone_surrogates(self) -> None:
        with writable_test_dir() as tmp:
            result = flush_logs(log_dir=tmp, events=[{"phase": "test", "text": "bad \udcac"}])
            log_path = Path(result["path"])
            content = log_path.read_text(encoding="utf-8")
            self.assertIn("<invalid-surrogate>", content)
            self.assertNotIn("\\udcac", content)

    def test_hook_runner_json_output_keeps_readable_unicode(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            hook_runner._write_json({"text": "中文调试"})
        output = buffer.getvalue()
        self.assertIn("中文调试", output)
        self.assertNotIn("\\u4e2d", output)

    def test_runtime_log_dir_writes_event_file(self) -> None:
        with writable_test_dir() as tmp:
            decision = runtime_enforcer(
                stage="pre_tool",
                task_text="inspect repository",
                tool_name="shell",
                tool_input={"command": "echo ok"},
                constitution_reviewed=True,
                log_dir=tmp,
                policy=self.policy,
            )
            log_path = Path(decision["log_flush"]["path"])
            self.assertEqual(log_path.name, "workbuddy_harness_events.jsonl")
            self.assertEqual(decision["log_flush"]["written"], 1)
            self.assertTrue(log_path.exists())

    def _run_hook(
        self,
        payload: dict[str, object],
        *args: str,
        log_dir: str,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "workbuddy_harness.hook_runner",
                "--log-dir",
                log_dir,
                *args,
            ],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_workbuddy_user_prompt_hook_stays_silent_for_low_risk_context(self) -> None:
        with writable_test_dir() as tmp:
            result = self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-a",
                    "cwd": tmp,
                    "prompt": "inspect local notes and summarize findings",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertTrue(output["continue"])
            self.assertNotIn("hookSpecificOutput", output)
            state_path = Path(tmp) / "workbuddy_hook_state.json"
            self.assertTrue(state_path.exists())

    def test_workbuddy_user_prompt_hook_extracts_recording_transcript(self) -> None:
        with writable_test_dir() as tmp:
            result = self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-recording",
                    "cwd": tmp,
                    "recording": {
                        "mime_type": "audio/webm",
                        "transcript": "delete stale files after review",
                    },
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            context = output["hookSpecificOutput"]["additionalContext"]
            self.assertIn("human_confirmation=required", context)
            state_path = Path(tmp) / "workbuddy_hook_state.json"
            state_text = state_path.read_text(encoding="utf-8")
            self.assertIn("delete stale files after review", state_text)

    def test_workbuddy_user_prompt_hook_exposes_debug_receipt_when_requested(self) -> None:
        with writable_test_dir() as tmp:
            result = self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-debug",
                    "cwd": tmp,
                    "prompt": "route debug full receipt for this task",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            context = output["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Claim Boundary Harness debug receipt", context)
            self.assertIn("matched_risk_triggers", context)

    def test_workbuddy_user_prompt_hook_sanitizes_lone_surrogate_payload(self) -> None:
        with writable_test_dir() as tmp:
            result = self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-surrogate",
                    "cwd": tmp,
                    "prompt": "bad \udcac",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertTrue(output["continue"])
            state_path = Path(tmp) / "workbuddy_hook_state.json"
            state_text = state_path.read_text(encoding="utf-8")
            self.assertIn("<invalid-surrogate>", state_text)
            self.assertNotIn("\\udcac", state_text)

    def test_workbuddy_pre_tool_hook_blocks_hard_tool(self) -> None:
        with writable_test_dir() as tmp:
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-b",
                    "cwd": tmp,
                    "prompt": "delete stale build files after review",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            result = self._run_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-b",
                    "cwd": tmp,
                    "tool_name": "Bash",
                    "tool_input": {"command": "rm -rf build"},
                },
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            output = json.loads(result.stdout)
            hook_output = output["hookSpecificOutput"]
            self.assertEqual(hook_output["permissionDecision"], "deny")
            self.assertIn("tool_call_requires_human_confirmation", hook_output["permissionDecisionReason"])

    def test_workbuddy_pre_tool_hook_allows_exact_single_event_confirmation_permit(self) -> None:
        with writable_test_dir() as tmp:
            task_text = "delete stale build files after review"
            tool_text = "Bash\nrm -rf build"
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-permit",
                    "cwd": tmp,
                    "prompt": task_text,
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            result = self._run_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-permit",
                    "cwd": tmp,
                    "tool_name": "Bash",
                    "tool_input": {"command": "rm -rf build"},
                },
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                "--human-confirmation-permit-json",
                self._permit_json(task_text, tool_text),
                "--human-confirmation-permit-use-ledger-path",
                str(Path(tmp) / "r5-permit-uses.jsonl"),
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertTrue(output["continue"])

    def test_workbuddy_pre_tool_hook_blocks_replayed_single_event_confirmation_permit(self) -> None:
        with writable_test_dir() as tmp:
            task_text = "delete stale build files after review"
            tool_text = "Bash\nrm -rf build"
            permit = self._permit_json(task_text, tool_text)
            ledger_path = str(Path(tmp) / "r5-permit-uses.jsonl")
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-permit-replay",
                    "cwd": tmp,
                    "prompt": task_text,
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            first = self._run_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-permit-replay",
                    "cwd": tmp,
                    "tool_name": "Bash",
                    "tool_input": {"command": "rm -rf build"},
                },
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                "--human-confirmation-permit-json",
                permit,
                "--human-confirmation-permit-use-ledger-path",
                ledger_path,
                log_dir=tmp,
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            second = self._run_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-permit-replay",
                    "cwd": tmp,
                    "tool_name": "Bash",
                    "tool_input": {"command": "rm -rf build"},
                },
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                "--human-confirmation-permit-json",
                permit,
                "--human-confirmation-permit-use-ledger-path",
                ledger_path,
                log_dir=tmp,
            )
            self.assertEqual(second.returncode, 2, second.stderr)
            output = json.loads(second.stdout)
            hook_output = output["hookSpecificOutput"]
            self.assertEqual(hook_output["permissionDecision"], "deny")
            self.assertIn("tool_call_requires_human_confirmation", hook_output["permissionDecisionReason"])

            log_path = Path(tmp) / "workbuddy_harness_events.jsonl"
            events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            replay_events = [
                event
                for event in events
                if event.get("phase") == "runtime_enforcer"
                and event.get("human_confirmation_permit", {}).get("issues") == ["permit_already_used"]
            ]
            self.assertTrue(replay_events)

    def test_workbuddy_direct_conversation_approval_allows_one_r5_tool_event(self) -> None:
        with writable_test_dir() as tmp:
            session_id = "session-direct-approval"
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": session_id,
                    "cwd": tmp,
                    "prompt": "delete the stale build directory after review",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": session_id,
                    "cwd": tmp,
                    "prompt": "授权完整清除，允许执行",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": session_id,
                "cwd": tmp,
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf build"},
            }
            first = self._run_hook(
                payload,
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                log_dir=tmp,
            )
            second = self._run_hook(
                payload,
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                log_dir=tmp,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 2, second.stderr)
            self.assertTrue(json.loads(first.stdout)["continue"])
            self.assertIn(
                "tool_call_requires_human_confirmation",
                json.loads(second.stdout)["hookSpecificOutput"]["permissionDecisionReason"],
            )
            used_records = [
                json.loads(line)
                for line in (Path(tmp) / "r5-permit-uses.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(used_records), 1)

    def test_workbuddy_short_confirmation_reply_requires_prior_confirmation_need(self) -> None:
        with writable_test_dir() as tmp:
            session_id = "session-short-approval"
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": session_id,
                    "cwd": tmp,
                    "prompt": "inspect files and summarize findings",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": session_id,
                    "cwd": tmp,
                    "prompt": "允许",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            state = json.loads((Path(tmp) / "workbuddy_hook_state.json").read_text(encoding="utf-8"))
            self.assertNotIn("pending_human_confirmation", state["sessions"][session_id])

    def test_workbuddy_host_permission_signal_allows_one_r5_tool_event(self) -> None:
        with writable_test_dir() as tmp:
            session_id = "session-host-approval"
            confirmation_id = "WB-PERMISSION-PROMPT-001"
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": session_id,
                    "cwd": tmp,
                    "prompt": "delete the stale build directory after review",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": session_id,
                "cwd": tmp,
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf build"},
                "runtime_human_confirmation": "confirmed",
                "runtime_confirmation_ts": time.time(),
                "runtime_confirmation_id": confirmation_id,
            }
            first = self._run_hook(
                payload,
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                log_dir=tmp,
            )
            second = self._run_hook(
                payload,
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                log_dir=tmp,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 2, second.stderr)

    def test_workbuddy_stale_host_permission_signal_does_not_release_r5(self) -> None:
        with writable_test_dir() as tmp:
            session_id = "session-stale-host-approval"
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": session_id,
                    "cwd": tmp,
                    "prompt": "delete the stale build directory after review",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            result = self._run_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": session_id,
                    "cwd": tmp,
                    "tool_name": "Bash",
                    "tool_input": {"command": "rm -rf build"},
                    "runtime_human_confirmation": "confirmed",
                    "runtime_confirmation_ts": time.time() - 301,
                    "runtime_confirmation_id": "WB-STALE-001",
                },
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(
                "tool_call_requires_human_confirmation",
                json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"],
            )

    def test_workbuddy_pre_tool_hook_does_not_block_write_content_examples(self) -> None:
        with writable_test_dir() as tmp:
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-write",
                    "cwd": tmp,
                    "prompt": "inspect files and summarize findings",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            result = self._run_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-write",
                    "cwd": tmp,
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": "notes.md",
                        "content": "Mention permission, delete, and rm -rf as documentation examples.",
                    },
                },
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertTrue(output["continue"])

    def test_workbuddy_pre_tool_hook_allows_low_risk_tool(self) -> None:
        with writable_test_dir() as tmp:
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-c",
                    "cwd": tmp,
                    "prompt": "inspect files and summarize findings",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            result = self._run_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-c",
                    "cwd": tmp,
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls"},
                },
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertTrue(output["continue"])

    def test_workbuddy_pre_tool_hook_blocks_unresolved_conversation_link(self) -> None:
        with writable_test_dir() as tmp:
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-link",
                    "cwd": tmp,
                    "prompt": "continue from the previous conversation",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            result = self._run_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-link",
                    "cwd": tmp,
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls"},
                },
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            output = json.loads(result.stdout)
            self.assertIn("conversation_link_decision_required", output["hookSpecificOutput"]["permissionDecisionReason"])

    def test_workbuddy_pre_tool_hook_allows_resolved_conversation_link(self) -> None:
        with writable_test_dir() as tmp:
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-link-ok",
                    "cwd": tmp,
                    "prompt": "continue from the previous conversation",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            result = self._run_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "session-link-ok",
                    "cwd": tmp,
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls"},
                },
                "--stage",
                "pre_tool",
                "--constitution-reviewed",
                "--conversation-link-resolved",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertTrue(output["continue"])

    def test_workbuddy_stop_hook_blocks_final_strong_claim(self) -> None:
        with writable_test_dir() as tmp:
            self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-final",
                    "cwd": tmp,
                    "prompt": "summarize the test result",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            result = self._run_hook(
                {
                    "hook_event_name": "Stop",
                    "session_id": "session-final",
                    "cwd": tmp,
                    "final_text": "This deployment is validated and verified successfully.",
                },
                "--stage",
                "final",
                "--constitution-reviewed",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            output = json.loads(result.stdout)
            self.assertFalse(output["continue"])
            self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "Stop")
            self.assertIn("claim_schema_verifier_blocked", output["systemMessage"])

    def test_workbuddy_stop_hook_allows_plain_final_text(self) -> None:
        with writable_test_dir() as tmp:
            result = self._run_hook(
                {
                    "hook_event_name": "Stop",
                    "session_id": "session-final-pass",
                    "cwd": tmp,
                    "final_text": "I inspected the files and found no matching errors.",
                },
                "--stage",
                "final",
                "--constitution-reviewed",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertTrue(output["continue"])


if __name__ == "__main__":
    unittest.main()
