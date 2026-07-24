from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .policy import load_policy


NEGATION_RE = re.compile(r"(?i)(\bdo\s+not\b|\bdon't\b|\bnever\b|\bnot\b|\bno\b)[\s\w'-]{0,128}$")
CHINESE_NEGATION_RE = re.compile(r"(不需要|无需|不要|别|禁止|不)\s*$")
DEFAULT_LOG_FILENAME = "workbuddy_harness_events.jsonl"
SURROGATE_RE = re.compile(r"[\ud800-\udfff]")
_PENDING_LOGS: list[dict[str, Any]] = []


def sanitize_json_value(value: Any) -> Any:
    """Return a JSON-serializable value without lone UTF-16 surrogate code points."""
    if isinstance(value, str):
        return SURROGATE_RE.sub("<invalid-surrogate>", value)
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(sanitize_json_value(key)): sanitize_json_value(item) for key, item in value.items()}
    return value


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()




def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _contract_token(value: Any) -> str:
    return re.sub(r"[\s-]+", "_", str(value or "").strip().lower())


def _risk_rank(risk_level: str, policy: dict[str, Any]) -> int:
    order = [str(item) for item in _as_list(policy.get("risk_order_high_to_low"))]
    try:
        return order.index(risk_level)
    except ValueError:
        return len(order)


def _higher_risk(left: str, right: str, policy: dict[str, Any]) -> str:
    return left if _risk_rank(left, policy) <= _risk_rank(right, policy) else right




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
    start = max(0, index - 256)
    prefix = source[start:index]
    return bool(NEGATION_RE.search(prefix) or CHINESE_NEGATION_RE.search(prefix[-32:]))


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


def _source_matched_terms(source: str, terms: Any) -> list[str]:
    hits: list[str] = []
    for term in _flatten_triggers(terms):
        if term.strip() and _trigger_regex(term).search(source):
            hits.append(term)
    return _unique(hits)


def _term_intersection(left_terms: Any, right_terms: Any) -> list[str]:
    right = {str(term).lower() for term in _flatten_triggers(right_terms) if str(term).strip()}
    return _unique([str(term) for term in _flatten_triggers(left_terms) if str(term).lower() in right])


def _r5_context_decision(*, source_text: str, positive_terms: list[str], negated_terms: list[str], policy: dict[str, Any]) -> dict[str, Any]:
    candidate_terms = _unique([str(item) for item in positive_terms])
    negated = _unique([str(item) for item in negated_terms])
    if not candidate_terms:
        return {
            "decision": "none",
            "action_surface": "none",
            "promote_to_risk": False,
            "candidate_terms": [],
            "negated_terms": negated,
            "reason": "no_R5_candidate",
        }

    rules = policy.get("r5_context_decision_rules", {})
    direct_action_hits = _source_matched_terms(source_text, rules.get("direct_action_terms", []))
    action_context_hits = _source_matched_terms(source_text, rules.get("action_context_terms", []))
    documentation_context_hits = _source_matched_terms(source_text, rules.get("documentation_context_terms", []))
    non_action_context_hits = _source_matched_terms(source_text, rules.get("non_action_context_terms", []))
    context_required_hits = _term_intersection(candidate_terms, rules.get("context_required_candidate_terms", []))
    always_action_hits = _term_intersection(candidate_terms, rules.get("always_action_candidate_terms", []))

    if direct_action_hits or (always_action_hits and not documentation_context_hits) or (
        context_required_hits and action_context_hits and not non_action_context_hits
    ):
        return {
            "decision": "requires_confirmation",
            "action_surface": "actionable_R5",
            "promote_to_risk": True,
            "candidate_terms": candidate_terms,
            "negated_terms": negated,
            "reason": "action_context_detected",
        }
    if documentation_context_hits or non_action_context_hits:
        return {
            "decision": "contextual_review",
            "action_surface": "documentation_or_discussion",
            "promote_to_risk": False,
            "candidate_terms": candidate_terms,
            "negated_terms": negated,
            "reason": "R5_terms_are_context_not_action",
        }
    return {
        "decision": "contextual_review",
        "action_surface": "ambiguous_R5_candidate",
        "promote_to_risk": False,
        "candidate_terms": candidate_terms,
        "negated_terms": negated,
        "reason": "R5_candidate_needs_context_review",
    }


def _conversation_full_lane_groups(task_text: str, contract: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], bool]:
    config = contract.get("conversation_memory_full_lane_triggers", {})
    groups = config.get("threshold_groups", {}) if isinstance(config, dict) else {}
    if not isinstance(groups, dict):
        return {}, False

    result: dict[str, dict[str, Any]] = {}
    triggered = False
    for group_name, settings in groups.items():
        if not isinstance(settings, dict):
            continue
        try:
            threshold = int(settings.get("threshold", 1) or 1)
        except (TypeError, ValueError):
            threshold = 1
        threshold = max(1, threshold)
        hits = _matching_triggers(task_text, settings.get("triggers", []))
        if not hits:
            continue
        group_triggered = len(hits) >= threshold
        result[str(group_name)] = {
            "threshold": threshold,
            "hits": hits,
            "triggered": group_triggered,
        }
        triggered = triggered or group_triggered
    return result, triggered


def _skill_audit_decision(task_text: str, contract: dict[str, Any]) -> dict[str, Any]:
    subject_hits = _matching_triggers(task_text, contract.get("subject_triggers", []))
    intent_hits = _matching_triggers(task_text, contract.get("audit_intent_triggers", []))
    safety_hits = _matching_triggers(task_text, contract.get("safety_triggers", []))
    redundancy_hits = _matching_triggers(task_text, contract.get("redundancy_triggers", []))
    profile = "none"
    if subject_hits and intent_hits:
        if safety_hits and redundancy_hits:
            profile = "safety_and_redundancy_audit"
        elif safety_hits:
            profile = "safety_audit"
        elif redundancy_hits:
            profile = "redundancy_audit"
    return {
        "profile": profile,
        "signals": _unique([*subject_hits, *intent_hits, *safety_hits, *redundancy_hits]),
    }


def _first_principles_decision(
    task_text: str,
    *,
    risk_level: str,
    target_surface: str,
    contract: dict[str, Any],
) -> dict[str, Any]:
    full_hits = _matching_triggers(task_text, contract.get("full_design_triggers", []))
    constraint_hits = _matching_triggers(task_text, contract.get("constraint_gate_triggers", []))
    none_hits = _matching_triggers(task_text, contract.get("none_triggers", []))
    profile = "none"
    if full_hits:
        profile = "full_design"
    elif none_hits:
        profile = "none"
    elif (
        constraint_hits
        or risk_level == "R5"
        or target_surface in set(_as_list(contract.get("high_impact_target_surfaces")))
    ):
        profile = "constraint_gate"
    elif risk_level in set(_as_list(contract.get("micro_constraint_risks"))):
        profile = "micro_constraints"
    return {
        "profile": profile,
        "signals": _unique([*full_hits, *constraint_hits, *none_hits]),
    }


