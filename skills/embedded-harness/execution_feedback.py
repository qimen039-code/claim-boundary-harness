from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable

from python_inline_write_analysis import (
    analyze_python_inline_write_command,
    python_inline_write_operation_binding,
)


SCHEMA = "cbh.execution_feedback_capsule.v1"
POWERSHELL_STATEMENT_LOOP_PIPELINE = "powershell_statement_loop_pipeline"
PROFILE_REGISTRY_SCHEMA = "cbh.behavior_correction_profile_registry.v1"
ROOT = Path(__file__).resolve().parent
DEFAULT_PROFILE_REGISTRY = ROOT / "behavior_correction_profiles.json"
DEFAULT_POLICY = ROOT / "embedded_harness_policy.json"
_POWERSHELL_SAFE_TEMPLATE = (
    "$rows = foreach ($item in $items) { ... }\n"
    "$rows | <next-pipeline-command>"
)
_POWERSHELL_ALLOWED_CONSTRUCTIONS = [
    "collect_then_pipe",
    "subexpression_then_pipe",
    "foreach_object_pipeline",
]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: str | bytes) -> str:
    material = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(material).hexdigest()


class CorrectionProfileRegistryError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _error_signature(
    profile_id: str,
    evidence_ids: Iterable[str],
    *,
    profile_version: int = 1,
    profile_sha256: str = "",
    target_binding_sha256: str = "",
    subject_binding_sha256: str = "",
) -> str:
    return _sha256(
        _canonical_json(
            {
                "profile_id": profile_id,
                "profile_version": profile_version,
                "profile_sha256": profile_sha256 or None,
                "target_binding_sha256": target_binding_sha256 or None,
                "subject_binding_sha256": subject_binding_sha256 or None,
                "evidence_ids": sorted(
                    {str(item) for item in evidence_ids if str(item)}
                ),
            }
        )
    )


@lru_cache(maxsize=4)
def _load_correction_profiles_cached(
    path_text: str,
    raw_sha256: str,
    raw_text: str,
) -> dict[str, dict[str, Any]]:
    del path_text, raw_sha256
    payload = json.loads(raw_text)
    if payload.get("schema") != PROFILE_REGISTRY_SCHEMA:
        raise ValueError("invalid behavior correction profile registry schema")
    profiles: dict[str, dict[str, Any]] = {}
    for candidate in payload.get("profiles") or []:
        if not isinstance(candidate, dict):
            raise ValueError("behavior correction profile must be an object")
        profile_id = str(candidate.get("profile_id") or "")
        if not profile_id or profile_id in profiles:
            raise ValueError("behavior correction profile_id missing or duplicated")
        profile_version = candidate.get("profile_version")
        if not isinstance(profile_version, int) or profile_version < 1:
            raise ValueError("behavior correction profile_version must be positive")
        priority = candidate.get("priority")
        if not isinstance(priority, int):
            raise ValueError("behavior correction profile priority must be an integer")
        for field in (
            "enforcement",
            "correction_family_id",
            "decision_mode",
            "promotion_status",
            "behavior_class",
            "environment",
            "trigger_stage",
            "match_kind",
            "binding_handler",
            "related_handler",
            "invalid_behavior",
            "content_goal",
            "target_binding",
            "rewrite_boundary",
            "rewrite_instruction",
            "safe_template",
            "verifier",
            "verifier_channel",
            "verifier_instruction",
            "resolution_code",
            "evidence_boundary",
            "escalation_boundary",
            "source_kind",
            "source_ref",
            "postcondition",
        ):
            if not candidate.get(field):
                raise ValueError(f"behavior correction profile field missing:{field}")
        normalized = dict(candidate)
        normalized["profile_sha256"] = _sha256(_canonical_json(candidate))
        profiles[profile_id] = normalized
    if not profiles:
        raise ValueError("behavior correction profile registry is empty")
    priorities = [int(item["priority"]) for item in profiles.values()]
    if len(priorities) != len(set(priorities)):
        raise ValueError("behavior correction profile priorities must be unique")
    return profiles


