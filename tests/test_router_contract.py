from __future__ import annotations

import hashlib
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


def permit_json(task_text: str, tool_text: str, *, permit_id: str = "PERMIT-test") -> str:
    payload = {
        "schema": "cbh.r5_human_confirmation_permit.v1",
        "permit_id": permit_id,
        "status": "active",
        "scope": "single_event",
        "risk_level": "R5",
        "confirmed_by": "human",
        "confirmed_at_utc": "2026-06-25T00:00:00Z",
        "expires_at_utc": "2099-01-01T00:00:00Z",
        "task_sha256": hashlib.sha256(task_text.encode("utf-8")).hexdigest(),
        "tool_sha256": hashlib.sha256(tool_text.encode("utf-8")).hexdigest(),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


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
        "id": "TC-005a",
        "task": "将已有文件局部补丁规则同步进公开仓库",
        "risk": "R3",
        "gates": ["change_contract_gate"],
    },
    {
        "id": "TC-005d",
        "task": "准备发布，但提交推送不执行。先做结构读图和现有 diff 审计。",
        "risk": "R3",
        "gates": ["change_contract_gate"],
        "candidate_r5": "提交",
    },
    {
        "id": "TC-005b",
        "task": "接续上一段对话记忆，创建此对话新记忆文件并链接上一段对话记忆文件",
        "risk": "R3",
        "gates": ["conversation_link_gate"],
        "expect": {
            "memory_lane": "current_conversation",
            "conversation_memory_decision": "create_or_update_current_conversation",
            "link_intent": "continue_from_latest",
            "record_intent": "explicit_conversation_memory_request",
            "hybrid_retrieval_profile": "meta_first_hybrid_required",
            "memory_write_profile": "strict_capsule_required",
        },
        "expect_in": {
            "memory_mode": ["write", "update"],
        },
    },
    {
        "id": "TC-005c",
        "task": "为当前对话建立对话账本，链接 raw session JSONL、segments.jsonl、evidence_refs 和当前对话记忆",
        "risk": "R3",
        "expect": {
            "target_surface": "conversation_ledger",
            "hybrid_retrieval_profile": "meta_first_hybrid_enhancement",
            "memory_write_profile": "none",
        },
        "expect_contains": {
            "module_need": "conversation_ledger_index",
        },
    },
    {
        "id": "TC-005e",
        "task": "skill 调用周期结束后释放大正文并保留 skill release receipt，下次从恢复入口重新激活",
        "risk": "R3",
        "expect": {
            "target_surface": "skill_matrix",
            "skill_lifecycle_profile": "reactivate_from_receipt",
        },
        "expect_contains": {
            "module_need": "skill_matrix",
        },
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
    for field, expected in case.get("expect", {}).items():
        assert payload.get(field) == expected
    for field, expected_values in case.get("expect_in", {}).items():
        assert payload.get(field) in expected_values
    for field, expected_value in case.get("expect_contains", {}).items():
        assert contains(payload.get(field), expected_value)


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


def test_tool_proxy_allows_exact_single_event_confirmation_permit(tmp_path: Path) -> None:
    if not POWERSHELL:
        pytest.skip("PowerShell is not available on PATH")
    task_text = "commit changes"
    tool_text = "shell_command\ngit commit -am update"
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
            task_text,
            "-ToolName",
            "shell_command",
            "-ToolInputJson",
            '{"command":"git commit -am update"}',
            "-Cwd",
            str(ROOT),
            "-ConstitutionReviewed",
            "-HumanConfirmationPermitJson",
            permit_json(task_text, tool_text),
            "-HumanConfirmationPermitUseLedgerPath",
            str(tmp_path / "r5-permit-uses.jsonl"),
        ],
    )
    assert code == 0
    assert payload["status"] == "pass"
    assert payload["effective_human_confirmed"] is True
    assert payload["human_confirmation_permit"]["status"] == "pass"
    assert payload["human_confirmation_permit"]["consumed"] is True


def test_tool_proxy_blocks_replayed_single_event_confirmation_permit(tmp_path: Path) -> None:
    if not POWERSHELL:
        pytest.skip("PowerShell is not available on PATH")
    task_text = "commit changes"
    tool_text = "shell_command\ngit commit -am update"
    permit = permit_json(task_text, tool_text, permit_id="PERMIT-replay")
    ledger = tmp_path / "r5-permit-uses.jsonl"
    base_args = [
        POWERSHELL,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "skills/embedded-harness/harness_tool_proxy.ps1",
        "-Stage",
        "pre_tool",
        "-TaskText",
        task_text,
        "-ToolName",
        "shell_command",
        "-ToolInputJson",
        '{"command":"git commit -am update"}',
        "-Cwd",
        str(ROOT),
        "-ConstitutionReviewed",
        "-HumanConfirmationPermitJson",
        permit,
        "-HumanConfirmationPermitUseLedgerPath",
        str(ledger),
    ]
    code, payload = run_json(base_args)
    assert code == 0
    assert payload["human_confirmation_permit"]["status"] == "pass"
    assert payload["human_confirmation_permit"]["consumed"] is True

    code, payload = run_json(base_args, allowed_exit_codes={2})
    assert code == 2
    assert payload["status"] == "blocked"
    assert "permit_already_used" in payload["human_confirmation_permit"]["issues"]
    assert "tool_call_requires_human_confirmation" in payload["blocked_reasons"]


def test_tool_proxy_blocks_mismatched_single_event_confirmation_permit() -> None:
    if not POWERSHELL:
        pytest.skip("PowerShell is not available on PATH")
    task_text = "commit changes"
    wrong_tool_text = "shell_command\ngit push"
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
            task_text,
            "-ToolName",
            "shell_command",
            "-ToolInputJson",
            '{"command":"git commit -am update"}',
            "-Cwd",
            str(ROOT),
            "-ConstitutionReviewed",
            "-HumanConfirmationPermitJson",
            permit_json(task_text, wrong_tool_text, permit_id="PERMIT-wrong-tool"),
        ],
        allowed_exit_codes={2},
    )
    assert code == 2
    assert payload["status"] == "blocked"
    assert "tool_hash_mismatch" in payload["human_confirmation_permit"]["issues"]
    assert "tool_call_requires_human_confirmation" in payload["blocked_reasons"]


def test_router_requires_external_evidence_for_uncertain_design_discussion() -> None:
    payload = run_router("我们不确定这个机制有没有成熟方案，需要外部证据后再决定是否吸纳")
    assert payload["needs_external_research"] is True
    assert "external_research" in payload["matched_risk_triggers"]
    assert "external_research_gate" in payload["module_need"]
    assert "general_web_cross_check" in payload["external_need"] or "source_grounded_learning_intake" in payload["external_need"]


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
