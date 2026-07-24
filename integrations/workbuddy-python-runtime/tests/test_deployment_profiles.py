from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
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
from workbuddy_harness.hook_runner import handle_user_prompt_event  # noqa: E402


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
                profile, files = self.bundle.selected_files(profile_id)
                self.assertEqual(
                    "docs/agent-deployment-map.md",
                    profile["required_predeployment_read"],
                )
                self.assertTrue((REPO_ROOT / profile["required_predeployment_read"]).is_file())
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
            self.assertEqual("docs/agent-deployment-map.md", receipt["required_predeployment_read"])
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

    def test_workbuddy_minimal_profile_is_nonblocking_and_stateless(self) -> None:
        profile_path = ADAPTER_ROOT / "deployment-profiles.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))["profiles"]["workbuddy-hook-minimal"]
        self.assertEqual(
            "advisory_route_plus_nonblocking_correction",
            profile["runtime_mode"],
        )
        self.assertFalse(profile["host_blocking"])
        self.assertFalse(profile["stateful_authorization"])
        self.assertEqual(["UserPromptSubmit"], profile["registered_hooks"])
        self.assertEqual(["PreToolUse"], profile["optional_hooks"])
        self.assertEqual("manual_after_host_protocol_verification", profile["pretool_activation"])
        self.assertNotIn("Stop", profile["registered_hooks"])
        self.assertEqual(
            "advisory_by_default_optional_codex_allow_updated_input",
            profile["output_contract"],
        )

    def test_staged_bundle_explicit_pretool_protocol_rewrites_real_foreach_regression(self) -> None:
        temp_root = ADAPTER_ROOT / ".test-tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="deployment-runtime-", dir=temp_root))
        try:
            self.bundle.stage("workbuddy-hook-minimal", output)
            adapter = output / "integrations" / "workbuddy-python-runtime"
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "PowerShell",
                "cwd": str(output),
                "tool_input": {
                    "command": "foreach ($error in $errors) { $error.ErrorId } | Sort-Object -Unique",
                    "timeout": 20,
                },
            }
            env = dict(os.environ)
            env["PYTHONPATH"] = str(adapter)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "workbuddy_harness.hook_runner",
                    "--stage",
                    "pre_tool",
                    "--executor-environment",
                    "powershell",
                    "--rewrite-protocol",
                    "codex_allow_updated_input",
                ],
                cwd=adapter,
                env=env,
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                encoding="utf-8",
                errors="strict",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            result = json.loads(completed.stdout)
            hook = result["hookSpecificOutput"]
            self.assertEqual("allow", hook["permissionDecision"])
            self.assertIn("$(foreach", hook["updatedInput"]["command"])
            self.assertEqual(20, hook["updatedInput"]["timeout"])
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
        output = handle_user_prompt_event(
            {
                "hook_event_name": "UserPromptSubmit",
                "prompt": "查找最新官方资料，更新当前对话记忆，并审计技能安全和可合并项",
            },
            policy=self.policy,
            cwd=str(ADAPTER_ROOT),
        )
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn('"agent_loop_action_ids"', context)
        self.assertIn('"task_execution_owner":"host_model_agent"', context)

    def test_workbuddy_routes_active_lane_context_to_the_model_agent_loop(self) -> None:
        temp_root = ADAPTER_ROOT / ".test-tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix="memory-route-", dir=temp_root))
        try:
            lane = workspace / "local-conversation-memory" / "active-lane"
            lane.mkdir(parents=True)
            (lane / "_META_INDEX.md").write_text(
                "# Current Conversation\n\nlane_state: ACTIVE\n",
                encoding="utf-8",
            )
            (lane / "index.json").write_text(
                json.dumps({"lane_state": "ACTIVE", "record_families": {}}, ensure_ascii=False),
                encoding="utf-8",
            )
            route = intake_router(
                "关于我们的记忆机制中的检索机制，确认它能在复合任务中实际触发。",
                cwd=str(workspace),
                policy=self.policy,
            )
            self.assertEqual(route["memory_source_hints"][0]["lane"], "current_conversation")
            self.assertIn("retrieve_matching_memory", route["action_binding_ids"])

            contract = build_agent_loop_contract(route)
            self.assertEqual(contract["task_execution_owner"], "host_model_agent")
            self.assertIn("memory_context_retrieval", contract["action_ids"])
            action = next(
                item for item in contract["actions"] if item["action_id"] == "memory_context_retrieval"
            )
            self.assertEqual(action["value"]["result_target"], "model_agent_additional_context")
            self.assertEqual(action["value"]["source_hints"][0]["lane"], "current_conversation")
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
            try:
                temp_root.rmdir()
            except OSError:
                pass

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