def load_correction_profiles(
    path: Path = DEFAULT_PROFILE_REGISTRY,
    *,
    expected_registry_sha256: str | None = None,
    policy_path: Path = DEFAULT_POLICY,
) -> dict[str, dict[str, Any]]:
    resolved_path = path.resolve()
    runtime_contract: dict[str, Any] | None = None
    try:
        raw = resolved_path.read_bytes()
    except OSError as exc:
        raise CorrectionProfileRegistryError(
            "behavior_correction_profile_registry_unreadable"
        ) from exc
    raw_sha256 = _sha256(raw)
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
        contract = policy["runtime_enforcement"]["behavior_correction_contract"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise CorrectionProfileRegistryError(
            "behavior_correction_policy_contract_unavailable"
        ) from exc
    if contract.get("schema") != "cbh.behavior_correction_contract.v1":
        raise CorrectionProfileRegistryError(
            "behavior_correction_policy_contract_invalid"
        )
    if contract.get("profile_registry_path") != DEFAULT_PROFILE_REGISTRY.name:
        raise CorrectionProfileRegistryError(
            "behavior_correction_profile_registry_path_mismatch"
        )
    contract_registry_sha256 = str(
        contract.get("profile_registry_sha256") or ""
    )
    runtime_contract = contract
    if resolved_path == DEFAULT_PROFILE_REGISTRY.resolve():
        if (
            expected_registry_sha256 is not None
            and expected_registry_sha256 != contract_registry_sha256
        ):
            raise CorrectionProfileRegistryError(
                "behavior_correction_explicit_hash_conflicts_policy"
            )
        expected_registry_sha256 = contract_registry_sha256
    elif expected_registry_sha256 is None:
        raise CorrectionProfileRegistryError(
            "behavior_correction_noncanonical_registry_hash_required"
        )
    if (
        expected_registry_sha256 is not None
        and raw_sha256 != expected_registry_sha256
    ):
        raise CorrectionProfileRegistryError(
            "behavior_correction_profile_registry_hash_mismatch"
        )
    try:
        raw_text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeError as exc:
        raise CorrectionProfileRegistryError(
            "behavior_correction_profile_registry_encoding_invalid"
        ) from exc
    try:
        profiles = {
            profile_id: dict(profile)
            for profile_id, profile in _load_correction_profiles_cached(
                str(resolved_path),
                raw_sha256,
                raw_text,
            ).items()
        }
        handlers = registered_handler_ids()
        policy_handler_fields = {
            "match_kind": "matcher_handler_allowlist",
            "binding_handler": "binding_handler_allowlist",
            "related_handler": "related_handler_allowlist",
            "verifier": "verifier_handler_allowlist",
        }
        for profile in profiles.values():
            enforcement = str(profile.get("enforcement") or "")
            if enforcement not in {
                "rewrite_current_event_nonblocking",
                "advisory_preflight_validate",
                "advisory_predictive_review",
            }:
                raise ValueError(
                    f"unsupported behavior correction enforcement:{profile.get('enforcement')}"
                )
            decision_mode = str(profile.get("decision_mode") or "")
            promotion_status = str(profile.get("promotion_status") or "")
            expected_enforcement = {
                "auto_rewrite": "rewrite_current_event_nonblocking",
                "preflight_validate": "advisory_preflight_validate",
                "predictive_review": "advisory_predictive_review",
            }.get(decision_mode)
            if expected_enforcement is None or enforcement != expected_enforcement:
                raise ValueError("behavior correction decision_mode/enforcement mismatch")
            if promotion_status not in {
                "accepted",
                "validation_only",
                "semantic_review_only",
            }:
                raise ValueError("invalid behavior correction promotion_status")
            if decision_mode == "auto_rewrite" and promotion_status != "accepted":
                raise ValueError("auto_rewrite profile must be accepted")
            if decision_mode != "auto_rewrite" and promotion_status == "accepted":
                raise ValueError("accepted profile must use auto_rewrite")
            for field in ("source_record_ids", "historical_replay_refs"):
                values = profile.get(field)
                if not isinstance(values, list) or any(
                    not isinstance(item, str) or not item for item in values
                ):
                    raise ValueError(f"invalid behavior correction {field}")
            if str(profile.get("trigger_stage") or "") not in {
                "pretool",
                "parser_rejection",
            }:
                raise ValueError(
                    f"unsupported behavior correction trigger stage:{profile.get('trigger_stage')}"
                )
            tool_roles = profile.get("tool_roles")
            if tool_roles is not None and (
                not isinstance(tool_roles, list)
                or any(
                    str(item) not in {"read_only", "mutating", "verifier", "unknown"}
                    for item in tool_roles
                )
            ):
                raise ValueError("invalid behavior correction tool_roles")
            tool_surfaces = profile.get("tool_surfaces")
            if tool_surfaces is not None and (
                not isinstance(tool_surfaces, list)
                or not tool_surfaces
                or any(
                    not isinstance(item, str) or not item
                    for item in tool_surfaces
                )
            ):
                raise ValueError("invalid behavior correction tool_surfaces")
            verifier_channels = profile.get("verifier_channels")
            if verifier_channels is not None and (
                not isinstance(verifier_channels, list)
                or not verifier_channels
                or any(
                    not isinstance(item, str) or not item
                    for item in verifier_channels
                )
            ):
                raise ValueError(
                    "invalid behavior correction verifier_channels"
                )
            if not isinstance(profile.get("allowed_constructions"), list) or not all(
                isinstance(item, str) and item
                for item in profile["allowed_constructions"]
            ):
                raise ValueError(
                    "invalid behavior correction allowed_constructions"
                )
            if not isinstance(profile.get("requires_exact_target_binding"), bool):
                raise ValueError(
                    "invalid behavior correction requires_exact_target_binding"
                )
            parser_error_ids_any = profile.get("parser_error_ids_any")
            if parser_error_ids_any is not None and (
                not isinstance(parser_error_ids_any, list)
                or not parser_error_ids_any
                or any(
                    not isinstance(item, str) or not item
                    for item in parser_error_ids_any
                )
            ):
                raise ValueError(
                    "invalid behavior correction parser_error_ids_any"
                )
            if str(profile.get("match_kind") or "") not in handlers["matcher"]:
                raise ValueError(
                    f"unknown behavior correction matcher:{profile.get('match_kind')}"
                )
            if str(profile.get("binding_handler") or "") not in handlers["binding"]:
                raise ValueError(
                    f"unknown behavior correction binding handler:{profile.get('binding_handler')}"
                )
            if str(profile.get("related_handler") or "") not in handlers["related"]:
                raise ValueError(
                    f"unknown behavior correction related handler:{profile.get('related_handler')}"
                )
            if str(profile.get("verifier") or "") not in handlers["verifier"]:
                raise ValueError(
                    f"unknown behavior correction verifier:{profile.get('verifier')}"
                )
            if runtime_contract is not None:
                for profile_field, contract_field in policy_handler_fields.items():
                    allowlist = {
                        str(item)
                        for item in runtime_contract.get(contract_field) or []
                        if str(item)
                    }
                    if str(profile.get(profile_field) or "") not in allowlist:
                        raise ValueError(
                            "behavior correction runtime handler not allowlisted:"
                            f"{profile_field}"
                        )
            migration = profile.get("runtime_migration")
            if enforcement == "rewrite_current_event_nonblocking":
                if not isinstance(migration, dict):
                    raise ValueError(
                        "nonblocking behavior correction profile requires runtime_migration"
                    )
                if migration.get("schema") != "cbh.behavior_correction_migration.v1":
                    raise ValueError("invalid behavior correction migration schema")
                if migration.get("status") != "accepted":
                    raise ValueError("behavior correction migration is not accepted")
                if migration.get("hook_event") != "PreToolUse":
                    raise ValueError("invalid behavior correction migration hook event")
                if migration.get("tool_name") != "Bash":
                    raise ValueError("invalid behavior correction migration tool name")
                if migration.get("correction_mode") != "allow_updated_input_nonblocking":
                    raise ValueError("invalid behavior correction migration mode")
                for field in (
                    "host_blocking",
                    "stateful",
                    "automatic_memory_write",
                    "automatic_policy_mutation",
                ):
                    if migration.get(field) is not False:
                        raise ValueError(
                            f"behavior correction migration {field} must be false"
                        )
                error_ids = migration.get("expected_parser_error_ids")
                if not isinstance(error_ids, list) or not error_ids or any(
                    not isinstance(item, str) or not item for item in error_ids
                ):
                    raise ValueError("invalid migration expected_parser_error_ids")
                handler_id = str(migration.get("rewrite_handler") or "")
                if handler_id not in handlers["rewrite"]:
                    raise ValueError("unknown behavior correction rewrite handler")
                if runtime_contract is not None:
                    migration_contract = runtime_contract.get("migration_hook")
                    if not isinstance(migration_contract, dict):
                        raise ValueError("behavior correction migration hook unavailable")
                    allowlist = {
                        str(item)
                        for item in migration_contract.get(
                            "rewrite_handler_allowlist"
                        )
                        or []
                        if str(item)
                    }
                    if handler_id not in allowlist:
                        raise ValueError(
                            "behavior correction rewrite handler not allowlisted"
                        )
            elif migration is not None:
                raise ValueError(
                    "advisory behavior correction profile cannot declare runtime_migration"
                )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorrectionProfileRegistryError(
            "behavior_correction_profile_registry_semantics_invalid"
        ) from exc
    return profiles


def _statement_loop_direct_pipeline(text: str) -> bool:
    segment = _powershell_loop_segment(text)
    return bool(
        segment
        and segment.get("construction") == "direct_pipeline"
    )


def _bash_heredoc_delimiter_modes_in_powershell(text: str) -> set[str]:
    normalized = _normalized_newlines(text)
    code_only = _powershell_code_only(text)
    modes: set[str] = set()
    command_head = re.compile(
        r"(?i)^\s*(?:python(?:\d+(?:\.\d+)*)?|py)\b"
    )
    for raw_line, code_line in zip(
        normalized.splitlines(),
        code_only.splitlines(),
    ):
        if not command_head.search(code_line):
            continue
        operator_index = code_line.find("<<")
        if operator_index < 0:
            continue
        delimiter = raw_line[operator_index + 2 :].lstrip()
        quoted = re.match(
            r"(?P<quote>['\"])[A-Za-z_][A-Za-z0-9_]*(?P=quote)",
            delimiter,
        )
        if quoted:
            modes.add("quoted")
        elif re.match(r"[A-Za-z_][A-Za-z0-9_]*", delimiter):
            modes.add("unquoted")
    return modes


def _bash_heredoc_in_powershell(text: str) -> bool:
    return "quoted" in _bash_heredoc_delimiter_modes_in_powershell(text)


def _unquoted_bash_heredoc_in_powershell(text: str) -> bool:
    return "unquoted" in _bash_heredoc_delimiter_modes_in_powershell(text)


def _candidate_write_delta(text: str) -> str:
    if "*** Begin Patch" not in text:
        return text
    return "\n".join(
        line[1:] for line in text.splitlines() if line.startswith("+")
    )


def _unicode_replacement_character_in_mutation(text: str) -> bool:
    return "\ufffd" in _candidate_write_delta(text)


def _unicode_replacement_character_in_python_inline_write(text: str) -> bool:
    analysis = analyze_python_inline_write_command(text)
    return bool(
        analysis.write_intent
        and analysis.contains_unicode_replacement_character
    )


_POWERSHELL_INTERPOLATED_VARIABLE_COLON_INVALID = re.compile(
    r"(?<!`)\$(?P<name>[A-Za-z_][A-Za-z0-9_]*):(?=$|[^A-Za-z0-9_])"
)
_POWERSHELL_INTERPOLATED_VARIABLE_COLON_BRACED = re.compile(
    r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}:"
)


