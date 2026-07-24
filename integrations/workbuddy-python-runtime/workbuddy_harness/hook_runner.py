#!/usr/bin/env python3
"""Nonblocking WorkBuddy bridge for Claim Boundary Harness.

UserPromptSubmit may add compact advisory route context. PreToolUse may return
only an accepted, mechanically verified ``allow + updatedInput`` correction.
No match, ambiguity, verifier failure, unsupported environment, or internal
error is a silent no-op. This bridge never denies, freezes, stores approval
state, grants authority, or owns the model agent's task.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from .agent_loop_contract import build_agent_loop_contract
from .gates import intake_router, sanitize_json_value
from .policy import load_policy


REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS_ROOT = REPO_ROOT / "skills" / "embedded-harness"
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))

Parser = Callable[[str], list[str] | None]

EVENT_STAGE = {
    "userpromptsubmit": "user_prompt",
    "pretooluse": "pre_tool",
}


def _event_name(payload: dict[str, Any]) -> str:
    return str(
        payload.get("hook_event_name") or payload.get("hookEventName") or ""
    ).casefold()


def _stage(explicit_stage: str, payload: dict[str, Any]) -> str:
    if explicit_stage != "auto":
        return explicit_stage
    return EVENT_STAGE.get(_event_name(payload), "passthrough")


def _text_parts(value: Any, *, depth: int = 0) -> list[str]:
    if depth > 6:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(_text_parts(item, depth=depth + 1))
        return parts
    if not isinstance(value, dict):
        return []
    preferred = {
        "prompt",
        "text",
        "transcript",
        "user_prompt",
        "userprompt",
        "message",
        "content",
    }
    parts: list[str] = []
    for key, item in value.items():
        normalized = "".join(
            ch for ch in str(key).casefold() if ch.isalnum() or ch == "_"
        )
        if normalized in preferred:
            parts.extend(_text_parts(item, depth=depth + 1))
    return parts


def _prompt_text(payload: dict[str, Any]) -> str:
    return "\n".join(
        part.strip()
        for part in _text_parts(payload)
        if isinstance(part, str) and part.strip()
    )


def _route_value(route: dict[str, Any], field: str, default: Any = "none") -> Any:
    receipt = route.get("compact_receipt")
    if isinstance(receipt, dict) and field in receipt:
        return receipt[field]
    return route.get(field, default)


def _advisory_context(route: dict[str, Any]) -> str:
    contract = build_agent_loop_contract(route)
    payload = {
        "risk_level": route.get("risk_level", "R0"),
        "classification_confidence": route.get(
            "classification_confidence", "high"
        ),
        "memory_need": _route_value(route, "memory_need"),
        "memory_mode": _route_value(route, "memory_mode"),
        "memory_lane": _route_value(route, "memory_lane"),
        "external_need": _route_value(route, "external_need", []),
        "claim_risk": _route_value(route, "claim_risk"),
        "human_confirmation_need": bool(
            _route_value(route, "human_confirmation_need", False)
        ),
        "agent_loop_action_ids": contract["action_ids"],
        "task_execution_owner": "host_model_agent",
        "host_blocking": False,
    }
    return "CBH advisory route: " + json.dumps(
        sanitize_json_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _needs_context(route: dict[str, Any]) -> bool:
    contract = build_agent_loop_contract(route)
    return any(
        (
            str(route.get("risk_level") or "R0") != "R0",
            str(route.get("classification_confidence") or "high") == "low",
            bool(_route_value(route, "human_confirmation_need", False)),
            bool(contract["action_ids"]),
            str(route.get("receipt_profile") or "")
            in {"extended_governance", "debug_receipt"},
        )
    )


def handle_user_prompt_event(
    payload: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    cwd: str = "",
) -> dict[str, Any]:
    task_text = _prompt_text(payload)
    route = intake_router(
        task_text,
        cwd=cwd or str(payload.get("cwd") or "."),
        policy=policy,
    )
    output: dict[str, Any] = {"continue": True, "suppressOutput": True}
    if _needs_context(route):
        output["hookSpecificOutput"] = {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": _advisory_context(route),
        }
    return output


def handle_pretool_event(
    payload: dict[str, Any],
    *,
    parser: Parser | None = None,
) -> dict[str, Any]:
    environment = str(
        payload.get("executor_environment")
        or payload.get("cbh_executor_environment")
        or ""
    ).casefold()
    if environment != "powershell":
        return {}
    try:
        from behavior_correction_hook import handle_event as handle_correction_event

        canonical_payload = dict(payload)
        tool_name = str(payload.get("tool_name") or "").casefold()
        if tool_name in {"bash", "powershell", "shell", "shell_command"}:
            canonical_payload["tool_name"] = "Bash"
        output = handle_correction_event(canonical_payload, parser=parser)
    except Exception:
        return {}
    hook_output = (
        output.get("hookSpecificOutput") if isinstance(output, dict) else None
    )
    if not isinstance(hook_output, dict):
        return {}
    if hook_output.get("permissionDecision") != "allow":
        return {}
    if not isinstance(hook_output.get("updatedInput"), dict):
        return {}
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Nonblocking WorkBuddy bridge for Claim Boundary Harness."
    )
    parser.add_argument(
        "--stage",
        choices=["auto", "user_prompt", "pre_tool", "post_tool", "final"],
        default="auto",
    )
    parser.add_argument("--cwd", default="")
    parser.add_argument("--policy", default="")
    parser.add_argument(
        "--executor-environment",
        choices=["", "powershell"],
        default=os.environ.get("CBH_EXECUTOR_ENVIRONMENT", ""),
        help="Explicit host-owned executor dialect for optional PreToolUse correction.",
    )
    parser.add_argument(
        "--rewrite-protocol",
        choices=["disabled", "codex_allow_updated_input"],
        default=os.environ.get("CBH_WORKBUDDY_REWRITE_PROTOCOL", "disabled"),
        help="Disabled by default until the WorkBuddy host protocol is verified.",
    )
    parser.add_argument(
        "--log-dir",
        default="",
        help="Accepted for v1.0 CLI compatibility; v1.1 stores no hook state.",
    )
    return parser


def _read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    parsed = json.loads(raw) if raw.strip() else {}
    return parsed if isinstance(parsed, dict) else {}


def _write_output(output: dict[str, Any]) -> None:
    if output:
        sys.stdout.write(
            json.dumps(
                sanitize_json_value(output),
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = _read_payload()
        stage = _stage(args.stage, payload)
        if stage == "user_prompt":
            output = handle_user_prompt_event(
                payload,
                policy=load_policy(args.policy or None),
                cwd=args.cwd,
            )
        elif stage == "pre_tool":
            if args.rewrite_protocol == "codex_allow_updated_input":
                event = dict(payload)
                if args.executor_environment:
                    event["cbh_executor_environment"] = args.executor_environment
                output = handle_pretool_event(event)
            else:
                output = {}
        else:
            output = {}
        _write_output(output)
    except Exception:
        # A bridge failure must never become an authorization or denial event.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
