from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .gates import flush_logs, intake_router, runtime_enforcer, sanitize_json_value
from .policy import load_policy


STATE_FILENAME = "workbuddy_hook_state.json"
SESSION_LIMIT = 50
EVENT_STAGE_MAP = {
    "UserPromptSubmit": "user_prompt",
    "PreToolUse": "pre_tool",
    "PostToolUse": "post_tool",
    "Stop": "final",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _read_hook_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    parsed = sanitize_json_value(parsed)
    return parsed if isinstance(parsed, dict) else {"payload": parsed}


def _write_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(sanitize_json_value(payload), ensure_ascii=True, sort_keys=True) + "\n")


def _hook_event(payload: dict[str, Any]) -> str:
    return str(
        payload.get("hook_event_name")
        or payload.get("hookEventName")
        or payload.get("event")
        or payload.get("event_name")
        or ""
    )


def _stage(args: argparse.Namespace, payload: dict[str, Any]) -> str:
    if args.stage != "auto":
        return str(args.stage)
    return EVENT_STAGE_MAP.get(_hook_event(payload), "pre_tool")


def _session_id(payload: dict[str, Any]) -> str:
    return str(
        payload.get("session_id")
        or payload.get("sessionId")
        or payload.get("conversation_id")
        or payload.get("conversationId")
        or "default"
    )


def _cwd(args: argparse.Namespace, payload: dict[str, Any]) -> str:
    return str(payload.get("cwd") or payload.get("workspace") or args.cwd or os.getcwd())


def _log_dir(args: argparse.Namespace, payload: dict[str, Any], cwd: str) -> Path:
    configured = args.log_dir or os.environ.get("AGENT_MEMORY_LANE_LOG_DIR") or payload.get("log_dir")
    if configured:
        return Path(str(configured))
    project_dir = os.environ.get("CODEBUDDY_PROJECT_DIR") or os.environ.get("WORKBUDDY_PROJECT_DIR")
    if project_dir:
        return Path(project_dir) / ".harness-logs"
    return Path(cwd) / ".harness-logs"


def _state_path(log_dir: Path) -> Path:
    return log_dir / STATE_FILENAME


def _load_state(log_dir: Path) -> dict[str, Any]:
    path = _state_path(log_dir)
    if not path.exists():
        return {"sessions": {}}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"sessions": {}}
    if not isinstance(parsed, dict):
        return {"sessions": {}}
    parsed.setdefault("sessions", {})
    if not isinstance(parsed["sessions"], dict):
        parsed["sessions"] = {}
    return parsed


def _save_state(log_dir: Path, state: dict[str, Any]) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    sessions = state.get("sessions", {})
    if isinstance(sessions, dict) and len(sessions) > SESSION_LIMIT:
        ordered = sorted(
            sessions.items(),
            key=lambda item: str(item[1].get("updated_at", "")) if isinstance(item[1], dict) else "",
        )
        state["sessions"] = dict(ordered[-SESSION_LIMIT:])
    _state_path(log_dir).write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _prompt_text(payload: dict[str, Any]) -> str:
    value = payload.get("prompt")
    if value is None:
        value = payload.get("user_prompt")
    if value is None:
        value = payload.get("message")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "content", "value"):
            if isinstance(value.get(key), str):
                return str(value[key])
    return ""


def _tool_name(payload: dict[str, Any]) -> str:
    return str(payload.get("tool_name") or payload.get("toolName") or payload.get("name") or "")


def _tool_input(payload: dict[str, Any]) -> Any:
    if "tool_input" in payload:
        return payload["tool_input"]
    if "toolInput" in payload:
        return payload["toolInput"]
    if "input" in payload:
        return payload["input"]
    return None


def _stored_task_text(state: dict[str, Any], session_id: str) -> str:
    session = state.get("sessions", {}).get(session_id, {})
    if isinstance(session, dict):
        return str(session.get("task_text") or "")
    return ""


def _remember_prompt(
    *,
    state: dict[str, Any],
    session_id: str,
    cwd: str,
    task_text: str,
    route: dict[str, Any],
) -> None:
    sessions = state.setdefault("sessions", {})
    sessions[session_id] = {
        "cwd": cwd,
        "task_text": task_text,
        "updated_at": _now(),
        "compact_receipt": route.get("compact_receipt", {}),
    }


def _decision_reason(decision: dict[str, Any]) -> str:
    reasons = decision.get("blocked_reasons") or []
    if isinstance(reasons, list) and reasons:
        return "; ".join(str(item) for item in reasons)
    return "blocked by Agent Memory Lane Harness"


def _allow_output() -> dict[str, Any]:
    return {"continue": True, "suppressOutput": True}


def _context_output(route: dict[str, Any]) -> dict[str, Any]:
    receipt = route.get("compact_receipt", {})
    context = (
        "Agent Memory Lane Harness route: "
        f"risk={receipt.get('risk_level', route.get('risk_level', 'unknown'))}; "
        f"gates={','.join(str(item) for item in receipt.get('required_gates', [])) or 'none'}; "
        f"memory={receipt.get('memory_mode', route.get('memory_mode', 'none'))}/"
        f"{receipt.get('memory_lane', route.get('memory_lane', 'none'))}; "
        f"external={','.join(str(item) for item in receipt.get('external_need', [])) or 'none'}; "
        f"claim={receipt.get('claim_risk', route.get('claim_risk', 'none'))}."
    )
    return {
        "continue": True,
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        },
    }


