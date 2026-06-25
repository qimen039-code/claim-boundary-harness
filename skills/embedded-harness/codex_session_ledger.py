#!/usr/bin/env python3
"""Build a lightweight conversation ledger from Codex Desktop JSONL sessions.

The tool is intentionally read-only with respect to raw sessions. It writes a
derived ledger directory containing indexes, bounded summaries, and evidence
references back to raw JSONL line ranges. Raw session logs remain canonical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EVIDENCE_EVENT_KINDS = {
    "user_message": "user_message",
    "task_complete": "task_complete",
    "context_compacted": "compaction",
    "compacted": "compaction",
    "token_count": "token_count",
    "patch_apply_end": "patch",
    "function_call": "tool_call",
    "custom_tool_call": "tool_call",
    "web_search_call": "web_search",
    "web_search_end": "web_search",
}


@dataclass
class TurnState:
    turn_id: str
    session_id: str
    line_start: int
    line_end: int
    time_start: str | None = None
    time_end: str | None = None
    event_counts: Counter[str] = field(default_factory=Counter)
    evidence_refs: list[str] = field(default_factory=list)
    domain_tags: set[str] = field(default_factory=set)
    summary_parts: list[str] = field(default_factory=list)
    compaction_boundary: bool = False
    token_pressure: dict[str, int | None] = field(
        default_factory=lambda: {"last_input_tokens": None, "model_context_window": None}
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def raw_file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    stat = path.stat()
    return {
        "exists": True,
        "path": str(path),
        "size_bytes": stat.st_size,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }


def sha16(raw_line: str) -> str:
    return hashlib.sha256(raw_line.encode("utf-8", errors="replace")).hexdigest()[:16]


def truncate(value: Any, limit: int = 420) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def payload_type(event: dict[str, Any]) -> str:
    payload = event.get("payload")
    if isinstance(payload, dict) and payload.get("type"):
        return str(payload["type"])
    return str(event.get("type") or "unknown")


def event_turn_id(event: dict[str, Any], current_turn_id: str | None) -> str | None:
    payload = event.get("payload")
    if isinstance(payload, dict) and payload.get("turn_id"):
        return str(payload["turn_id"])
    if isinstance(payload, dict):
        passthrough = payload.get("internal_chat_message_metadata_passthrough")
        if isinstance(passthrough, dict) and passthrough.get("turn_id"):
            return str(passthrough["turn_id"])
    return current_turn_id


def session_id_from_path(path: Path) -> str:
    match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", path.name)
    if match:
        return match.group(1)
    return path.stem


def json_line_records(path: Path) -> Iterable[tuple[int, str, dict[str, Any]]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            raw = raw_line.rstrip("\n")
            if not raw.strip():
                continue
            try:
                yield line_no, raw, json.loads(raw)
            except json.JSONDecodeError:
                continue


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                records.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
    return records


def ensure_turn(
    turns: dict[str, TurnState],
    session_id: str,
    turn_id: str,
    line_no: int,
    timestamp: str | None,
) -> TurnState:
    if turn_id not in turns:
        turns[turn_id] = TurnState(
            turn_id=turn_id,
            session_id=session_id,
            line_start=line_no,
            line_end=line_no,
            time_start=timestamp,
            time_end=timestamp,
        )
    turn = turns[turn_id]
    turn.line_end = max(turn.line_end, line_no)
    turn.time_end = timestamp or turn.time_end
    if not turn.time_start:
        turn.time_start = timestamp
    return turn


def evidence_summary(kind: str, event: dict[str, Any]) -> tuple[str, list[str]]:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    tags: list[str] = []
    if kind == "user_message":
        return f"user: {truncate(payload.get('message'), 240)}", ["user_intent"]
    if kind == "task_complete":
        return f"task_complete: {truncate(payload.get('last_agent_message'), 320)}", ["task_complete"]
    if kind == "patch_apply_end":
        changes = payload.get("changes")
        change_count = len(changes) if isinstance(changes, dict) else 0
        success = payload.get("success")
        return f"patch_apply_end: success={success} changes={change_count}", ["code_change", "artifact"]
    if kind in {"context_compacted", "compacted"}:
        return "context compacted; raw evidence required for exact details", ["compaction_boundary"]
    if kind == "token_count":
        info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
        last = info.get("last_token_usage") if isinstance(info.get("last_token_usage"), dict) else {}
        return (
            f"token_count: last_input_tokens={last.get('input_tokens')} context_window={info.get('model_context_window')}",
            ["token_pressure"],
        )
    if kind in {"web_search_call", "web_search_end"}:
        return f"web_search: {truncate(payload.get('query') or payload.get('action'), 240)}", ["external_research"]
    if kind in {"function_call", "custom_tool_call"}:
        name = payload.get("name") or payload.get("call_id") or "tool_call"
        return f"tool_call: {truncate(name, 160)}", ["tool_call"]
    return f"{kind}: raw event observed", []


def build_ledger(
    session_paths: list[Path],
    output_dir: Path,
    *,
    ledger_id: str | None = None,
    title: str = "Conversation ledger",
    project_lane: str = "PROJECTLESS",
    conversation_memory_id: str | None = None,
    conversation_memory_path: str | None = None,
    project_memory_id: str | None = None,
    continues_from_ledger_id: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    if not ledger_id:
        first = session_id_from_path(session_paths[0]) if session_paths else "empty"
        ledger_id = f"ledger:{first}"

    sessions: list[dict[str, Any]] = []
    all_turn_records: list[dict[str, Any]] = []
    all_segments: list[dict[str, Any]] = []
    all_capsules: list[dict[str, Any]] = []
    all_anchors: list[dict[str, Any]] = []
    all_evidence: list[dict[str, Any]] = []
    all_links: list[dict[str, Any]] = []
    domain_index: dict[str, list[str]] = defaultdict(list)

    for session_index, session_path in enumerate(session_paths, start=1):
        session_path = session_path.resolve()
        starting_raw_state = raw_file_state(session_path)
        session_id = session_id_from_path(session_path)
        host = "codex"
        session_meta: dict[str, Any] = {}
        event_counts: Counter[str] = Counter()
        turns: dict[str, TurnState] = {}
        current_turn_id: str | None = None
        started_at: str | None = None
        ended_at: str | None = None
        first_line: int | None = None
        last_line = 0

        for line_no, raw, event in json_line_records(session_path):
            first_line = first_line or line_no
            last_line = line_no
            timestamp = event.get("timestamp")
            started_at = started_at or timestamp
            ended_at = timestamp or ended_at
            kind = payload_type(event)
            event_counts[kind] += 1

            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            if event.get("type") == "session_meta" and isinstance(payload, dict):
                session_meta = payload
                session_id = str(payload.get("session_id") or payload.get("id") or session_id)
                host = str(payload.get("originator") or "codex")
                all_anchors.append(
                    {
                        "anchor_id": f"ANCHOR-{session_id}-session-start",
                        "ledger_id": ledger_id,
                        "session_id": session_id,
                        "turn_id": None,
                        "anchor_type": "session_start",
                        "timestamp": timestamp,
                        "summary": "session_meta observed",
                        "evidence_refs": [],
                        "source_tag": "conversation_ledger",
                        "belief_status": "raw_observed",
                        "confidence": "high",
                        "derived_from": [],
                        "score_method": "none",
                    }
                )

            if kind == "turn_context" and isinstance(payload, dict) and payload.get("turn_id"):
                current_turn_id = str(payload["turn_id"])
                turn = ensure_turn(turns, session_id, current_turn_id, line_no, timestamp)
                turn.domain_tags.add("turn_context")
                all_anchors.append(
                    {
                        "anchor_id": f"ANCHOR-{session_id}-{current_turn_id}-turn-start",
                        "ledger_id": ledger_id,
                        "session_id": session_id,
                        "turn_id": current_turn_id,
                        "anchor_type": "turn_start",
                        "timestamp": timestamp,
                        "summary": "turn_context observed",
                        "evidence_refs": [],
                        "source_tag": "conversation_ledger",
                        "belief_status": "raw_observed",
                        "confidence": "high",
                        "derived_from": [],
                        "score_method": "none",
                    }
                )

            turn_id = event_turn_id(event, current_turn_id)
            if turn_id:
                turn = ensure_turn(turns, session_id, turn_id, line_no, timestamp)
                turn.event_counts[kind] += 1
            else:
                turn = None

            evidence_kind = EVIDENCE_EVENT_KINDS.get(kind)
            if evidence_kind:
                ref_id = f"EVID-{session_id}-{line_no:06d}"
                summary, tags = evidence_summary(kind, event)
                ref = {
                    "ref_id": ref_id,
                    "ledger_id": ledger_id,
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "evidence_kind": evidence_kind,
                    "event_type": kind,
                    "summary": summary,
                    "source_tag": "raw_session",
                    "belief_status": "raw_observed",
                    "confidence": "high",
                    "derived_from": {
                        "source_type": "raw_session_jsonl",
                        "path": str(session_path),
                        "line_start": line_no,
                        "line_end": line_no,
                        "sha256_16": sha16(raw),
                    },
                    "source_monitoring": {
                        "raw_log_is_canonical": True,
                        "summary_is_navigation_only": True,
                    },
                    "lifecycle": "active",
                    "created_at": now,
                }
                all_evidence.append(ref)
                if turn:
                    turn.evidence_refs.append(ref_id)
                    turn.domain_tags.update(tags)
                    if len(turn.summary_parts) < 6 and summary:
                        turn.summary_parts.append(summary)
                    if evidence_kind == "compaction":
                        turn.compaction_boundary = True
                    if kind == "token_count":
                        info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
                        last = info.get("last_token_usage") if isinstance(info.get("last_token_usage"), dict) else {}
                        if isinstance(last.get("input_tokens"), int):
                            turn.token_pressure["last_input_tokens"] = last.get("input_tokens")
                        if isinstance(info.get("model_context_window"), int):
                            turn.token_pressure["model_context_window"] = info.get("model_context_window")

                if evidence_kind == "compaction":
                    all_anchors.append(
                        {
                            "anchor_id": f"ANCHOR-{session_id}-{line_no:06d}-compaction",
                            "ledger_id": ledger_id,
                            "session_id": session_id,
                            "turn_id": turn_id,
                            "anchor_type": "compaction_boundary",
                            "timestamp": timestamp,
                            "summary": "context compaction observed; exact details require raw evidence",
                            "evidence_refs": [ref_id],
                            "source_tag": "conversation_ledger",
                            "belief_status": "raw_observed",
                            "confidence": "high",
                            "derived_from": [ref_id],
                            "score_method": "none",
                        }
                    )
                elif evidence_kind in {"task_complete", "patch"}:
                    all_anchors.append(
                        {
                            "anchor_id": f"ANCHOR-{session_id}-{line_no:06d}-{evidence_kind}",
                            "ledger_id": ledger_id,
                            "session_id": session_id,
                            "turn_id": turn_id,
                            "anchor_type": evidence_kind,
                            "timestamp": timestamp,
                            "summary": summary,
                            "evidence_refs": [ref_id],
                            "source_tag": "conversation_ledger",
                            "belief_status": "bounded_claim",
                            "confidence": "medium",
                            "derived_from": [ref_id],
                            "score_method": "none",
                        }
                    )

        raw_ref = {
            "source_type": "raw_session_jsonl",
            "path": str(session_path),
            "line_start": first_line or 0,
            "line_end": last_line,
        }
        sessions.append(
            {
                "record_id": f"SESSION-{session_id}",
                "status": "active",
                "ledger_id": ledger_id,
                "session_id": session_id,
                "host": host,
                "raw_session_path": str(session_path),
                "project_lane": project_lane,
                "cwd": session_meta.get("cwd"),
                "model": session_meta.get("model_provider") or session_meta.get("model"),
                "client_version": session_meta.get("cli_version"),
                "started_at": started_at,
                "ended_at": ended_at,
                "raw_size_bytes": starting_raw_state.get("size_bytes"),
                "raw_mtime_utc": starting_raw_state.get("mtime_utc"),
                "raw_line_count": last_line,
                "event_counts": dict(sorted(event_counts.items())),
                "source_tag": "raw_session_manifest",
                "belief_status": "raw_observed",
                "confidence": "high",
                "derived_from": raw_ref,
                "source_monitoring": {
                    "raw_log_is_canonical": True,
                    "summary_is_navigation_only": True,
                },
                "lifecycle": "active",
            }
        )
        all_links.append(
            {
                "link_id": f"LINK-{session_id}-raw-session-ledger",
                "status": "active",
                "ledger_id": ledger_id,
                "link_type": "raw_session_to_ledger",
                "from_id": str(session_path),
                "to_id": ledger_id,
                "created_at": now,
                "created_by": "codex_session_ledger.py",
                "write_policy": "link_only",
                "evidence_boundary": "raw_log_is_canonical_no_payload_copy",
                "evidence_refs": [],
            }
        )

        for ordinal, turn in enumerate(turns.values(), start=1):
            turn_record_id = f"TURN-{session_id}-{ordinal:04d}"
            all_turn_records.append(
                {
                    "record_id": turn_record_id,
                    "status": "active",
                    "ledger_id": ledger_id,
                    "session_id": session_id,
                    "turn_id": turn.turn_id,
                    "line_start": turn.line_start,
                    "line_end": turn.line_end,
                    "time_start": turn.time_start,
                    "time_end": turn.time_end,
                    "event_counts": dict(sorted(turn.event_counts.items())),
                    "token_pressure": turn.token_pressure,
                    "evidence_refs": turn.evidence_refs,
                    "source_tag": "conversation_ledger",
                    "belief_status": "bounded_claim",
                    "confidence": "medium",
                    "derived_from": turn.evidence_refs,
                    "score_method": "none",
                }
            )
            tags = sorted(turn.domain_tags or {"general"})
            segment_id = f"SEG-{session_id}-{ordinal:04d}"
            summary = " | ".join(turn.summary_parts) if turn.summary_parts else "turn observed; inspect evidence_refs for details"
            segment = {
                "segment_id": segment_id,
                "status": "active",
                "ledger_id": ledger_id,
                "session_id": session_id,
                "turn_id": turn.turn_id,
                "time_start": turn.time_start,
                "time_end": turn.time_end,
                "line_start": turn.line_start,
                "line_end": turn.line_end,
                "domain_tags": tags,
                "summary": truncate(summary, 1000),
                "compaction_boundary": turn.compaction_boundary,
                "evidence_refs": turn.evidence_refs,
                "source_tag": "conversation_ledger",
                "belief_status": "bounded_claim",
                "confidence": "medium",
                "derived_from": turn.evidence_refs,
                "score_method": "none",
            }
            all_segments.append(segment)
            for tag in tags:
                domain_index[tag].append(segment_id)

    if conversation_memory_id:
        all_links.append(
            {
                "link_id": f"LINK-{ledger_id}-conversation-memory",
                "status": "active",
                "ledger_id": ledger_id,
                "link_type": "ledger_to_conversation_memory",
                "from_id": ledger_id,
                "to_id": conversation_memory_id,
                "to_path": conversation_memory_path,
                "created_at": now,
                "created_by": "codex_session_ledger.py",
                "write_policy": "link_only",
                "evidence_boundary": "ledger_links_to_memory_no_payload_copy",
                "evidence_refs": [],
            }
        )
    if project_memory_id:
        all_links.append(
            {
                "link_id": f"LINK-{ledger_id}-project-memory",
                "status": "active",
                "ledger_id": ledger_id,
                "link_type": "ledger_to_project_memory",
                "from_id": ledger_id,
                "to_id": project_memory_id,
                "created_at": now,
                "created_by": "codex_session_ledger.py",
                "write_policy": "link_only",
                "evidence_boundary": "ledger_links_to_project_memory_no_payload_copy",
                "evidence_refs": [],
            }
        )
    if continues_from_ledger_id:
        all_links.append(
            {
                "link_id": f"LINK-{continues_from_ledger_id}-continues-{ledger_id}",
                "status": "active",
                "ledger_id": ledger_id,
                "link_type": "continuation",
                "from_id": continues_from_ledger_id,
                "to_id": ledger_id,
                "created_at": now,
                "created_by": "codex_session_ledger.py",
                "write_policy": "link_only",
                "evidence_boundary": "continuation_link_no_payload_copy",
                "evidence_refs": [],
            }
        )

    evidence_kind_by_ref = {str(record.get("ref_id")): str(record.get("evidence_kind")) for record in all_evidence}
    for segment in all_segments:
        evidence_refs = [str(ref_id) for ref_id in segment.get("evidence_refs", [])]
        event_kinds = sorted({evidence_kind_by_ref[ref_id] for ref_id in evidence_refs if ref_id in evidence_kind_by_ref})
        capsule_id = str(segment["segment_id"]).replace("SEG-", "CAP-", 1)
        all_capsules.append(
            {
                "capsule_id": capsule_id,
                "capsule_type": "event_domain_classification",
                "status": "active",
                "ledger_id": ledger_id,
                "session_id": segment.get("session_id"),
                "turn_id": segment.get("turn_id"),
                "time_start": segment.get("time_start"),
                "time_end": segment.get("time_end"),
                "domain_tags": segment.get("domain_tags", []),
                "event_kinds": event_kinds,
                "meta_summary": segment.get("summary"),
                "compaction_boundary": segment.get("compaction_boundary", False),
                "evidence_refs": evidence_refs,
                "source_tag": "conversation_ledger_capsule",
                "belief_status": "bounded_claim",
                "confidence": "medium",
                "derived_from": {
                    "segment_id": segment.get("segment_id"),
                    "evidence_refs": evidence_refs,
                },
                "source_monitoring": {
                    "raw_log_is_canonical": True,
                    "summary_is_navigation_only": True,
                    "classification_is_derivative": True,
                },
                "score_method": "deterministic_event_mapping",
                "lifecycle": "active",
                "created_at": now,
            }
        )

    capsule_domain_index: dict[str, list[str]] = defaultdict(list)
    for capsule in all_capsules:
        for tag in capsule.get("domain_tags", []):
            capsule_domain_index[str(tag)].append(str(capsule["capsule_id"]))

    write_jsonl(output_dir / "sessions.jsonl", sessions)
    write_jsonl(output_dir / "turns.jsonl", all_turn_records)
    write_jsonl(output_dir / "segments.jsonl", all_segments)
    write_jsonl(output_dir / "capsules.jsonl", all_capsules)
    write_jsonl(output_dir / "time_anchors.jsonl", all_anchors)
    write_jsonl(output_dir / "evidence_refs.jsonl", all_evidence)
    write_jsonl(output_dir / "links.jsonl", all_links)

    domain_payload = {
        "ledger_id": ledger_id,
        "status": "active",
        "updated_at": now,
        "domains": {key: sorted(value) for key, value in sorted(domain_index.items())},
        "capsule_domains": {key: sorted(value) for key, value in sorted(capsule_domain_index.items())},
        "retrieval_order": [
            "_LEDGER_INDEX.md",
            "domain_index.json, capsules.jsonl, or sessions.jsonl",
            "segments.jsonl",
            "evidence_refs.jsonl",
            "raw session snippet only when exact detail matters",
        ],
    }
    (output_dir / "domain_index.json").write_text(json.dumps(domain_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "_LEDGER_INDEX.md").write_text(
        ledger_index_text(
            ledger_id=ledger_id,
            title=title,
            project_lane=project_lane,
            now=now,
            session_count=len(sessions),
            turn_count=len(all_turn_records),
            segment_count=len(all_segments),
            capsule_count=len(all_capsules),
            evidence_count=len(all_evidence),
            conversation_memory_id=conversation_memory_id,
            project_memory_id=project_memory_id,
        ),
        encoding="utf-8",
    )

    return {
        "status": "pass",
        "ledger_id": ledger_id,
        "output_dir": str(output_dir.resolve()),
        "sessions": len(sessions),
        "turns": len(all_turn_records),
        "segments": len(all_segments),
        "capsules": len(all_capsules),
        "evidence_refs": len(all_evidence),
        "links": len(all_links),
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=False) + "\n")


def status_from(checks: list[dict[str, Any]]) -> str:
    statuses = {str(check.get("status")) for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


def add_check(checks: list[dict[str, Any]], check_id: str, status: str, summary: str, **evidence: Any) -> None:
    checks.append({"id": check_id, "status": status, "summary": summary, "evidence": evidence})


def doctor_ledger(ledger_dir: Path) -> dict[str, Any]:
    """Validate ledger structure without reading raw session payloads."""

    ledger_dir = ledger_dir.resolve()
    checks: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    stale_sessions: list[dict[str, Any]] = []
    required_jsonl = [
        "sessions.jsonl",
        "turns.jsonl",
        "segments.jsonl",
        "time_anchors.jsonl",
        "evidence_refs.jsonl",
        "links.jsonl",
    ]
    optional_jsonl = ["capsules.jsonl"]
    required_files = ["_LEDGER_INDEX.md", "domain_index.json", *required_jsonl]

    for name in required_files:
        path = ledger_dir / name
        add_check(
            checks,
            f"file.{name}",
            "pass" if path.exists() else "fail",
            "required ledger file exists" if path.exists() else "required ledger file is missing",
            path=str(path),
        )

    parsed: dict[str, list[dict[str, Any]]] = {}
    for name in [*required_jsonl, *optional_jsonl]:
        path = ledger_dir / name
        if not path.exists():
            if name in optional_jsonl:
                add_check(
                    checks,
                    f"optional.{name}",
                    "warn",
                    "optional capsule compatibility view is missing; rebuild to create it",
                    path=str(path),
                )
            continue
        try:
            records = read_jsonl(path)
            parsed[name] = records
            counts[name] = len(records)
            add_check(checks, f"jsonl.{name}", "pass", "JSONL parsed", records=len(records))
        except ValueError as exc:
            add_check(checks, f"jsonl.{name}", "fail", "JSONL parse failed", error=str(exc))

    domain_path = ledger_dir / "domain_index.json"
    if domain_path.exists():
        try:
            json.loads(domain_path.read_text(encoding="utf-8"))
            add_check(checks, "json.domain_index", "pass", "domain_index.json parsed")
        except json.JSONDecodeError as exc:
            add_check(checks, "json.domain_index", "fail", "domain_index.json parse failed", error=str(exc))

    for session in parsed.get("sessions.jsonl", []):
        raw_path = Path(str(session.get("raw_session_path") or ""))
        raw_state = raw_file_state(raw_path)
        if not raw_state["exists"]:
            add_check(checks, "raw.exists", "fail", "raw session path is missing", path=str(raw_path))
            continue
        recorded_size = session.get("raw_size_bytes")
        recorded_mtime = session.get("raw_mtime_utc")
        size_changed = recorded_size is not None and recorded_size != raw_state.get("size_bytes")
        mtime_changed = recorded_mtime is not None and recorded_mtime != raw_state.get("mtime_utc")
        if recorded_size is None or recorded_mtime is None:
            add_check(
                checks,
                "raw.staleness",
                "warn",
                "raw staleness metadata is missing; rebuild once to enable stat-only stale checks",
                path=str(raw_path),
            )
            stale_sessions.append({"session_id": session.get("session_id"), "reason": "missing_stat_metadata"})
        elif size_changed or mtime_changed:
            add_check(
                checks,
                "raw.staleness",
                "warn",
                "raw session stat differs from ledger record",
                path=str(raw_path),
                recorded_size_bytes=recorded_size,
                current_size_bytes=raw_state.get("size_bytes"),
                recorded_mtime_utc=recorded_mtime,
                current_mtime_utc=raw_state.get("mtime_utc"),
            )
            stale_sessions.append({"session_id": session.get("session_id"), "reason": "raw_stat_changed"})
        else:
            add_check(checks, "raw.staleness", "pass", "raw session stat matches ledger record", path=str(raw_path))

    links = parsed.get("links.jsonl", [])
    link_types = {str(record.get("link_type")) for record in links}
    add_check(
        checks,
        "links.raw_session_to_ledger",
        "pass" if "raw_session_to_ledger" in link_types else "fail",
        "raw session link exists" if "raw_session_to_ledger" in link_types else "raw session link is missing",
    )
    add_check(
        checks,
        "links.memory",
        "pass" if {"ledger_to_conversation_memory", "ledger_to_project_memory"} & link_types else "warn",
        "memory link exists" if {"ledger_to_conversation_memory", "ledger_to_project_memory"} & link_types else "no project/conversation memory link recorded",
    )

    anchors = parsed.get("time_anchors.jsonl", [])
    compaction_count = sum(1 for record in anchors if record.get("anchor_type") == "compaction_boundary")
    counts["compaction_anchors"] = compaction_count
    add_check(
        checks,
        "anchors.compaction",
        "pass" if compaction_count else "warn",
        "compaction anchors recorded" if compaction_count else "no compaction anchors recorded",
        count=compaction_count,
    )

    result = {
        "status": status_from(checks),
        "mode": "doctor",
        "ledger_dir": str(ledger_dir),
        "stale": bool(stale_sessions),
        "stale_sessions": stale_sessions,
        "counts": counts,
        "checks": checks,
        "cost_boundary": "does not read raw session payloads; uses ledger JSON/JSONL and raw file stat only",
    }
    return result


def find_evidence_ref(ledger_dir: Path, ref_id: str) -> dict[str, Any] | None:
    evidence_path = ledger_dir / "evidence_refs.jsonl"
    if not evidence_path.exists():
        return None
    with evidence_path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            if ref_id not in raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if record.get("ref_id") == ref_id:
                return record
    return None


def read_raw_window(path: Path, line_start: int, line_end: int, *, context_lines: int, max_chars_per_line: int) -> list[dict[str, Any]]:
    start = max(1, line_start - context_lines)
    end = max(line_end, line_end + context_lines)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            if line_no < start:
                continue
            if line_no > end:
                break
            full_text = raw.rstrip("\n")
            text = full_text
            truncated = len(text) > max_chars_per_line
            if truncated:
                text = text[: max_chars_per_line - 3] + "..."
            rows.append({"line": line_no, "text": text, "sha256_16": sha16(full_text), "truncated": truncated})
    return rows


def resolve_evidence(ledger_dir: Path, ref_id: str, *, context_lines: int = 20, max_chars_per_line: int = 800) -> dict[str, Any]:
    ledger_dir = ledger_dir.resolve()
    evidence = find_evidence_ref(ledger_dir, ref_id)
    if evidence is None:
        return {"status": "fail", "mode": "resolve", "ref_id": ref_id, "error": "evidence ref not found"}
    derived = evidence.get("derived_from") if isinstance(evidence.get("derived_from"), dict) else {}
    raw_path = Path(str(derived.get("path") or ""))
    if not raw_path.exists():
        return {"status": "fail", "mode": "resolve", "ref_id": ref_id, "error": "raw path not found", "path": str(raw_path)}
    line_start = int(derived.get("line_start") or 1)
    line_end = int(derived.get("line_end") or line_start)
    window = read_raw_window(
        raw_path,
        line_start,
        line_end,
        context_lines=max(0, context_lines),
        max_chars_per_line=max(80, max_chars_per_line),
    )
    target_row = next((row for row in window if row["line"] == line_start), None)
    expected_hash = derived.get("sha256_16")
    hash_match = target_row.get("sha256_16") == expected_hash if expected_hash and target_row else None
    return {
        "status": "pass" if hash_match is not False else "warn",
        "mode": "resolve",
        "ref_id": ref_id,
        "evidence": evidence,
        "raw_window": window,
        "hash_match": hash_match,
        "cost_boundary": "reads only the selected raw line window, not the full session into memory",
    }


def refresh_ledger(
    session_paths: list[Path],
    output_dir: Path,
    *,
    force: bool = False,
    auto: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    if output_dir.exists() and not force:
        doctor = doctor_ledger(output_dir)
        if doctor["status"] != "fail" and not doctor.get("stale"):
            return {
                "status": "pass",
                "mode": "refresh",
                "refreshed": False,
                "reason": "ledger_is_fresh",
                "doctor": doctor,
            }
        if auto and doctor["status"] == "warn" and not doctor.get("stale"):
            return {
                "status": "warn",
                "mode": "refresh",
                "refreshed": False,
                "reason": "auto_mode_warn_only_no_stale_raw_stat",
                "doctor": doctor,
                "cost_boundary": "auto mode does not rebuild on non-stale warnings",
            }
    result = build_ledger(session_paths, output_dir, **kwargs)
    result["mode"] = "refresh"
    result["refreshed"] = True
    return result


def auto_check(
    output_dir: Path,
    *,
    session_paths: list[Path] | None = None,
    refresh_on_stale: bool = False,
    build_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cheap boundary check for normal turns and stop/final hooks.

    This is the default low-cost guard: inspect ledger files and raw file stats.
    It does not read raw payloads. If `refresh_on_stale` is set and a session
    path is provided, it rebuilds only when the stat-only check says stale.
    """

    output_dir = output_dir.resolve()
    if not output_dir.exists():
        if refresh_on_stale and session_paths:
            result = build_ledger(session_paths, output_dir, **(build_kwargs or {}))
            result["mode"] = "auto"
            result["action"] = "built_missing_ledger"
            return result
        return {
            "status": "warn",
            "mode": "auto",
            "action": "missing_ledger",
            "ledger_dir": str(output_dir),
            "cost_boundary": "checked ledger directory only",
        }

    doctor = doctor_ledger(output_dir)
    if refresh_on_stale and doctor.get("stale") and session_paths:
        result = build_ledger(session_paths, output_dir, **(build_kwargs or {}))
        result["mode"] = "auto"
        result["action"] = "refreshed_stale_ledger"
        result["previous_doctor"] = doctor
        return result

    return {
        "status": doctor["status"],
        "mode": "auto",
        "action": "checked_only",
        "doctor": doctor,
        "cost_boundary": "stat-only by default; no raw session payload read",
    }


