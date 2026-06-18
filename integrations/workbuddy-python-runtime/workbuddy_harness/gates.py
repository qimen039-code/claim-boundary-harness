from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .policy import load_policy


NEGATION_RE = re.compile(r"(?i)(\bdo\s+not\b|\bdon't\b|\bnever\b|\bnot\b|\bno\b)[\s\w'-]{0,36}$")
HARD_TOOL_PATTERNS = [
    r"(?i)\bRemove-Item\b",
    r"(?i)\brmdir\b",
    r"(?i)\bdel\b",
    r"(?i)\bgit\s+commit\b",
    r"(?i)\bgit\s+push\b",
    r"(?i)\bgit\s+reset\b",
    r"(?i)\bgit\s+checkout\b",
    r"(?i)\binstall\b",
    r"(?i)\blogin\b",
    r"(?i)\bpayment\b",
    r"(?i)\bpermission\b",
    r"(?i)\bfirewall\b",
    r"(?i)\bproxy\b",
    r"(?i)\bnetsh\b",
    r"(?i)\bSet-ExecutionPolicy\b",
    r"(?i)\blong-term memory\b",
    r"(?i)\bwrite memory\b",
    r"(?i)\bsensitive transfer\b",
]
CHANGE_TOOL_PATTERNS = [
    r"(?i)\bapply_patch\b",
    r"(?i)\bSet-Content\b",
    r"(?i)\bAdd-Content\b",
    r"(?i)\bMove-Item\b",
    r"(?i)\bCopy-Item\b",
    r"(?i)\bgit\s+add\b",
]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _flatten_triggers(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_flatten_triggers(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(_flatten_triggers(item))
        return out
    return [str(value)]


def _is_english_trigger(text: str) -> bool:
    return bool(re.fullmatch(r"[\x20-\x7E]+", text) and re.search(r"[A-Za-z0-9]", text))


def _trigger_regex(text: str) -> re.Pattern[str]:
    escaped = re.escape(text)
    if _is_english_trigger(text):
        return re.compile(rf"(?i)(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])")
    return re.compile(escaped)


def _is_negated(source: str, index: int) -> bool:
    start = max(0, index - 48)
    return bool(NEGATION_RE.search(source[start:index]))


def _trigger_matches(source: str, triggers: Any) -> dict[str, list[str]]:
    positive: list[str] = []
    negated: list[str] = []
    for trigger in _flatten_triggers(triggers):
        if not trigger.strip():
            continue
        for match in _trigger_regex(trigger).finditer(source):
            if _is_negated(source, match.start()):
                negated.append(trigger)
            else:
                positive.append(trigger)
    return {
        "positive": sorted(set(positive)),
        "negated": sorted(set(negated)),
    }


def _first_matching_rule(source: str, rules: dict[str, Any], order: list[str]) -> str | None:
    for name in order:
        if _trigger_matches(source, rules.get(name, []))["positive"]:
            return name
    return None


def _matching_triggers(source: str, triggers: Any) -> list[str]:
    return _trigger_matches(source, triggers)["positive"]


def _unique(items: list[str]) -> list[str]:
    return sorted(set(items), key=items.index)


def _path_text(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.abspath(os.path.realpath(os.fspath(path)))).rstrip("\\/")


def _path_inside(path: str, root: str) -> bool:
    path_norm = _path_text(path)
    root_norm = _path_text(root)
    try:
        return os.path.commonpath([path_norm, root_norm]) == root_norm
    except ValueError:
        return False


def _project_lane(cwd: str, policy: dict[str, Any]) -> str:
    for lane, roots in policy.get("project_lanes", {}).items():
        for root in _as_list(roots):
            if _path_inside(cwd, str(root)):
                return str(lane)
    return "PROJECTLESS"


def _tool_text(tool_name: str = "", tool_input: Any = None) -> str:
    parts = [tool_name or ""]
    if tool_input is None:
        return "\n".join(part for part in parts if part)
    if isinstance(tool_input, str):
        parts.append(tool_input)
    else:
        try:
            parts.append(json.dumps(tool_input, ensure_ascii=False, sort_keys=True))
        except TypeError:
            parts.append(str(tool_input))
    return "\n".join(part for part in parts if part)


def _pattern_hits(text: str, patterns: list[str]) -> list[str]:
    return sorted({pattern for pattern in patterns if re.search(pattern, text)})


def intake_router(task_text: str = "", cwd: str | None = None, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_policy()
    cwd = cwd or os.getcwd()
    risk_rules = policy.get("risk_trigger_rules") or policy.get("risk_keyword_rules") or {}
    matched_risk_triggers: dict[str, list[str]] = {}
    negated_risk_triggers: dict[str, list[str]] = {}
    triggered_risks: list[str] = []
    required_gates = ["microkernel"]
    approval_required: list[str] = []
    required_skills: list[str] = []

    for risk_name in _as_list(policy.get("risk_order_high_to_low")):
        name = str(risk_name)
        match_set = _trigger_matches(task_text, risk_rules.get(name, {}))
        if match_set["negated"]:
            negated_risk_triggers[name] = match_set["negated"]
        if match_set["positive"]:
            triggered_risks.append(name)
            matched_risk_triggers[name] = match_set["positive"]
            required_gates.extend(str(gate) for gate in _as_list(policy.get("risk_gate_rules", {}).get(name)))
            approval_required.extend(str(rule) for rule in _as_list(policy.get("risk_approval_rules", {}).get(name)))

    risk_level = "R0"
    for risk_name in _as_list(policy.get("risk_order_high_to_low")):
        if str(risk_name) in triggered_risks:
            risk_level = str(risk_name)
            break

    classification_confidence = "high"
    fallback_recommended = False
    if not triggered_risks:
        fallback_match = _trigger_matches(task_text, policy.get("fallback_boundary_triggers", []))
        if fallback_match["positive"]:
            fallback_recommended = True
            classification_confidence = "low"
            required_gates.append("model_boundary_review_gate")
            matched_risk_triggers["fallback_boundary"] = fallback_match["positive"]
        if fallback_match["negated"]:
            negated_risk_triggers["fallback_boundary"] = fallback_match["negated"]

    lane = _project_lane(cwd, policy)
    if lane != "PROJECTLESS":
        required_gates.extend(["memory_isolation_gate", "project_agents_gate"])
        required_skills.append(f"{lane} project AGENTS/router")

    skill_matches = _trigger_matches(task_text, policy.get("skill_matrix_triggers", []))
    if skill_matches["positive"]:
        required_skills.append("troubleshooting-skill-matrix")

    external_matches = _trigger_matches(task_text, policy.get("external_research_triggers", []))
    needs_external_research = bool(external_matches["positive"])
    if external_matches["positive"]:
        matched_risk_triggers["external_research"] = external_matches["positive"]
    if external_matches["negated"]:
        negated_risk_triggers["external_research"] = external_matches["negated"]

    contract = policy.get("router_decision_contract", {})
    target_surface = _first_matching_rule(
        task_text,
        contract.get("target_surface_trigger_rules", {}),
        ["git_action", "tool_call", "adapter", "public_docs", "private_rule", "local_harness", "skill_matrix", "project_memory"],
    ) or "current_chat"
    if target_surface == "current_chat" and "R3" in triggered_risks:
        target_surface = "local_harness"

    audience = _first_matching_rule(
        task_text,
        contract.get("audience_trigger_rules", {}),
        ["public_user", "local_maintainer"],
    )
    if not audience:
        audience = "project_operator" if lane != "PROJECTLESS" else "current_chat"

    semantic_ambiguity = _matching_triggers(task_text, contract.get("semantic_ambiguity_triggers", []))
    if "R3" in triggered_risks:
        semantic_ambiguity.append("governance_or_change_surface")
    semantic_ambiguity = _unique(semantic_ambiguity)

    external_need: list[str] = []
    for mode_name, mode in policy.get("search_and_learning_decision_matrix", {}).get("search_modes", {}).items():
        if _matching_triggers(task_text, mode.get("triggers", [])):
            external_need.append(str(mode_name))
    if needs_external_research and not external_need:
        external_need.append("official_authority_source_search")
    if not external_need:
        external_need.append("none")
    external_need = _unique(external_need)

    paired_memory_hits = _matching_triggers(task_text, contract.get("paired_memory_triggers", []))
    memory_hits = _matching_triggers(task_text, contract.get("memory_need_triggers", []))
    if paired_memory_hits:
        memory_need = "paired_err_sol"
    elif memory_hits:
        memory_need = "index_only"
    else:
        memory_need = "none"

    explicit_record_hits = _matching_triggers(task_text, contract.get("explicit_record_triggers", []))
    common_error_hits = _matching_triggers(task_text, contract.get("common_error_triggers", []))
    projectization_signals = _matching_triggers(task_text, contract.get("projectization_signals", []))
    projectization_threshold = int(contract.get("projectization_threshold", 3))

    if lane != "PROJECTLESS":
        projectization_decision = "current_project"
    elif len(projectization_signals) >= projectization_threshold:
        projectization_decision = "emergent_project_candidate"
    else:
        projectization_decision = "not_project"

    if common_error_hits:
        memory_need = "common_error_corpus"
    elif explicit_record_hits and memory_need == "none":
        memory_need = "paired_err_sol"

    if explicit_record_hits:
        record_intent = "explicit_user_request"
    elif common_error_hits:
        record_intent = "inferred_reusable_error"
    elif projectization_decision == "emergent_project_candidate":
        record_intent = "projectization_review"
    else:
        record_intent = "no_record"

    if common_error_hits:
        memory_lane = "common_error_corpus"
    elif explicit_record_hits:
        memory_lane = "self_reflection_matrix"
    elif lane != "PROJECTLESS":
        memory_lane = "current_project"
    elif projectization_decision == "emergent_project_candidate":
        memory_lane = "emergent_project_candidate"
    else:
        memory_lane = "none"

    if record_intent in {"explicit_user_request", "inferred_reusable_error"}:
        memory_mode = "write"
    elif memory_need != "none":
        memory_mode = "read"
    else:
        memory_mode = "none"

    if explicit_record_hits or common_error_hits:
        required_skills.append("troubleshooting-skill-matrix")

    strong_claim_hits = _matching_triggers(task_text, policy.get("blocked_claim_phrases_without_schema", []))
    if strong_claim_hits:
        claim_risk = "strong_claim_needs_schema"
    elif "claim_gate" in required_gates:
        claim_risk = "weak_claim"
    else:
        claim_risk = "none"

    module_need: list[str] = []
    if lane != "PROJECTLESS":
        module_need.append("project_router")
    if required_skills:
        module_need.append("skill_matrix")
    if semantic_ambiguity:
        module_need.append("semantic_anchors")
    if memory_need != "none":
        module_need.append("memory_meta_index")
    if external_need and external_need[0] != "none":
        module_need.append("external_research_gate")
    if claim_risk != "none":
        module_need.append("claim_schema_verifier")
    if risk_level == "R5" or classification_confidence == "low":
        module_need.append("runtime_gate")
    if not module_need:
        module_need.append("none")
    module_need = _unique(module_need)

    required_gates_out = _unique(required_gates)
    routing_receipt = {
        "task_type": risk_level,
        "target_surface": target_surface,
        "audience": audience,
        "project_lane": lane,
        "risk_level": risk_level,
        "semantic_ambiguity": semantic_ambiguity,
        "module_need": module_need,
        "memory_need": memory_need,
        "memory_mode": memory_mode,
        "memory_lane": memory_lane,
        "record_intent": record_intent,
        "external_need": external_need,
        "claim_risk": claim_risk,
        "projectization_decision": projectization_decision,
        "projectization_signals": projectization_signals,
        "required_gates": required_gates_out,
    }

    return {
        "ts": _now(),
        "phase": "intake_router",
        "status": "pass",
        "cwd": cwd,
        "routing_receipt": routing_receipt,
        "target_surface": target_surface,
        "audience": audience,
        "project_lane": lane,
        "risk_level": risk_level,
        "semantic_ambiguity": semantic_ambiguity,
        "module_need": module_need,
        "memory_need": memory_need,
        "memory_mode": memory_mode,
        "memory_lane": memory_lane,
        "record_intent": record_intent,
        "external_need": external_need,
        "claim_risk": claim_risk,
        "projectization_decision": projectization_decision,
        "projectization_signals": projectization_signals,
        "triggered_risks": sorted(set(triggered_risks), key=triggered_risks.index),
        "matched_risk_triggers": matched_risk_triggers,
        "negated_risk_triggers": negated_risk_triggers,
        "classification_confidence": classification_confidence,
        "required_gates": required_gates_out,
        "required_skills": _unique(required_skills),
        "needs_external_research": needs_external_research,
        "approval_required": _unique(approval_required),
        "fallback_model_judgment_used": False,
        "fallback_model_judgment_recommended": fallback_recommended,
        "enforcement_boundary": policy.get("gate_enforcement_boundary", ""),
    }


def memory_isolation_gate(
    project_lane: str = "PROJECTLESS",
    requested_path: str = "",
    *,
    cross_reference_allow: bool = False,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy()
    allowed_roots = [str(root) for root in _as_list(policy.get("memory_roots", {}).get(project_lane))]
    status = "pass"
    reason = "no requested path"
    resolved_requested = None

    if requested_path:
        resolved_requested = _path_text(requested_path)
        inside = any(_path_inside(requested_path, root) for root in allowed_roots)
        if inside:
            reason = "requested path is inside active project memory roots"
        elif cross_reference_allow:
            status = "cross_reference_allowed"
            reason = "requested path is outside active lane but explicit cross-reference allow was provided"
        else:
            status = "blocked"
            reason = "requested path is outside active project memory roots"

    return {
        "ts": _now(),
        "phase": "memory_isolation_gate",
        "status": status,
        "project_lane": project_lane,
        "allowed_roots": allowed_roots,
        "allowed_roots_resolved": sorted({_path_text(root) for root in allowed_roots}),
        "requested_path": requested_path,
        "resolved_requested_path": resolved_requested,
        "reason": reason,
    }


def claim_schema_verifier(
    *,
    claim_json: str | list[dict[str, Any]] | dict[str, Any] | None = None,
    final_text: str = "",
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy()
    issues: list[str] = []
    claims: list[dict[str, Any]] = []

    if claim_json:
        try:
            parsed = json.loads(claim_json) if isinstance(claim_json, str) else claim_json
            claims = parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            issues.append("claim_json_parse_failed")

    for claim in claims:
        if not isinstance(claim, dict):
            issues.append("claim_not_object")
            continue
        for field in ("claim_type", "source_type", "evidence_boundary"):
            if not str(claim.get(field, "")).strip():
                issues.append(f"missing_{field}")
        source_type = str(claim.get("source_type", ""))
        if source_type in {"external_retrieval", "memory_capsule_ref"} and not str(claim.get("source_ref", "")).strip():
            issues.append(f"missing_source_ref_for_{source_type}")

    if final_text:
        for phrase in _as_list(policy.get("blocked_claim_phrases_without_schema")):
            if str(phrase) in final_text and not claims:
                issues.append(f"blocked_claim_phrase_without_schema:{phrase}")

    return {
        "ts": _now(),
        "phase": "claim_schema_verifier",
        "status": "blocked" if issues else "pass",
        "claims_checked": len(claims),
        "issues": sorted(set(issues)),
        "rule": "schema completeness check only; no extra LLM judgment",
    }


def runtime_enforcer(
    *,
    stage: str = "pre_task",
    task_text: str = "",
    cwd: str | None = None,
    tool_name: str = "",
    tool_input: Any = None,
    claim_json: str | list[dict[str, Any]] | dict[str, Any] | None = None,
    human_confirmed: bool = False,
    boundary_reviewed: bool = False,
    constitution_reviewed: bool = False,
    constitution_path: str = "",
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy()
    cwd = cwd or os.getcwd()
    route_text = "\n".join(part for part in [task_text, tool_name, _tool_text(tool_input=tool_input)] if part)
    route = intake_router(route_text, cwd, policy)
    tool_text = _tool_text(tool_name, tool_input)
    hard_hits = _pattern_hits(tool_text, HARD_TOOL_PATTERNS)
    change_hits = _pattern_hits(tool_text, CHANGE_TOOL_PATTERNS)

    blocked: list[str] = []
    warnings: list[str] = []

    if route["risk_level"] == "R5" and not human_confirmed:
        blocked.append("human_confirmation_required_for_R5")
    if hard_hits and not human_confirmed:
        blocked.append("tool_call_requires_human_confirmation")
    if route["fallback_model_judgment_recommended"] and not boundary_reviewed:
        blocked.append("boundary_review_required_for_low_confidence_route")

    resolved_constitution = ""
    constitution_candidates = [constitution_path, os.path.join(cwd, "AGENTS.md")]
    for candidate in constitution_candidates:
        if candidate and Path(candidate).exists():
            resolved_constitution = str(Path(candidate).resolve())
            break
    if route["risk_level"] != "R0" and not resolved_constitution and not constitution_reviewed:
        blocked.append("constitution_entry_missing_or_unreviewed")

    if stage == "final":
        claim_result = claim_schema_verifier(claim_json=claim_json, final_text=task_text, policy=policy)
        if claim_result["status"] != "pass":
            blocked.append("claim_schema_verifier_blocked")

    if change_hits and route["risk_level"] == "R0":
        warnings.append("tool_looks_mutating_but_route_is_R0")

    return {
        "ts": _now(),
        "phase": "runtime_enforcer",
        "stage": stage,
        "status": "blocked" if blocked else "pass",
        "cwd": cwd,
        "route": route,
        "tool_name": tool_name,
        "tool_hard_hits": hard_hits,
        "tool_change_hits": change_hits,
        "constitution_path": resolved_constitution,
        "blocked_reasons": sorted(set(blocked)),
        "warnings": sorted(set(warnings)),
        "enforcement": "hard only when host treats this in-process function as the sole pre-execution gate",
    }