def _powershell_interpolated_variable_colon(text: str) -> bool:
    return bool(_POWERSHELL_INTERPOLATED_VARIABLE_COLON_INVALID.search(text))


MatcherHandler = Callable[[str], bool]
BindingHandler = Callable[[str, str, str], Any]
RelatedHandler = Callable[[dict[str, Any], dict[str, Any]], bool]
VerifierHandler = Callable[[dict[str, Any]], tuple[str, str]]
RewriteHandler = Callable[[str], str | None]


def _normalized_whitespace(text: str) -> str:
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())


def _normalized_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _powershell_code_only(text: str) -> str:
    normalized = _normalized_newlines(text)
    output: list[str] = []
    here_end: str | None = None
    quote: str | None = None
    block_comment_depth = 0

    def masked(value: str) -> str:
        return "".join(
            char if char in {"\r", "\n"} else " " for char in value
        )

    for line in normalized.splitlines(keepends=True):
        if here_end is not None:
            output.append(masked(line))
            if line.strip() == here_end:
                here_end = None
            continue
        line_output: list[str] = []
        index = 0
        while index < len(line):
            char = line[index]
            if char in {"\r", "\n"}:
                line_output.append(char)
                index += 1
                continue
            if block_comment_depth:
                if line.startswith("<#", index):
                    line_output.extend((" ", " "))
                    block_comment_depth += 1
                    index += 2
                    continue
                if line.startswith("#>", index):
                    line_output.extend((" ", " "))
                    block_comment_depth -= 1
                    index += 2
                    continue
                line_output.append(" ")
                index += 1
                continue
            if quote is not None:
                if quote == "'" and line.startswith("''", index):
                    line_output.extend((" ", " "))
                    index += 2
                    continue
                if quote == '"' and char == "`" and index + 1 < len(line):
                    line_output.append(masked(line[index : index + 2]))
                    index += 2
                    continue
                line_output.append(" ")
                if char == quote:
                    quote = None
                index += 1
                continue
            if line.startswith("<#", index):
                line_output.extend((" ", " "))
                block_comment_depth = 1
                index += 2
                continue
            if char == "#":
                line_output.append(masked(line[index:]))
                index = len(line)
                continue
            if (
                char == "@"
                and index + 1 < len(line)
                and line[index + 1] in {"'", '"'}
                and not line[index + 2 :].strip()
            ):
                here_end = line[index + 1] + "@"
                line_output.append(masked(line[index:]))
                index = len(line)
                continue
            if char in {"'", '"'}:
                quote = char
                line_output.append(" ")
                index += 1
                continue
            line_output.append(char)
            index += 1
        output.append("".join(line_output))
    return "".join(output)


def _cwd_binding(execution_cwd: str) -> str | None:
    if not execution_cwd:
        return None
    try:
        return os.path.normcase(str(Path(execution_cwd).resolve(strict=False)))
    except (OSError, RuntimeError, ValueError):
        return os.path.normcase(execution_cwd.strip()) or None


def _normalized_surrounding_context(text: str) -> str:
    return _normalized_newlines(text).strip(" \t\r\n;")


def _matching_delimiter(
    code_only: str,
    start: int,
    opening: str,
    closing: str,
) -> int | None:
    if start < 0 or start >= len(code_only) or code_only[start] != opening:
        return None
    depth = 0
    for index in range(start, len(code_only)):
        char = code_only[index]
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
    return None


def _powershell_loop_segment(text: str) -> dict[str, Any] | None:
    normalized = _normalized_newlines(text)
    code_only = _powershell_code_only(normalized)
    for match in re.finditer(
        r"(?i)\b(?P<kind>foreach|for|while)\s*\(",
        code_only,
    ):
        open_paren = code_only.find("(", match.start())
        close_paren = _matching_delimiter(code_only, open_paren, "(", ")")
        if close_paren is None:
            continue
        open_brace = close_paren + 1
        while open_brace < len(code_only) and code_only[open_brace].isspace():
            open_brace += 1
        if open_brace >= len(code_only) or code_only[open_brace] != "{":
            continue
        close_brace = _matching_delimiter(code_only, open_brace, "{", "}")
        if close_brace is None:
            continue

        segment_start = max(
            code_only.rfind(";", 0, match.start()),
            code_only.rfind("\n", 0, match.start()),
        ) + 1
        prefix = code_only[segment_start : match.start()]
        assigned = re.search(
            r"(?i)(?P<variable>\$[A-Za-z_][A-Za-z0-9_]*)\s*=\s*$",
            prefix,
        )
        pipe_index: int | None = None
        construction: str | None = None
        tail = code_only[close_brace + 1 :]
        direct = re.match(r"\s*\|", tail)
        if direct:
            pipe_index = close_brace + 1 + direct.end() - 1
            construction = "direct_pipeline"
        elif assigned:
            collected = re.match(
                r"(?is)\s*;?\s*"
                + re.escape(assigned.group("variable"))
                + r"\s*\|",
                tail,
            )
            if collected:
                pipe_index = close_brace + 1 + collected.end() - 1
                construction = "collect_then_pipe"
        else:
            subexpression = re.match(r"\s*\)\s*\|", tail)
            if subexpression:
                pipe_index = close_brace + 1 + subexpression.end() - 1
                construction = "subexpression_then_pipe"
        if pipe_index is None:
            continue
        return {
            "kind": match.group("kind").casefold(),
            "construction": construction,
            "loop_start": match.start(),
            "loop_end": close_brace + 1,
            "pipe_index": pipe_index,
            "prefix": normalized[:segment_start],
            "header": normalized[open_paren + 1 : close_paren],
            "body": normalized[open_brace + 1 : close_brace],
            "downstream": normalized[pipe_index + 1 :],
        }
    return None


def _rewrite_powershell_statement_loop_subexpression(text: str) -> str | None:
    """Wrap one direct statement-loop pipeline in a PowerShell subexpression."""

    normalized = _normalized_newlines(text)
    segment = _powershell_loop_segment(normalized)
    if not segment or segment.get("construction") != "direct_pipeline":
        return None
    loop_start = int(segment["loop_start"])
    loop_end = int(segment["loop_end"])
    candidate = (
        normalized[:loop_start]
        + "$("
        + normalized[loop_start:loop_end]
        + ")"
        + normalized[loop_end:]
    )
    if "\r\n" in text and "\n" not in text.replace("\r\n", ""):
        return candidate.replace("\n", "\r\n")
    return candidate


def _powershell_loop_pipeline_subject(
    text: str,
    target_binding_sha256: str,
    execution_cwd: str,
) -> Any:
    segment = _powershell_loop_segment(text)
    if segment:
        return {
            "kind": segment["kind"],
            "prefix": _normalized_surrounding_context(segment["prefix"]),
            "header": _normalized_newlines(segment["header"]).strip(),
            "body": _normalized_newlines(segment["body"]).strip(),
            "downstream": _normalized_newlines(segment["downstream"]).strip(),
            "target_binding_sha256": target_binding_sha256 or None,
            "execution_cwd": _cwd_binding(execution_cwd),
        }
    return {
        "fallback_text_sha256": _sha256(_normalized_newlines(text)),
        "target_binding_sha256": target_binding_sha256 or None,
        "execution_cwd": _cwd_binding(execution_cwd),
    }