def ledger_index_text(
    *,
    ledger_id: str,
    title: str,
    project_lane: str,
    now: str,
    session_count: int,
    turn_count: int,
    segment_count: int,
    capsule_count: int,
    evidence_count: int,
    conversation_memory_id: str | None,
    project_memory_id: str | None,
) -> str:
    return f"""# Conversation Ledger Index

This is a generated first-read routing surface for a conversation ledger.

## Ledger

```text
ledger_id: {ledger_id}
ledger_type: conversation_ledger
status: active
title: {title}
project_lane: {project_lane}
created_or_updated_at: {now}
conversation_memory_id: {conversation_memory_id or "null"}
project_memory_id: {project_memory_id or "null"}
```

## Counts

```text
sessions: {session_count}
turns: {turn_count}
segments: {segment_count}
capsules: {capsule_count}
evidence_refs: {evidence_count}
```

## Retrieval Rule

```text
read _LEDGER_INDEX.md
-> choose domain_index.json, capsules.jsonl, or sessions.jsonl
-> open matching segments.jsonl records
-> open selected evidence_refs.jsonl records
-> inspect raw session snippets or artifacts only when exact detail matters
```

## Source Boundary

- Raw session JSONL and artifact/test outputs are canonical evidence.
- Ledger summaries are navigation only.
- Client compaction summaries are not full-detail evidence.
- Exact user wording, code diffs, test results, external facts, R5 confirmations,
  and memory links require evidence refs.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        choices=["build", "doctor", "refresh", "resolve", "auto"],
        default="build",
        help="Operation mode. Omit for legacy build behavior.",
    )
    parser.add_argument("--session-jsonl", action="append", help="Codex session JSONL path. Can be repeated.")
    parser.add_argument("--output-dir", help="Directory where ledger files will be written.")
    parser.add_argument("--ledger-dir", help="Existing ledger directory for doctor/resolve. Defaults to --output-dir.")
    parser.add_argument("--ledger-id", default=None, help="Stable ledger id. Defaults to ledger:<first_session_id>.")
    parser.add_argument("--title", default="Conversation ledger", help="Human title for _LEDGER_INDEX.md.")
    parser.add_argument("--project-lane", default="PROJECTLESS")
    parser.add_argument("--conversation-memory-id", default=None)
    parser.add_argument("--conversation-memory-path", default=None)
    parser.add_argument("--project-memory-id", default=None)
    parser.add_argument("--continues-from-ledger-id", default=None)
    parser.add_argument("--ref-id", help="Evidence ref id for resolve mode.")
    parser.add_argument("--context-lines", type=int, default=20, help="Raw line context for resolve mode.")
    parser.add_argument("--max-chars-per-line", type=int, default=800, help="Truncate raw lines in resolve mode.")
    parser.add_argument("--force", action="store_true", help="Force refresh even when stat-only doctor says fresh.")
    parser.add_argument("--refresh-on-stale", action="store_true", help="In auto mode, rebuild only when stat-only checks say stale.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ledger_dir_arg = args.ledger_dir or args.output_dir
    if args.command == "doctor":
        if not ledger_dir_arg:
            raise SystemExit("--ledger-dir or --output-dir is required for doctor mode")
        result = doctor_ledger(Path(ledger_dir_arg))
    elif args.command == "resolve":
        if not ledger_dir_arg:
            raise SystemExit("--ledger-dir or --output-dir is required for resolve mode")
        if not args.ref_id:
            raise SystemExit("--ref-id is required for resolve mode")
        result = resolve_evidence(
            Path(ledger_dir_arg),
            args.ref_id,
            context_lines=args.context_lines,
            max_chars_per_line=args.max_chars_per_line,
        )
    elif args.command == "auto":
        if not ledger_dir_arg:
            raise SystemExit("--ledger-dir or --output-dir is required for auto mode")
        build_kwargs = {
            "ledger_id": args.ledger_id,
            "title": args.title,
            "project_lane": args.project_lane,
            "conversation_memory_id": args.conversation_memory_id,
            "conversation_memory_path": args.conversation_memory_path,
            "project_memory_id": args.project_memory_id,
            "continues_from_ledger_id": args.continues_from_ledger_id,
        }
        result = auto_check(
            Path(ledger_dir_arg),
            session_paths=[Path(item) for item in args.session_jsonl] if args.session_jsonl else None,
            refresh_on_stale=args.refresh_on_stale,
            build_kwargs=build_kwargs,
        )
    else:
        if not args.session_jsonl:
            raise SystemExit("--session-jsonl is required for build/refresh mode")
        if not args.output_dir:
            raise SystemExit("--output-dir is required for build/refresh mode")
        build_kwargs = {
            "ledger_id": args.ledger_id,
            "title": args.title,
            "project_lane": args.project_lane,
            "conversation_memory_id": args.conversation_memory_id,
            "conversation_memory_path": args.conversation_memory_path,
            "project_memory_id": args.project_memory_id,
            "continues_from_ledger_id": args.continues_from_ledger_id,
        }
        if args.command == "refresh":
            result = refresh_ledger(
                [Path(item) for item in args.session_jsonl],
                Path(args.output_dir),
                force=args.force,
                **build_kwargs,
            )
        else:
            result = build_ledger(
                [Path(item) for item in args.session_jsonl],
                Path(args.output_dir),
                **build_kwargs,
            )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