def _unique(items: list[str]) -> list[str]:
    return sorted(set(items), key=items.index)


def _resolve_log_path(
    *,
    log_path: str | os.PathLike[str] | None = None,
    log_dir: str | os.PathLike[str] | None = None,
) -> Path | None:
    if log_dir is not None:
        return Path(log_dir) / DEFAULT_LOG_FILENAME
    if log_path is None:
        return None
    path = Path(log_path)
    if path.exists() and path.is_dir():
        return path / DEFAULT_LOG_FILENAME
    if str(log_path).endswith(("\\", "/")):
        return path / DEFAULT_LOG_FILENAME
    return path


def flush_logs(
    *,
    log_path: str | os.PathLike[str] | None = None,
    log_dir: str | os.PathLike[str] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    path = _resolve_log_path(log_path=log_path, log_dir=log_dir)
    pending = list(events) if events is not None else list(_PENDING_LOGS)
    if path is None:
        return {
            "ts": _now(),
            "phase": "flush_logs",
            "status": "skipped",
            "written": 0,
            "path": "",
            "reason": "no log_path or log_dir provided",
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    if pending:
        with path.open("a", encoding="utf-8") as handle:
            for event in pending:
                handle.write(json.dumps(sanitize_json_value(event), ensure_ascii=False, sort_keys=True) + "\n")
        if events is None:
            del _PENDING_LOGS[: len(pending)]

    return {
        "ts": _now(),
        "phase": "flush_logs",
        "status": "pass",
        "written": len(pending),
        "path": str(path),
    }


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


def _active_conversation_memory_lane(cwd: str) -> str:
    current = Path(cwd).resolve()
    for _ in range(5):
        root = current / "local-conversation-memory"
        if root.exists() and root.is_dir():
            for lane in root.iterdir():
                if not lane.is_dir():
                    continue
                meta_path = lane / "_META_INDEX.md"
                index_path = lane / "index.json"
                if not meta_path.exists() and not index_path.exists():
                    continue
                parts: list[str] = []
                for path in (meta_path, index_path):
                    if path.exists():
                        try:
                            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
                        except OSError:
                            continue
                combined = "\n".join(parts)
                if re.search(r"(?:lane_state|status)[\"']?\s*[:=]\s*[\"']?active", combined, re.IGNORECASE) or "single_conversation_project_shaped_lane" in combined:
                    return str(lane)
        if current.parent == current:
            break
        current = current.parent
    return ""






























def _conversation_link_intent(task_text: str, policy: dict[str, Any]) -> str:
    contract = policy.get("conversation_linking_contract", {})
    ordered_rules = [
        ("merge_memories_explicit", "merge_triggers"),
        ("archive_or_seal_memory", "archive_triggers"),
        ("continue_from_referenced_memory", "continue_reference_triggers"),
        ("continue_from_latest", "continue_latest_triggers"),
    ]
    for intent, trigger_key in ordered_rules:
        if _matching_triggers(task_text, contract.get(trigger_key, [])):
            return intent
    return "none"




def causal_attribution_gate(*, final_text: str, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_policy()
    contract = policy.get("router_decision_contract", {})
    groups = contract.get("causal_attribution_triggers", {})
    issues: list[str] = []
    if not final_text or not isinstance(groups, dict):
        return {
            "ts": _now(),
            "phase": "causal_attribution_gate",
            "status": "pass",
            "patterns": [],
            "issues": [],
            "rule": "High-risk causal attribution review only; scoped local causal reasoning is not blocked.",
        }

    patterns: list[str] = []
    segments = [segment for segment in re.split(r"(?<=[.!?。！？；;])\s+|[\r\n]+", final_text) if segment.strip()]
    for segment in segments:
        hits = {
            name: _matching_triggers(segment, groups.get(name, []))
            for name in (
                "abstract_subject_terms",
                "causal_predicate_terms",
                "global_effect_terms",
                "time_range_terms",
                "stability_assertion_terms",
                "sample_terms",
                "generalization_terms",
                "origin_path_terms",
                "definition_terms",
                "scope_limiter_terms",
            )
        }
        if hits["scope_limiter_terms"]:
            continue
        if hits["abstract_subject_terms"] and hits["causal_predicate_terms"] and hits["global_effect_terms"]:
            patterns.append("abstract_system_causal_global_effect")
        if hits["time_range_terms"] and hits["stability_assertion_terms"]:
            patterns.append("time_range_stability_assertion")
        if hits["sample_terms"] and hits["generalization_terms"]:
            patterns.append("single_sample_generalization")
        if hits["abstract_subject_terms"] and hits["origin_path_terms"] and hits["definition_terms"]:
            patterns.append("origin_path_as_mechanism_definition")

    issues.extend(f"causal_attribution_boundary_required:{pattern}" for pattern in _unique(patterns))

    return {
        "ts": _now(),
        "phase": "causal_attribution_gate",
        "status": "blocked" if issues else "pass",
        "patterns": _unique(patterns),
        "issues": sorted(set(issues)),
        "rule": "High-risk causal attribution review only; scoped local causal reasoning is not blocked.",
    }


def intake_router(task_text: str = "", cwd: str | None = None, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_policy()
    cwd = cwd or os.getcwd()
    risk_rules = policy.get("risk_trigger_rules") or policy.get("risk_keyword_rules") or {}
    matched_risk_triggers: dict[str, list[str]] = {}
    negated_risk_triggers: dict[str, list[str]] = {}
    risk_candidates: dict[str, list[str]] = {}
    risk_context_decisions: dict[str, dict[str, Any]] = {}
    triggered_risks: list[str] = []
    required_gates = ["microkernel"]
    approval_required: list[str] = []
    required_skills: list[str] = []
    classification_confidence = "high"
    fallback_recommended = False

    for risk_name in _as_list(policy.get("risk_order_high_to_low")):
        name = str(risk_name)
        match_set = _trigger_matches(task_text, risk_rules.get(name, {}))
        if match_set["negated"]:
            negated_risk_triggers[name] = match_set["negated"]
        if name == "R5" and match_set["positive"]:
            r5_decision = _r5_context_decision(
                source_text=task_text,
                positive_terms=match_set["positive"],
                negated_terms=match_set["negated"],
                policy=policy,
            )
            risk_candidates["R5"] = match_set["positive"]
            risk_context_decisions["R5"] = r5_decision
            if not r5_decision.get("promote_to_risk"):
                if r5_decision.get("action_surface") == "ambiguous_R5_candidate":
                    classification_confidence = "low"
                    required_gates.append("risk_context_review_gate")
                continue
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

    if not triggered_risks:
        fallback_match = _trigger_matches(task_text, policy.get("fallback_boundary_triggers", []))
        contract = policy.get("router_decision_contract", {})
        short_max = int(contract.get("fallback_short_text_max_chars", 30))
        long_min = int(contract.get("fallback_long_text_min_chars", 100))
        task_len = len(task_text.strip())
        fallback_eligible = task_len >= long_min or (task_len >= short_max and bool(fallback_match["positive"]))
        if fallback_eligible:
            fallback_recommended = True
            classification_confidence = "low"
            required_gates.append("model_boundary_review_gate")
            matched_risk_triggers["fallback_boundary"] = fallback_match["positive"] or ["long_unclassified_task"]
        if fallback_match["negated"]:
            negated_risk_triggers["fallback_boundary"] = fallback_match["negated"]

    lane = _project_lane(cwd, policy)
    active_conversation_memory_lane_path = _active_conversation_memory_lane(cwd)
    has_active_conversation_memory_lane = bool(active_conversation_memory_lane_path)
    if lane != "PROJECTLESS":
        required_gates.extend(["memory_isolation_gate", "project_agents_gate"])
        required_skills.append(f"{lane} project AGENTS/router")

    contract = policy.get("router_decision_contract", {})
    skill_audit = _skill_audit_decision(task_text, contract.get("skill_audit_contract", {}))
    skill_audit_profile = str(skill_audit["profile"])
    skill_audit_signals = list(skill_audit["signals"])
    if skill_audit_profile != "none":
        audit_contract = contract.get("skill_audit_contract", {})
        required_gates.extend(str(item) for item in _as_list(audit_contract.get("required_gates")))
        required_skill = str(audit_contract.get("required_skill") or "")
        if required_skill:
            required_skills.append(required_skill)
        risk_level = _higher_risk(risk_level, str(audit_contract.get("minimum_risk") or "R3"), policy)
        if "R3" not in triggered_risks:
            triggered_risks.append("R3")
        matched_risk_triggers["skill_audit"] = skill_audit_signals

    skill_matches = _trigger_matches(task_text, policy.get("skill_matrix_triggers", []))
    if skill_matches["positive"]:
        required_skills.append("troubleshooting-skill-matrix")

    external_matches = _trigger_matches(task_text, policy.get("external_research_triggers", []))
    needs_external_research = bool(external_matches["positive"])
    if external_matches["positive"]:
        matched_risk_triggers["external_research"] = external_matches["positive"]
    if external_matches["negated"]:
        negated_risk_triggers["external_research"] = external_matches["negated"]

    target_surface = "skill_matrix" if skill_audit_profile != "none" else (
        _first_matching_rule(
            task_text,
            contract.get("target_surface_trigger_rules", {}),
            ["git_action", "tool_call", "adapter", "public_docs", "conversation_ledger", "conversation_memory", "private_rule", "local_harness", "skill_matrix", "project_memory"],
        ) or "current_chat"
    )
    if target_surface == "current_chat" and "R3" in triggered_risks:
        target_surface = "local_harness"

    first_principles = _first_principles_decision(
        task_text,
        risk_level=risk_level,
        target_surface=target_surface,
        contract=contract.get("first_principles_contract", {}),
    )
    first_principles_profile = str(first_principles["profile"])
    first_principles_signals = list(first_principles["signals"])
    first_principles_contract = contract.get("first_principles_contract", {})
    if first_principles_profile in set(_as_list(first_principles_contract.get("gate_profiles"))):
        required_gate = str(first_principles_contract.get("required_gate") or "")
        if required_gate:
            required_gates.append(required_gate)

    audience = _first_matching_rule(
        task_text,
        contract.get("audience_trigger_rules", {}),
        ["public_user", "local_maintainer"],
    )
    if not audience:
        audience = "project_operator" if lane != "PROJECTLESS" else "current_chat"

    semantic_ambiguity = _matching_triggers(task_text, contract.get("semantic_ambiguity_triggers", []))
    scope_reassessment_hits = _matching_triggers(task_text, contract.get("scope_reassessment_triggers", []))
    if scope_reassessment_hits:
        semantic_ambiguity.append("composite_or_scope_reassessment")
        required_gates.append("scope_reassessment_gate")
    observation_scope_hits = _matching_triggers(task_text, contract.get("observation_scope_triggers", []))
    if observation_scope_hits:
        semantic_ambiguity.append("observation_scope_required")
        required_gates.append("observation_scope_gate")
        matched_risk_triggers["observation_scope"] = observation_scope_hits
    feedback_loop_hits = _matching_triggers(task_text, contract.get("feedback_loop_triggers", []))
    feedback_loop_profile = "none"
    if feedback_loop_hits:
        semantic_ambiguity.append("feedback_loop_required")
        required_gates.append("feedback_loop_gate")
        matched_risk_triggers["feedback_loop"] = feedback_loop_hits
        feedback_loop_profile = "explicit_cycle"
    issue_prevention_gates = contract.get("issue_prevention_gates", {})
    if isinstance(issue_prevention_gates, dict):
        for gate_name, gate in issue_prevention_gates.items():
            if not isinstance(gate, dict):
                continue
            gate_hits = _matching_triggers(task_text, gate.get("triggers", []))
            if gate_hits:
                semantic_ambiguity.append(str(gate_name))
                required_gates.append(str(gate_name))
                matched_risk_triggers[str(gate_name)] = gate_hits
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
    static_knowledge_hits = _matching_triggers(task_text, contract.get("static_knowledge_triggers", []))
    if paired_memory_hits:
        memory_need = "paired_err_sol"
    elif memory_hits or static_knowledge_hits or feedback_loop_hits:
        memory_need = "index_only"
    else:
        memory_need = "none"
    if paired_memory_hits:
        semantic_ambiguity.append("feedback_loop_required")
        required_gates.append("feedback_loop_gate")
        matched_risk_triggers["feedback_loop_memory"] = paired_memory_hits
        if feedback_loop_profile != "explicit_cycle":
            feedback_loop_profile = "prevention_review"
    if static_knowledge_hits:
        required_gates.append("static_knowledge_index_gate")

    explicit_record_hits = _matching_triggers(task_text, contract.get("explicit_record_triggers", []))
    common_error_hits = _matching_triggers(task_text, contract.get("common_error_triggers", []))
    common_error_prevention_hits = _matching_triggers(task_text, contract.get("common_error_prevention_triggers", []))
    common_error_write_intent = bool(common_error_hits and explicit_record_hits)
    r5_decision_for_memory_intent = risk_context_decisions.get("R5", {})
    r5_candidates_for_memory_intent = (
        _as_list(r5_decision_for_memory_intent.get("candidate_terms"))
        if r5_decision_for_memory_intent.get("promote_to_risk") is True
        else []
    )
    explicit_long_term_memory_write_intent = bool(
        {str(item) for item in r5_candidates_for_memory_intent}.intersection({"write memory", "写入记忆"})
    )
    if common_error_hits:
        if common_error_write_intent:
            if feedback_loop_profile == "none":
                feedback_loop_profile = "record_candidate"
            matched_risk_triggers["common_error_candidate"] = common_error_hits
        elif common_error_prevention_hits:
            semantic_ambiguity.append("feedback_loop_required")
            required_gates.append("feedback_loop_gate")
            matched_risk_triggers["feedback_loop_common_error"] = common_error_hits
            if feedback_loop_profile != "explicit_cycle":
                feedback_loop_profile = "prevention_review"
        else:
            if feedback_loop_profile == "none":
                feedback_loop_profile = "index_hint"
            matched_risk_triggers["common_error_index_hint"] = common_error_hits
    if common_error_hits and common_error_prevention_hits:
        semantic_ambiguity.append("feedback_loop_required")
        required_gates.append("feedback_loop_gate")
    semantic_ambiguity = _unique(semantic_ambiguity)
    projectization_signals = _matching_triggers(task_text, contract.get("projectization_signals", []))
    projectization_threshold = int(contract.get("projectization_threshold", 5))

    if lane != "PROJECTLESS":
        projectization_decision = "current_project"
    elif len(projectization_signals) >= projectization_threshold:
        projectization_decision = "emergent_project_candidate"
    else:
        projectization_decision = "not_project"

    conversation_explicit_hits = _matching_triggers(task_text, contract.get("conversation_memory_explicit_triggers", []))
    conversation_signals = _matching_triggers(task_text, contract.get("conversation_memory_signals", []))
    self_reflection_record_hits = [] if conversation_explicit_hits else explicit_record_hits
    conversation_threshold = int(contract.get("conversation_memory_threshold", 5))
    conversation_full_lane_groups, conversation_full_lane_triggered = _conversation_full_lane_groups(task_text, contract)
    conversation_memory_decision = "none"
    read_only_audit_hits = _matching_triggers(task_text, contract.get("read_only_memory_audit_triggers", []))
    active_conversation_write_intent_hits = _matching_triggers(task_text, contract.get("active_conversation_write_intent_triggers", []))
    read_only_memory_audit_intent = bool(read_only_audit_hits) and not (
        active_conversation_write_intent_hits or explicit_record_hits or common_error_write_intent
    )
    active_conversation_write_intent = bool(
        active_conversation_write_intent_hits or explicit_record_hits or common_error_write_intent
    )
    active_conversation_memory_durable_signal = has_active_conversation_memory_lane and not read_only_memory_audit_intent and (
        active_conversation_write_intent
        or conversation_full_lane_triggered
        or len(conversation_signals) >= conversation_threshold
        or len(projectization_signals) >= projectization_threshold
        or risk_level in {"R4", "R5"}
    )
    if lane == "PROJECTLESS":
        if conversation_explicit_hits:
            conversation_memory_decision = "create_or_update_current_conversation"
        elif active_conversation_memory_durable_signal:
            conversation_memory_decision = "create_or_update_current_conversation"
        elif len(conversation_signals) >= conversation_threshold or conversation_full_lane_triggered:
            if projectization_decision == "not_project" and not read_only_memory_audit_intent:
                conversation_memory_decision = "checkpoint_candidate"

    link_intent = _conversation_link_intent(task_text, policy)
    if link_intent != "none":
        link_should_create_current_conversation = link_intent in {
            "continue_from_latest",
            "continue_from_referenced_memory",
        } and bool(conversation_explicit_hits or active_conversation_write_intent)
        if link_should_create_current_conversation:
            conversation_memory_decision = "create_or_update_current_conversation"
        else:
            conversation_memory_decision = "read_referenced_conversation"
    else:
        link_should_create_current_conversation = False

    if common_error_hits:
        memory_need = "common_error_corpus"
    elif self_reflection_record_hits and memory_need == "none":
        memory_need = "paired_err_sol"
    elif explicit_long_term_memory_write_intent and memory_need == "none":
        memory_need = "index_only"

    if common_error_write_intent:
        record_intent = "inferred_reusable_error"
    elif conversation_memory_decision == "create_or_update_current_conversation":
        if conversation_explicit_hits:
            record_intent = "explicit_conversation_memory_request"
        else:
            record_intent = "conversation_checkpoint"
    elif self_reflection_record_hits:
        record_intent = "explicit_user_request"
    elif explicit_long_term_memory_write_intent:
        record_intent = "explicit_user_request"
    elif conversation_memory_decision == "checkpoint_candidate":
        record_intent = "conversation_checkpoint"
    elif projectization_decision == "emergent_project_candidate":
        record_intent = "projectization_review"
    elif link_intent in {"merge_memories_explicit", "archive_or_seal_memory"}:
        record_intent = "explicit_cross_conversation_update"
    elif link_intent != "none":
        record_intent = "conversation_link_review"
    else:
        record_intent = "no_record"

    if link_intent != "none" and link_should_create_current_conversation and memory_need == "none":
        memory_need = "conversation_state"
    elif link_intent != "none" and memory_need == "none":
        memory_need = "index_only"
    elif conversation_memory_decision != "none" and memory_need == "none":
        memory_need = "conversation_state"
    if link_intent != "none":
        required_gates.append("conversation_link_gate")

    if common_error_hits:
        memory_lane = "common_error_corpus"
    elif lane != "PROJECTLESS":
        memory_lane = "current_project"
    elif link_intent != "none" and link_should_create_current_conversation:
        memory_lane = "current_conversation"
    elif link_intent != "none":
        memory_lane = "referenced_conversation"
    elif explicit_long_term_memory_write_intent and has_active_conversation_memory_lane:
        memory_lane = "current_conversation"
    elif explicit_long_term_memory_write_intent:
        memory_lane = "global_inbox"
    elif conversation_memory_decision != "none" and (has_active_conversation_memory_lane or conversation_explicit_hits):
        memory_lane = "current_conversation"
    elif self_reflection_record_hits:
        memory_lane = "self_reflection_matrix"
    elif projectization_decision == "emergent_project_candidate":
        memory_lane = "emergent_project_candidate"
    elif conversation_memory_decision != "none":
        memory_lane = "current_conversation"
    else:
        memory_lane = "none"

    if record_intent in {
        "explicit_user_request",
        "inferred_reusable_error",
        "explicit_conversation_memory_request",
        "conversation_checkpoint",
        "explicit_cross_conversation_update",
    }:
        if memory_lane == "current_conversation" and has_active_conversation_memory_lane:
            memory_mode = "update"
        else:
            memory_mode = "write"
    elif memory_need != "none":
        memory_mode = "read"
    else:
        memory_mode = "none"

    if (
        conversation_memory_decision == "create_or_update_current_conversation"
        and memory_mode in {"write", "update"}
    ) or (link_intent != "none" and memory_lane == "current_conversation"):
        risk_level = _higher_risk(risk_level, "R3", policy)
        if "R3" not in triggered_risks:
            triggered_risks.append("R3")
        matched_risk_triggers["R3"] = _unique(
            _as_list(matched_risk_triggers.get("R3")) + ["conversation_memory_write_or_link"]
        )
        required_gates.extend(str(gate) for gate in _as_list(policy.get("risk_gate_rules", {}).get("R3")))

    hybrid_retrieval_profile = "none"
    if memory_need != "none":
        hybrid_retrieval_profile = "meta_first_hybrid_enhancement"
    if memory_need in {"capsule_payload", "paired_err_sol", "common_error_corpus", "conversation_state"} or link_intent != "none":
        hybrid_retrieval_profile = "meta_first_hybrid_required"

    memory_write_profile = "none"
    if memory_mode in {"write", "update"}:
        memory_write_profile = "context_complete_required"
    if record_intent in {
        "explicit_user_request",
        "explicit_conversation_memory_request",
        "explicit_cross_conversation_update",
    }:
        memory_write_profile = "strict_capsule_required"

    def has_any(triggers: list[str]) -> bool:
        return bool(_matching_triggers(task_text, triggers))

    read_semantic_boundary: list[str] = []
    if has_any(["continue this conversation", "resume", "handoff", "context compression", "open loops", "current goal", "global goal", "接续", "继续上一段", "上下文压缩", "任务源头", "当前目标", "全局目标", "交接", "未完成事项"]):
        read_semantic_boundary.append("continuity_goal")
    if has_any(["exact anchor", "exact wording", "DOI", "commit hash", "hash", "tag", "version marker", "lane id", "path", "精确锚点", "原文", "准确字面", "版本标记", "路径", "哈希", "标签"]):
        read_semantic_boundary.append("exact_anchor")
    if has_any(["command log", "tool log", "execution log", "error output", "actually ran", "whether I ran", "whether you ran", "skipped", "self-report", "命令日志", "工具日志", "执行日志", "错误输出", "是否真的运行", "是否执行", "尝试过", "跳过", "事后描述"]):
        read_semantic_boundary.append("execution_trace")
    if has_any(["PDF", "HTML", "README", "release", "artifact", "final output", "compiled output", "test output", "diff", "最终输出", "编译产物", "发布产物", "测试输出", "公开文档"]):
        read_semantic_boundary.append("output_truth")
    if link_intent != "none" or has_any(["cross lane", "cross project", "merge memory", "backfill", "archive memory", "cold lane", "backup snapshot", "lane ownership", "跨 lane", "跨项目", "合并记忆", "链接记忆", "归属", "回填", "归档记忆", "备份快照", "隔离互联"]):
        read_semantic_boundary.append("cross_boundary")
    if has_any(["source validity", "source dependency", "official source", "authority", "conflict", "supersede", "retracted", "external evidence", "源证据", "来源依赖", "官方", "权威", "冲突", "覆盖旧", "失效", "撤回", "外部证据"]):
        read_semantic_boundary.append("source_validity")
    if has_any(["causal", "causality", "prove", "proves", "cause", "causes", "long-term", "global effect", "hallucination drift", "validated causality", "future similar cases", "similar future events", "recurrence risk", "prevent similar recurrence", "因果", "证明", "导致", "长期降低", "长期提升", "全局效果", "全局问题", "系统性问题", "后续可能", "后续同类", "同类事件", "类似事件", "复发风险", "预防同类", "幻觉漂移", "能力变化"]):
        read_semantic_boundary.append("causal_scope")
    if has_any(["modify", "update", "fix", "patch", "sync", "adapt", "rewrite", "delete", "remove", "configure", "AGENTS", "router", "policy", "修改", "更新", "修复", "补丁", "同步", "适配", "重写", "删除", "移除", "配置"]):
        read_semantic_boundary.append("change_integrity")
    debt_hygiene_profile_hits = _matching_triggers(
        task_text,
        ["contamination", "pollution", "technical debt", "dirty tree debt", "cleanup grouping", "memory pollution", "target pollution", "污染", "记忆污染", "目标污染", "技术债", "脏树债", "清查分组", "候选技术债"],
    )
    if debt_hygiene_profile_hits:
        read_semantic_boundary.append("contamination_or_debt")
    if not read_semantic_boundary and (memory_need != "none" or target_surface in {"project_memory", "conversation_ledger", "skill_matrix", "local_harness"}):
        read_semantic_boundary.append("orientation")
    read_semantic_boundary = _unique(read_semantic_boundary)

    read_depth_profile = "none"
    if "contamination_or_debt" in read_semantic_boundary and has_any(["full audit", "full lane", "migration", "backfill", "cleanup", "全量审计", "全面审计", "全 lane", "迁移", "回填", "清查", "清理"]):
        read_depth_profile = "full_lane_audit"
    elif "source_validity" in read_semantic_boundary or "causal_scope" in read_semantic_boundary:
        read_depth_profile = "source_cascade_review"
    elif "cross_boundary" in read_semantic_boundary:
        read_depth_profile = "cross_lane_link_review"
    elif "output_truth" in read_semantic_boundary:
        read_depth_profile = "artifact_output_window"
    elif "execution_trace" in read_semantic_boundary or "exact_anchor" in read_semantic_boundary:
        read_depth_profile = "raw_context_window"
    elif "change_integrity" in read_semantic_boundary:
        read_depth_profile = "artifact_output_window"
    elif "continuity_goal" in read_semantic_boundary:
        read_depth_profile = "segment_window"
    elif "orientation" in read_semantic_boundary:
        read_depth_profile = "capsule_only"

    edit_operation_profile = "none"
    read_only_task = has_any(["read-only", "readonly", "inspect only", "check only", "do not modify", "do not execute", "report only", "只读", "只检查", "不要修改", "不修改", "不要执行", "不执行", "先检查"])
    disk_delete_match = re.search(r"(?i)(删除|移除|清理|delete|remove).{0,48}(文件夹|目录|folder|directory|file|文件|旧\s*release|release\s*folder)|\brm\s+-rf\b|Remove-Item", task_text)
    disk_delete_requested = bool(disk_delete_match and not _is_negated(task_text, disk_delete_match.start()))
    record_delete_match = re.search(r"(?i)(删掉|删除|移除|去掉|remove|delete).{0,48}(段|描述|行|条目|内容|字段|section|paragraph|line|entry|README\s+中)", task_text)
    record_delete_requested = bool(record_delete_match and not _is_negated(task_text, record_delete_match.start()))
    full_rewrite_requested = bool(re.search(r"(?i)(完全|整个|整份|全部|全量).{0,24}(重写|rewrite|replace|rebuild|重新生成)|full\s+rewrite|rewrite\s+the\s+whole|replace\s+the\s+whole", task_text))
    append_requested = has_any(["append", "append-only", "append delta", "ledger", "jsonl", "changelog", "context backup", "execution log", "追加", "追加写入", "上下文备份", "执行日志", "对话账本", "变更日志"])
    add_new_requested = has_any(["create new file", "add new file", "new artifact", "新增文件", "新建文件", "创建新文件", "新增产物"])
    supersede_requested = has_any(["supersede", "superseded", "replace while preserving", "替代并保留", "覆盖旧说法", "标记为 superseded"])
    archive_requested = has_any(["archive", "move to archive", "quarantine", "归档", "移动到归档", "隔离放入", "冷归档"])
    section_replace_requested = has_any(["section replace", "replace section", "replace paragraph", "小节替换", "替换这一段", "替换这段", "段落替换"])
    in_place_patch_requested = has_any(["update", "modify", "fix", "patch", "sync", "adapt", "optimize", "edit", "更新", "修改", "修复", "补丁", "同步", "适配", "优化", "改进"])
    if disk_delete_requested:
        edit_operation_profile = "delete_from_disk"
    elif record_delete_requested:
        edit_operation_profile = "delete_record_content"
    elif full_rewrite_requested:
        edit_operation_profile = "full_rewrite"
    elif append_requested:
        edit_operation_profile = "append_delta"
    elif add_new_requested:
        edit_operation_profile = "add_new_artifact"
    elif supersede_requested:
        edit_operation_profile = "supersede_with_link"
    elif archive_requested and not read_only_task:
        edit_operation_profile = "archive_or_move"
    elif section_replace_requested:
        edit_operation_profile = "section_replace"
    elif in_place_patch_requested or risk_level == "R3":
        edit_operation_profile = "in_place_patch"
    elif read_only_task or risk_level == "R1":
        edit_operation_profile = "read_only"

    if read_semantic_boundary:
        matched_risk_triggers["read_semantic_boundary"] = read_semantic_boundary
    if read_depth_profile != "none":
        matched_risk_triggers["read_depth_profile"] = [read_depth_profile]
    if edit_operation_profile != "none":
        matched_risk_triggers["edit_operation_profile"] = [edit_operation_profile]

    if self_reflection_record_hits or common_error_hits:
        required_skills.append("troubleshooting-skill-matrix")

    skill_lifecycle_profile = "none"
    skill_listing_hits = _matching_triggers(
        task_text,
        ["skill listing", "skill list", "available skills", "skills list", "skill 清单", "技能清单"],
    )
    skill_active_frame_hits = _matching_triggers(
        task_text,
        ["skill", "SKILL.md", "skill matrix", "semantic anchor", "技能", "技能矩阵", "语义锚点"],
    )
    skill_release_receipt_hits = _matching_triggers(
        task_text,
        [
            "skill release receipt",
            "release receipt",
            "skill ttl",
            "active frame ttl",
            "release skill",
            "clear skill body",
            "调用周期",
            "释放回执",
            "激活帧",
            "用完释放",
            "清理大正文",
        ],
    )
    skill_reactivate_hits = _matching_triggers(
        task_text,
        ["reactivate skill", "reactivate from receipt", "resume skill", "resume from skill receipt", "重新激活", "恢复入口", "从回执恢复"],
    )
    if skill_listing_hits:
        skill_lifecycle_profile = "listing_only"
    if target_surface == "skill_matrix" or required_skills or skill_active_frame_hits:
        skill_lifecycle_profile = "active_frame_required"
    if skill_release_receipt_hits:
        skill_lifecycle_profile = "release_receipt_required"
    if skill_reactivate_hits:
        skill_lifecycle_profile = "reactivate_from_receipt"

    tool_surface_need = "none"
    tool_discovery_status = "not_needed"
    skill_or_tool_need = "none"
    plugin_need = "none"
    preferred_call_surface = "none"
    tool_surface_reason: list[str] = []
    tool_surface_groups = contract.get("tool_surface_trigger_groups", {})
    explicit_tool_surface_hits = _matching_triggers(
        task_text,
        [
            "@github",
            "@browser",
            "@chrome",
            "@nvidia",
            "@hugging-face",
            "@vercel",
            "@gmail",
            "@slack",
            "@canva",
            "plugin://",
            "app://",
            "tool_search",
            "MCP",
            "connector",
            "plugin",
            "插件",
            "连接器",
        ],
    )
    github_plugin_hits = _matching_triggers(task_text, tool_surface_groups.get("github_plugin", []))
    platform_plugin_hits = _matching_triggers(task_text, tool_surface_groups.get("platform_plugin", []))
    codex_native_skill_hits = _matching_triggers(task_text, tool_surface_groups.get("codex_native_skill", []))
    browser_surface_hits = _matching_triggers(task_text, tool_surface_groups.get("browser_surface", []))
    if explicit_tool_surface_hits or github_plugin_hits or platform_plugin_hits:
        tool_surface_need = "plugin_mcp"
        skill_or_tool_need = "mcp_or_app_tool"
        preferred_call_surface = "plugin_or_connector"
        if explicit_tool_surface_hits:
            plugin_need = "user_named"
            tool_discovery_status = "user_named"
            tool_surface_reason.append("explicit_plugin_or_connector")
        else:
            plugin_need = "candidate_discovery_required"
            tool_discovery_status = "not_checked"
            tool_surface_reason.append("platform_object_without_explicit_tool")
    if codex_native_skill_hits:
        if tool_surface_need != "none":
            tool_surface_need = "multiple"
        else:
            tool_surface_need = "native_skill"
            tool_discovery_status = "not_checked"
            preferred_call_surface = "native_skill"
        skill_or_tool_need = "codex_native_skill"
        tool_surface_reason.append("codex_native_skill_candidate")
    if browser_surface_hits:
        if tool_surface_need != "none":
            tool_surface_need = "multiple"
        else:
            tool_surface_need = "browser"
            tool_discovery_status = "not_checked"
        skill_or_tool_need = "mcp_or_app_tool"
        preferred_call_surface = "browser_or_chrome"
        tool_surface_reason.append("browser_or_chrome_candidate")
    if target_surface == "tool_call" and tool_surface_need == "none":
        tool_surface_need = "shell"
        skill_or_tool_need = "shell_or_local_tool"
        preferred_call_surface = "shell"
        tool_surface_reason.append("local_tool_or_shell_surface")
    if tool_discovery_status in {"not_checked", "user_named"}:
        required_gates.append("tool_surface_discovery_gate")
    tool_surface_reason = _unique(tool_surface_reason)

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
    if required_skills or target_surface == "skill_matrix" or skill_lifecycle_profile != "none":
        module_need.append("skill_matrix")
    if semantic_ambiguity:
        module_need.append("semantic_anchors")
    if memory_need != "none":
        module_need.append("memory_meta_index")
    if static_knowledge_hits:
        module_need.append("static_knowledge_index")
    if target_surface == "conversation_ledger":
        module_need.append("conversation_ledger_index")
    if conversation_memory_decision != "none":
        module_need.append("conversation_memory_index")
    if link_intent != "none":
        module_need.append("memory_link_ledger")
    if tool_discovery_status in {"not_checked", "user_named"}:
        module_need.append("tool_surface_discovery")
    if external_need and external_need[0] != "none":
        module_need.append("external_research_gate")
    if claim_risk != "none":
        module_need.append("claim_schema_verifier")
    if risk_level == "R5" or classification_confidence == "low":
        module_need.append("runtime_gate")
    if not module_need:
        module_need.append("none")
    module_need = _unique(module_need)

    action_bindings: list[dict[str, str]] = []
    if memory_need != "none":
        action_bindings.append(
            {
                "action": "retrieve_matching_memory",
                "completion_evidence": "selected_record_id_and_provenance",
            }
        )
    if external_need and external_need[0] != "none":
        action_bindings.append(
            {
                "action": "perform_external_research_route",
                "completion_evidence": "source_ledger_or_citations",
            }
        )
    action_binding_ids = [item["action"] for item in action_bindings]

    memory_source_hints: list[dict[str, str]] = []
    if memory_need != "none" and has_active_conversation_memory_lane:
        memory_source_hints.append(
            {
                "lane": "current_conversation",
                "root_path": active_conversation_memory_lane_path,
                "meta_path": str(Path(active_conversation_memory_lane_path) / "_META_INDEX.md"),
                "isolation": "exact_active_conversation_lane",
            }
        )
    if memory_need != "none" and lane != "PROJECTLESS":
        for root in _as_list(policy.get("memory_roots", {}).get(lane)):
            if not str(root):
                continue
            memory_source_hints.append(
                {
                    "lane": "current_project",
                    "root_path": str(root),
                    "meta_path": str(Path(str(root)) / "_META_INDEX.md"),
                    "isolation": "registered_project_lane_root",
                }
            )

    receipt_profile = "compact_runtime"
    profile_reason = ["default_compact_runtime"]
    debug_hits = _matching_triggers(task_text, policy.get("receipt_profiles", {}).get("debug_triggers", []))
    if debug_hits:
        receipt_profile = "debug_receipt"
        profile_reason.append("debug_requested")
    else:
        if target_surface in {"public_docs", "local_harness", "project_memory", "conversation_ledger", "skill_matrix", "adapter", "private_rule"}:
            profile_reason.append("governance_surface")
        if audience in {"public_user", "local_maintainer"}:
            profile_reason.append("audience_boundary")
        if semantic_ambiguity:
            profile_reason.append("semantic_ambiguity")
        if skill_lifecycle_profile != "none":
            profile_reason.append("skill_lifecycle")
        if memory_mode in {"write", "update"} or record_intent != "no_record":
            profile_reason.append("memory_write_or_record")
        if projectization_decision == "emergent_project_candidate":
            profile_reason.append("projectization_candidate")
        if conversation_memory_decision != "none":
            profile_reason.append("conversation_memory_candidate")
        if link_intent != "none":
            profile_reason.append("conversation_link_boundary")
        if len(profile_reason) > 1:
            receipt_profile = "extended_governance"
    profile_reason = _unique(profile_reason)

    required_gates_out = _unique(required_gates)
    human_confirmation_need = bool(_unique(approval_required))
    routing_receipt = {
        "task_type": risk_level,
        "target_surface": target_surface,
        "audience": audience,
        "project_lane": lane,
        "risk_level": risk_level,
        "semantic_ambiguity": semantic_ambiguity,
        "module_need": module_need,
        "tool_surface_need": tool_surface_need,
        "tool_discovery_status": tool_discovery_status,
        "skill_or_tool_need": skill_or_tool_need,
        "plugin_need": plugin_need,
        "preferred_call_surface": preferred_call_surface,
        "tool_surface_reason": tool_surface_reason,
        "skill_lifecycle_profile": skill_lifecycle_profile,
        "skill_audit_profile": skill_audit_profile,
        "skill_audit_signals": skill_audit_signals,
        "feedback_loop_profile": feedback_loop_profile,
        "first_principles_profile": first_principles_profile,
        "first_principles_signals": first_principles_signals,
        "read_semantic_boundary": read_semantic_boundary,
        "read_depth_profile": read_depth_profile,
        "edit_operation_profile": edit_operation_profile,
        "memory_need": memory_need,
        "hybrid_retrieval_profile": hybrid_retrieval_profile,
        "memory_mode": memory_mode,
        "memory_write_profile": memory_write_profile,
        "memory_lane": memory_lane,
        "memory_source_hints": memory_source_hints,
        "action_bindings": action_bindings,
        "record_intent": record_intent,
        "external_need": external_need,
        "claim_risk": claim_risk,
        "projectization_decision": projectization_decision,
        "conversation_memory_decision": conversation_memory_decision,
        "link_intent": link_intent,
        "conversation_signals": _unique(conversation_explicit_hits + conversation_signals),
        "conversation_full_lane_triggered": conversation_full_lane_triggered,
        "conversation_full_lane_groups": conversation_full_lane_groups,
        "receipt_profile": receipt_profile,
        "projectization_signals": projectization_signals,
        "required_gates": required_gates_out,
    }
    compact_receipt = {
        "task_type": risk_level,
        "risk_level": risk_level,
        "required_gates": required_gates_out,
        "tool_surface_need": tool_surface_need,
        "tool_discovery_status": tool_discovery_status,
        "skill_or_tool_need": skill_or_tool_need,
        "plugin_need": plugin_need,
        "preferred_call_surface": preferred_call_surface,
        "skill_lifecycle_profile": skill_lifecycle_profile,
        "skill_audit_profile": skill_audit_profile,
        "feedback_loop_profile": feedback_loop_profile,
        "first_principles_profile": first_principles_profile,
        "read_semantic_boundary": read_semantic_boundary,
        "read_depth_profile": read_depth_profile,
        "edit_operation_profile": edit_operation_profile,
        "memory_mode": memory_mode,
        "hybrid_retrieval_profile": hybrid_retrieval_profile,
        "memory_write_profile": memory_write_profile,
        "memory_lane": memory_lane,
        "memory_source_hints": memory_source_hints,
        "action_binding_ids": action_binding_ids,
        "conversation_memory_decision": conversation_memory_decision,
        "conversation_full_lane_triggered": conversation_full_lane_triggered,
        "link_intent": link_intent,
        "external_need": external_need,
        "claim_risk": claim_risk,
        "human_confirmation_need": human_confirmation_need,
    }

    return {
        "ts": _now(),
        "phase": "intake_router",
        "status": "pass",
        "cwd": cwd,
        "routing_receipt": routing_receipt,
        "compact_receipt": compact_receipt,
        "receipt_profile": receipt_profile,
        "profile_reason": profile_reason,
        "target_surface": target_surface,
        "audience": audience,
        "project_lane": lane,
        "risk_level": risk_level,
        "semantic_ambiguity": semantic_ambiguity,
        "module_need": module_need,
        "tool_surface_need": tool_surface_need,
        "tool_discovery_status": tool_discovery_status,
        "skill_or_tool_need": skill_or_tool_need,
        "plugin_need": plugin_need,
        "preferred_call_surface": preferred_call_surface,
        "tool_surface_reason": tool_surface_reason,
        "skill_lifecycle_profile": skill_lifecycle_profile,
        "skill_audit_profile": skill_audit_profile,
        "skill_audit_signals": skill_audit_signals,
        "feedback_loop_profile": feedback_loop_profile,
        "first_principles_profile": first_principles_profile,
        "first_principles_signals": first_principles_signals,
        "read_semantic_boundary": read_semantic_boundary,
        "read_depth_profile": read_depth_profile,
        "edit_operation_profile": edit_operation_profile,
        "memory_need": memory_need,
        "hybrid_retrieval_profile": hybrid_retrieval_profile,
        "memory_mode": memory_mode,
        "memory_write_profile": memory_write_profile,
        "memory_lane": memory_lane,
        "memory_source_hints": memory_source_hints,
        "action_bindings": action_bindings,
        "action_binding_ids": action_binding_ids,
        "record_intent": record_intent,
        "external_need": external_need,
        "claim_risk": claim_risk,
        "projectization_decision": projectization_decision,
        "conversation_memory_decision": conversation_memory_decision,
        "link_intent": link_intent,
        "projectization_signals": projectization_signals,
        "conversation_signals": _unique(conversation_explicit_hits + conversation_signals),
        "conversation_full_lane_triggered": conversation_full_lane_triggered,
        "conversation_full_lane_groups": conversation_full_lane_groups,
        "triggered_risks": sorted(set(triggered_risks), key=triggered_risks.index),
        "matched_risk_triggers": matched_risk_triggers,
        "negated_risk_triggers": negated_risk_triggers,
        "risk_candidates": risk_candidates,
        "risk_context_decisions": risk_context_decisions,
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

    contract = policy.get("claim_schema_contract", {})
    allowed_source_types = {_contract_token(item) for item in _as_list(contract.get("allowed_source_types"))}
    source_ref_required_for = {_contract_token(item) for item in _as_list(contract.get("source_ref_required_for"))}
    allowed_evidence_boundaries = {_contract_token(item) for item in _as_list(contract.get("evidence_boundary_enum"))}
    strong_evidence_boundaries = {
        _contract_token(item) for item in _as_list(contract.get("strong_claim_evidence_boundaries"))
    }

    for claim in claims:
        if not isinstance(claim, dict):
            issues.append("claim_not_object")
            continue
        for field in ("claim_type", "source_type", "evidence_boundary"):
            if not str(claim.get(field, "")).strip():
                issues.append(f"missing_{field}")
        source_type = _contract_token(claim.get("source_type", ""))
        evidence_boundary = _contract_token(claim.get("evidence_boundary", ""))
        if allowed_source_types and source_type not in allowed_source_types:
            issues.append(f"unsupported_source_type:{claim.get('source_type', '')}")
        if allowed_evidence_boundaries and evidence_boundary not in allowed_evidence_boundaries:
            issues.append(f"unsupported_evidence_boundary:{claim.get('evidence_boundary', '')}")
        if source_type in source_ref_required_for and not str(claim.get("source_ref", "")).strip():
            issues.append(f"missing_source_ref_for_{source_type}")

    if final_text:
        for phrase in _as_list(policy.get("blocked_claim_phrases_without_schema")):
            if str(phrase) in final_text:
                if not claims:
                    issues.append(f"blocked_claim_phrase_without_schema:{phrase}")
                    continue
                if strong_evidence_boundaries and not any(
                    _contract_token(claim.get("evidence_boundary", "")) in strong_evidence_boundaries
                    for claim in claims
                    if isinstance(claim, dict)
                ):
                    issues.append(f"insufficient_evidence_boundary_for_strong_phrase:{phrase}")
        causal_result = causal_attribution_gate(final_text=final_text, policy=policy)
        if causal_result["status"] != "pass":
            issues.extend(str(issue) for issue in causal_result["issues"])

    return {
        "ts": _now(),
        "phase": "claim_schema_verifier",
        "status": "blocked" if issues else "pass",
        "claims_checked": len(claims),
        "issues": sorted(set(issues)),
        "rule": "schema enum, evidence-boundary, and high-risk causal attribution pattern check only; no extra LLM judgment",
    }
