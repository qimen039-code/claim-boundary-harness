#!/usr/bin/env python3
"""Compile selected human-authored TOML policy sections into policy JSON.

Runtime gates intentionally continue to read embedded_harness_policy.json.
This helper is an offline maintenance tool for high-churn sections only.
"""

from __future__ import annotations

import argparse
import copy
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

TRACKED_PATHS: list[tuple[str, ...]] = [
    ("risk_trigger_rules", "R5"),
    ("r5_context_decision_rules",),
    ("router_decision_contract", "observation_scope_triggers"),
    ("router_decision_contract", "feedback_loop_triggers"),
    ("router_decision_contract", "causal_attribution_contract"),
    ("router_decision_contract", "causal_attribution_triggers"),
    ("router_decision_contract", "conversation_memory_full_lane_triggers"),
    ("runtime_enforcement", "human_confirmation_permit"),
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


def _normal_feedback_loop_triggers(authoring: dict[str, Any]) -> list[str] | None:
    router = authoring.get("router_decision_contract", {})
    if not isinstance(router, dict):
        raise ValueError("router_decision_contract must be a table")
    triggers = router.get("feedback_loop_triggers")
    if triggers is None:
        return None
    return _string_list(triggers, "router_decision_contract.feedback_loop_triggers")


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


def _normal_permit(authoring: dict[str, Any]) -> dict[str, Any] | None:
    runtime = authoring.get("runtime_enforcement", {})
    if not isinstance(runtime, dict):
        raise ValueError("runtime_enforcement must be a table")
    permit = runtime.get("human_confirmation_permit")
    if permit is None:
        return None
    if not isinstance(permit, dict):
        raise ValueError("human_confirmation_permit must be a table")
    required_scope = permit.get("required_scope")
    if required_scope != "single_event":
        raise ValueError("human_confirmation_permit.required_scope must be single_event")
    schema = permit.get("schema")
    if schema != "cbh.r5_human_confirmation_permit.v1":
        raise ValueError("human_confirmation_permit.schema is unsupported")
    return {
        "enabled": bool(permit.get("enabled", True)),
        "schema": schema,
        "required_scope": required_scope,
        "required_fields": _string_list(permit.get("required_fields"), "human_confirmation_permit.required_fields"),
        "consume_on_pass": bool(permit.get("consume_on_pass", True)),
        "consume_requires_tool_text": bool(permit.get("consume_requires_tool_text", True)),
        "used_ledger_env_var": str(permit.get("used_ledger_env_var") or "CBH_R5_PERMIT_USE_LEDGER"),
        "used_ledger_record_schema": str(permit.get("used_ledger_record_schema") or "cbh.r5_human_confirmation_permit_use.v1"),
        "rule": str(permit.get("rule") or ""),
    }


def compile_policy(base_policy: dict[str, Any], authoring: dict[str, Any]) -> dict[str, Any]:
    compiled = copy.deepcopy(base_policy)

    risk_rules = _normal_risk_trigger_rules(authoring)
    if risk_rules:
        for risk, value in risk_rules.items():
            _set_path(compiled, ("risk_trigger_rules", risk), value)

    r5_context = _normal_r5_context(authoring)
    if r5_context is not None:
        _set_path(compiled, ("r5_context_decision_rules",), r5_context)

    observation_scope_triggers = _normal_observation_scope_triggers(authoring)
    if observation_scope_triggers is not None:
        _set_path(compiled, ("router_decision_contract", "observation_scope_triggers"), observation_scope_triggers)

    feedback_loop_triggers = _normal_feedback_loop_triggers(authoring)
    if feedback_loop_triggers is not None:
        _set_path(compiled, ("router_decision_contract", "feedback_loop_triggers"), feedback_loop_triggers)

    causal_contract = _normal_causal_attribution_contract(authoring)
    if causal_contract is not None:
        _set_path(compiled, ("router_decision_contract", "causal_attribution_contract"), causal_contract)

    causal_triggers = _normal_causal_attribution_triggers(authoring)
    if causal_triggers is not None:
        _set_path(compiled, ("router_decision_contract", "causal_attribution_triggers"), causal_triggers)

    full_lane = _normal_full_lane(authoring)
    if full_lane is not None:
        _set_path(compiled, ("router_decision_contract", "conversation_memory_full_lane_triggers"), full_lane)

    permit = _normal_permit(authoring)
    if permit is not None:
        _set_path(compiled, ("runtime_enforcement", "human_confirmation_permit"), permit)

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
