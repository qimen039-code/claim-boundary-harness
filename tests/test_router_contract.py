from __future__ import annotations

import hashlib
import os
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def run_json(args: list[str], *, allowed_exit_codes: set[int] | None = None, env: dict[str, str] | None = None) -> tuple[int, dict]:
    allowed = allowed_exit_codes or {0}
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
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


def run_router_with_cwd(task: str, cwd: Path, *, env: dict[str, str] | None = None) -> dict:
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
            str(cwd),
        ],
        env=env,
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
        "id": "TC-004d",
        "task": "只读检查 Example Project Memory Bank 已更新和长期记忆状态，不写入记忆",
        "not_risk": "R5",
        "context_surface": "documentation_or_discussion",
        "candidate_r5": "长期记忆",
    },
    {
        "id": "TC-004e",
        "task": "fix README wording, then commit and push",
        "risk": "R5",
        "context_surface": "actionable_R5",
        "promote_r5": True,
    },
    {
        "id": "TC-004f",
        "task": "修复 README 后进行提交推送",
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
    {
        "id": "TC-008a",
        "task": "self-check README/docs wording for similar boundary errors",
        "risk": "R1",
        "gates": ["read_only_context_gate"],
    },
    {
        "id": "TC-008b",
        "task": "self-check README/docs wording for similar boundary errors; if a fix is needed, update README",
        "risk": "R3",
        "gates": ["change_contract_gate", "scope_reassessment_gate"],
    },
    {
        "id": "TC-009",
        "task": "从 6 月 15 日以来整体上是否一直更稳定",
        "gates": ["observation_scope_gate"],
        "expect_contains": {
            "semantic_ambiguity": "observation_scope_required",
        },
    },
    {
        "id": "TC-009a",
        "task": "为这个同类错误加入记忆-预测-验证-校准反馈闭环，观察下次是否复发",
        "gates": ["feedback_loop_gate"],
        "expect": {
            "memory_need": "index_only",
            "feedback_loop_profile": "explicit_cycle",
        },
        "expect_contains": {
            "semantic_ambiguity": "feedback_loop_required",
            "module_need": "memory_meta_index",
        },
    },
    {
        "id": "TC-009b",
        "task": "查看 ERR-2026-06-29-01 / SOL-2026-06-29-01 这个同类错误的解决记录",
        "gates": ["feedback_loop_gate"],
        "expect": {
            "memory_need": "paired_err_sol",
            "feedback_loop_profile": "prevention_review",
        },
        "expect_contains": {
            "semantic_ambiguity": "feedback_loop_required",
            "module_need": "memory_meta_index",
        },
        "expect_trigger_contains": {
            "feedback_loop_memory": "解决记录",
        },
    },
    {
        "id": "TC-009c",
        "task": "查看 common error 记录并按里面的预防规则继续排查",
        "gates": ["feedback_loop_gate"],
        "expect": {
            "memory_need": "common_error_corpus",
            "memory_mode": "read",
            "record_intent": "no_record",
            "feedback_loop_profile": "prevention_review",
        },
        "expect_contains": {
            "semantic_ambiguity": "feedback_loop_required",
            "module_need": "memory_meta_index",
        },
        "expect_trigger_contains": {
            "feedback_loop_common_error": "common error",
        },
    },
    {
        "id": "TC-009d",
        "task": "record this error as a common error after the fix is verified",
        "not_gates": ["feedback_loop_gate"],
        "expect": {
            "memory_need": "common_error_corpus",
            "memory_mode": "write",
            "record_intent": "inferred_reusable_error",
            "feedback_loop_profile": "record_candidate",
        },
        "expect_contains": {
            "module_need": "memory_meta_index",
        },
        "expect_trigger_contains": {
            "common_error_candidate": "common error",
        },
    },
    {
        "id": "TC-009e",
        "task": "查看 common error 记录",
        "not_gates": ["feedback_loop_gate"],
        "expect": {
            "memory_need": "common_error_corpus",
            "memory_mode": "read",
            "record_intent": "no_record",
            "feedback_loop_profile": "index_hint",
        },
        "expect_contains": {
            "module_need": "memory_meta_index",
        },
        "expect_trigger_contains": {
            "common_error_index_hint": "common error",
        },
    },
    {
        "id": "TC-009f",
        "task": "自检后发现当前项目有大量记忆污染、目标污染、脏树债和技术债，先清查分组，清理必须清理项，并把可暂存内容标记为候选技术债",
        "risk": "R3",
        "gates": ["debt_hygiene_gate"],
        "expect_contains": {
            "semantic_ambiguity": "debt_hygiene_required",
            "module_need": "debt_hygiene_gate",
        },
        "expect_trigger_contains": {
            "debt_hygiene": "技术债",
        },
    },
    {
        "id": "TC-009g",
        "task": "Release text includes DOI, version marker, commit hash, path, client support status, deployment status, and memory lane id; preserve exact anchors.",
        "gates": ["exact_anchor_preservation_gate"],
        "expect_trigger_contains": {
            "exact_anchor_preservation_gate": "DOI",
        },
    },
    {
        "id": "TC-009h",
        "task": "Build a current status table from these unverified local notes and latest status fields.",
        "gates": ["current_status_table_evidence_gate"],
        "expect_trigger_contains": {
            "current_status_table_evidence_gate": "current status table",
        },
    },
    {
        "id": "TC-009i",
        "task": "我不记得之前说过的旧的存储点叫什么来着",
        "gates": ["unknown_memory_reference_gate"],
        "expect": {
            "memory_need": "index_only",
            "memory_mode": "read",
        },
        "expect_contains": {
            "module_need": "memory_meta_index",
        },
        "expect_trigger_contains": {
            "unknown_memory_reference_gate": "叫什么来着",
        },
    },
    {
        "id": "TC-009j",
        "task": "Judge whether this answer is hallucinated, unsupported, incomplete, or a non-answer.",
        "gates": ["hallucination_detection_anchor_gate"],
        "expect_trigger_contains": {
            "hallucination_detection_anchor_gate": "non-answer",
        },
    },
    {
        "id": "TC-009k",
        "task": "Review the public README and release note for private leakage or local-only trace before publishing.",
        "gates": ["public_private_surface_gate"],
        "expect_trigger_contains": {
            "public_private_surface_gate": "public README",
        },
    },
    {
        "id": "TC-009l",
        "task": "I already checked and verified this; explain the prior action from command log or tool log evidence.",
        "gates": ["self_report_log_grounding_gate"],
        "expect_trigger_contains": {
            "self_report_log_grounding_gate": "already checked",
        },
    },
    {
        "id": "TC-009m",
        "task": "This is not blame; find the root cause, cleanup plan, and prevent recurrence.",
        "gates": ["root_cause_cleanup_gate"],
        "expect_trigger_contains": {
            "root_cause_cleanup_gate": "root cause",
        },
    },
    {
        "id": "TC-009n",
        "task": "The packet mentions Project A; should we backfill memory or is this lane pollution?",
        "gates": ["lane_ownership_gate"],
        "expect_trigger_contains": {
            "lane_ownership_gate": "backfill memory",
        },
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
    for gate in case.get("not_gates", []):
        assert not contains(payload.get("required_gates"), gate)
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
    for trigger_key, expected_value in case.get("expect_trigger_contains", {}).items():
        assert contains(payload.get("matched_risk_triggers", {}).get(trigger_key), expected_value)


def test_router_uses_local_project_lane_overlay(tmp_path: Path) -> None:
    project = tmp_path / "AI_Lead_Radar"
    memory_bank = project / "memory-bank"
    memory_bank.mkdir(parents=True)
    overlay = tmp_path / "project_lanes.local.json"
    overlay.write_text(
        json.dumps(
            {
                "schema": "cbh.project_lane_overlay.v1",
                "project_lanes": {"AI_Lead_Radar": [str(project)]},
                "memory_roots": {"AI_Lead_Radar": [str(memory_bank)]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["CBH_PROJECT_LANES_FILE"] = str(overlay)

    payload = run_router_with_cwd("只读检查 Memory Bank 已更新和长期记忆状态", project, env=env)

    assert payload["project_lane"] == "AI_Lead_Radar"
    assert payload["memory_lane"] == "current_project"
    assert payload["risk_level"] != "R5"


def test_router_marks_project_long_term_memory_write_as_write_mode(tmp_path: Path) -> None:
    project = tmp_path / "AI_Lead_Radar"
    memory_bank = project / "memory-bank"
    memory_bank.mkdir(parents=True)
    overlay = tmp_path / "project_lanes.local.json"
    overlay.write_text(
        json.dumps(
            {
                "schema": "cbh.project_lane_overlay.v1",
                "project_lanes": {"AI_Lead_Radar": [str(project)]},
                "memory_roots": {"AI_Lead_Radar": [str(memory_bank)]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["CBH_PROJECT_LANES_FILE"] = str(overlay)

    payload = run_router_with_cwd("写入记忆：记录这个长期记忆修复", project, env=env)

    assert payload["project_lane"] == "AI_Lead_Radar"
    assert payload["risk_level"] == "R5"
    assert payload["memory_lane"] == "current_project"
    assert payload["memory_mode"] == "write"
    assert payload["record_intent"] == "explicit_user_request"


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


def test_router_records_route_issue_and_requires_external_evidence_for_linked_current_mechanism() -> None:
    payload = run_router("路由问题，进行记录，改进：用户给了外链且涉及 Claude 现势机制和第三方 XTrace 口径，不能当官方事实")
    assert payload["risk_level"] == "R4"
    assert payload["record_intent"] == "inferred_reusable_error"
    assert payload["memory_need"] == "common_error_corpus"
    assert payload["memory_mode"] == "write"
    assert payload["memory_lane"] == "common_error_corpus"
    assert payload["conversation_memory_decision"] == "none"
    assert payload["feedback_loop_profile"] == "record_candidate"
    assert payload["needs_external_research"] is True
    assert "external_research" in payload["matched_risk_triggers"]
    assert "common_error_candidate" in payload["matched_risk_triggers"]
    assert "external_research_gate" in payload["module_need"]
    assert "feedback_loop_gate" not in payload["required_gates"]
    assert "official_authority_source_search" in payload["external_need"]
    assert "general_web_cross_check" in payload["external_need"]
    assert "source_grounded_learning_intake" in payload["external_need"]


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


def test_powershell_claim_schema_blocks_causal_attribution_overclaim() -> None:
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
            "-FinalText",
            "CBH solved hallucination drift for all agents.",
        ],
        allowed_exit_codes={2},
    )
    assert code == 2
    assert "causal_attribution_boundary_required:abstract_system_causal_global_effect" in payload["issues"]


def test_powershell_claim_schema_allows_scoped_causal_hypothesis() -> None:
    if not POWERSHELL:
        pytest.skip("PowerShell is not available on PATH")
    _, payload = run_json(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "skills/embedded-harness/harness_claim_schema_verifier.ps1",
            "-FinalText",
            "In this local sample, this is a causal_hypothesis, not proof: memory anchors may have reduced this task's drift.",
        ]
    )
    assert payload["status"] == "pass"


def test_powershell_claim_schema_scope_limiter_is_sentence_local() -> None:
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
            "-FinalText",
            "In this local sample, this is a causal_hypothesis, not proof. CBH solved hallucination drift for all agents.",
        ],
        allowed_exit_codes={2},
    )
    assert code == 2
    assert "causal_attribution_boundary_required:abstract_system_causal_global_effect" in payload["issues"]


def test_cbh_doctor_runs_without_failures() -> None:
    code, payload = run_json(
        [sys.executable, "tools/cbh_doctor.py", "--repo-root", ".", "--json"],
        allowed_exit_codes={0},
    )
    assert code == 0
    assert payload["status"] in {"pass", "warn"}
    failed = [check for check in payload["checks"] if check["status"] == "fail"]
    assert failed == []
