from __future__ import annotations

from typing import Any


SCHEMA = "cbh.workbuddy_agent_loop_contract.v1"


def _route_value(route: dict[str, Any], field: str, default: Any = "none") -> Any:
    receipt = route.get("compact_receipt")
    if isinstance(receipt, dict) and field in receipt:
        return receipt[field]
    return route.get(field, default)


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item) for item in values if str(item) and str(item) != "none"]


def build_agent_loop_contract(route: dict[str, Any]) -> dict[str, Any]:
    """Translate advisory route fields into explicit host-loop actions.

    Building this contract does not execute the actions. A WorkBuddy-compatible
    host must call the corresponding memory, search, tool-selection, skill, and
    final-review surfaces and record its own consumption receipt.
    """

    actions: list[dict[str, Any]] = []

    def add(action_id: str, stage: str, fields: list[str], value: Any) -> None:
        actions.append(
            {
                "action_id": action_id,
                "stage": stage,
                "source_fields": fields,
                "value": value,
                "consumer": "workbuddy_agent_loop",
                "hook_only_status": "advisory_context_only",
            }
        )

    memory_mode = str(_route_value(route, "memory_mode"))
    memory_lane = str(_route_value(route, "memory_lane"))
    if memory_mode != "none":
        add("memory_operation", "before_or_after_task", ["memory_mode", "memory_lane"], {
            "mode": memory_mode,
            "lane": memory_lane,
        })

    hybrid_profile = str(_route_value(route, "hybrid_retrieval_profile"))
    if hybrid_profile != "none":
        add("hybrid_memory_retrieval", "before_memory_read", ["hybrid_retrieval_profile"], hybrid_profile)

    write_profile = str(_route_value(route, "memory_write_profile"))
    if write_profile != "none":
        add("memory_write_shape", "before_memory_write", ["memory_write_profile"], write_profile)

    external_need = _text_list(_route_value(route, "external_need", []))
    if external_need:
        add("external_research", "before_fact_claim", ["external_need"], external_need)

    claim_risk = str(_route_value(route, "claim_risk"))
    if claim_risk != "none":
        add("claim_boundary_review", "before_final", ["claim_risk"], claim_risk)

    feedback_profile = str(_route_value(route, "feedback_loop_profile"))
    if feedback_profile != "none":
        add("feedback_loop", "during_reusable_memory_use", ["feedback_loop_profile"], feedback_profile)

    skill_profile = str(_route_value(route, "skill_lifecycle_profile"))
    if skill_profile not in {"none", "listing_only"}:
        add("skill_lifecycle", "during_skill_phase", ["skill_lifecycle_profile"], skill_profile)

    tool_surface = str(_route_value(route, "tool_surface_need"))
    if tool_surface != "none":
        add("tool_surface_discovery", "before_tool_selection", ["tool_surface_need"], tool_surface)

    first_principles = str(_route_value(route, "first_principles_profile"))
    if first_principles not in {"none", "micro_constraints"}:
        add("constraint_mapping", "before_patch_or_design", ["first_principles_profile"], first_principles)

    skill_audit = str(_route_value(route, "skill_audit_profile"))
    if skill_audit != "none":
        add("skill_audit", "before_skill_change", ["skill_audit_profile"], skill_audit)

    return {
        "schema": SCHEMA,
        "consumer_status": "unbound_until_host_loop_calls_consumer",
        "hook_only_mode": True,
        "host_loop_required": bool(actions),
        "actions": actions,
        "action_ids": [item["action_id"] for item in actions],
    }


def validate_agent_loop_receipt(contract: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    """Validate a host-owned receipt without pretending that CBH ran the actions."""

    if contract.get("schema") != SCHEMA:
        return {"status": "invalid", "missing_action_ids": [], "reason": "unsupported_contract_schema"}
    completed = {
        str(item.get("action_id"))
        for item in receipt.get("actions", [])
        if isinstance(item, dict) and item.get("status") in {"completed", "not_applicable_with_reason"}
    }
    required = {str(item) for item in contract.get("action_ids", [])}
    missing = sorted(required - completed)
    return {
        "status": "complete" if not missing else "incomplete",
        "missing_action_ids": missing,
        "reason": "host_reported_consumption" if not missing else "host_loop_actions_unconsumed",
    }