def _quoted_bash_heredoc_segment(text: str) -> dict[str, str] | None:
    normalized = _normalized_newlines(text)
    match = re.search(
        r"(?ims)^\s*(?P<head>(?:python(?:\d+(?:\.\d+)*)?|py)\b[^\n]*?)"
        r"\s+<<\s*(?P<tag_quote>['\"])(?P<tag>[A-Za-z_][A-Za-z0-9_]*)(?P=tag_quote)\s*\n"
        r"(?P<body>.*?)^\s*(?P=tag)\s*$",
        normalized,
    )
    if not match:
        return None
    return {
        "head": match.group("head").strip(),
        "body": match.group("body").rstrip("\n"),
        "interpolation_mode": "literal",
        "prefix": normalized[: match.start()],
        "suffix": normalized[match.end() :],
    }


def _powershell_python_transport_segment(text: str) -> dict[str, str] | None:
    normalized = _normalized_newlines(text)
    match = re.search(
        r"(?ims)(?P<var>\$[A-Za-z_][A-Za-z0-9_]*)\s*=\s*@(?P<quote>['\"])\s*\n"
        r"(?P<body>.*?)\n(?P=quote)@\s*(?:;|\n)+\s*"
        r"(?P=var)\s*\|\s*(?P<head>(?:python(?:\d+(?:\.\d+)*)?|py)\b[^\n;]*)",
        normalized,
    )
    if not match:
        return None
    quote = match.group("quote")
    return {
        "head": match.group("head").strip(),
        "body": match.group("body").rstrip("\n"),
        "interpolation_mode": (
            "literal" if quote == "'" else "powershell_expanding"
        ),
        "prefix": normalized[: match.start()],
        "suffix": normalized[match.end() :],
    }


def _python_inline_script_subject(
    text: str,
    target_binding_sha256: str,
    execution_cwd: str,
) -> Any:
    segment = (
        _quoted_bash_heredoc_segment(text)
        or _powershell_python_transport_segment(text)
    )
    if segment:
        return {
            "interpreter_and_args": segment["head"],
            "interpreter_and_args_sha256": _sha256(
                segment["head"]
            ),
            "script_body": segment["body"],
            "interpolation_mode": segment["interpolation_mode"],
            "prefix": _normalized_surrounding_context(segment["prefix"]),
            "suffix": _normalized_surrounding_context(segment["suffix"]),
            "target_binding_sha256": target_binding_sha256 or None,
            "execution_cwd": _cwd_binding(execution_cwd),
        }
    return {
        "fallback_text_sha256": _sha256(_normalized_newlines(text)),
        "target_binding_sha256": target_binding_sha256 or None,
        "execution_cwd": _cwd_binding(execution_cwd),
    }


def _unquoted_bash_heredoc_segment(text: str) -> dict[str, str] | None:
    normalized = _normalized_newlines(text)
    match = re.search(
        r"(?ims)(?P<script>"
        r"^\s*(?:python(?:\d+(?:\.\d+)*)?|py)\b[^\n]*?"
        r"\s+<<\s*(?!['\"])(?P<tag>[A-Za-z_][A-Za-z0-9_]*)\s*\n"
        r".*?^(?P=tag)\s*$)",
        normalized,
    )
    if not match:
        return None
    return {
        "script": match.group("script").strip(),
        "prefix": normalized[: match.start()],
        "suffix": normalized[match.end() :],
    }


def _unquoted_bash_heredoc_script(text: str) -> str | None:
    segment = _unquoted_bash_heredoc_segment(text)
    return segment["script"] if segment else None


def _literal_powershell_transport_to_bash_segment(
    text: str,
) -> dict[str, str] | None:
    normalized = _normalized_newlines(text)
    match = re.search(
        r"(?ims)(?P<var>\$[A-Za-z_][A-Za-z0-9_]*)\s*=\s*@'\s*\n"
        r"(?P<script>.*?)\n'@\s*(?:;|\n)+\s*"
        r"(?P=var)\s*\|\s*bash(?:\.exe)?\s+(?P<mode>-(?:s|n))(?=\s|;|$)",
        normalized,
    )
    if not match:
        return None
    script_segment = _unquoted_bash_heredoc_segment(match.group("script"))
    if script_segment is None:
        return None
    if (
        _normalized_surrounding_context(script_segment["prefix"])
        or _normalized_surrounding_context(script_segment["suffix"])
    ):
        return None
    return {
        "script": script_segment["script"],
        "mode": match.group("mode").casefold(),
        "prefix": normalized[: match.start()],
        "suffix": normalized[match.end() :],
    }


def _literal_powershell_transport_to_bash(text: str) -> str | None:
    segment = _literal_powershell_transport_to_bash_segment(text)
    return segment["script"] if segment else None


def _python_expanding_heredoc_transport_subject(
    text: str,
    target_binding_sha256: str,
    execution_cwd: str,
) -> Any:
    transport = _literal_powershell_transport_to_bash_segment(text)
    direct = None if transport is not None else _unquoted_bash_heredoc_segment(text)
    segment = transport or direct
    if segment is not None:
        return {
            "bash_script": segment["script"],
            "interpolation_mode": "bash_expanding",
            "prefix": _normalized_surrounding_context(segment["prefix"]),
            "suffix": _normalized_surrounding_context(segment["suffix"]),
            "target_binding_sha256": target_binding_sha256 or None,
            "execution_cwd": _cwd_binding(execution_cwd),
        }
    return {
        "fallback_text_sha256": _sha256(_normalized_newlines(text)),
        "target_binding_sha256": target_binding_sha256 or None,
        "execution_cwd": _cwd_binding(execution_cwd),
    }


def _exact_mutation_target_subject(
    text: str,
    target_binding_sha256: str,
    execution_cwd: str,
) -> Any:
    operation_binding = python_inline_write_operation_binding(text)
    if operation_binding is None:
        normalized = _normalized_newlines(text)
        patch_structure: list[Any] = []
        patch_header_seen = False
        for line in normalized.splitlines():
            if re.match(
                r"^\*\*\*\s+(?:Add|Update|Delete)\s+File:\s*.+$",
                line,
            ):
                patch_header_seen = True
                patch_structure.append(line)
            elif re.match(r"^\*\*\*\s+Move\s+to:\s*.+$", line):
                patch_structure.append(line)
            elif line.startswith(("+", "-")):
                patch_structure.append(
                    {
                        "patch_line_role": (
                            "addition" if line.startswith("+") else "removal"
                        )
                    }
                )
            else:
                patch_structure.append(line)
        operation_binding = (
            {
                "operation_kind": "apply_patch",
                "patch_structure": patch_structure,
            }
            if patch_header_seen
            else {
                "operation_kind": "opaque_fail_closed",
                "text_sha256": _sha256(normalized),
            }
        )
    return {
        "target_binding_sha256": target_binding_sha256 or None,
        "execution_cwd": _cwd_binding(execution_cwd),
        "operation_binding": operation_binding,
    }


def _powershell_interpolated_variable_colon_subject(
    text: str,
    target_binding_sha256: str,
    execution_cwd: str,
) -> Any:
    normalized = _normalized_newlines(text)
    canonical = _POWERSHELL_INTERPOLATED_VARIABLE_COLON_BRACED.sub(
        lambda match: f"${match.group('name')}:",
        normalized,
    )
    canonical = _POWERSHELL_INTERPOLATED_VARIABLE_COLON_INVALID.sub(
        lambda match: f"${match.group('name')}:",
        canonical,
    )
    return {
        "canonical_text": canonical,
        "target_binding_sha256": target_binding_sha256 or None,
        "execution_cwd": _cwd_binding(execution_cwd),
    }


