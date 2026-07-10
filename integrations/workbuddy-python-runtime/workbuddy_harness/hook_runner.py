from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .gates import (
    build_single_event_human_confirmation_permit,
    flush_logs,
    intake_router,
    runtime_enforcer,
    sanitize_json_value,
)
from .policy import load_policy


STATE_FILENAME = "workbuddy_hook_state.json"
SESSION_LIMIT = 50
STATE_LOCK_FILENAME = STATE_FILENAME + ".lock"
MAX_EXTRACTED_TEXT_CHARS = 12000
MAX_EXTRACTED_TEXT_PARTS = 16
MAX_EXTRACT_DEPTH = 6
CONFIRMATION_TTL_SECONDS = 300
MAX_CONFIRMATION_TEXT_CHARS = 500
MAX_CONSUMED_CONFIRMATION_IDS = 100
EVENT_STAGE_MAP = {
    "UserPromptSubmit": "user_prompt",
    "PreToolUse": "pre_tool",
    "PostToolUse": "post_tool",
    "Stop": "final",
}
TEXT_KEY_NAMES = {
    "answer",
    "caption",
    "content",
    "finaltext",
    "message",
    "messages",
    "output",
    "prompt",
    "response",
    "summary",
    "text",
    "transcript",
    "transcription",
    "userprompt",
    "value",
}
PROMPT_KEY_NAMES = {
    "content",
    "message",
    "messages",
    "prompt",
    "request",
    "text",
    "userprompt",
}
FINAL_KEY_NAMES = {
    "answer",
    "content",
    "final",
    "finalmessage",
    "finalresponse",
    "finaltext",
    "message",
    "output",
    "response",
    "result",
    "text",
}
SILENT_PROMPT_GATES = {"microkernel", "read_only_context_gate"}
RAW_MEDIA_KEY_NAMES = {
    "audio",
    "audiodata",
    "base64",
    "binary",
    "blob",
    "bytes",
    "dataurl",
    "image",
    "raw",
    "video",
}
CONFIRMATION_DENIAL_RE = re.compile(
    r"(?:不允许|不授权|不同意|不要执行|别执行|停止执行|取消|拒绝|do\s+not|don't|deny|denied|reject|cancel|stop)",
    re.IGNORECASE,
)
CONFIRMATION_QUESTION_RE = re.compile(
    r"(?:是否|能否|可否|可以吗|允许吗|确认吗|执行吗|放行吗|[?？]|can\s+(?:you|i)|should\s+(?:you|i)|may\s+i)",
    re.IGNORECASE,
)
CONFIRMATION_EXPLICIT_RE = re.compile(
    r"(?:确认(?:执行|继续|放行)|允许(?:执行|继续|放行|删除|清理|安装|提交|推送|发布|提权)|"
    r"同意(?:执行|继续|放行|删除|清理|安装|提交|推送|发布|提权)|"
    r"授权(?:执行|继续|放行|完整清除|删除|清理|安装|提交|推送|发布|提权)|"
    r"批准(?:执行|继续|放行)|可以(?:执行|继续|放行)|继续执行|执行吧|放行吧|"
    r"(?:i\s+)?(?:approve|authorize|confirm)(?:\s+(?:this|it|the\s+action|execution))?|"
    r"go\s+ahead|proceed(?:\s+with\s+(?:it|the\s+action))?)",
    re.IGNORECASE,
)
CONFIRMATION_SHORT_REPLY_RE = re.compile(
    r"^(?:允许|确认|同意|授权|批准|可以|继续|执行|放行|是|好的|好|yes|y|ok|okay|approved?|confirmed?|proceed|go\s+ahead)[。.!！\s]*$",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_confirmation_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) or str(value).strip().replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _confirmation_window(confirmed_at: datetime) -> tuple[str, str]:
    confirmed = confirmed_at.astimezone(timezone.utc)
    expires = confirmed + timedelta(seconds=CONFIRMATION_TTL_SECONDS)
    return confirmed.isoformat().replace("+00:00", "Z"), expires.isoformat().replace("+00:00", "Z")


def _route_waits_for_human_confirmation(session: dict[str, Any]) -> bool:
    receipt = session.get("compact_receipt", {}) if isinstance(session, dict) else {}
    return bool(isinstance(receipt, dict) and receipt.get("human_confirmation_need"))


