from __future__ import annotations

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
        "id": "TC-005f",
        "task": "对我们的 skill 进行安全漏洞、隐藏风险、冗余和可合并内容审计",
        "risk": "R3",
        "gates": ["change_contract_gate"],
        "expect": {
            "target_surface": "skill_matrix",
        },
        "expect_contains": {
            "module_need": "skill_matrix",
        },
    },
    {
        "id": "TC-005g",
        "task": "audit skills for security hidden risks token bloat redundancy and merge candidates",
        "risk": "R3",
        "gates": ["change_contract_gate"],
        "expect": {
            "target_surface": "skill_matrix",
        },
        "expect_contains": {
            "module_need": "skill_matrix",
        },
    },
    {
        "id": "TC-005g-zh-combined",
        "task": "审计当前安装技能是否存在隐藏安全风险、重复功能和可合并项",
        "risk": "R3",
        "gates": ["skill_audit_gate", "change_contract_gate", "first_principles_gate"],
        "expect": {
            "target_surface": "skill_matrix",
            "skill_audit_profile": "safety_and_redundancy_audit",
            "first_principles_profile": "constraint_gate",
        },
        "expect_contains": {
            "module_need": "skill_matrix",
        },
    },
    {
        "id": "TC-005g-zh-safety-paraphrase",
        "task": "检查这些技能有没有偷偷联网、越权读写或相互覆盖",
        "gates": ["skill_audit_gate", "change_contract_gate"],
        "expect": {
            "target_surface": "skill_matrix",
            "skill_audit_profile": "safety_audit",
        },
        "expect_in": {
            "risk_level": ["R3", "R4", "R5"],
        },
    },
    {
        "id": "TC-005g-zh-redundancy-paraphrase",
        "task": "把功能重叠且长期未用的能力模块整理一下，看看哪些该合并",
        "risk": "R3",
        "gates": ["skill_audit_gate", "change_contract_gate"],
        "expect": {
            "target_surface": "skill_matrix",
            "skill_audit_profile": "redundancy_audit",
        },
    },
    {
        "id": "TC-005g-non-skill-negative",
        "task": "审计这个 Python 文件的安全问题",
        "not_gates": ["skill_audit_gate"],
        "expect": {
            "skill_audit_profile": "none",
        },
    },
    {
        "id": "TC-005g-first-principles-constraint",
        "task": "修改全局路由器的记忆写入策略",
        "gates": ["first_principles_gate"],
        "expect": {
            "first_principles_profile": "constraint_gate",
        },
    },
    {
        "id": "TC-005g-first-principles-full-design",
        "task": "设计一个新的跨客户端权限机制",
        "gates": ["first_principles_gate"],
        "expect": {
            "first_principles_profile": "full_design",
        },
    },
    {
        "id": "TC-005g-first-principles-recurrence",
        "task": "修复这个重复出现的数据一致性 bug",
        "gates": ["first_principles_gate"],
        "expect": {
            "first_principles_profile": "constraint_gate",
        },
    },
    {
        "id": "TC-005g-first-principles-typo-negative",
        "task": "修正文档里的一个错别字",
        "not_gates": ["first_principles_gate"],
        "expect": {
            "first_principles_profile": "none",
        },
    },
    {
        "id": "TC-005g-first-principles-version-negative",
        "task": "同步版本号",
        "not_gates": ["first_principles_gate"],
        "expect": {
            "first_principles_profile": "none",
        },
    },
    {
        "id": "TC-005h",
        "task": "查找 GitHub 上 Yuan1z0825/nature-skills 仓库并读取 SKILL.md",
        "risk": "R4",
        "gates": ["tool_surface_discovery_gate"],
        "expect": {
            "tool_surface_need": "plugin_mcp",
            "tool_discovery_status": "not_checked",
            "plugin_need": "candidate_discovery_required",
            "preferred_call_surface": "plugin_or_connector",
        },
        "expect_contains": {
            "module_need": "tool_surface_discovery",
        },
    },
    {
        "id": "TC-005i",
        "task": "[@github] 读取某个仓库的 release 和 Actions 日志",
        "gates": ["tool_surface_discovery_gate"],
        "expect": {
            "tool_discovery_status": "user_named",
            "plugin_need": "user_named",
            "preferred_call_surface": "plugin_or_connector",
        },
        "expect_contains": {
            "module_need": "tool_surface_discovery",
        },
    },
    {
        "id": "TC-005j",
        "task": "帮我分析这个 PDF 并整理文档摘要",
        "gates": ["tool_surface_discovery_gate"],
        "expect": {
            "tool_surface_need": "native_skill",
            "skill_or_tool_need": "codex_native_skill",
            "preferred_call_surface": "native_skill",
        },
        "expect_contains": {
            "module_need": "tool_surface_discovery",
        },
    },
    {
        "id": "TC-005k",
        "task": "运行本地 pytest 并查看失败日志",
        "risk": "R1",
        "expect": {
            "tool_surface_need": "none",
            "tool_discovery_status": "not_needed",
            "plugin_need": "none",
            "preferred_call_surface": "none",
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
        "id": "TC-008c",
        "task": "检测框架是否还在生效，是否因为 Codex 版本大更新而漂移",
        "risk": "R1",
        "not_risk": "R3",
        "gates": ["read_only_context_gate"],
        "r3_context_surface": "read_only_diagnostic",
        "promote_r3": False,
        "expect": {
            "edit_operation_profile": "read_only",
        },
    },
    {
        "id": "TC-008d",
        "task": "进行修复，同时检测 Codex 更新后的框架状态",
        "risk": "R3",
        "gates": ["change_contract_gate"],
        "r3_context_surface": "actionable_R3",
        "promote_r3": True,
    },
    {
        "id": "TC-008e",
        "task": "检测后更新配置并验证结果",
        "risk": "R3",
        "gates": ["change_contract_gate"],
        "r3_context_surface": "actionable_R3",
        "promote_r3": True,
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
        "id": "TC-009o",
        "task": "这个局部任务因果判断是否忽略了全局观、当前目标、状态表和文件图",
        "gates": ["global_task_context_gate"],
        "expect_contains": {
            "semantic_ambiguity": "global_task_context_gate",
        },
        "expect_trigger_contains": {
            "global_task_context_gate": "局部任务",
        },
    },
    {
        "id": "TC-009p",
        "task": "这次 router 和 policy 更新要保持环环相扣，只更新 Codex 和 WorkBuddy，不更新 Bash",
        "risk": "R4",
        "gates": ["linked_surface_sync_gate"],
        "expect_contains": {
            "semantic_ambiguity": "linked_surface_sync_gate",
        },
        "expect_trigger_contains": {
            "linked_surface_sync_gate": "环环相扣",
        },
    },
    {
        "id": "TC-009q",
        "task": "建立反馈闭环；这个全局问题需要从当前事件发散分析后续可能出现的同类事件，并进行预防，避免再只照顾局部",
        "gates": ["global_task_context_gate", "feedback_loop_gate"],
        "expect": {
            "feedback_loop_profile": "explicit_cycle",
            "read_depth_profile": "source_cascade_review",
        },
        "expect_contains": {
            "read_semantic_boundary": "causal_scope",
        },
        "expect_trigger_contains": {
            "global_task_context_gate": "全局问题",
            "feedback_loop": "反馈闭环",
        },
    },
    {
        "id": "TC-009r",
        "task": "这次表现和旧问题不是同一类，但结构相似，可能是新型异常，先标记为候选复发再轻量复评",
        "gates": ["novel_recurrence_candidate_gate"],
        "not_gates": ["global_task_context_gate", "feedback_loop_gate"],
        "expect_contains": {
            "semantic_ambiguity": "novel_recurrence_candidate_gate",
        },
        "expect_trigger_contains": {
            "novel_recurrence_candidate_gate": "新型异常",
        },
    },
    {
        "id": "TC-009s",
        "task": "Should this research line use a target function, a mechanical judge, or external governance?",
        "gates": ["research_triage_gate"],
        "expect_contains": {
            "semantic_ambiguity": "research_triage_gate",
        },
        "expect_trigger_contains": {
            "research_triage_gate": "target function",
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
    {
        "id": "TC-009p",
        "task": "上下文压缩后继续这个长对话，先回顾当前任务源头和全局目标",
        "expect": {
            "read_depth_profile": "segment_window",
        },
        "expect_contains": {
            "read_semantic_boundary": "continuity_goal",
        },
    },
    {
        "id": "TC-009q",
        "task": "检查我刚才是否真的运行了本地 pandas 检查，必须看实际命令日志和错误输出",
        "expect": {
            "read_depth_profile": "raw_context_window",
        },
        "expect_contains": {
            "read_semantic_boundary": "execution_trace",
        },
    },
    {
        "id": "TC-009r",
        "task": "PDF 编译成功了，但我要确认最终 PDF 里作者中文有没有丢失，不能只看源码",
        "expect": {
            "read_depth_profile": "artifact_output_window",
        },
        "expect_contains": {
            "read_semantic_boundary": "output_truth",
        },
    },
    {
        "id": "TC-009s",
        "task": "接续上一段对话记忆，但不要合并旧 lane，只建立链接并继续",
        "expect": {
            "read_depth_profile": "cross_lane_link_review",
        },
        "expect_contains": {
            "read_semantic_boundary": "cross_boundary",
        },
    },
    {
        "id": "TC-009t",
        "task": "这个本地案例能不能证明 CBH 长期降低幻觉漂移？",
        "expect": {
            "read_depth_profile": "source_cascade_review",
        },
        "expect_contains": {
            "read_semantic_boundary": "causal_scope",
        },
    },
    {
        "id": "TC-009u",
        "task": "更新 AGENTS.md 中的记忆规则，不要重写整个文件",
        "risk": "R3",
        "expect": {
            "edit_operation_profile": "in_place_patch",
            "read_depth_profile": "artifact_output_window",
        },
        "expect_contains": {
            "read_semantic_boundary": "change_integrity",
        },
    },
    {
        "id": "TC-009v",
        "task": "把这个任务段的原始上下文和执行日志追加到上下文备份，不要重写旧文件",
        "expect": {
            "edit_operation_profile": "append_delta",
        },
        "expect_contains": {
            "read_semantic_boundary": "execution_trace",
        },
    },
    {
        "id": "TC-009w",
        "task": "完全重写这个生成的报告文件，旧文件先保留为备份",
        "expect": {
            "edit_operation_profile": "full_rewrite",
        },
    },
    {
        "id": "TC-009x",
        "task": "删掉 README 中过时的一段描述，但不要删除文件",
        "expect": {
            "edit_operation_profile": "delete_record_content",
        },
    },
    {
        "id": "TC-009y",
        "task": "删除旧 release 文件夹",
        "risk": "R5",
        "expect": {
            "edit_operation_profile": "delete_from_disk",
        },
    },
    {
        "id": "TC-009z",
        "task": "不要删除任何文件，只检查哪些内容可能需要归档",
        "not_risk": "R5",
        "expect": {
            "edit_operation_profile": "read_only",
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
    if "r3_context_surface" in case:
        assert payload.get("risk_context_decisions", {}).get("R3", {}).get("action_surface") == case["r3_context_surface"]
    if "promote_r3" in case:
        assert bool(payload.get("risk_context_decisions", {}).get("R3", {}).get("promote_to_risk")) is case["promote_r3"]
    for field, expected in case.get("expect", {}).items():
        assert payload.get(field) == expected
    for field, expected_values in case.get("expect_in", {}).items():
        assert payload.get(field) in expected_values
    for field, expected_value in case.get("expect_contains", {}).items():
        assert contains(payload.get(field), expected_value)
    for trigger_key, expected_value in case.get("expect_trigger_contains", {}).items():
        assert contains(payload.get("matched_risk_triggers", {}).get(trigger_key), expected_value)


def test_router_skill_audit_and_first_principles_survive_long_middle_distractors() -> None:
    skill_task = "普通背景说明。" * 120 + "请审计这些技能是否存在隐藏风险、重复功能和可合并项。" + "其余背景。" * 120
    skill_payload = run_router(skill_task)
    assert skill_payload["target_surface"] == "skill_matrix"
    assert skill_payload["skill_audit_profile"] == "safety_and_redundancy_audit"
    assert contains(skill_payload["required_gates"], "skill_audit_gate")

    principle_task = "普通实现背景。" * 120 + "需要修改全局路由器的记忆写入策略并保留现有边界。" + "其余背景。" * 120
    principle_payload = run_router(principle_task)
    assert principle_payload["first_principles_profile"] == "constraint_gate"
    assert contains(principle_payload["required_gates"], "first_principles_gate")


def test_router_combines_global_context_and_feedback_prevention() -> None:
    payload = run_router("建立反馈闭环；这个全局问题需要从当前事件发散分析后续可能出现的同类事件，并进行预防，避免再只照顾局部")
    assert contains(payload.get("required_gates"), "global_task_context_gate")
    assert contains(payload.get("required_gates"), "feedback_loop_gate")
    assert contains(payload.get("semantic_ambiguity"), "global_task_context_gate")
    assert contains(payload.get("semantic_ambiguity"), "feedback_loop_required")
    assert payload["feedback_loop_profile"] == "explicit_cycle"


def test_router_uses_local_project_lane_overlay(tmp_path: Path) -> None:
    project = tmp_path / "EXAMPLE_PROJECT"
    memory_bank = project / "memory-bank"
    memory_bank.mkdir(parents=True)
    overlay = tmp_path / "project_lanes.local.json"
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
    env = dict(os.environ)
    env["CBH_PROJECT_LANES_FILE"] = str(overlay)

    payload = run_router_with_cwd("只读检查 Memory Bank 已更新和长期记忆状态", project, env=env)

    assert payload["project_lane"] == "EXAMPLE_PROJECT"
    assert payload["memory_lane"] == "current_project"
    assert payload["risk_level"] != "R5"


def test_router_promotes_explicit_project_record_request_to_r3(tmp_path: Path) -> None:
    project = tmp_path / "EXAMPLE_PROJECT"
    memory_bank = project / "memory-bank"
    memory_bank.mkdir(parents=True)
    overlay = tmp_path / "project_lanes.local.json"
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
    env = dict(os.environ)
    env["CBH_PROJECT_LANES_FILE"] = str(overlay)

    payload = run_router_with_cwd("record this problem", project, env=env)

    assert payload["project_lane"] == "EXAMPLE_PROJECT"
    assert payload["risk_level"] == "R3"
    assert payload["risk_context_decisions"]["R3"]["action_surface"] == "actionable_R3"
    assert payload["memory_lane"] == "current_project"
    assert payload["memory_mode"] == "write"
    assert payload["record_intent"] == "explicit_user_request"
    assert payload["fallback_model_judgment_recommended"] is False


def test_router_recognizes_isolated_long_conversation_lane_without_writing_memory() -> None:
    payload = run_router(
        "当前对话是独立的长单对话，不属于任何项目内容，"
        "这是相互隔离的，但是有互联通道"
    )

    assert payload["project_lane"] == "PROJECTLESS"
    assert payload["projectization_decision"] == "not_project"
    assert payload["memory_lane"] == "current_conversation"
    assert payload["memory_mode"] == "none"
    assert payload["record_intent"] == "no_record"
    assert payload["conversation_memory_decision"] == "none"
    assert payload["link_intent"] == "none"
    assert contains(payload.get("required_gates"), "lane_ownership_gate")


def test_router_exposes_active_conversation_source_for_compound_memory_retrieval(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
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

    payload = run_router_with_cwd(
        "关于我们的记忆机制中的检索机制，以及外部求索深度学习机制，是否能实际在触发时自动调用并实际生效。",
        workspace,
    )

    hints = payload["memory_source_hints"]
    assert len(hints) == 1
    assert hints[0]["lane"] == "current_conversation"
    assert Path(hints[0]["root_path"]).resolve() == lane.resolve()
    assert contains(payload["action_binding_ids"], "retrieve_matching_memory")


def test_router_binds_nonblocking_correction_lifecycle_for_tool_surface() -> None:
    payload = run_router("Use shell_command to inspect these files and summarize the result")

    assert payload["correction_lifecycle_profile"] == "surface_preflight"
    assert contains(payload["module_need"], "correction_lifecycle")
    assert contains(payload["action_binding_ids"], "prepare_task_local_correction_bundle")


def test_router_marks_project_long_term_memory_write_as_write_mode(tmp_path: Path) -> None:
    project = tmp_path / "EXAMPLE_PROJECT"
    memory_bank = project / "memory-bank"
    memory_bank.mkdir(parents=True)
    overlay = tmp_path / "project_lanes.local.json"
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
    env = dict(os.environ)
    env["CBH_PROJECT_LANES_FILE"] = str(overlay)

    payload = run_router_with_cwd("写入记忆：记录这个长期记忆修复", project, env=env)

    assert payload["project_lane"] == "EXAMPLE_PROJECT"
    assert payload["risk_level"] == "R5"
    assert payload["memory_lane"] == "current_project"
    assert payload["memory_mode"] == "write"
    assert payload["record_intent"] == "explicit_user_request"


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