_MATCHER_HANDLERS: dict[str, MatcherHandler] = {
    "powershell_statement_loop_direct_pipeline": _statement_loop_direct_pipeline,
    "powershell_interpolated_variable_colon": (
        _powershell_interpolated_variable_colon
    ),
    "bash_heredoc_in_powershell": _bash_heredoc_in_powershell,
    "unquoted_bash_heredoc_in_powershell": (
        _unquoted_bash_heredoc_in_powershell
    ),
    "unicode_replacement_character_in_mutation": (
        _unicode_replacement_character_in_mutation
    ),
    "unicode_replacement_character_in_python_inline_write": (
        _unicode_replacement_character_in_python_inline_write
    ),
}

_BINDING_HANDLERS: dict[str, BindingHandler] = {
    "powershell_loop_pipeline_subject": _powershell_loop_pipeline_subject,
    "powershell_interpolated_variable_colon_subject": (
        _powershell_interpolated_variable_colon_subject
    ),
    "python_inline_script_subject": _python_inline_script_subject,
    "python_expanding_heredoc_transport_subject": (
        _python_expanding_heredoc_transport_subject
    ),
    "exact_mutation_target_subject": _exact_mutation_target_subject,
}


def derive_subject_binding(
    profile: dict[str, Any],
    *,
    text: str,
    target_binding_sha256: str,
    execution_cwd: str = "",
) -> str:
    handler_id = str(profile.get("binding_handler") or "")
    handler = _BINDING_HANDLERS.get(handler_id)
    if handler is None:
        raise ValueError(f"unknown behavior correction binding handler:{handler_id}")
    return _sha256(
        _canonical_json(
            {
                "binding_handler": handler_id,
                "material": handler(
                    text,
                    target_binding_sha256,
                    execution_cwd,
                ),
            }
        )
    )


def _profile_matches(profile: dict[str, Any], text: str) -> bool:
    match_kind = str(profile.get("match_kind") or "")
    handler = _MATCHER_HANDLERS.get(match_kind)
    return bool(handler and handler(text))


