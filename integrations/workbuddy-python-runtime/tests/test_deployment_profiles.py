from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ADAPTER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ADAPTER_ROOT.parents[1]
sys.path.insert(0, str(ADAPTER_ROOT))

from workbuddy_harness import (  # noqa: E402
    build_agent_loop_contract,
    intake_router,
    load_policy,
    validate_agent_loop_receipt,
)
from workbuddy_harness.hook_runner import _context_output  # noqa: E402


def load_bundle_module():
    path = ADAPTER_ROOT / "scripts" / "build-deployment-bundle.py"
    spec = importlib.util.spec_from_file_location("cbh_build_deployment_bundle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load deployment bundle builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeploymentProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy()
        cls.bundle = load_bundle_module()

    def test_minimal_profiles_resolve_existing_runtime_files_only(self) -> None:
        for profile_id in ("workbuddy-hook-minimal", "workbuddy-loop-integration-sdk", "codex-local-minimal"):
            with self.subTest(profile_id=profile_id):
                _, files = self.bundle.selected_files(profile_id)
                self.assertTrue(files)
                self.assertFalse(any(path.startswith("docs/") for path in files))
                self.assertFalse(any("/tests/" in f"/{path}/" for path in files))
                self.assertFalse(any(path.lower().endswith((".pdf", ".pptx", ".docx")) for path in files))
                for path in files:
                    self.assertTrue((REPO_ROOT / path).is_file(), path)

    def test_staged_bundle_writes_exact_receipt_without_full_repo(self) -> None:
        temp_root = ADAPTER_ROOT / ".test-tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="deployment-", dir=temp_root))
        try:
            receipt = self.bundle.stage("workbuddy-hook-minimal", output)
            stored = json.loads((output / "cbh-deployment-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(stored, receipt)
            self.assertFalse(receipt["full_repository_copy"])
            self.assertFalse((output / "docs").exists())
            self.assertFalse((output / "tests").exists())
            self.assertTrue((output / "integrations/workbuddy-python-runtime/workbuddy_harness/hook_runner.py").is_file())
        finally:
            shutil.rmtree(output, ignore_errors=True)
            try:
                temp_root.rmdir()
            except OSError:
                pass

    def test_agent_loop_contract_exposes_unconsumed_route_actions(self) -> None:
        route = intake_router(
            "查找最新官方资料，更新当前对话记忆，并审计技能安全和可合并项",
            cwd=str(ADAPTER_ROOT),
            policy=self.policy,
        )
        contract = build_agent_loop_contract(route)
        self.assertTrue(contract["host_loop_required"])
        self.assertEqual(contract["consumer_status"], "unbound_until_host_loop_calls_consumer")
        self.assertIn("external_research", contract["action_ids"])
        self.assertIn("memory_operation", contract["action_ids"])
        self.assertIn("skill_audit", contract["action_ids"])
        output = _context_output(route)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("loop_consumer=required", context)
        self.assertIn("loop_actions=", context)

    def test_agent_loop_receipt_must_cover_every_action(self) -> None:
        contract = {
            "schema": "cbh.workbuddy_agent_loop_contract.v1",
            "action_ids": ["memory_operation", "external_research"],
        }
        incomplete = validate_agent_loop_receipt(
            contract,
            {"actions": [{"action_id": "memory_operation", "status": "completed"}]},
        )
        self.assertEqual(incomplete["status"], "incomplete")
        self.assertEqual(incomplete["missing_action_ids"], ["external_research"])
        complete = validate_agent_loop_receipt(
            contract,
            {
                "actions": [
                    {"action_id": "memory_operation", "status": "completed"},
                    {"action_id": "external_research", "status": "not_applicable_with_reason"},
                ]
            },
        )
        self.assertEqual(complete["status"], "complete")


if __name__ == "__main__":
    unittest.main()
