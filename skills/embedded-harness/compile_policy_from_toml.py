#!/usr/bin/env python3
"""Compile selected human-authored TOML policy sections into policy JSON.

Direct advisory consumers read embedded_harness_policy.json. This helper is an
offline maintenance tool for high-churn sections only.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_AUTHORING = SCRIPT_DIR / "embedded_harness_policy.authoring.toml"
DEFAULT_POLICY = SCRIPT_DIR / "embedded_harness_policy.json"

R5_CONTEXT_FIELDS = [
    "direct_action_terms",
    "explicit_action_phrases",
    "explicit_action_negation_phrases",
    "context_required_candidate_terms",
    "always_action_candidate_terms",
    "action_context_terms",
    "non_action_context_terms",
    "documentation_context_terms",
]

R3_CONTEXT_FIELDS = [
    "diagnostic_intent_terms",
    "explicit_mutation_phrases",
    "strong_mutation_terms",
]

TRACKED_PATHS: list[tuple[str, ...]] = [
    ("risk_trigger_rules", "R5"),
    ("r5_context_decision_rules",),
    ("r3_context_decision_rules",),
    ("router_decision_contract", "receipt_fields"),
    ("router_decision_contract", "observation_scope_triggers"),
    ("router_decision_contract", "feedback_loop_triggers"),
    ("router_decision_contract", "feedback_loop_profile_rule"),
    ("router_decision_contract", "common_error_prevention_triggers"),
    ("router_decision_contract", "harness_governance_recall_triggers"),
    ("router_decision_contract", "reflexive_gap_contract"),
    ("router_decision_contract", "action_binding_contract"),
    ("router_decision_contract", "correction_lifecycle_contract"),
    ("router_decision_contract", "explicit_record_triggers"),
    ("router_decision_contract", "conversation_lane_declaration_triggers"),
    ("router_decision_contract", "causal_attribution_contract"),
    ("router_decision_contract", "causal_attribution_triggers"),
    ("router_decision_contract", "issue_prevention_gates"),
    ("router_decision_contract", "conversation_memory_full_lane_triggers"),
    ("runtime_enforcement", "behavior_correction_contract"),
]


def _load_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"JSON policy root must be an object: {path}")
    return parsed


def _load_toml(path: Path) -> dict[str, Any]:
    parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"TOML authoring root must be an object: {path}")
    if parsed.get("schema_version") != "cbh.policy_authoring.v1":
        raise ValueError("unsupported or missing schema_version")
    return parsed


def _string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{path} must be a non-empty string array")
    return list(value)


def _get_path(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set_path(payload: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = payload
    for part in path[:-1]:
        next_value = current.setdefault(part, {})
        if not isinstance(next_value, dict):
            raise ValueError(f"cannot set {'.'.join(path)} because {part} is not an object")
        current = next_value
    current[path[-1]] = value


def _normal_risk_trigger_rules(authoring: dict[str, Any]) -> dict[str, Any] | None:
    rules = authoring.get("risk_trigger_rules")
    if rules is None:
        return None
    if not isinstance(rules, dict):
        raise ValueError("risk_trigger_rules must be a table")
    normalized: dict[str, Any] = {}
    for risk, value in rules.items():
        if not isinstance(value, dict):
            raise ValueError(f"risk_trigger_rules.{risk} must be a table")
        normalized[str(risk)] = {
            lang: _string_list(items, f"risk_trigger_rules.{risk}.{lang}")
            for lang, items in value.items()
        }
    return normalized


def _normal_r5_context(authoring: dict[str, Any]) -> dict[str, Any] | None:
    rules = authoring.get("r5_context_decision_rules")
    if rules is None:
        return None
    if not isinstance(rules, dict):
        raise ValueError("r5_context_decision_rules must be a table")
    missing = [field for field in R5_CONTEXT_FIELDS if field not in rules]
    if missing:
        raise ValueError("r5_context_decision_rules missing fields: " + ", ".join(missing))
    return {field: _string_list(rules[field], f"r5_context_decision_rules.{field}") for field in R5_CONTEXT_FIELDS}


def _normal_r3_context(authoring: dict[str, Any]) -> dict[str, Any] | None:
    rules = authoring.get("r3_context_decision_rules")
    if rules is None:
        return None
    if not isinstance(rules, dict):
        raise ValueError("r3_context_decision_rules must be a table")
    missing = [field for field in R3_CONTEXT_FIELDS if field not in rules]
    if missing:
        raise ValueError("r3_context_decision_rules missing fields: " + ", ".join(missing))
    return {field: _string_list(rules[field], f"r3_context_decision_rules.{field}") for field in R3_CONTEXT_FIELDS}


def _normal_full_lane(authoring: dict[str, Any]) -> dict[str, Any] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    config = router.get("conversation_memory_full_lane_triggers")
    if config is None:
        return None
    if not isinstance(config, dict):
        raise ValueError("conversation_memory_full_lane_triggers must be a table")
    groups = config.get("threshold_groups")
    if not isinstance(groups, dict) or not groups:
        raise ValueError("conversation_memory_full_lane_triggers.threshold_groups must be a non-empty table")

    normalized_groups: dict[str, Any] = {}
    for name, group in groups.items():
        if not isinstance(group, dict):
            raise ValueError(f"threshold group {name} must be a table")
        threshold = group.get("threshold")
        if not isinstance(threshold, int) or threshold < 1:
            raise ValueError(f"threshold group {name} must have threshold >= 1")
        normalized_groups[str(name)] = {
            "threshold": threshold,
            "triggers": _string_list(group.get("triggers"), f"threshold_groups.{name}.triggers"),
        }

    decision_rule = config.get("decision_rule")
    if not isinstance(decision_rule, str) or not decision_rule:
        raise ValueError("conversation_memory_full_lane_triggers.decision_rule must be a non-empty string")
    return {"decision_rule": decision_rule, "threshold_groups": normalized_groups}


def _normal_causal_attribution_contract(authoring: dict[str, Any]) -> dict[str, Any] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    contract = router.get("causal_attribution_contract")
    if contract is None:
        return None
    if not isinstance(contract, dict):
        raise ValueError("causal_attribution_contract must be a table")
    return {
        "purpose": str(contract.get("purpose") or ""),
        "required_distinctions": _string_list(
            contract.get("required_distinctions"), "causal_attribution_contract.required_distinctions"
        ),
        "default_status": str(contract.get("default_status") or "causal_hypothesis"),
        "rule": str(contract.get("rule") or ""),
        "exclusion": str(contract.get("exclusion") or ""),
    }


def _normal_observation_scope_triggers(authoring: dict[str, Any]) -> list[str] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    triggers = router.get("observation_scope_triggers")
    if triggers is None:
        return None
    return _string_list(triggers, "router_decision_contract.observation_scope_triggers")


def _normal_receipt_fields(authoring: dict[str, Any]) -> list[str] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    fields = router.get("receipt_fields")
    if fields is None:
        return None
    return _string_list(fields, "router_decision_contract.receipt_fields")


def _normal_feedback_loop_triggers(authoring: dict[str, Any]) -> list[str] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    triggers = router.get("feedback_loop_triggers")
    if triggers is None:
        return None
    return _string_list(triggers, "router_decision_contract.feedback_loop_triggers")


def _normal_feedback_loop_profile_rule(authoring: dict[str, Any]) -> str | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    rule = router.get("feedback_loop_profile_rule")
    if rule is None:
        return None
    if not isinstance(rule, str) or not rule.strip():
        raise ValueError("router_decision_contract.feedback_loop_profile_rule must be a non-empty string")
    return rule


def _normal_common_error_prevention_triggers(authoring: dict[str, Any]) -> list[str] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    triggers = router.get("common_error_prevention_triggers")
    if triggers is None:
        return None
    return _string_list(triggers, "router_decision_contract.common_error_prevention_triggers")


def _normal_harness_governance_recall_triggers(authoring: dict[str, Any]) -> list[str] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    triggers = router.get("harness_governance_recall_triggers")
    if triggers is None:
        return None
    return _string_list(triggers, "router_decision_contract.harness_governance_recall_triggers")


def _normal_action_binding_contract(authoring: dict[str, Any]) -> dict[str, Any] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    contract = router.get("action_binding_contract")
    if contract is None:
        return None
    if not isinstance(contract, dict):
        raise ValueError("action_binding_contract must be a table")
    soft_predictions = contract.get("soft_target_prediction_reviews")
    soft_actions = contract.get("soft_target_next_actions")
    if not isinstance(soft_predictions, int) or not 1 <= soft_predictions <= 12:
        raise ValueError("action_binding_contract.soft_target_prediction_reviews must be between 1 and 12")
    if not isinstance(soft_actions, int) or not 1 <= soft_actions <= 32:
        raise ValueError("action_binding_contract.soft_target_next_actions must be between 1 and 32")
    if contract.get("coverage_expansion_allowed") is not True:
        raise ValueError("action_binding_contract.coverage_expansion_allowed must be true")
    return {
        "enabled": bool(contract.get("enabled", True)),
        "binding_mode": str(contract.get("binding_mode") or "inline_receipt_no_extra_tool_call"),
        "soft_target_prediction_reviews": soft_predictions,
        "soft_target_next_actions": soft_actions,
        "coverage_expansion_allowed": True,
        "profile_values": _string_list(contract.get("profile_values"), "action_binding_contract.profile_values"),
        "prediction_review_profile_values": _string_list(
            contract.get("prediction_review_profile_values"),
            "action_binding_contract.prediction_review_profile_values",
        ),
        "prediction_review_source_fields": _string_list(
            contract.get("prediction_review_source_fields"),
            "action_binding_contract.prediction_review_source_fields",
        ),
        "next_action_values": _string_list(
            contract.get("next_action_values"), "action_binding_contract.next_action_values"
        ),
        "completion_evidence_values": _string_list(
            contract.get("completion_evidence_values"),
            "action_binding_contract.completion_evidence_values",
        ),
        "rule": str(contract.get("rule") or ""),
    }


def _normal_correction_lifecycle_contract(
    authoring: dict[str, Any],
) -> dict[str, Any] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    contract = router.get("correction_lifecycle_contract")
    if contract is None:
        return None
    if not isinstance(contract, dict):
        raise ValueError("correction_lifecycle_contract must be a table")
    if contract.get("enabled") is not True:
        raise ValueError("correction_lifecycle_contract.enabled must be true")
    if contract.get("schema") != "cbh.correction_lifecycle_contract.v1":
        raise ValueError("correction_lifecycle_contract.schema is unsupported")
    objective_order = _string_list(
        contract.get("objective_order"),
        "correction_lifecycle_contract.objective_order",
    )
    if objective_order != [
        "real_effectiveness_and_required_components",
        "minimum_sufficient_implementation",
        "execution_time_and_token_efficiency",
        "surface_simplicity",
    ]:
        raise ValueError("correction_lifecycle_contract.objective_order mismatch")
    stages = _string_list(
        contract.get("stages"),
        "correction_lifecycle_contract.stages",
    )
    decision_modes = _string_list(
        contract.get("decision_modes"),
        "correction_lifecycle_contract.decision_modes",
    )
    if set(decision_modes) != {
        "auto_rewrite",
        "preflight_validate",
        "predictive_review",
        "no_match",
    }:
        raise ValueError("correction_lifecycle_contract.decision_modes mismatch")
    interaction_triggers = contract.get("interaction_surface_triggers")
    if not isinstance(interaction_triggers, dict):
        raise ValueError(
            "correction_lifecycle_contract.interaction_surface_triggers must be a table"
        )
    normalized_triggers = {
        name: _string_list(
            interaction_triggers.get(name),
            f"correction_lifecycle_contract.interaction_surface_triggers.{name}",
        )
        for name in ("structured_tool", "browser", "desktop_app", "keyboard_mouse")
    }
    normalized = copy.deepcopy(contract)
    normalized["objective_order"] = objective_order
    normalized["stages"] = stages
    normalized["decision_modes"] = decision_modes
    for field in (
        "source_lanes",
        "promotion_states",
        "interaction_action_binding_fields",
    ):
        normalized[field] = _string_list(
            contract.get(field),
            f"correction_lifecycle_contract.{field}",
        )
    normalized["interaction_surface_triggers"] = normalized_triggers
    return normalized


def _normal_reflexive_gap_contract(authoring: dict[str, Any]) -> dict[str, Any] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    contract = router.get("reflexive_gap_contract")
    if contract is None:
        return None
    if not isinstance(contract, dict):
        raise ValueError("reflexive_gap_contract must be a table")
    if contract.get("enabled") is not True:
        raise ValueError("reflexive_gap_contract.enabled must be true")
    expected_contract_fields = {
        "enabled",
        "required_gate",
        "semantic_marker",
        "explicit_request_triggers",
        "exclusion_triggers",
        "knowledge_action_groups",
        "goal_fidelity_groups",
        "counterevidence_groups",
        "knowledge_coverage_groups",
    }
    unexpected_contract_fields = sorted(set(contract) - expected_contract_fields)
    if unexpected_contract_fields:
        raise ValueError(
            "reflexive_gap_contract has unexpected fields: "
            + ", ".join(unexpected_contract_fields)
        )

    required_gate = contract.get("required_gate")
    semantic_marker = contract.get("semantic_marker")
    if not isinstance(required_gate, str) or not required_gate:
        raise ValueError("reflexive_gap_contract.required_gate must be a non-empty string")
    if not isinstance(semantic_marker, str) or not semantic_marker:
        raise ValueError("reflexive_gap_contract.semantic_marker must be a non-empty string")

    normalized: dict[str, Any] = {
        "enabled": True,
        "required_gate": required_gate,
        "semantic_marker": semantic_marker,
        "explicit_request_triggers": _string_list(
            contract.get("explicit_request_triggers"),
            "reflexive_gap_contract.explicit_request_triggers",
        ),
        "exclusion_triggers": _string_list(
            contract.get("exclusion_triggers"),
            "reflexive_gap_contract.exclusion_triggers",
        ),
    }
    for group_name, facet_names in {
        "knowledge_action_groups": ("knowledge", "execution", "contrast"),
        "goal_fidelity_groups": ("goal", "proxy_or_stall"),
        "counterevidence_groups": ("attribution", "unverified"),
        "knowledge_coverage_groups": ("unmodeled", "high_impact", "uncertainty"),
    }.items():
        group = contract.get(group_name)
        if not isinstance(group, dict):
            raise ValueError(f"reflexive_gap_contract.{group_name} must be a table")
        unexpected_group_fields = sorted(set(group) - set(facet_names))
        if unexpected_group_fields:
            raise ValueError(
                f"reflexive_gap_contract.{group_name} has unexpected fields: "
                + ", ".join(unexpected_group_fields)
            )
        normalized[group_name] = {
            facet_name: _string_list(
                group.get(facet_name),
                f"reflexive_gap_contract.{group_name}.{facet_name}",
            )
            for facet_name in facet_names
        }
    return normalized


def _normal_explicit_record_triggers(authoring: dict[str, Any]) -> list[str] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    triggers = router.get("explicit_record_triggers")
    if triggers is None:
        return None
    return _string_list(triggers, "router_decision_contract.explicit_record_triggers")


def _normal_conversation_lane_declaration_triggers(authoring: dict[str, Any]) -> list[str] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    triggers = router.get("conversation_lane_declaration_triggers")
    if triggers is None:
        return None
    return _string_list(triggers, "router_decision_contract.conversation_lane_declaration_triggers")


def _normal_referenced_conversation_memory_contract(
    authoring: dict[str, Any],
) -> dict[str, Any] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    contract = router.get("referenced_conversation_memory_contract")
    if contract is None:
        return None
    if not isinstance(contract, dict):
        raise ValueError(
            "router_decision_contract.referenced_conversation_memory_contract must be a table"
        )
    if contract.get("enabled") is not True:
        raise ValueError("referenced_conversation_memory_contract.enabled must be true")
    required_strings = (
        "registry_path",
        "registry_schema",
        "required_gate",
        "memory_need",
        "memory_lane",
        "conversation_memory_decision",
        "match_rule",
        "completion_rule",
    )
    normalized: dict[str, Any] = {"enabled": True}
    for field in required_strings:
        value = contract.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"referenced_conversation_memory_contract.{field} must be a non-empty string"
            )
        normalized[field] = value
    if Path(normalized["registry_path"]).name != normalized["registry_path"]:
        raise ValueError(
            "referenced_conversation_memory_contract.registry_path must be a local file name"
        )
    normalized["candidate_states"] = _string_list(
        contract.get("candidate_states"),
        "router_decision_contract.referenced_conversation_memory_contract.candidate_states",
    )
    max_candidates = int(contract.get("max_candidates") or 0)
    if max_candidates < 1 or max_candidates > 10:
        raise ValueError(
            "referenced_conversation_memory_contract.max_candidates must be between 1 and 10"
        )
    normalized["max_candidates"] = max_candidates
    return normalized


def _normal_causal_attribution_triggers(authoring: dict[str, Any]) -> dict[str, Any] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    triggers = router.get("causal_attribution_triggers")
    if triggers is None:
        return None
    if not isinstance(triggers, dict) or not triggers:
        raise ValueError("causal_attribution_triggers must be a non-empty table")
    return {
        str(name): _string_list(items, f"causal_attribution_triggers.{name}")
        for name, items in triggers.items()
    }


def _normal_issue_prevention_gates(authoring: dict[str, Any]) -> dict[str, Any] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    gates = router.get("issue_prevention_gates")
    if gates is None:
        return None
    if not isinstance(gates, dict) or not gates:
        raise ValueError("issue_prevention_gates must be a non-empty table")
    normalized: dict[str, Any] = {}
    for name, gate in gates.items():
        if not isinstance(gate, dict):
            raise ValueError(f"issue_prevention_gates.{name} must be a table")
        normalized[str(name)] = {
            "purpose": str(gate.get("purpose") or ""),
            "triggers": _string_list(gate.get("triggers"), f"issue_prevention_gates.{name}.triggers"),
        }
    return normalized


def _normal_behavior_correction_contract(
    authoring: dict[str, Any],
) -> dict[str, Any] | None:
    runtime = authoring.get("runtime_enforcement", {})
    if not isinstance(runtime, dict):
        raise ValueError("runtime_enforcement must be a table")
    contract = runtime.get("behavior_correction_contract")
    if contract is None:
        return None
    if not isinstance(contract, dict):
        raise ValueError("behavior_correction_contract must be a table")
    if contract.get("enabled") is not True:
        raise ValueError("behavior_correction_contract.enabled must be true")
    if contract.get("schema") != "cbh.behavior_correction_contract.v1":
        raise ValueError("behavior_correction_contract.schema is unsupported")
    retired_fields = {
        "first_match_enforcement",
        "repeat_match_enforcement",
        "verifier_unavailable_enforcement",
        "capacity_overflow_mode",
        "exact_target_unresolved_enforcement",
    }.intersection(contract)
    if retired_fields:
        raise ValueError(
            "behavior_correction_contract contains retired fields:"
            + ",".join(sorted(retired_fields))
        )
    registry_name = str(contract.get("profile_registry_path") or "")
    if registry_name != "behavior_correction_profiles.json":
        raise ValueError(
            "behavior_correction_contract.profile_registry_path is unsupported"
        )
    registry_path = SCRIPT_DIR / registry_name
    try:
        registry_bytes = registry_path.read_bytes()
        registry = json.loads(registry_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("behavior correction profile registry is unreadable") from exc
    if registry.get("schema") != "cbh.behavior_correction_profile_registry.v1":
        raise ValueError("behavior correction profile registry schema is unsupported")
    if contract.get("profile_registry_schema") != registry.get("schema"):
        raise ValueError("behavior_correction_contract.profile_registry_schema mismatch")
    for field in (
        "automatic_freeze",
        "automatic_long_term_memory_write",
        "automatic_policy_mutation",
    ):
        if contract.get(field) is not False:
            raise ValueError(f"behavior_correction_contract.{field} must be false")
    prohibited = set(contract.get("prohibited_auto_actions") or [])
    if prohibited != {"session_freeze", "long_term_memory_write", "policy_mutation"}:
        raise ValueError("behavior_correction_contract.prohibited_auto_actions mismatch")
    normalized = copy.deepcopy(contract)
    migration = normalized.get("migration_hook")
    if not isinstance(migration, dict) or migration.get("enabled") is not True:
        raise ValueError("behavior_correction_contract.migration_hook must be enabled")
    if migration.get("schema") != "cbh.behavior_correction_migration_hook.v1":
        raise ValueError("behavior_correction_contract.migration_hook schema is unsupported")
    if migration.get("hook_event") != "PreToolUse":
        raise ValueError("behavior_correction_contract.migration_hook event is unsupported")
    if migration.get("tool_name_matcher") != "^Bash$":
        raise ValueError("behavior_correction_contract.migration_hook matcher is unsupported")
    if migration.get("output_contract") != "allow_updated_input_only":
        raise ValueError("behavior_correction_contract.migration_hook output is unsupported")
    for field in (
        "host_blocking",
        "stateful",
        "automatic_memory_write",
        "automatic_policy_mutation",
    ):
        if migration.get(field) is not False:
            raise ValueError(
                f"behavior_correction_contract.migration_hook.{field} must be false"
            )
    entrypoint = str(migration.get("entrypoint") or "")
    if entrypoint != "behavior_correction_hook.py":
        raise ValueError("behavior_correction_contract.migration_hook entrypoint is unsupported")
    try:
        entrypoint_bytes = (SCRIPT_DIR / entrypoint).read_bytes()
    except OSError as exc:
        raise ValueError("behavior correction migration hook is unreadable") from exc
    migration["entrypoint_sha256"] = hashlib.sha256(entrypoint_bytes).hexdigest()
    normalized["profile_registry_sha256"] = hashlib.sha256(registry_bytes).hexdigest()
    return normalized


def compile_policy(base_policy: dict[str, Any], authoring: dict[str, Any]) -> dict[str, Any]:
    compiled = copy.deepcopy(base_policy)
    compiled.get("router_decision_contract", {}).pop(
        "referenced_conversation_memory_contract", None
    )
    compiled.get("runtime_enforcement", {}).pop(
        "dangerous_delete_advisory_contract", None
    )

    risk_rules = _normal_risk_trigger_rules(authoring)
    if risk_rules:
        for risk, value in risk_rules.items():
            _set_path(compiled, ("risk_trigger_rules", risk), value)

    r5_context = _normal_r5_context(authoring)
    if r5_context is not None:
        _set_path(compiled, ("r5_context_decision_rules",), r5_context)

    r3_context = _normal_r3_context(authoring)
    if r3_context is not None:
        _set_path(compiled, ("r3_context_decision_rules",), r3_context)

    receipt_fields = _normal_receipt_fields(authoring)
    if receipt_fields is not None:
        _set_path(compiled, ("router_decision_contract", "receipt_fields"), receipt_fields)

    observation_scope_triggers = _normal_observation_scope_triggers(authoring)
    if observation_scope_triggers is not None:
        _set_path(compiled, ("router_decision_contract", "observation_scope_triggers"), observation_scope_triggers)

    feedback_loop_triggers = _normal_feedback_loop_triggers(authoring)
    if feedback_loop_triggers is not None:
        _set_path(compiled, ("router_decision_contract", "feedback_loop_triggers"), feedback_loop_triggers)

    feedback_loop_profile_rule = _normal_feedback_loop_profile_rule(authoring)
    if feedback_loop_profile_rule is not None:
        _set_path(
            compiled,
            ("router_decision_contract", "feedback_loop_profile_rule"),
            feedback_loop_profile_rule,
        )

    common_error_prevention_triggers = _normal_common_error_prevention_triggers(authoring)
    if common_error_prevention_triggers is not None:
        _set_path(
            compiled,
            ("router_decision_contract", "common_error_prevention_triggers"),
            common_error_prevention_triggers,
        )

    harness_governance_recall_triggers = _normal_harness_governance_recall_triggers(authoring)
    if harness_governance_recall_triggers is not None:
        _set_path(
            compiled,
            ("router_decision_contract", "harness_governance_recall_triggers"),
            harness_governance_recall_triggers,
        )

    reflexive_gap_contract = _normal_reflexive_gap_contract(authoring)
    if reflexive_gap_contract is not None:
        _set_path(
            compiled,
            ("router_decision_contract", "reflexive_gap_contract"),
            reflexive_gap_contract,
        )

    action_binding_contract = _normal_action_binding_contract(authoring)
    if action_binding_contract is not None:
        _set_path(
            compiled,
            ("router_decision_contract", "action_binding_contract"),
            action_binding_contract,
        )

    correction_lifecycle_contract = _normal_correction_lifecycle_contract(authoring)
    if correction_lifecycle_contract is not None:
        _set_path(
            compiled,
            ("router_decision_contract", "correction_lifecycle_contract"),
            correction_lifecycle_contract,
        )

    explicit_record_triggers = _normal_explicit_record_triggers(authoring)
    if explicit_record_triggers is not None:
        _set_path(compiled, ("router_decision_contract", "explicit_record_triggers"), explicit_record_triggers)

    conversation_lane_declaration_triggers = _normal_conversation_lane_declaration_triggers(authoring)
    if conversation_lane_declaration_triggers is not None:
        _set_path(
            compiled,
            ("router_decision_contract", "conversation_lane_declaration_triggers"),
            conversation_lane_declaration_triggers,
        )

    referenced_conversation_memory_contract = _normal_referenced_conversation_memory_contract(
        authoring
    )
    if referenced_conversation_memory_contract is not None:
        _set_path(
            compiled,
            ("router_decision_contract", "referenced_conversation_memory_contract"),
            referenced_conversation_memory_contract,
        )

    causal_contract = _normal_causal_attribution_contract(authoring)
    if causal_contract is not None:
        _set_path(compiled, ("router_decision_contract", "causal_attribution_contract"), causal_contract)

    causal_triggers = _normal_causal_attribution_triggers(authoring)
    if causal_triggers is not None:
        _set_path(compiled, ("router_decision_contract", "causal_attribution_triggers"), causal_triggers)

    issue_prevention_gates = _normal_issue_prevention_gates(authoring)
    if issue_prevention_gates is not None:
        _set_path(compiled, ("router_decision_contract", "issue_prevention_gates"), issue_prevention_gates)

    full_lane = _normal_full_lane(authoring)
    if full_lane is not None:
        _set_path(compiled, ("router_decision_contract", "conversation_memory_full_lane_triggers"), full_lane)

    behavior_correction = _normal_behavior_correction_contract(authoring)
    if behavior_correction is not None:
        _set_path(
            compiled,
            ("runtime_enforcement", "behavior_correction_contract"),
            behavior_correction,
        )

    return compiled


def changed_tracked_paths(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return [".".join(path) for path in TRACKED_PATHS if _get_path(before, path) != _get_path(after, path)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile TOML-maintained harness policy sections into JSON.")
    parser.add_argument("--authoring", default=str(DEFAULT_AUTHORING), help="TOML authoring file.")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY), help="Base embedded_harness_policy.json file.")
    parser.add_argument("--output", default="", help="Optional output policy JSON path. Omit for no write.")
    parser.add_argument("--check", action="store_true", help="Fail if TOML-compiled sections differ from the policy JSON.")
    args = parser.parse_args(argv)

    authoring_path = Path(args.authoring)
    policy_path = Path(args.policy)
    base_policy = _load_json(policy_path)
    authoring = _load_toml(authoring_path)
    compiled = compile_policy(base_policy, authoring)

    changed = changed_tracked_paths(base_policy, compiled)
    if args.check:
        status = "pass" if not changed else "blocked"
        print(
            json.dumps(
                {
                    "phase": "compile_policy_from_toml",
                    "status": status,
                    "authoring_path": str(authoring_path),
                    "policy_path": str(policy_path),
                    "changed_tracked_paths": changed,
                    "rule": "TOML authoring must match the JSON consumed by runtime adapters.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not changed else 2

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(compiled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "phase": "compile_policy_from_toml",
                    "status": "pass",
                    "output_path": str(output_path),
                    "changed_tracked_paths": changed,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(json.dumps(compiled, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - command-line maintenance tool reports concise failure.
        print(
            json.dumps(
                {
                    "phase": "compile_policy_from_toml",
                    "status": "blocked",
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)
