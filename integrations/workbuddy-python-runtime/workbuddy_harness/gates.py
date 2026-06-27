from __future__ import annotations

import json
import hashlib
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .policy import load_policy


NEGATION_RE = re.compile(r"(?i)(\bdo\s+not\b|\bdon't\b|\bnever\b|\bnot\b|\bno\b)[\s\w'-]{0,128}$")
RISK_LABEL_RE = re.compile(r"^R[0-5]$")
DEFAULT_LOG_FILENAME = "workbuddy_harness_events.jsonl"
SURROGATE_RE = re.compile(r"[\ud800-\udfff]")
COMMAND_TOOL_NAME_RE = re.compile(r"(?i)(bash|powershell|shell|terminal|cmd|command|exec|run)")
COMMAND_INPUT_KEYS = {
    "args",
    "argv",
    "bash_command",
    "bashcommand",
    "cmd",
    "command",
    "command_line",
    "commandline",
    "powershell_command",
    "powershellcommand",
    "script",
    "shell_command",
    "shellcommand",
}
COMMAND_INPUT_KEY_NAMES = {"".join(ch for ch in item.lower() if ch.isalnum()) for item in COMMAND_INPUT_KEYS}
HARD_TOOL_PATTERNS = [
    r"(?i)\bRemove-Item\b",
    r"(?i)\brmdir\b",
    r"(?i)\bdel\b",
    r"(?i)\brm\s+-(?:[a-z]*r[a-z]*f|[a-z]*f[a-z]*r)\b",
    r"(?i)\brm\s+-[^\s]*r[^\s]*\s+-[^\s]*f\b",
    r"(?i)\brm\s+-[^\s]*f[^\s]*\s+-[^\s]*r\b",
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


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8", errors="replace")).hexdigest()


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


def _extract_risk_label(value: str = "") -> str:
    text = str(value or "").strip()
    return text if RISK_LABEL_RE.fullmatch(text) else ""


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
                if re.search(r"status[\"']?\s*[:=]\s*[\"']?ACTIVE", combined) or "single_conversation_project_shaped_lane" in combined:
                    return str(lane)
        if current.parent == current:
            break
        current = current.parent
    return ""


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


def _input_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _is_command_tool(tool_name: str = "", tool_input: Any = None) -> bool:
    if COMMAND_TOOL_NAME_RE.search(str(tool_name or "")):
        return True
    if isinstance(tool_input, dict):
        return any(_input_key(key) in COMMAND_INPUT_KEY_NAMES for key in tool_input)
    return False


def _command_input_parts(value: Any, depth: int = 0) -> list[str]:
    if depth > 4 or value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(_command_input_parts(item, depth + 1))
        return parts
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if _input_key(key) in COMMAND_INPUT_KEY_NAMES:
                if isinstance(item, str):
                    parts.append(item)
                else:
                    try:
                        parts.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
                    except TypeError:
                        parts.append(str(item))
            elif isinstance(item, (dict, list)):
                parts.extend(_command_input_parts(item, depth + 1))
        return parts
    return []


def _risk_relevant_tool_text(tool_name: str = "", tool_input: Any = None) -> str:
    parts = [tool_name or ""]
    if _is_command_tool(tool_name, tool_input):
        command_parts = _command_input_parts(tool_input)
        if command_parts:
            parts.extend(command_parts)
        elif isinstance(tool_input, str):
            parts.append(tool_input)
    return "\n".join(part for part in parts if part)


def _pattern_hits(text: str, patterns: list[str]) -> list[str]:
    return sorted({pattern for pattern in patterns if re.search(pattern, text)})


def _read_confirmation_permit(*, permit_path: str = "", permit_json: str = "") -> dict[str, Any] | None:
    if permit_json:
        loaded = json.loads(permit_json)
        return loaded if isinstance(loaded, dict) else None
    if permit_path:
        loaded = json.loads(Path(permit_path).read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else None
    return None


def _permit_use_ledger_path(path: str = "") -> Path:
    if path:
        return Path(path)
    env_path = os.environ.get("CBH_R5_PERMIT_USE_LEDGER")
    if env_path:
        return Path(env_path)
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base) / "codex-embedded-harness" / "r5_permit_use_ledger.jsonl"
    return Path(tempfile.gettempdir()) / "codex-embedded-harness" / "r5_permit_use_ledger.jsonl"


def _permit_consume_key(*, permit_id: str, task_hash: str, tool_hash: str) -> str:
    return _sha256_hex("\n".join([permit_id, task_hash, tool_hash]))


def _permit_already_used(path: Path, consume_key: str) -> bool:
    if not consume_key or not path.exists():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("consume_key") == consume_key:
                return True
    except OSError:
        return False
    return False


def _append_permit_use(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _confirmation_permit_result(
    *,
    task_text: str,
    tool_text: str,
    permit_path: str = "",
    permit_json: str = "",
    permit_use_ledger_path: str = "",
    policy: dict[str, Any],
) -> dict[str, Any]:
    expected_task_hash = _sha256_hex(task_text)
    expected_tool_hash = _sha256_hex(tool_text)
    result: dict[str, Any] = {
        "status": "missing",
        "permit_id": None,
        "issues": [],
        "expected_task_sha256": expected_task_hash,
        "expected_tool_sha256": expected_tool_hash,
        "consume_key": None,
        "use_ledger_path": None,
        "consumed": False,
        "pending_consume": False,
        "rule": "short-lived single-event scoped permit only; natural-language approval is not sufficient; a concrete tool-event permit is recorded as used before the caller proceeds",
    }
    if not permit_path and not permit_json:
        return result
    config = policy.get("runtime_enforcement", {}).get("human_confirmation_permit", {})
    if config and config.get("enabled") is False:
        result["status"] = "blocked"
        result["issues"] = ["permit_disabled_by_policy"]
        return result

    issues: list[str] = []
    permit: dict[str, Any] | None = None
    try:
        permit = _read_confirmation_permit(permit_path=permit_path, permit_json=permit_json)
    except Exception as exc:
        issues.append(f"permit_parse_failed:{exc}")
    if not permit:
        if not issues:
            issues.append("permit_missing")
    else:
        result["permit_id"] = permit.get("permit_id")
        if permit.get("schema") != "cbh.r5_human_confirmation_permit.v1":
            issues.append("unsupported_permit_schema")
        if permit.get("status") != "active":
            issues.append("permit_not_active")
        if permit.get("confirmed_by") != "human":
            issues.append("permit_not_human_confirmed")
        if permit.get("risk_level") != "R5":
            issues.append("permit_not_r5_scoped")
        if permit.get("scope") != "single_event":
            issues.append("permit_not_single_event_scoped")
        if permit.get("task_sha256") != expected_task_hash:
            issues.append("task_hash_mismatch")
        if tool_text and permit.get("tool_sha256") != expected_tool_hash:
            issues.append("tool_hash_mismatch")
        expires_text = str(permit.get("expires_at_utc") or "")
        try:
            expires_at = datetime.fromisoformat(expires_text.replace("Z", "+00:00"))
            if expires_at.astimezone(timezone.utc) < datetime.now(timezone.utc):
                issues.append("permit_expired")
        except ValueError:
            issues.append("permit_expiry_missing_or_invalid")
        consume_on_pass = config.get("consume_on_pass", True) is not False
        consume_requires_tool_text = config.get("consume_requires_tool_text", True) is not False
        if not issues and consume_on_pass and (tool_text or not consume_requires_tool_text):
            ledger_path = _permit_use_ledger_path(permit_use_ledger_path)
            consume_key = _permit_consume_key(
                permit_id=str(permit.get("permit_id") or ""),
                task_hash=expected_task_hash,
                tool_hash=expected_tool_hash,
            )
            result["consume_key"] = consume_key
            result["use_ledger_path"] = str(ledger_path)
            if _permit_already_used(ledger_path, consume_key):
                issues.append("permit_already_used")
            else:
                result["pending_consume"] = True
    result["issues"] = sorted(set(issues))
    result["status"] = "pass" if not issues else "blocked"
    return result


def _apply_risk_override(route: dict[str, Any], risk_level: str, policy: dict[str, Any]) -> dict[str, Any]:
    risk = _extract_risk_label(risk_level)
    if not risk:
        return route

    updated = deepcopy(route)
    merged_risk = _higher_risk(str(updated.get("risk_level", "R0")), risk, policy)
    updated["risk_level"] = merged_risk
    updated["task_type"] = merged_risk

    for receipt_key in ("routing_receipt", "compact_receipt"):
        receipt = updated.get(receipt_key)
        if isinstance(receipt, dict):
            receipt["risk_level"] = merged_risk
            receipt["task_type"] = merged_risk

    if merged_risk != "R0":
        triggered = _as_list(updated.get("triggered_risks"))
        if merged_risk not in triggered:
            triggered.append(merged_risk)
        updated["triggered_risks"] = _unique([str(item) for item in triggered])
        matched = dict(updated.get("matched_risk_triggers", {}))
        matched.setdefault(merged_risk, [])
        matched[merged_risk] = _unique([str(item) for item in matched[merged_risk]] + [f"explicit_risk_level:{risk}"])
        updated["matched_risk_triggers"] = matched

    gates = [str(item) for item in _as_list(updated.get("required_gates"))]
    gates.extend(str(gate) for gate in _as_list(policy.get("risk_gate_rules", {}).get(merged_risk)))
    updated["required_gates"] = _unique(gates)
    if isinstance(updated.get("routing_receipt"), dict):
        updated["routing_receipt"]["required_gates"] = updated["required_gates"]
    if isinstance(updated.get("compact_receipt"), dict):
        updated["compact_receipt"]["required_gates"] = updated["required_gates"]

    approvals = [str(item) for item in _as_list(updated.get("approval_required"))]
    approvals.extend(str(rule) for rule in _as_list(policy.get("risk_approval_rules", {}).get(merged_risk)))
    updated["approval_required"] = _unique(approvals)
    human_confirmation_need = bool(updated["approval_required"])
    if isinstance(updated.get("compact_receipt"), dict):
        updated["compact_receipt"]["human_confirmation_need"] = human_confirmation_need

    module_need = [str(item) for item in _as_list(updated.get("module_need"))]
    if merged_risk == "R5" or str(updated.get("classification_confidence")) == "low":
        module_need.append("runtime_gate")
    updated["module_need"] = _unique(module_need)
    if isinstance(updated.get("routing_receipt"), dict):
        updated["routing_receipt"]["module_need"] = updated["module_need"]

    return updated


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


def _conversation_link_required(route: dict[str, Any], policy: dict[str, Any]) -> bool:
    contract = policy.get("conversation_linking_contract", {})
    required_intents = {str(item) for item in _as_list(contract.get("link_required_intents"))}
    return str(route.get("link_intent", "none")) in required_intents


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
        ["git_action", "tool_call", "adapter", "public_docs", "conversation_ledger", "conversation_memory", "private_rule", "local_harness", "skill_matrix", "project_memory"],
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
    scope_reassessment_hits = _matching_triggers(task_text, contract.get("scope_reassessment_triggers", []))
    if scope_reassessment_hits:
        semantic_ambiguity.append("composite_or_scope_reassessment")
        required_gates.append("scope_reassessment_gate")
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
    elif memory_hits or static_knowledge_hits:
        memory_need = "index_only"
    else:
        memory_need = "none"
    if static_knowledge_hits:
        required_gates.append("static_knowledge_index_gate")

    explicit_record_hits = _matching_triggers(task_text, contract.get("explicit_record_triggers", []))
    common_error_hits = _matching_triggers(task_text, contract.get("common_error_triggers", []))
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
        active_conversation_write_intent_hits or explicit_record_hits or common_error_hits
    )
    active_conversation_write_intent = bool(
        active_conversation_write_intent_hits or explicit_record_hits or common_error_hits
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

    if common_error_hits:
        record_intent = "inferred_reusable_error"
    elif conversation_memory_decision == "create_or_update_current_conversation":
        if conversation_explicit_hits:
            record_intent = "explicit_conversation_memory_request"
        else:
            record_intent = "conversation_checkpoint"
    elif self_reflection_record_hits:
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
    if external_need and external_need[0] != "none":
        module_need.append("external_research_gate")
    if claim_risk != "none":
        module_need.append("claim_schema_verifier")
    if risk_level == "R5" or classification_confidence == "low":
        module_need.append("runtime_gate")
    if not module_need:
        module_need.append("none")
    module_need = _unique(module_need)

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
        "skill_lifecycle_profile": skill_lifecycle_profile,
        "memory_need": memory_need,
        "hybrid_retrieval_profile": hybrid_retrieval_profile,
        "memory_mode": memory_mode,
        "memory_write_profile": memory_write_profile,
        "memory_lane": memory_lane,
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
        "skill_lifecycle_profile": skill_lifecycle_profile,
        "memory_mode": memory_mode,
        "hybrid_retrieval_profile": hybrid_retrieval_profile,
        "memory_write_profile": memory_write_profile,
        "memory_lane": memory_lane,
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
        "skill_lifecycle_profile": skill_lifecycle_profile,
        "memory_need": memory_need,
        "hybrid_retrieval_profile": hybrid_retrieval_profile,
        "memory_mode": memory_mode,
        "memory_write_profile": memory_write_profile,
        "memory_lane": memory_lane,
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

    return {
        "ts": _now(),
        "phase": "claim_schema_verifier",
        "status": "blocked" if issues else "pass",
        "claims_checked": len(claims),
        "issues": sorted(set(issues)),
        "rule": "schema enum and evidence-boundary check only; no extra LLM judgment",
    }


def runtime_enforcer(
    *,
    stage: str = "pre_task",
    task_text: str = "",
    original_task_text: str = "",
    risk_level: str = "",
    cwd: str | None = None,
    tool_name: str = "",
    tool_input: Any = None,
    claim_json: str | list[dict[str, Any]] | dict[str, Any] | None = None,
    final_text: str = "",
    human_confirmed: bool = False,
    human_confirmation_permit_path: str = "",
    human_confirmation_permit_json: str = "",
    human_confirmation_permit_use_ledger_path: str = "",
    boundary_reviewed: bool = False,
    conversation_link_resolved: bool = False,
    constitution_reviewed: bool = False,
    constitution_path: str = "",
    log_path: str | os.PathLike[str] | None = None,
    log_dir: str | os.PathLike[str] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy()
    cwd = cwd or os.getcwd()
    task_text_for_route = original_task_text or ("" if _extract_risk_label(task_text) else task_text)
    explicit_risk_level = risk_level or _extract_risk_label(task_text)
    tool_risk_text = _risk_relevant_tool_text(tool_name, tool_input)
    route_text = "\n".join(part for part in [task_text_for_route, tool_risk_text] if part)
    route = intake_router(route_text, cwd, policy)
    route = _apply_risk_override(route, explicit_risk_level, policy)
    tool_text = tool_risk_text
    configured_hard_patterns = _as_list(policy.get("runtime_enforcement", {}).get("hard_tool_patterns"))
    hard_patterns = [str(item) for item in configured_hard_patterns] or HARD_TOOL_PATTERNS
    hard_hits = _pattern_hits(tool_text, hard_patterns)
    change_hits = _pattern_hits(tool_text, CHANGE_TOOL_PATTERNS)
    conversation_link_required = _conversation_link_required(route, policy)
    permit_result = _confirmation_permit_result(
        task_text=task_text_for_route,
        tool_text=tool_text,
        permit_path=human_confirmation_permit_path,
        permit_json=human_confirmation_permit_json,
        permit_use_ledger_path=human_confirmation_permit_use_ledger_path,
        policy=policy,
    )
    effective_human_confirmed = bool(human_confirmed) or permit_result.get("status") == "pass"

    blocked: list[str] = []
    warnings: list[str] = []

    if route["risk_level"] == "R5" and not effective_human_confirmed:
        blocked.append("human_confirmation_required_for_R5")
    if hard_hits and not effective_human_confirmed:
        blocked.append("tool_call_requires_human_confirmation")
    if route["fallback_model_judgment_recommended"] and not boundary_reviewed:
        blocked.append("boundary_review_required_for_low_confidence_route")
    if stage in {"pre_task", "pre_tool"} and conversation_link_required and not conversation_link_resolved:
        reason = str(policy.get("conversation_linking_contract", {}).get("unresolved_block_reason") or "conversation_link_decision_required")
        blocked.append(reason)

    resolved_constitution = ""
    constitution_candidates = [constitution_path, os.path.join(cwd, "AGENTS.md")]
    for candidate in constitution_candidates:
        if candidate and Path(candidate).exists():
            resolved_constitution = str(Path(candidate).resolve())
            break
    if route["risk_level"] != "R0" and not resolved_constitution and not constitution_reviewed:
        blocked.append("constitution_entry_missing_or_unreviewed")

    if stage == "final":
        text_to_scan = final_text or task_text
        claim_result = claim_schema_verifier(claim_json=claim_json, final_text=text_to_scan, policy=policy)
        if claim_result["status"] != "pass":
            blocked.append("claim_schema_verifier_blocked")

    if change_hits and route["risk_level"] == "R0":
        warnings.append("tool_looks_mutating_but_route_is_R0")

    if not blocked and permit_result.get("pending_consume"):
        try:
            _append_permit_use(
                Path(str(permit_result["use_ledger_path"])),
                {
                    "schema": "cbh.r5_human_confirmation_permit_use.v1",
                    "permit_id": permit_result.get("permit_id"),
                    "consume_key": permit_result.get("consume_key"),
                    "task_sha256": permit_result.get("expected_task_sha256"),
                    "tool_sha256": permit_result.get("expected_tool_sha256"),
                    "used_at_utc": _now(),
                },
            )
            permit_result["consumed"] = True
        except OSError as exc:
            blocked.append("human_confirmation_permit_consume_failed")
            permit_result["issues"] = sorted(set([*permit_result.get("issues", []), f"permit_use_ledger_write_failed:{exc}"]))
            permit_result["status"] = "blocked"
            effective_human_confirmed = False

    result = {
        "ts": _now(),
        "phase": "runtime_enforcer",
        "stage": stage,
        "status": "blocked" if blocked else "pass",
        "cwd": cwd,
        "route": route,
        "task_text_for_route": task_text_for_route,
        "explicit_risk_level": explicit_risk_level,
        "tool_name": tool_name,
        "tool_text_scope": "command_fields_only_for_command_tools",
        "tool_hard_hits": hard_hits,
        "tool_change_hits": change_hits,
        "human_confirmed": bool(human_confirmed),
        "effective_human_confirmed": bool(effective_human_confirmed),
        "human_confirmation_permit": permit_result,
        "conversation_link_required": conversation_link_required,
        "conversation_link_resolved": conversation_link_resolved,
        "constitution_path": resolved_constitution,
        "blocked_reasons": sorted(set(blocked)),
        "warnings": sorted(set(warnings)),
        "final_text_scanned": bool(stage == "final" and final_text),
        "enforcement": "hard only when host treats this in-process function as the sole pre-execution gate",
    }
    if log_path is not None or log_dir is not None:
        result["log_flush"] = flush_logs(log_path=log_path, log_dir=log_dir, events=[result])
    return result
