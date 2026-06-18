from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workbuddy_harness import (  # noqa: E402
    claim_schema_verifier,
    flush_logs,
    intake_router,
    load_policy,
    memory_isolation_gate,
    runtime_enforcer,
)


class HarnessGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy()

    def test_router_detects_r5_delete(self) -> None:
        route = intake_router("delete stale files after review", policy=self.policy)
        self.assertEqual(route["risk_level"], "R5")
        self.assertIn("R5", route["triggered_risks"])

    def test_router_detects_plain_commit_and_push_as_r5(self) -> None:
        route = intake_router("commit and push the current repository update", policy=self.policy)
        self.assertEqual(route["risk_level"], "R5")
        self.assertIn("commit", route["matched_risk_triggers"].get("R5", []))
        self.assertIn("push", route["matched_risk_triggers"].get("R5", []))

    def test_router_uses_compact_profile_for_plain_local_r5(self) -> None:
        route = intake_router("delete old files after explicit review", policy=self.policy)
        self.assertEqual(route["risk_level"], "R5")
        self.assertEqual(route["receipt_profile"], "compact_runtime")
        self.assertTrue(route["compact_receipt"]["human_confirmation_need"])

    def test_router_expands_profile_for_public_governance(self) -> None:
        route = intake_router("update public README harness routing rules", policy=self.policy)
        self.assertEqual(route["receipt_profile"], "extended_governance")
        self.assertIn("governance_surface", route["profile_reason"])

    def test_router_uses_debug_profile_when_requested(self) -> None:
        route = intake_router("route debug full receipt for this task", policy=self.policy)
        self.assertEqual(route["receipt_profile"], "debug_receipt")

    def test_router_honors_simple_negation(self) -> None:
        route = intake_router("do not delete anything, only inspect files", policy=self.policy)
        self.assertNotEqual(route["risk_level"], "R5")
        self.assertIn("R1", route["triggered_risks"])
        self.assertIn("delete", route["negated_risk_triggers"].get("R5", []))

    def test_router_detects_github_external_research(self) -> None:
        route = intake_router("compare GitHub open source repositories and learn from them", policy=self.policy)
        self.assertTrue(route["needs_external_research"])
        self.assertIn("external_research", route["matched_risk_triggers"])
        self.assertEqual(route["target_surface"], "public_docs")
        self.assertIn("github_open_source_repository_search", route["external_need"])

    def test_router_receipt_detects_memory_contract_need(self) -> None:
        route = intake_router("update routing decision layer and memory meta index contract", policy=self.policy)
        self.assertIn(route["risk_level"], {"R3", "R4"})
        self.assertEqual(route["routing_receipt"]["target_surface"], "local_harness")
        self.assertEqual(route["memory_need"], "index_only")
        self.assertIn("memory_meta_index", route["module_need"])

    def test_router_detects_explicit_error_recording(self) -> None:
        route = intake_router("record this error in the self-reflection matrix", policy=self.policy)
        self.assertEqual(route["memory_mode"], "write")
        self.assertEqual(route["memory_lane"], "self_reflection_matrix")
        self.assertEqual(route["record_intent"], "explicit_user_request")

    def test_router_detects_projectization_candidate(self) -> None:
        route = intake_router("README VERSION CHANGELOG tests adapter repository release", policy=self.policy)
        self.assertEqual(route["projectization_decision"], "emergent_project_candidate")
        self.assertEqual(route["record_intent"], "projectization_review")

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
        with tempfile.TemporaryDirectory() as tmp:
            result = flush_logs(log_dir=tmp, events=[{"phase": "test", "status": "pass"}])
            log_path = Path(result["path"])
            self.assertEqual(log_path.name, "workbuddy_harness_events.jsonl")
            self.assertEqual(log_path.parent, Path(tmp))
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["written"], 1)
            self.assertTrue(log_path.exists())

    def test_runtime_log_dir_writes_event_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
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


if __name__ == "__main__":
    unittest.main()
