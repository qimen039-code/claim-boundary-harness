from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def run_json(args: list[str], *, allowed_exit_codes: set[int] | None = None) -> tuple[int, dict]:
    allowed = allowed_exit_codes or {0}
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode not in allowed:
        raise AssertionError(
            f"unexpected exit {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    try:
        return result.returncode, json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"invalid JSON output:\n{result.stdout}\nstderr:\n{result.stderr}") from exc


def run_router(task: str) -> dict:
    if not POWERSHELL:
        pytest.skip("PowerShell is not available on PATH")
    _, payload = run_json(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "skills/embedded-harness/harness_intake_router.ps1",
            "-TaskText",
            task,
            "-Cwd",
            str(ROOT / "path with spaces" / "project"),
        ]
    )
    return payload


def contains(items, expected: str) -> bool:
    return expected in list(items or [])


ROUTER_CASES = [
    {
        "id": "TC-002",
        "task": "fix the script and run benchmark",
        "risk": "R4",
        "triggered": ["R4", "R3"],
        "gates": ["verification_gate", "claim_gate"],
    },
    {
        "id": "TC-003",
        "task": "delete this folder",
        "risk": "R5",
        "context_surface": "actionable_R5",
        "promote_r5": True,
    },
    {
        "id": "TC-004",
        "task": "do not delete anything",
        "not_risk": "R5",
        "negated_r5": "delete",
    },
    {
        "id": "TC-004a",
        "task": "trigger list contains commit push 删除 提交, docs discussion only, no npm/pip distribution",
        "not_risk": "R5",
        "context_surface": "documentation_or_discussion",
        "candidate_r5": "commit",
    },
    {
        "id": "TC-004b",
        "task": "提交报告",
        "not_risk": "R5",
        "context_surface": "documentation_or_discussion",
        "candidate_r5": "提交",
    },
    {
        "id": "TC-004c",
        "task": "删除旧 release",
        "risk": "R5",
        "context_surface": "actionable_R5",
        "promote_r5": True,
    },
    {
        "id": "TC-005",
        "task": "read this report and update public docs/tests from it",
        "risk": "R3",
        "gates": ["change_contract_gate", "scope_reassessment_gate"],
    },
    {
        "id": "TC-006",
        "task": "check whether this feature exists, then implement it if missing",
        "risk": "R3",
        "gates": ["change_contract_gate"],
    },
    {
        "id": "TC-008",
        "task": "review whether this feature is complete and identify unfinished public or local work",
        "risk": "R1",
        "gates": ["read_only_context_gate", "scope_reassessment_gate"],
    },
]


@pytest.mark.parametrize("case", ROUTER_CASES, ids=[case["id"] for case in ROUTER_CASES])
def test_router_contract_cases(case: dict) -> None:
    payload = run_router(case["task"])
    if "risk" in case:
        assert payload["risk_level"] == case["risk"]
    if "not_risk" in case:
        assert payload["risk_level"] != case["not_risk"]
    for risk in case.get("triggered", []):
        assert contains(payload.get("triggered_risks"), risk)
    for gate in case.get("gates", []):
        assert contains(payload.get("required_gates"), gate)
    if "negated_r5" in case:
        assert contains(payload.get("negated_risk_triggers", {}).get("R5"), case["negated_r5"])
    if "candidate_r5" in case:
        assert contains(payload.get("risk_candidates", {}).get("R5"), case["candidate_r5"])
    if "context_surface" in case:
        assert payload.get("risk_context_decisions", {}).get("R5", {}).get("action_surface") == case["context_surface"]
    if "promote_r5" in case:
        assert bool(payload.get("risk_context_decisions", {}).get("R5", {}).get("promote_to_risk")) is case["promote_r5"]