def _conversation_confirmation_signal(
    *,
    text: str,
    session_id: str,
    previous_session: dict[str, Any],
) -> dict[str, Any] | None:
    normalized = " ".join(text.strip().split())
    if not normalized or len(normalized) > MAX_CONFIRMATION_TEXT_CHARS:
        return None
    if CONFIRMATION_DENIAL_RE.search(normalized) or CONFIRMATION_QUESTION_RE.search(normalized):
        return None
    short_reply_after_request = bool(
        _route_waits_for_human_confirmation(previous_session) and CONFIRMATION_SHORT_REPLY_RE.fullmatch(normalized)
    )
    if not short_reply_after_request and not CONFIRMATION_EXPLICIT_RE.search(normalized):
        return None
    confirmed_at = _utc_now()
    confirmed_at_text, expires_at_text = _confirmation_window(confirmed_at)
    confirmation_id = "WB-CONV-" + _sha256_text(
        "\n".join([session_id, confirmed_at_text, normalized])
    )[:32]
    return {
        "schema": "cbh.workbuddy_human_confirmation.v1",
        "confirmation_id": confirmation_id,
        "status": "confirmed",
        "scope": "single_event",
        "confirmed_by": "human",
        "source": "conversation_explicit_approval",
        "confirmed_at_utc": confirmed_at_text,
        "expires_at_utc": expires_at_text,
        "confirmation_text_sha256": _sha256_text(normalized),
    }


def _payload_confirmation_signal(payload: dict[str, Any], session_id: str) -> dict[str, Any] | None:
    raw_signal: Any = payload.get("cbh_human_confirmation") or payload.get("workbuddy_human_confirmation")
    if isinstance(raw_signal, dict):
        if raw_signal.get("schema") != "cbh.workbuddy_human_confirmation.v1":
            return None
        status = str(raw_signal.get("status") or "").lower()
        scope = str(raw_signal.get("scope") or "").lower()
        confirmed_by = str(raw_signal.get("confirmed_by") or "").lower()
        source = str(raw_signal.get("source") or "").lower()
        confirmed_at = _parse_confirmation_time(raw_signal.get("confirmed_at_utc"))
        confirmation_id = str(raw_signal.get("confirmation_id") or "")
        if (
            status != "confirmed"
            or scope != "single_event"
            or confirmed_by != "human"
            or source not in {"workbuddy_permission_prompt", "conversation_explicit_approval"}
            or not confirmed_at
            or not confirmation_id
        ):
            return None
    elif str(payload.get("runtime_human_confirmation") or "").lower() == "confirmed":
        confirmed_at = _parse_confirmation_time(
            payload.get("runtime_confirmation_ts") or payload.get("runtime_confirmation_at_utc")
        )
        if not confirmed_at:
            return None
        source = "workbuddy_permission_prompt"
        confirmation_id = str(payload.get("runtime_confirmation_id") or "")
        if not confirmation_id:
            confirmation_id = "WB-HOST-" + _sha256_text(
                "\n".join([session_id, confirmed_at.isoformat(), source])
            )[:32]
    else:
        return None

    now = _utc_now()
    if confirmed_at > now + timedelta(seconds=30):
        return None
    if now - confirmed_at > timedelta(seconds=CONFIRMATION_TTL_SECONDS):
        return None
    confirmed_at_text, expires_at_text = _confirmation_window(confirmed_at)
    return {
        "schema": "cbh.workbuddy_human_confirmation.v1",
        "confirmation_id": confirmation_id,
        "status": "confirmed",
        "scope": "single_event",
        "confirmed_by": "human",
        "source": source,
        "confirmed_at_utc": confirmed_at_text,
        "expires_at_utc": expires_at_text,
    }


def _read_hook_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    parsed = sanitize_json_value(parsed)
    return parsed if isinstance(parsed, dict) else {"payload": parsed}


