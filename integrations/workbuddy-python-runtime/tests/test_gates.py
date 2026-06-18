from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workbuddy_harness import (  # noqa: E402
    claim_schema_verifier,
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

    def test_router_honors_simple_negation(self) -> None:
        route = intake_router("do not delete anything, only inspect files", policy=self.policy)
        self.assertNotEqual(route["risk_level"], "R5")
        self.assertIn("R1", route["triggered_risks"])
        self.assertIn("delete", route["negated_risk_triggers"].get("R5", []))

    def test_router_detects_github_external_research(self) -> None:
        route = intake_router("compare GitHub open source repositories and learn from them", policy=self.policy)
        self.assertTrue(route["needs_external_research"])
        self.assertIn("external_research", route["matched_risk_triggers"])

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


if __name__ == "__main__":
    unittest.main()
