from __future__ import annotations

import json
import os
import subprocess
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

    def test_router_detects_explicit_conversation_memory_request(self) -> None:
        route = intake_router("checkpoint this conversation so we can continue this conversation later", policy=self.policy)
        self.assertEqual(route["conversation_memory_decision"], "create_or_update_current_conversation")
        self.assertEqual(route["memory_lane"], "current_conversation")
        self.assertEqual(route["memory_mode"], "write")
        self.assertEqual(route["record_intent"], "explicit_conversation_memory_request")
        self.assertIn("conversation_memory_index", route["module_need"])

    def test_router_detects_conversation_checkpoint_candidate(self) -> None:
        route = intake_router("long conversation with open loops and context compression risk", policy=self.policy)
        self.assertEqual(route["conversation_memory_decision"], "checkpoint_candidate")
        self.assertEqual(route["memory_lane"], "current_conversation")
        self.assertEqual(route["record_intent"], "conversation_checkpoint")

    def test_router_does_not_create_conversation_memory_for_plain_chat(self) -> None:
        route = intake_router("explain why markdown is common", policy=self.policy)
        self.assertEqual(route["conversation_memory_decision"], "none")
        self.assertEqual(route["memory_lane"], "none")
        self.assertEqual(route["memory_mode"], "none")

    def test_router_projectization_takes_precedence_over_conversation_memory(self) -> None:
        route = intake_router("README VERSION CHANGELOG tests adapter repository release long conversation", policy=self.policy)
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
        with tempfile.TemporaryDirectory() as tmp:
            result = flush_logs(log_dir=tmp, events=[{"phase": "test", "status": "pass"}])
            log_path = Path(result["path"])
            self.assertEqual(log_path.name, "workbuddy_harness_events.jsonl")
            self.assertEqual(log_path.parent, Path(tmp))
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["written"], 1)
            self.assertTrue(log_path.exists())

    def test_flush_logs_sanitizes_lone_surrogates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = flush_logs(log_dir=tmp, events=[{"phase": "test", "text": "bad \udcac"}])
            log_path = Path(result["path"])
            content = log_path.read_text(encoding="utf-8")
            self.assertIn("<invalid-surrogate>", content)
            self.assertNotIn("\\udcac", content)

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

    def test_workbuddy_user_prompt_hook_stores_route_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_hook(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-a",
                    "cwd": tmp,
                    "prompt": "inspect files and summarize the repository",
                },
                "--stage",
                "user_prompt",
                log_dir=tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            hook_output = output["hookSpecificOutput"]
            self.assertEqual(hook_output["hookEventName"], "UserPromptSubmit")
            self.assertIn("Agent Memory Lane Harness route", hook_output["additionalContext"])
            state_path = Path(tmp) / "workbuddy_hook_state.json"
            self.assertTrue(state_path.exists())

    def test_workbuddy_user_prompt_hook_extracts_recording_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
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
            self.assertIn("risk=R5", context)
            state_path = Path(tmp) / "workbuddy_hook_state.json"
            state_text = state_path.read_text(encoding="utf-8")
            self.assertIn("delete stale files after review", state_text)

    def test_workbuddy_user_prompt_hook_sanitizes_lone_surrogate_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
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
        with tempfile.TemporaryDirectory() as tmp:
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

    def test_workbuddy_pre_tool_hook_does_not_block_write_content_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
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
        with tempfile.TemporaryDirectory() as tmp:
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

    def test_workbuddy_stop_hook_blocks_final_strong_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
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
        with tempfile.TemporaryDirectory() as tmp:
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