def _deny_output(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "continue": False,
        "suppressOutput": False,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": _decision_reason(decision),
        },
    }


def _log_event(log_dir: Path, event: dict[str, Any]) -> None:
    flush_logs(log_dir=log_dir, events=[event])


def _handle_user_prompt(
    *,
    args: argparse.Namespace,
    payload: dict[str, Any],
    cwd: str,
    log_dir: Path,
    state: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    task_text = _prompt_text(payload)
    route = intake_router(task_text, cwd, policy)
    _remember_prompt(state=state, session_id=_session_id(payload), cwd=cwd, task_text=task_text, route=route)
    _save_state(log_dir, state)
    _log_event(
        log_dir,
        {
            "ts": _now(),
            "phase": "workbuddy_hook_runner",
            "stage": "user_prompt",
            "status": "pass",
            "session_id": _session_id(payload),
            "cwd": cwd,
            "route": route,
            "fail_open": args.fail_open,
        },
    )
    return 0, _context_output(route)


def _handle_pre_tool(
    *,
    args: argparse.Namespace,
    payload: dict[str, Any],
    cwd: str,
    log_dir: Path,
    state: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    session_id = _session_id(payload)
    task_text = _prompt_text(payload) or _stored_task_text(state, session_id)
    decision = runtime_enforcer(
        stage="pre_tool",
        task_text=task_text,
        cwd=cwd,
        tool_name=_tool_name(payload),
        tool_input=_tool_input(payload),
        human_confirmed=args.human_confirmed,
        boundary_reviewed=args.boundary_reviewed,
        constitution_reviewed=args.constitution_reviewed,
        constitution_path=args.constitution_path,
        log_dir=log_dir,
        policy=policy,
    )
    if decision["status"] == "blocked":
        return 2, _deny_output(decision)
    return 0, _allow_output()


def _handle_passthrough(
    *,
    stage: str,
    args: argparse.Namespace,
    payload: dict[str, Any],
    cwd: str,
    log_dir: Path,
) -> tuple[int, dict[str, Any]]:
    _log_event(
        log_dir,
        {
            "ts": _now(),
            "phase": "workbuddy_hook_runner",
            "stage": stage,
            "status": "pass",
            "session_id": _session_id(payload),
            "cwd": cwd,
            "event": _hook_event(payload),
            "note": "event logged; no pre-execution block is possible at this stage",
            "fail_open": args.fail_open,
        },
    )
    return 0, _allow_output()


def _handle_error(args: argparse.Namespace, stage: str, exc: Exception) -> tuple[int, dict[str, Any]]:
    reason = str(sanitize_json_value(f"Agent Memory Lane Harness hook runner failed: {exc}"))
    if args.fail_open:
        return 0, {
            "continue": True,
            "suppressOutput": False,
            "systemMessage": reason,
        }
    if stage == "pre_tool":
        return 2, {
            "continue": False,
            "suppressOutput": False,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            },
        }
    return 1, {"continue": False, "suppressOutput": False, "systemMessage": reason}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WorkBuddy hook runner for Agent Memory Lane Harness.")
    parser.add_argument(
        "--stage",
        choices=["auto", "user_prompt", "pre_tool", "post_tool", "final"],
        default="auto",
        help="Hook stage. Default reads hook_event_name from stdin JSON.",
    )
    parser.add_argument("--cwd", default="", help="Workspace cwd fallback.")
    parser.add_argument("--policy", default="", help="Optional embedded_harness_policy.json path.")
    parser.add_argument("--log-dir", default="", help="Directory for JSONL event logs and hook state.")
    parser.add_argument("--constitution-path", default="", help="Optional AGENTS.md or equivalent constitution path.")
    parser.add_argument(
        "--constitution-reviewed",
        action="store_true",
        help="Mark the constitution entry as already reviewed for this hook call.",
    )
    parser.add_argument(
        "--boundary-reviewed",
        action="store_true",
        help="Mark low-confidence routing boundary review as complete.",
    )
    parser.add_argument(
        "--human-confirmed",
        action="store_true",
        help="Mark explicit human confirmation as present for R5 or hard tools.",
    )
    parser.add_argument(
        "--fail-open",
        action="store_true",
        help="Do not block when the hook runner itself fails. Use only during adapter setup.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload: dict[str, Any] = {}
    stage = args.stage
    try:
        payload = _read_hook_payload()
        stage = _stage(args, payload)
        cwd = _cwd(args, payload)
        log_dir = _log_dir(args, payload, cwd)
        state = _load_state(log_dir)
        policy = load_policy(args.policy or None)
        if stage == "user_prompt":
            code, output = _handle_user_prompt(
                args=args,
                payload=payload,
                cwd=cwd,
                log_dir=log_dir,
                state=state,
                policy=policy,
            )
        elif stage == "pre_tool":
            code, output = _handle_pre_tool(
                args=args,
                payload=payload,
                cwd=cwd,
                log_dir=log_dir,
                state=state,
                policy=policy,
            )
        else:
            code, output = _handle_passthrough(
                stage=stage,
                args=args,
                payload=payload,
                cwd=cwd,
                log_dir=log_dir,
            )
        _write_json(output)
        return code
    except Exception as exc:  # pragma: no cover - tested through public behavior, not branch internals.
        code, output = _handle_error(args, stage, exc)
        _write_json(output)
        return code


if __name__ == "__main__":
    raise SystemExit(main())