def test_tool_proxy_blocks_high_risk_command() -> None:
    if not POWERSHELL:
        pytest.skip("PowerShell is not available on PATH")
    code, payload = run_json(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "skills/embedded-harness/harness_tool_proxy.ps1",
            "-Stage",
            "pre_tool",
            "-TaskText",
            "commit changes",
            "-ToolName",
            "shell_command",
            "-ToolInputJson",
            '{"command":"git commit -am update"}',
            "-Cwd",
            str(ROOT),
            "-ConstitutionReviewed",
        ],
        allowed_exit_codes={2},
    )
    assert code == 2
    assert payload["status"] == "blocked"
    assert "tool_call_requires_human_confirmation" in payload["blocked_reasons"]


def test_powershell_router_rejects_sibling_project_prefix() -> None:
    if not POWERSHELL:
        pytest.skip("PowerShell is not available on PATH")
    _, payload = run_json(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "skills/embedded-harness/harness_intake_router.ps1",
            "-TaskText",
            "inspect project files",
            "-Cwd",
            r"C:\path\to\project-evil",
        ]
    )
    assert payload["project_lane"] == "PROJECTLESS"


def test_powershell_runtime_preserves_original_task_text_and_risk_override() -> None:
    if not POWERSHELL:
        pytest.skip("PowerShell is not available on PATH")
    code, payload = run_json(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "skills/embedded-harness/harness_runtime_enforcer.ps1",
            "-Stage",
            "pre_tool",
            "-TaskText",
            "R5",
            "-OriginalTaskText",
            "delete stale files after review",
            "-ToolName",
            "shell_command",
            "-ToolInputJson",
            '{"command":"echo ok"}',
            "-Cwd",
            str(ROOT),
            "-ConstitutionReviewed",
        ],
        allowed_exit_codes={2},
    )
    assert code == 2
    assert payload["route"]["risk_level"] == "R5"
    assert payload["task_text_for_route"] == "delete stale files after review"
    assert "human_confirmation_required_for_R5" in payload["blocked_reasons"]


def test_powershell_runtime_ignores_non_command_tool_content_for_hard_patterns() -> None:
    if not POWERSHELL:
        pytest.skip("PowerShell is not available on PATH")
    _, payload = run_json(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "skills/embedded-harness/harness_runtime_enforcer.ps1",
            "-Stage",
            "pre_tool",
            "-TaskText",
            "inspect repository docs",
            "-ToolName",
            "Write",
            "-ToolInputJson",
            '{"file_path":"notes.md","content":"Document delete, permission, and rm -rf as examples only."}',
            "-Cwd",
            str(ROOT),
            "-ConstitutionReviewed",
        ]
    )
    assert payload["status"] == "pass"
    assert payload["tool_hard_hits"] == []


def test_powershell_claim_schema_requires_ref_and_strong_evidence() -> None:
    if not POWERSHELL:
        pytest.skip("PowerShell is not available on PATH")
    code, payload = run_json(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "skills/embedded-harness/harness_claim_schema_verifier.ps1",
            "-ClaimJson",
            '{"claim_type":"architecture_decision","source_type":"local_file","evidence_boundary":"whiteboard_smoke"}',
        ],
        allowed_exit_codes={2},
    )
    assert code == 2
    assert "missing_source_ref_for_local_file" in payload["issues"]

    code, payload = run_json(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "skills/embedded-harness/harness_claim_schema_verifier.ps1",
            "-ClaimJson",
            '{"claim_type":"architecture_decision","source_type":"local_file","source_ref":"README.md","evidence_boundary":"whiteboard_smoke"}',
            "-FinalText",
            "This result is validated.",
        ],
        allowed_exit_codes={2},
    )
    assert code == 2
    assert any(issue.startswith("insufficient_evidence_boundary_for_strong_phrase") for issue in payload["issues"])


def test_cbh_doctor_runs_without_failures() -> None:
    code, payload = run_json(
        [sys.executable, "tools/cbh_doctor.py", "--repo-root", ".", "--json"],
        allowed_exit_codes={0},
    )
    assert code == 0
    assert payload["status"] in {"pass", "warn"}
    failed = [check for check in payload["checks"] if check["status"] == "fail"]
    assert failed == []