def detect_correction_profiles(
    *,
    stage: str,
    environment: str,
    tool_role: str,
    tool_surface: str = "",
    text: str,
    parser_error_ids: Iterable[str] = (),
    profiles: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    candidates = load_correction_profiles() if profiles is None else profiles
    errors = [str(item) for item in parser_error_ids if str(item)]
    matches: list[dict[str, Any]] = []
    for profile in candidates.values():
        if str(profile.get("trigger_stage") or "") != stage:
            continue
        profile_environment = str(profile.get("environment") or "")
        if profile_environment not in {"any", environment}:
            continue
        roles = {
            str(item) for item in profile.get("tool_roles") or [] if str(item)
        }
        if roles and tool_role not in roles:
            continue
        surfaces = {
            str(item)
            for item in profile.get("tool_surfaces") or []
            if str(item)
        }
        if surfaces and tool_surface not in surfaces:
            continue
        if profile.get("requires_parser_errors") is True and not errors:
            continue
        required_error_ids = {
            str(item)
            for item in profile.get("parser_error_ids_any") or []
            if str(item)
        }
        if required_error_ids and not required_error_ids.intersection(errors):
            continue
        if _profile_matches(profile, text):
            matches.append(dict(profile))
    return sorted(
        matches,
        key=lambda item: (-int(item.get("priority") or 0), str(item["profile_id"])),
    )


def detect_correction_profile(
    *,
    stage: str,
    environment: str,
    tool_role: str,
    tool_surface: str = "",
    text: str,
    parser_error_ids: Iterable[str] = (),
    profiles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    matches = detect_correction_profiles(
        stage=stage,
        environment=environment,
        tool_role=tool_role,
        tool_surface=tool_surface,
        text=text,
        parser_error_ids=parser_error_ids,
        profiles=profiles,
    )
    return matches[0] if matches else None


def new_correction_capsule(
    *,
    profile: dict[str, Any],
    session_id_sha256: str,
    episode_id: str,
    task_sha256: str,
    evidence_ids: Iterable[str],
    tool_sha256: str,
    now: str,
    target_binding_sha256: str = "",
    subject_binding_sha256: str = "",
) -> dict[str, Any]:
    profile_id = str(profile.get("profile_id") or "")
    profile_version = int(profile.get("profile_version") or 1)
    profile_sha256 = str(profile.get("profile_sha256") or "")
    error_signature = _error_signature(
        profile_id,
        evidence_ids,
        profile_version=profile_version,
        profile_sha256=profile_sha256,
        target_binding_sha256=target_binding_sha256,
        subject_binding_sha256=subject_binding_sha256,
    )
    source_record_id = str(profile.get("source_record_id") or "")
    source_kind = str(profile.get("source_kind") or "")
    source_ref = str(profile.get("source_ref") or source_record_id)
    identity = {
        "session_id_sha256": session_id_sha256,
        "episode_id": episode_id,
        "task_sha256": task_sha256,
        "profile_id": profile_id,
        "profile_version": profile_version,
        "profile_sha256": profile_sha256,
        "error_signature_sha256": error_signature,
        "target_binding_sha256": target_binding_sha256 or None,
        "subject_binding_sha256": subject_binding_sha256 or None,
    }
    return {
        "schema": SCHEMA,
        "capsule_id": "EFC-" + _sha256(_canonical_json(identity))[:32],
        **identity,
        "binding_schema": "cbh.execution_subject_target_binding.v1",
        "source_record_id": source_record_id or None,
        "source_kind": source_kind,
        "source_ref": source_ref,
        "correction_family_id": str(profile.get("correction_family_id") or ""),
        "decision_mode": str(profile.get("decision_mode") or "predictive_review"),
        "promotion_status": str(profile.get("promotion_status") or "semantic_review_only"),
        "source_record_ids": list(profile.get("source_record_ids") or []),
        "postcondition": str(profile.get("postcondition") or ""),
        "status": "active",
        "strategy_status": "candidate",
        "attempt_count": 1,
        "last_tool_sha256": tool_sha256,
        "created_at_utc": now,
        "updated_at_utc": now,
    }


def new_feedback_capsule(
    *,
    session_id_sha256: str,
    episode_id: str,
    task_sha256: str,
    shell: str,
    error_class: str,
    parser_error_ids: Iterable[str],
    source_record_id: str,
    tool_sha256: str,
    now: str,
) -> dict[str, Any]:
    profiles = load_correction_profiles()
    profile = profiles.get(error_class)
    if profile is None and error_class == POWERSHELL_STATEMENT_LOOP_PIPELINE:
        profile = profiles["powershell_statement_loop_pipeline"]
    if profile is None:
        raise ValueError(f"unknown behavior correction profile:{error_class}")
    if source_record_id and source_record_id != profile.get("source_record_id"):
        profile = {**profile, "source_record_id": source_record_id}
    capsule = new_correction_capsule(
        profile=profile,
        session_id_sha256=session_id_sha256,
        episode_id=episode_id,
        task_sha256=task_sha256,
        evidence_ids=parser_error_ids,
        tool_sha256=tool_sha256,
        now=now,
    )
    capsule["shell"] = shell
    return capsule


def _is_related_statement_loop_command(command: str) -> bool:
    if "|" not in command:
        return False
    return bool(
        re.search(
            r"(?is)(?:^|[;\r\n])\s*(?:\$[A-Za-z_][A-Za-z0-9_]*\s*=\s*)?"
            r"(?:foreach|for|while)\s*\(",
            command,
        )
        or re.search(r"(?is)(?:\$\(|\()\s*(?:foreach|for|while)\s*\(", command)
    )


def _related_statement_loop(
    capsule: dict[str, Any],
    context: dict[str, Any],
) -> bool:
    return _is_related_statement_loop_command(str(context.get("command") or ""))


def _related_python_transport(
    capsule: dict[str, Any],
    context: dict[str, Any],
) -> bool:
    command = str(context.get("command") or "")
    lower = command.casefold()
    return "python" in lower and (
        _bash_heredoc_in_powershell(command)
        or "@'" in command
        or '@"' in command
        or re.search(
            r"(?i)\bpython(?:\d+(?:\.\d+)*)?\s+(?:-m\s+)?[^\s]+\.py\b",
            command,
        )
        is not None
    )


def _related_expanding_bash_transport(
    capsule: dict[str, Any],
    context: dict[str, Any],
) -> bool:
    command = str(context.get("command") or "")
    return bool(
        _unquoted_bash_heredoc_in_powershell(command)
        or _literal_powershell_transport_to_bash(command) is not None
    )


def _related_interpolated_variable_colon(
    capsule: dict[str, Any],
    context: dict[str, Any],
) -> bool:
    command = str(context.get("command") or "")
    return bool(
        _POWERSHELL_INTERPOLATED_VARIABLE_COLON_INVALID.search(command)
        or _POWERSHELL_INTERPOLATED_VARIABLE_COLON_BRACED.search(command)
    )


def _related_same_target_mutation(
    capsule: dict[str, Any],
    context: dict[str, Any],
) -> bool:
    if str(context.get("tool_role") or "") != "mutating":
        return False
    expected_target = str(capsule.get("target_binding_sha256") or "")
    observed_target = str(context.get("target_binding_sha256") or "")
    return not expected_target or expected_target == observed_target


def _related_same_target_python_inline_write(
    capsule: dict[str, Any],
    context: dict[str, Any],
) -> bool:
    expected_target = str(capsule.get("target_binding_sha256") or "")
    observed_target = str(context.get("target_binding_sha256") or "")
    if not expected_target or expected_target != observed_target:
        return False
    return analyze_python_inline_write_command(
        str(context.get("text") or context.get("command") or "")
    ).write_intent


def _verify_same_powershell_parser(
    context: dict[str, Any],
) -> tuple[str, str]:
    if str(context.get("stage") or "") != "parser_result":
        return "not_applicable", ""
    errors = [str(item) for item in context.get("parser_error_ids") or [] if str(item)]
    if errors:
        return "failed", "same_parser_errors_present"
    return "passed", "same_parser_zero_errors"


def _verify_powershell_transport_pending_bash_syntax(
    context: dict[str, Any],
) -> tuple[str, str]:
    stage = str(context.get("stage") or "")
    if stage == "bash_posttool":
        if context.get("outcome_status") == "no_failure_observed":
            mode = str(context.get("bash_mode") or "")
            return (
                "passed",
                "same_bash_syntax_only_posttool_passed"
                if mode == "-n"
                else "same_bash_execution_posttool_implies_parse_success",
            )
        return "failed", "same_bash_posttool_failed"
    if stage != "parser_result":
        return "not_applicable", ""
    errors = [str(item) for item in context.get("parser_error_ids") or [] if str(item)]
    if errors:
        return "failed", "powershell_parser_errors_present"
    transport = _literal_powershell_transport_to_bash_segment(
        str(context.get("command") or "")
    )
    if transport is not None:
        return "pending", "awaiting_same_bash_posttool"
    return "pending", "bash_syntax_evidence_not_observed"


def _verify_unicode_input_and_readback(
    context: dict[str, Any],
) -> tuple[str, str]:
    stage = str(context.get("stage") or "")
    if stage not in {"pretool_input", "posttool_readback"}:
        return "not_applicable", ""
    if stage == "posttool_readback" and context.get("readback_status") != "verified":
        return "pending", "exact_target_readback_unavailable"
    text = _candidate_write_delta(str(context.get("text") or ""))
    if "\ufffd" in text:
        return "failed", "unicode_replacement_character_present"
    try:
        if text.encode("utf-8", errors="strict").decode(
            "utf-8", errors="strict"
        ) != text:
            return "failed", "strict_utf8_roundtrip_mismatch"
    except UnicodeError:
        return "failed", "strict_utf8_roundtrip_failed"
    return (
        "passed",
        "posttool_exact_target_unicode_integrity_verified"
        if stage == "posttool_readback"
        else "same_target_input_unicode_integrity_verified",
    )


def _verify_python_inline_unicode_input_and_readback(
    context: dict[str, Any],
) -> tuple[str, str]:
    stage = str(context.get("stage") or "")
    if stage == "posttool_readback":
        return _verify_unicode_input_and_readback(context)
    if stage != "pretool_input":
        return "not_applicable", ""
    analysis = analyze_python_inline_write_command(
        str(context.get("text") or "")
    )
    if not analysis.write_intent:
        return "not_applicable", ""
    if analysis.unresolved_target:
        return "pending", "python_inline_write_target_unresolved"
    if any(not sink.payload_is_literal for sink in analysis.sinks):
        return "pending", "python_inline_write_payload_unresolved"
    if not analysis.literal_text_payloads:
        return "pending", "python_inline_text_payload_unavailable"
    if analysis.contains_unicode_replacement_character:
        return "failed", "unicode_replacement_character_present_in_write_payload"
    try:
        for payload in analysis.literal_text_payloads:
            if payload.encode("utf-8", errors="strict").decode(
                "utf-8", errors="strict"
            ) != payload:
                return "failed", "strict_utf8_roundtrip_mismatch"
    except UnicodeError:
        return "failed", "strict_utf8_roundtrip_failed"
    return "passed", "python_inline_write_payload_unicode_integrity_verified"


_RELATED_HANDLERS: dict[str, RelatedHandler] = {
    "powershell_statement_loop_related_command": _related_statement_loop,
    "powershell_interpolated_variable_colon_related_command": (
        _related_interpolated_variable_colon
    ),
    "powershell_python_transport_related_command": _related_python_transport,
    "powershell_expanding_bash_transport_related_command": (
        _related_expanding_bash_transport
    ),
    "same_target_mutation": _related_same_target_mutation,
    "same_target_python_inline_write": (
        _related_same_target_python_inline_write
    ),
}

_VERIFIER_HANDLERS: dict[str, VerifierHandler] = {
    "same_powershell_parser_zero_errors": _verify_same_powershell_parser,
    "powershell_transport_pending_bash_syntax": (
        _verify_powershell_transport_pending_bash_syntax
    ),
    "input_unicode_no_replacement_character_and_utf8_roundtrip": (
        _verify_unicode_input_and_readback
    ),
    "python_inline_payload_no_replacement_character_and_utf8_roundtrip": (
        _verify_python_inline_unicode_input_and_readback
    ),
}

_REWRITE_HANDLERS: dict[str, RewriteHandler] = {
    "powershell_statement_loop_subexpression": (
        _rewrite_powershell_statement_loop_subexpression
    ),
}


def registered_handler_ids() -> dict[str, set[str]]:
    return {
        "matcher": set(_MATCHER_HANDLERS),
        "binding": set(_BINDING_HANDLERS),
        "related": set(_RELATED_HANDLERS),
        "verifier": set(_VERIFIER_HANDLERS),
        "rewrite": set(_REWRITE_HANDLERS),
    }


def matches_behavior_pattern(match_kind: str, text: str) -> bool:
    """Expose one canonical, side-effect-free matcher for advisory consumers."""
    handler = _MATCHER_HANDLERS.get(match_kind)
    if handler is None:
        raise ValueError(f"unknown behavior correction matcher:{match_kind}")
    return bool(handler(text))


def apply_behavior_rewrite(profile: dict[str, Any], text: str) -> str | None:
    """Apply only an explicitly accepted, allowlisted deterministic rewrite."""

    migration = profile.get("runtime_migration")
    if not isinstance(migration, dict) or migration.get("status") != "accepted":
        return None
    handler_id = str(migration.get("rewrite_handler") or "")
    handler = _REWRITE_HANDLERS.get(handler_id)
    if handler is None:
        raise ValueError(f"unknown behavior correction rewrite handler:{handler_id}")
    return handler(text)


def _profile_for_capsule(
    capsule: dict[str, Any],
    profiles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if profiles is None:
        try:
            profiles = load_correction_profiles()
        except CorrectionProfileRegistryError:
            return None
    profile = profiles.get(str(capsule.get("profile_id") or ""))
    if profile is None:
        return None
    if int(profile.get("profile_version") or 1) != int(
        capsule.get("profile_version") or 1
    ):
        return None
    capsule_profile_sha256 = str(capsule.get("profile_sha256") or "")
    if capsule_profile_sha256 and capsule_profile_sha256 != str(
        profile.get("profile_sha256") or ""
    ):
        return None
    return profile


def correction_is_related(
    capsule: dict[str, Any],
    *,
    stage: str,
    command: str = "",
    text: str = "",
    tool_role: str = "",
    tool_surface: str = "",
    target_binding_sha256: str = "",
    execution_cwd: str = "",
    profiles: dict[str, dict[str, Any]] | None = None,
) -> bool:
    if capsule.get("schema") != SCHEMA or capsule.get("status") != "active":
        return False
    profile = _profile_for_capsule(capsule, profiles)
    if profile is None:
        return False
    required_surfaces = {
        str(item)
        for item in profile.get("tool_surfaces") or []
        if str(item)
    }
    if required_surfaces and tool_surface not in required_surfaces:
        return False
    expected_subject = str(capsule.get("subject_binding_sha256") or "")
    observed_text = command or text
    if expected_subject:
        observed_subject = derive_subject_binding(
            profile,
            text=observed_text,
            target_binding_sha256=target_binding_sha256,
            execution_cwd=execution_cwd,
        )
        if observed_subject != expected_subject:
            return False
    related_handler = _RELATED_HANDLERS[str(profile["related_handler"])]
    return related_handler(
        capsule,
        {
            "stage": stage,
            "command": command,
            "text": text,
            "tool_role": tool_role,
            "tool_surface": tool_surface,
            "target_binding_sha256": target_binding_sha256,
            "execution_cwd": execution_cwd,
        },
    )


def correction_uses_verifier_channel(
    capsule: dict[str, Any],
    channel: str,
    profiles: dict[str, dict[str, Any]] | None = None,
) -> bool:
    profile = _profile_for_capsule(capsule, profiles)
    channels = (
        {
            str(item)
            for item in profile.get("verifier_channels") or []
            if str(item)
        }
        if profile is not None
        else set()
    )
    return bool(
        profile is not None
        and (
            str(profile.get("verifier_channel") or "") == channel
            or channel in channels
        )
    )


def mark_verifier_unavailable(
    capsule: dict[str, Any],
    *,
    tool_sha256: str,
    reason: str,
    now: str,
) -> dict[str, Any]:
    updated = dict(capsule)
    if updated.get("schema") != SCHEMA or updated.get("status") != "active":
        return updated
    updated["last_tool_sha256"] = tool_sha256
    updated["updated_at_utc"] = now
    updated["verification_status"] = "mechanical_verifier_unavailable"
    updated["last_verifier_status"] = "unavailable"
    updated["last_verifier_reason"] = " ".join(reason.split())[:240]
    return updated


def observe_repeated_trigger(
    capsule: dict[str, Any],
    *,
    evidence_ids: Iterable[str],
    tool_sha256: str,
    now: str,
) -> tuple[dict[str, Any], str]:
    updated = dict(capsule)
    if updated.get("schema") != SCHEMA or updated.get("status") != "active":
        return updated, "inactive"
    observed_signature = _error_signature(
        str(updated.get("profile_id") or updated.get("error_class") or ""),
        evidence_ids,
        profile_version=int(updated.get("profile_version") or 1),
        profile_sha256=str(updated.get("profile_sha256") or ""),
        target_binding_sha256=str(updated.get("target_binding_sha256") or ""),
        subject_binding_sha256=str(updated.get("subject_binding_sha256") or ""),
    )
    updated["last_tool_sha256"] = tool_sha256
    updated["updated_at_utc"] = now
    updated["last_error_signature_sha256"] = observed_signature
    if observed_signature != str(updated.get("error_signature_sha256") or ""):
        return updated, "different_signature"
    updated["attempt_count"] = int(updated.get("attempt_count") or 0) + 1
    updated["strategy_status"] = "review_required"
    updated["review_reason"] = "repeated_same_behavior_signature"
    updated["review_required_at_utc"] = now
    return updated, "repeated_failure"


def observe_related_parse(
    capsule: dict[str, Any],
    *,
    command: str,
    parser_error_ids: Iterable[str],
    tool_sha256: str,
    now: str,
    target_binding_sha256: str = "",
    execution_cwd: str = "",
    profiles: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str]:
    updated = dict(capsule)
    if updated.get("schema") != SCHEMA or updated.get("status") != "active":
        return updated, "inactive"
    profile = _profile_for_capsule(updated, profiles)
    if profile is None:
        return updated, "profile_unavailable"
    context = {
        "stage": "parser_result",
        "command": command,
        "parser_error_ids": list(parser_error_ids),
        "target_binding_sha256": target_binding_sha256,
        "execution_cwd": execution_cwd,
    }
    if not correction_is_related(
        updated,
        stage="parser_result",
        command=command,
        target_binding_sha256=target_binding_sha256,
        execution_cwd=execution_cwd,
        profiles=profiles,
    ):
        return updated, "unrelated"
    errors = sorted(
        {str(item) for item in context["parser_error_ids"] if str(item)}
    )
    if errors:
        repeated, outcome = observe_repeated_trigger(
            updated,
            evidence_ids=errors,
            tool_sha256=tool_sha256,
            now=now,
        )
        repeated["last_parser_error_signature_sha256"] = repeated.get(
            "last_error_signature_sha256"
        )
        if outcome == "repeated_failure":
            repeated["review_reason"] = "repeated_same_parser_signature"
        return repeated, outcome
    verifier = _VERIFIER_HANDLERS[str(profile["verifier"])]
    verifier_status, verifier_reason = verifier(context)
    if verifier_status != "passed":
        updated["last_verifier_status"] = verifier_status
        updated["last_verifier_reason"] = verifier_reason
        updated["updated_at_utc"] = now
        if (
            verifier_status == "pending"
            and verifier_reason == "awaiting_same_bash_posttool"
        ):
            transport = _literal_powershell_transport_to_bash_segment(command)
            if transport is not None:
                updated["strategy_status"] = "candidate_verified"
                updated["verification_status"] = "awaiting_same_bash_posttool"
                updated["pending_tool_sha256"] = tool_sha256
                updated["pending_bash_mode"] = transport["mode"]
        return (
            updated,
            "verification_pending"
            if verifier_status == "pending"
            else "verification_failed",
        )
    updated["last_tool_sha256"] = tool_sha256
    updated["updated_at_utc"] = now
    updated["status"] = "resolved"
    updated["resolution"] = str(profile.get("resolution_code") or "")
    updated["evidence_boundary"] = str(profile.get("evidence_boundary") or "")
    updated["resolved_at_utc"] = now
    updated["resolved_tool_sha256"] = tool_sha256
    return updated, "resolved"


def observe_related_input(
    capsule: dict[str, Any],
    *,
    text: str,
    tool_role: str,
    tool_surface: str = "",
    target_binding_sha256: str,
    tool_sha256: str,
    now: str,
    execution_cwd: str = "",
    profiles: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str]:
    updated = dict(capsule)
    if updated.get("schema") != SCHEMA or updated.get("status") != "active":
        return updated, "inactive"
    profile = _profile_for_capsule(updated, profiles)
    if profile is None:
        return updated, "profile_unavailable"
    context = {
        "stage": "pretool_input",
        "text": text,
        "tool_role": tool_role,
        "tool_surface": tool_surface,
        "target_binding_sha256": target_binding_sha256,
        "execution_cwd": execution_cwd,
    }
    if not correction_is_related(
        updated,
        stage="pretool_input",
        text=text,
        tool_role=tool_role,
        tool_surface=tool_surface,
        target_binding_sha256=target_binding_sha256,
        execution_cwd=execution_cwd,
        profiles=profiles,
    ):
        return updated, "unrelated"
    verifier = _VERIFIER_HANDLERS[str(profile["verifier"])]
    verifier_status, verifier_reason = verifier(context)
    if verifier_status == "failed":
        repeated, outcome = observe_repeated_trigger(
            updated,
            evidence_ids=[
                str(updated.get("profile_id") or updated.get("error_class") or "")
            ],
            tool_sha256=tool_sha256,
            now=now,
        )
        repeated["last_verifier_status"] = verifier_status
        repeated["last_verifier_reason"] = verifier_reason
        repeated["verification_status"] = verifier_reason or "verification_failed"
        return repeated, outcome
    updated["last_tool_sha256"] = tool_sha256
    updated["updated_at_utc"] = now
    if verifier_status != "passed":
        updated["last_verifier_status"] = verifier_status
        updated["last_verifier_reason"] = verifier_reason
        updated["verification_status"] = verifier_reason or "verification_pending"
        return (
            updated,
            "verification_pending"
            if verifier_status == "pending"
            else "verification_failed",
        )
    updated["last_verifier_status"] = verifier_status
    updated["last_verifier_reason"] = verifier_reason
    updated["strategy_status"] = "candidate_verified"
    updated["verification_status"] = "awaiting_posttool_readback"
    updated["candidate_resolution"] = str(profile.get("resolution_code") or "")
    updated["pending_tool_sha256"] = tool_sha256
    return updated, "candidate_verified"


def observe_posttool_verification(
    capsule: dict[str, Any],
    *,
    tool_sha256: str,
    outcome_status: str,
    readback_status: str,
    readback_text: str,
    now: str,
) -> tuple[dict[str, Any], str]:
    updated = dict(capsule)
    if updated.get("schema") != SCHEMA or updated.get("status") != "active":
        return updated, "inactive"
    if str(updated.get("pending_tool_sha256") or "") != tool_sha256:
        return updated, "unrelated"
    profile = _profile_for_capsule(updated)
    if profile is None:
        return updated, "profile_unavailable"
    updated["last_tool_sha256"] = tool_sha256
    updated["updated_at_utc"] = now
    if outcome_status != "no_failure_observed":
        updated["verification_status"] = "posttool_failed"
        return updated, "tool_failed"
    verifier = _VERIFIER_HANDLERS[str(profile["verifier"])]
    verifier_context = (
        {
            "stage": "bash_posttool",
            "outcome_status": outcome_status,
            "bash_mode": str(updated.get("pending_bash_mode") or ""),
        }
        if updated.get("verification_status") == "awaiting_same_bash_posttool"
        else {
            "stage": "posttool_readback",
            "text": readback_text,
            "readback_status": readback_status,
        }
    )
    verifier_status, verifier_reason = verifier(verifier_context)
    updated["last_verifier_status"] = verifier_status
    updated["last_verifier_reason"] = verifier_reason
    if verifier_status == "pending":
        updated["verification_status"] = (
            verifier_reason or "awaiting_exact_target_readback"
        )
        return updated, "verification_pending"
    if verifier_status != "passed":
        updated["verification_status"] = verifier_reason or "verification_failed"
        return updated, "verification_failed"
    updated["status"] = "resolved"
    updated["strategy_status"] = "resolved"
    updated["verification_status"] = "posttool_verified"
    updated["resolution"] = str(profile.get("resolution_code") or "")
    updated["evidence_boundary"] = str(profile.get("evidence_boundary") or "")
    updated["resolved_at_utc"] = now
    updated["resolved_tool_sha256"] = tool_sha256
    return updated, "resolved"


def feedback_context(capsule: dict[str, Any]) -> str:
    if capsule.get("schema") != SCHEMA or capsule.get("status") != "active":
        return ""
    profile = _profile_for_capsule(capsule)
    legacy_binding = (
        capsule.get("action_binding")
        if isinstance(capsule.get("action_binding"), dict)
        else {}
    )
    source = str(capsule.get("source_record_id") or "unknown")
    if source == "unknown":
        source = str(capsule.get("source_ref") or "unknown")
    template = str(
        (profile or {}).get("safe_template")
        or capsule.get("safe_template")
        or _POWERSHELL_SAFE_TEMPLATE
    )
    strategy_status = str(capsule.get("strategy_status") or "candidate")
    profile_id = str(capsule.get("profile_id") or capsule.get("error_class") or "unknown")
    environment = str(
        (profile or {}).get("environment")
        or legacy_binding.get("environment")
        or capsule.get("environment")
        or "unknown"
    )
    rewrite_boundary = str(
        (profile or {}).get("rewrite_boundary")
        or legacy_binding.get("rewrite_boundary")
        or "bounded_behavior_rewrite"
    )
    verifier = str(
        (profile or {}).get("verifier")
        or legacy_binding.get("verifier")
        or capsule.get("verifier")
        or "mechanical_verifier"
    )
    rewrite_instruction = str(
        (profile or {}).get("rewrite_instruction")
        or legacy_binding.get("rewrite_instruction")
        or "只改写当前机械命中的行为结构。"
    )
    verifier_instruction = str(
        (profile or {}).get("verifier_instruction")
        or legacy_binding.get("verifier_instruction")
        or f"运行机械验证器 {verifier}"
    )
    evidence_boundary = str(
        (profile or {}).get("evidence_boundary")
        or "仅按当前机械证据边界退休，不扩张为运行正确性或语义正确性证明。"
    )
    status_note = (
        "同一行为签名已复发，当前候选需重新审查并重新绑定验证器；其他环境、文档文本和无关动作不受影响。"
        if strategy_status == "review_required"
        else "本次只校正当前已机械命中的候选行为，并保留原任务继续执行。"
    )
    return (
        "CBH 行为纠偏校准："
        f"profile={profile_id}; environment={environment}; 来源 {source}。{status_note}"
        "保留原目标内容和精确目标位置；不要顺手更换路径、输入集合或输出目标。"
        f"改写边界={rewrite_boundary}；{rewrite_instruction}建议安全形式：\n"
        f"{template}\n"
        f"机械验证器={verifier}；{verifier_instruction}；"
        f"证据边界={evidence_boundary}验证通过后本胶囊自动退休。"
    )[:1000]
