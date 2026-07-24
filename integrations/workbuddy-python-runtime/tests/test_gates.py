from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import workbuddy_harness.hook_runner as hook_runner  # noqa: E402
from workbuddy_harness import (  # noqa: E402
    build_agent_loop_contract,
    claim_schema_verifier,
    intake_router,
    load_policy,
    memory_isolation_gate,
    validate_agent_loop_receipt,
)


class AdvisoryRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy()
        cls.neutral_cwd = ROOT / ".test-cwd"
        cls.neutral_cwd.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.neutral_cwd, ignore_errors=True)

    def test_r5_route_remains_advisory_context(self) -> None:
        route = intake_router(
            "delete stale build files after review",
            cwd=str(self.neutral_cwd),
            policy=self.policy,
        )

        self.assertEqual("R5", route["risk_level"])
        self.assertTrue(route["compact_receipt"]["human_confirmation_need"])
        self.assertNotIn("blocked_reasons", route)

    def test_user_prompt_context_keeps_model_agent_ownership(self) -> None:
        output = hook_runner.handle_user_prompt_event(
            {
                "hook_event_name": "UserPromptSubmit",
                "cwd": str(self.neutral_cwd),
                "prompt": "delete stale build files after review",
            },
            policy=self.policy,
        )

        self.assertTrue(output["continue"])
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn('"host_blocking":false', context)
        self.assertIn('"task_execution_owner":"host_model_agent"', context)

    def test_pretool_without_verified_environment_is_silent(self) -> None:
        output = hook_runner.handle_pretool_event(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "cwd": str(self.neutral_cwd),
                "tool_input": {"command": "rm -rf build"},
            }
        )
        self.assertEqual({}, output)

    def test_pretool_parser_failure_is_silent_noop(self) -> None:
        def broken_parser(_: str) -> list[str] | None:
            raise RuntimeError("parser unavailable")

        output = hook_runner.handle_pretool_event(
            {
                "hook_event_name": "PreToolUse",
                "executor_environment": "powershell",
                "tool_name": "Bash",
                "cwd": str(self.neutral_cwd),
                "tool_input": {
                    "command": "foreach ($error in $errors) { $error.ErrorId } | Sort-Object -Unique"
                },
            },
            parser=broken_parser,
        )
        self.assertEqual({}, output)

    def test_stop_stage_is_unregistered_silent_noop(self) -> None:
        stdin = io.StringIO(
            json.dumps(
                {
                    "hook_event_name": "Stop",
                    "cwd": str(self.neutral_cwd),
                    "final_text": "done",
                }
            )
        )
        stdout = io.StringIO()
        original_stdin = sys.stdin
        try:
            sys.stdin = stdin
            with redirect_stdout(stdout):
                code = hook_runner.main(["--stage", "final"])
        finally:
            sys.stdin = original_stdin

        self.assertEqual(0, code)
        self.assertEqual("", stdout.getvalue())

    def test_invalid_input_is_silent_noop(self) -> None:
        stdin = io.StringIO("{not-json")
        stdout = io.StringIO()
        original_stdin = sys.stdin
        try:
            sys.stdin = stdin
            with redirect_stdout(stdout):
                code = hook_runner.main(["--stage", "pre_tool"])
        finally:
            sys.stdin = original_stdin

        self.assertEqual(0, code)
        self.assertEqual("", stdout.getvalue())

    def test_memory_isolation_receipt_does_not_execute_reads(self) -> None:
        allowed = str(self.neutral_cwd / "memory")
        policy = dict(self.policy)
        policy["memory_roots"] = {"EXAMPLE": [allowed]}
        inside = memory_isolation_gate(
            "EXAMPLE",
            str(Path(allowed) / "record.md"),
            policy=policy,
        )
        outside = memory_isolation_gate(
            "EXAMPLE",
            str(self.neutral_cwd / "other" / "record.md"),
            policy=policy,
        )

        self.assertEqual("pass", inside["status"])
        self.assertEqual("blocked", outside["status"])
        self.assertEqual("memory_isolation_gate", outside["phase"])

    def test_claim_schema_verifier_is_an_advisory_receipt(self) -> None:
        receipt = claim_schema_verifier(
            claim_json={
                "claim_type": "local_test_result",
                "source_type": "local_test",
                "source_ref": "integrations/workbuddy-python-runtime/tests/test_gates.py",
                "evidence_boundary": "local_regression_passed",
            },
            final_text="Local test passed; remote CI was not checked.",
            policy=self.policy,
        )
        self.assertEqual("pass", receipt["status"])

    def test_agent_loop_contract_requires_host_owned_consumption(self) -> None:
        route = {
            "memory_need": "index_only",
            "memory_mode": "read",
            "memory_lane": "current_conversation",
            "external_need": ["official_authority_source_search"],
        }
        contract = build_agent_loop_contract(route)

        self.assertEqual("host_model_agent", contract["task_execution_owner"])
        self.assertTrue(contract["host_loop_required"])
        incomplete = validate_agent_loop_receipt(contract, {"actions": []})
        self.assertEqual("incomplete", incomplete["status"])

    def test_json_output_preserves_readable_unicode(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            hook_runner._write_output({"text": "中文调试"})
        self.assertIn("中文调试", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