def _write_json(payload: dict[str, Any]) -> None:
    line = json.dumps(sanitize_json_value(payload), ensure_ascii=False, sort_keys=True) + "\n"
    try:
        sys.stdout.write(line)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(line.encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()


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


def _key_name(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _trim_text(text: str) -> str:
    return text.strip()[:MAX_EXTRACTED_TEXT_CHARS]


def _join_text_parts(parts: list[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for part in parts:
        clean = _trim_text(part)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        unique.append(clean)
        if len(unique) >= MAX_EXTRACTED_TEXT_PARTS:
            break
    return _trim_text("\n".join(unique))


def _extract_text_parts(value: Any, *, force_text: bool = False, key_name: str = "", depth: int = 0) -> list[str]:
    if depth > MAX_EXTRACT_DEPTH:
        return []

    normalized_key = _key_name(key_name)
    if isinstance(value, str):
        if force_text or normalized_key in TEXT_KEY_NAMES:
            clean = _trim_text(value)
            return [clean] if clean else []
        return []

    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(_extract_text_parts(item, force_text=force_text, key_name=key_name, depth=depth + 1))
            if len(parts) >= MAX_EXTRACTED_TEXT_PARTS:
                break
        return parts

    if isinstance(value, dict):
        parts: list[str] = []
        for child_key, child_value in value.items():
            child_name = _key_name(child_key)
            if child_name in RAW_MEDIA_KEY_NAMES and not isinstance(child_value, (dict, list)):
                continue
            child_force = force_text or child_name in TEXT_KEY_NAMES
            if child_force or isinstance(child_value, (dict, list)):
                parts.extend(
                    _extract_text_parts(
                        child_value,
                        force_text=child_force,
                        key_name=str(child_key),
                        depth=depth + 1,
                    )
                )
            if len(parts) >= MAX_EXTRACTED_TEXT_PARTS:
                break
        return parts

    return []


def _text_from_named_keys(payload: dict[str, Any], key_names: set[str]) -> str:
    parts: list[str] = []
    for key, value in payload.items():
        if _key_name(key) in key_names:
            parts.extend(_extract_text_parts(value, force_text=True, key_name=str(key)))
    return _join_text_parts(parts)


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


def _state_lock_path(log_dir: Path) -> Path:
    return log_dir / STATE_LOCK_FILENAME


@contextmanager
def _exclusive_state_lock(log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    lock_path = _state_lock_path(log_dir)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _locked_state(log_dir: Path):
    with _exclusive_state_lock(log_dir):
        yield _load_state(log_dir)


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
    path = _state_path(log_dir)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _prompt_text(payload: dict[str, Any], *, include_nested_text: bool = True) -> str:
    explicit = _text_from_named_keys(payload, PROMPT_KEY_NAMES)
    if explicit:
        return explicit
    if include_nested_text:
        return _join_text_parts(_extract_text_parts(payload))
    return ""


def _final_text(payload: dict[str, Any]) -> str:
    explicit = _text_from_named_keys(payload, FINAL_KEY_NAMES)
    if explicit:
        return explicit
    return _join_text_parts(_extract_text_parts(payload))


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
    confirmation_signal: dict[str, Any] | None = None,
) -> None:
    sessions = state.setdefault("sessions", {})
    previous = sessions.get(session_id, {})
    if not isinstance(previous, dict):
        previous = {}
    if confirmation_signal:
        updated = dict(previous)
        updated.update(
            {
                "cwd": cwd,
                "task_text": str(previous.get("task_text") or task_text),
                "latest_user_prompt": task_text,
                "updated_at": _now(),
                "pending_human_confirmation": confirmation_signal,
            }
        )
        sessions[session_id] = updated
        return
    sessions[session_id] = {
        "cwd": cwd,
        "task_text": task_text,
        "latest_user_prompt": task_text,
        "updated_at": _now(),
        "compact_receipt": route.get("compact_receipt", {}),
        "consumed_confirmation_ids": list(previous.get("consumed_confirmation_ids") or [])[
            -MAX_CONSUMED_CONFIRMATION_IDS:
        ],
    }


def _pending_confirmation_signal(state: dict[str, Any], session_id: str) -> dict[str, Any] | None:
    session = state.get("sessions", {}).get(session_id, {})
    if not isinstance(session, dict):
        return None
    signal = session.get("pending_human_confirmation")
    if not isinstance(signal, dict):
        return None
    expires_at = _parse_confirmation_time(signal.get("expires_at_utc"))
    if not expires_at or expires_at < _utc_now():
        session.pop("pending_human_confirmation", None)
        return None
    return signal


def _confirmation_already_consumed(state: dict[str, Any], session_id: str, confirmation_id: str) -> bool:
    session = state.get("sessions", {}).get(session_id, {})
    if not isinstance(session, dict):
        return False
    return confirmation_id in {str(item) for item in session.get("consumed_confirmation_ids") or []}


def _consume_confirmation(state: dict[str, Any], session_id: str, confirmation_id: str) -> None:
    session = state.get("sessions", {}).get(session_id, {})
    if not isinstance(session, dict):
        return
    pending = session.get("pending_human_confirmation")
    if isinstance(pending, dict) and str(pending.get("confirmation_id") or "") == confirmation_id:
        session.pop("pending_human_confirmation", None)
    consumed = [str(item) for item in session.get("consumed_confirmation_ids") or []]
    if confirmation_id not in consumed:
        consumed.append(confirmation_id)
    session["consumed_confirmation_ids"] = consumed[-MAX_CONSUMED_CONFIRMATION_IDS:]
    session["updated_at"] = _now()


def _decision_reason(decision: dict[str, Any]) -> str:
    reasons = decision.get("blocked_reasons") or []
    if isinstance(reasons, list) and reasons:
        return "; ".join(str(item) for item in reasons)
    return "blocked by Claim Boundary Harness"


def _allow_output() -> dict[str, Any]:
    return {"continue": True, "suppressOutput": True}


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _without_none(values: list[str]) -> list[str]:
    return [item for item in values if item and item != "none"]


def _needs_prompt_context(route: dict[str, Any]) -> bool:
    receipt = route.get("compact_receipt", {})
    required_gates = _without_none(_as_text_list(receipt.get("required_gates") or route.get("required_gates")))
    external_need = _without_none(_as_text_list(receipt.get("external_need") or route.get("external_need")))
    memory_mode = str(receipt.get("memory_mode", route.get("memory_mode", "none")))
    claim_risk = str(receipt.get("claim_risk", route.get("claim_risk", "none")))

    return any(
        [
            bool(receipt.get("human_confirmation_need")),
            bool(external_need),
            memory_mode != "none",
            claim_risk != "none",
            str(route.get("classification_confidence")) == "low",
            str(route.get("receipt_profile")) in {"extended_governance", "debug_receipt"},
            any(gate not in SILENT_PROMPT_GATES for gate in required_gates),
        ]
    )


def _context_output(route: dict[str, Any]) -> dict[str, Any]:
    if not _needs_prompt_context(route):
        return _allow_output()

    if str(route.get("receipt_profile")) == "debug_receipt":
        context = "Claim Boundary Harness debug receipt: " + json.dumps(
            sanitize_json_value(route),
            ensure_ascii=False,
            sort_keys=True,
        )
        return {
            "continue": True,
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            },
        }

    receipt = route.get("compact_receipt", {})
    required_gates = _without_none(_as_text_list(receipt.get("required_gates", [])))
    external_need = _without_none(_as_text_list(receipt.get("external_need", [])))
    memory_mode = str(receipt.get("memory_mode", route.get("memory_mode", "none")))
    memory_lane = str(receipt.get("memory_lane", route.get("memory_lane", "none")))
    claim_risk = str(receipt.get("claim_risk", route.get("claim_risk", "none")))
    link_intent = str(receipt.get("link_intent", route.get("link_intent", "none")))

    parts: list[str] = []
    if str(route.get("classification_confidence")) == "low":
        parts.append("boundary_review=required")
    if bool(receipt.get("human_confirmation_need")):
        parts.append("human_confirmation=required")
    visible_gates = [gate for gate in required_gates if gate not in SILENT_PROMPT_GATES]
    if visible_gates:
        parts.append(f"gates={','.join(visible_gates)}")
    if memory_mode != "none":
        parts.append(f"memory={memory_mode}/{memory_lane}")
    if link_intent != "none":
        parts.append(f"link={link_intent}")
    if external_need:
        parts.append(f"external={','.join(external_need)}")
    if claim_risk != "none":
        parts.append(f"claim={claim_risk}")

    context = "Claim Boundary Harness boundary: " + "; ".join(parts) + "."
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


def _final_deny_output(decision: dict[str, Any]) -> dict[str, Any]:
    reason = _decision_reason(decision)
    return {
        "continue": False,
        "suppressOutput": False,
        "systemMessage": reason,
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
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
    session_id = _session_id(payload)
    previous_session = state.get("sessions", {}).get(session_id, {})
    if not isinstance(previous_session, dict):
        previous_session = {}
    confirmation_signal = _conversation_confirmation_signal(
        text=task_text,
        session_id=session_id,
        previous_session=previous_session,
    )
    _remember_prompt(
        state=state,
        session_id=session_id,
        cwd=cwd,
        task_text=task_text,
        route=route,
        confirmation_signal=confirmation_signal,
    )
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
    task_text = _stored_task_text(state, session_id) or _prompt_text(payload, include_nested_text=False)
    tool_name = _tool_name(payload)
    tool_input = _tool_input(payload)
    permit_json = args.human_confirmation_permit_json
    permit_path = args.human_confirmation_permit_path
    permit_use_ledger_path = args.human_confirmation_permit_use_ledger_path
    bridge_signal: dict[str, Any] | None = None

    if not permit_json and not permit_path and not args.human_confirmed:
        probe = runtime_enforcer(
            stage="pre_tool",
            task_text=task_text,
            cwd=cwd,
            tool_name=tool_name,
            tool_input=tool_input,
            boundary_reviewed=args.boundary_reviewed,
            conversation_link_resolved=args.conversation_link_resolved,
            constitution_reviewed=args.constitution_reviewed,
            constitution_path=args.constitution_path,
            policy=policy,
        )
        confirmation_needed = bool(
            {"human_confirmation_required_for_R5", "tool_call_requires_human_confirmation"}
            & set(probe.get("blocked_reasons") or [])
        )
        if confirmation_needed:
            bridge_signal = _payload_confirmation_signal(payload, session_id) or _pending_confirmation_signal(
                state, session_id
            )
            confirmation_id = str((bridge_signal or {}).get("confirmation_id") or "")
            if bridge_signal and not _confirmation_already_consumed(state, session_id, confirmation_id):
                permit = build_single_event_human_confirmation_permit(
                    task_text=task_text,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    permit_id=confirmation_id,
                    confirmed_at_utc=str(bridge_signal["confirmed_at_utc"]),
                    expires_at_utc=str(bridge_signal["expires_at_utc"]),
                    confirmation_source=str(bridge_signal["source"]),
                )
                permit_json = json.dumps(permit, ensure_ascii=False, separators=(",", ":"))
                permit_use_ledger_path = permit_use_ledger_path or str(log_dir / "r5-permit-uses.jsonl")

    decision = runtime_enforcer(
        stage="pre_tool",
        task_text=task_text,
        cwd=cwd,
        tool_name=tool_name,
        tool_input=tool_input,
        human_confirmed=args.human_confirmed,
        human_confirmation_permit_path=permit_path,
        human_confirmation_permit_json=permit_json,
        human_confirmation_permit_use_ledger_path=permit_use_ledger_path,
        boundary_reviewed=bool(args.boundary_reviewed or (bridge_signal and permit_json)),
        conversation_link_resolved=args.conversation_link_resolved,
        constitution_reviewed=args.constitution_reviewed,
        constitution_path=args.constitution_path,
        log_dir=log_dir,
        policy=policy,
    )
    if decision["status"] == "pass" and bridge_signal:
        confirmation_id = str(bridge_signal.get("confirmation_id") or "")
        if confirmation_id:
            _consume_confirmation(state, session_id, confirmation_id)
            _save_state(log_dir, state)
    if decision["status"] == "blocked":
        return 2, _deny_output(decision)
    return 0, _allow_output()


def _handle_final(
    *,
    args: argparse.Namespace,
    payload: dict[str, Any],
    cwd: str,
    log_dir: Path,
    state: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    session_id = _session_id(payload)
    task_text = _stored_task_text(state, session_id) or _prompt_text(payload, include_nested_text=False)
    decision = runtime_enforcer(
        stage="final",
        task_text=task_text,
        cwd=cwd,
        final_text=_final_text(payload),
        human_confirmed=args.human_confirmed,
        human_confirmation_permit_path=args.human_confirmation_permit_path,
        human_confirmation_permit_json=args.human_confirmation_permit_json,
        human_confirmation_permit_use_ledger_path=args.human_confirmation_permit_use_ledger_path,
        boundary_reviewed=args.boundary_reviewed,
        conversation_link_resolved=args.conversation_link_resolved,
        constitution_reviewed=args.constitution_reviewed,
        constitution_path=args.constitution_path,
        log_dir=log_dir,
        policy=policy,
    )
    if decision["status"] == "blocked":
        return 2, _final_deny_output(decision)
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
    reason = str(sanitize_json_value(f"Claim Boundary Harness hook runner failed: {exc}"))
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
    parser = argparse.ArgumentParser(description="WorkBuddy hook runner for Claim Boundary Harness.")
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
        "--conversation-link-resolved",
        action="store_true",
        help="Mark required conversation-memory link selection or merge/archive decision as resolved.",
    )
    parser.add_argument(
        "--human-confirmed",
        action="store_true",
        help="Mark explicit human confirmation as present for R5 or hard tools.",
    )
    parser.add_argument(
        "--human-confirmation-permit-path",
        default="",
        help="Optional cbh.r5_human_confirmation_permit.v1 JSON file for one exact R5 or hard-tool event.",
    )
    parser.add_argument(
        "--human-confirmation-permit-json",
        default="",
        help="Inline cbh.r5_human_confirmation_permit.v1 JSON for one exact R5 or hard-tool event.",
    )
    parser.add_argument(
        "--human-confirmation-permit-use-ledger-path",
        default="",
        help="Optional JSONL ledger path used to record single-event R5 permit use and block replay.",
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
        policy = load_policy(args.policy or None)
        if stage in {"user_prompt", "pre_tool", "final"}:
            with _locked_state(log_dir) as state:
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
                    code, output = _handle_final(
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
