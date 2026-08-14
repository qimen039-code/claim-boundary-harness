from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any


HARNESS_ROOT = Path(__file__).resolve().parent
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))

from behavior_correction_gate import build_behavior_correction_receipt  # noqa: E402
from execution_feedback import CorrectionProfileRegistryError  # noqa: E402
from engineering_execution import build_engineering_execution_receipt  # noqa: E402
from external_retrieval_strategy import build_external_retrieval_receipt  # noqa: E402
from semantic_memory import (  # noqa: E402
    META_SCHEMA as SEMANTIC_MEMORY_META_SCHEMA,
    STORE_SCHEMA as SEMANTIC_MEMORY_STORE_SCHEMA,
    materialize_memory_record,
)
from task_continuity import (  # noqa: E402
    apply_task_event,
    build_dynamic_reminders,
    build_task_capsule_context,
    decide_task_continuity,
    initialize_task_capsule,
    new_task_capsule,
    page_result,
    plan_transport,
)


SCHEMA = "cbh.model_context_consumption.v1"
SOFT_TARGET_RECORDS = 3
MAX_DIRECT_RECORDS = 8
CONTEXT_SOFT_TARGET_CHARS = 3200
DIRECT_SCORE = 60
MEMORY_QUERY_TYPES = {"current_state", "history_reason", "contradiction_check"}

GENERIC_TERMS = {
    "agent",
    "current",
    "data",
    "framework",
    "memory",
    "model",
    "record",
    "system",
    "task",
    "内容",
    "当前",
    "问题",
    "大模型",
    "系统",
    "机制",
    "框架",
    "模型",
    "记录",
    "记忆",
}

DIRECT_FIELDS = (
    "retrieval_terms",
    "semantic_anchors",
    "trigger_aliases",
    "aliases",
    "phrase",
    "exact_trigger",
    "title",
    "event_id",
    "error_id",
    "solution_id",
)

DISPLAY_FIELDS = (
    "decision",
    "anchored_meaning",
    "summary",
    "solution",
    "solution_applied",
    "prevention_rule",
    "future_reuse_rule",
    "next_action",
    "error",
)

SEMANTIC_MEMORY_FAMILIES = {
    "error": "ERR",
    "solution": "SOL",
    "common_error": "CE",
    "interaction_error": "IE",
    "semantic_anchor": "ANCHOR",
    "major_incident": "INC",
    "event_cluster": "CLUSTER",
}


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_flatten_strings(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(_flatten_strings(item))
        return result
    return []


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _route_field(route: dict[str, Any], name: str, default: Any = None) -> Any:
    receipt = route.get("routing_receipt")
    if isinstance(receipt, dict) and name in receipt:
        return receipt[name]
    compact = route.get("compact_receipt")
    if isinstance(compact, dict) and name in compact:
        return compact[name]
    return route.get(name, default)


def _route_object_list(route: dict[str, Any], name: str) -> list[dict[str, Any]]:
    value = _route_field(route, name, [])
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _normalized_confirmation_request(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    scalar_fields = (
        "schema",
        "action",
        "target_binding",
        "scope",
        "impact",
        "recovery",
        "persistence",
    )
    request: dict[str, Any] = {
        key: str(value[key])
        for key in scalar_fields
        if isinstance(value.get(key), str) and value[key]
    }
    for key in ("target", "non_targets", "required_disclosures"):
        items = value.get(key)
        if isinstance(items, list):
            request[key] = [str(item) for item in items if str(item)]
    required = {"action", "target", "scope", "impact", "recovery", "non_targets"}
    if not required.issubset(request):
        return None
    request["persistence"] = "none"
    return request


def _path_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _terms(text: str) -> set[str]:
    normalized = _normalize(text)
    terms = {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_.:/-]{2,}", normalized)
        if token not in GENERIC_TERMS
    }
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
        if chunk not in GENERIC_TERMS and len(chunk) <= 18:
            terms.add(chunk)
        for width in (2, 3, 4):
            if len(chunk) < width:
                continue
            for start in range(len(chunk) - width + 1):
                gram = chunk[start : start + width]
                if gram not in GENERIC_TERMS:
                    terms.add(gram)
    return terms


def _record_id(record: dict[str, Any], *, fallback: str) -> str:
    for key in ("record_id", "anchor_id", "incident_id", "decision_id", "link_id", "memory_id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _candidate(
    record: dict[str, Any],
    *,
    family: str,
    path: Path,
    line: int,
    fallback_id: str,
    navigation_only: bool = False,
) -> dict[str, Any]:
    record_id = _record_id(record, fallback=fallback_id)
    direct_values = [record_id]
    for field in DIRECT_FIELDS:
        direct_values.extend(_flatten_strings(record.get(field)))
    return {
        "record_id": record_id,
        "family": family,
        "path": str(path),
        "line": line,
        "raw": record,
        "direct_values": _unique(direct_values),
        "all_values": _unique(_flatten_strings(record)),
        "navigation_only": navigation_only,
    }


def _load_source_hint(hint: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_root = str(hint.get("root_path") or "")
    if not raw_root:
        return [], {"root_path": raw_root, "status": "rejected", "reason": "missing_root_path"}
    root = Path(raw_root)
    if not root.is_dir():
        return [], {"root_path": raw_root, "status": "rejected", "reason": "root_not_found"}

    meta = Path(str(hint.get("meta_path") or root / "_META_INDEX.md"))
    if not _path_inside(meta, root):
        return [], {"root_path": raw_root, "status": "rejected", "reason": "meta_outside_root"}

    candidates: list[dict[str, Any]] = []
    source_paths: list[str] = []
    semantic_store_path = root / "store.json"
    semantic_meta_path = root / "meta.jsonl"
    if semantic_store_path.is_file() and semantic_meta_path.is_file():
        try:
            store_manifest = json.loads(
                semantic_store_path.read_text(encoding="utf-8", errors="strict")
            )
            if store_manifest.get("schema") != SEMANTIC_MEMORY_STORE_SCHEMA:
                raise ValueError("invalid_semantic_memory_store_schema")
            with semantic_meta_path.open(
                "r", encoding="utf-8", errors="strict", newline=""
            ) as handle:
                for line_no, raw_line in enumerate(handle, start=1):
                    if raw_line.endswith("\r\n"):
                        raise ValueError("semantic_memory_meta_crlf_not_allowed")
                    if not raw_line.strip():
                        continue
                    semantic_meta = json.loads(raw_line)
                    if (
                        not isinstance(semantic_meta, dict)
                        or semantic_meta.get("schema") != SEMANTIC_MEMORY_META_SCHEMA
                    ):
                        raise ValueError("invalid_semantic_memory_meta_schema")
                    memory_class = str(
                        semantic_meta.get("memory_class") or "reference"
                    )
                    candidate = _candidate(
                        {
                            "record_id": semantic_meta["record_id"],
                            "retrieval_terms": semantic_meta.get("retrieval_terms") or [],
                            "aliases": [semantic_meta.get("candidate_label") or ""],
                            "summary": semantic_meta.get("summary") or "",
                            "current_status": semantic_meta.get("current_status") or "",
                            "source_tag": semantic_meta.get("source_tag")
                            or "semantic_memory_meta",
                            "belief_status": semantic_meta.get("belief_status")
                            or "navigation_only",
                            "query_types": semantic_meta.get("query_types") or [],
                            "evidence_boundary": semantic_meta.get("evidence_boundary")
                            or "navigation_only_open_selected_record_for_facts",
                        },
                        family=SEMANTIC_MEMORY_FAMILIES.get(memory_class, "V3"),
                        path=semantic_meta_path,
                        line=line_no,
                        fallback_id=f"V3-{line_no}",
                        navigation_only=True,
                    )
                    candidate["semantic_store_root"] = str(root)
                    candidate["semantic_meta"] = semantic_meta
                    candidates.append(candidate)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            return [], {
                "root_path": str(root.resolve()),
                "status": "rejected",
                "reason": f"invalid_semantic_memory_store:{type(exc).__name__}:{exc}",
            }
        source_paths.extend([str(semantic_store_path), str(semantic_meta_path)])

    index_path = root / "index.json"
    if index_path.is_file():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8-sig", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return [], {
                "root_path": str(root.resolve()),
                "status": "rejected",
                "reason": f"invalid_index_json:{type(exc).__name__}",
            }
        if isinstance(index, dict):
            candidates.append(
                _candidate(
                    index,
                    family="META",
                    path=index_path,
                    line=1,
                    fallback_id=f"META-{root.name}",
                    navigation_only=True,
                )
            )
            source_paths.append(str(index_path))
            families = index.get("record_families")
            if isinstance(families, dict):
                for family, relative in families.items():
                    if not isinstance(relative, str) or not relative:
                        continue
                    path = root / relative
                    if not _path_inside(path, root) or not path.is_file() or path.suffix.casefold() != ".jsonl":
                        continue
                    try:
                        with path.open("r", encoding="utf-8", errors="strict") as handle:
                            for line_no, raw_line in enumerate(handle, start=1):
                                if not raw_line.strip():
                                    continue
                                record = json.loads(raw_line)
                                if not isinstance(record, dict):
                                    continue
                                candidates.append(
                                    _candidate(
                                        record,
                                        family=str(family),
                                        path=path,
                                        line=line_no,
                                        fallback_id=f"{str(family).upper()}-{line_no}",
                                    )
                                )
                    except (OSError, UnicodeError, json.JSONDecodeError):
                        continue
                    source_paths.append(str(path))

    if meta.is_file():
        try:
            meta_text = meta.read_text(encoding="utf-8-sig", errors="strict")
        except (OSError, UnicodeError):
            meta_text = ""
        if meta_text:
            headings = re.findall(r"(?m)^#{1,4}\s+(.+?)\s*$", meta_text)
            literals = re.findall(r"`([^`]+)`", meta_text)
            candidates.append(
                _candidate(
                    {
                        "record_id": f"META-{root.name}",
                        "title": headings,
                        "retrieval_terms": literals,
                        "summary": "Memory meta index; open a linked record for fact evidence.",
                        "source_tag": "memory_meta_index",
                        "belief_status": "navigation_only",
                    },
                    family="META",
                    path=meta,
                    line=1,
                    fallback_id=f"META-{root.name}",
                    navigation_only=True,
                )
            )
            source_paths.append(str(meta))

    if not source_paths:
        return [], {
            "root_path": str(root.resolve()),
            "status": "rejected",
            "reason": "no_meta_or_indexed_family",
        }
    return candidates, {
        "lane": str(hint.get("lane") or "unknown"),
        "root_path": str(root.resolve()),
        "status": "accepted",
        "isolation": str(hint.get("isolation") or "route_declared"),
        "source_paths": _unique(source_paths),
    }


def _read_navigation_document(
    path: Path,
    *,
    root: Path,
    kind: str,
    query_terms: list[str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not _path_inside(path, root):
        return None, {"kind": kind, "path": str(path), "reason": "path_outside_declared_root"}
    if not path.is_file():
        return None, {"kind": kind, "path": str(path), "reason": "file_not_found"}
    try:
        text = path.read_text(encoding="utf-8-sig", errors="strict")
    except (OSError, UnicodeError):
        return None, {"kind": kind, "path": str(path), "reason": "utf8_read_failed"}
    if "\ufffd" in text:
        return None, {"kind": kind, "path": str(path), "reason": "replacement_character_present"}
    lines = text.splitlines()
    if len(text) <= 5000:
        excerpt = text
        excerpt_mode = "full"
    else:
        selected_indexes = set(range(min(28, len(lines))))
        normalized_terms = [term.casefold() for term in query_terms if len(term.strip()) >= 2]
        for index, line in enumerate(lines):
            normalized_line = line.casefold()
            if any(term in normalized_line for term in normalized_terms):
                selected_indexes.update(range(max(0, index - 1), min(len(lines), index + 2)))
        excerpt_lines: list[str] = []
        excerpt_chars = 0
        for index in sorted(selected_indexes):
            line = lines[index]
            if excerpt_lines and excerpt_chars + len(line) + 1 > 4000:
                break
            excerpt_lines.append(line)
            excerpt_chars += len(line) + 1
        excerpt = "\n".join(excerpt_lines)
        excerpt_mode = "identity_plus_query_matches"
    return (
        {
            "kind": kind,
            "path": str(path.resolve()),
            "sha256": _sha256(path),
            "excerpt": excerpt,
            "excerpt_mode": excerpt_mode,
            "source_char_count": len(text),
            "excerpt_char_count": len(excerpt),
            "omitted_char_count": max(0, len(text) - len(excerpt)),
            "full_source_available_at_path": True,
            "source_tag": "conversation_navigation",
            "belief_status": "navigation_only",
        },
        None,
    )


def _ledger_snapshot_status(ledger_root: Path) -> dict[str, Any]:
    sessions_path = ledger_root / "sessions.jsonl"
    if not sessions_path.is_file():
        return {"status": "unknown", "reason": "sessions_index_missing"}
    try:
        records = [
            json.loads(line)
            for line in sessions_path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "unknown", "reason": "sessions_index_unreadable"}
    if not records:
        return {"status": "unknown", "reason": "sessions_index_empty"}
    record = records[-1]
    raw_path = Path(str(record.get("raw_session_path") or ""))
    recorded_size = record.get("raw_size_bytes")
    if not raw_path.is_file() or not isinstance(recorded_size, int):
        return {
            "status": "unknown",
            "reason": "raw_session_or_recorded_stat_missing",
            "raw_session_path": str(raw_path),
        }
    current_size = raw_path.stat().st_size
    return {
        "status": "current_snapshot" if current_size == recorded_size else "stale_readonly",
        "raw_session_path": str(raw_path.resolve()),
        "recorded_size_bytes": recorded_size,
        "current_size_bytes": current_size,
        "rule": "Stale ledgers remain read-only navigation; this consumer never refreshes or writes them.",
    }


def _conversation_navigation_bundle(route: dict[str, Any], prompt: str) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    prompt_terms = [
        token
        for token in re.split(r"[^\w\u4e00-\u9fff]+", prompt)
        if len(token) >= 3
    ]
    for hint in _route_object_list(route, "memory_source_hints"):
        if str(hint.get("navigation_profile") or "") != "meta_state_links_ledger_one_hop":
            continue
        root = Path(str(hint.get("root_path") or ""))
        if not root.is_dir():
            rejected.append({"root_path": str(root), "reason": "root_not_found"})
            continue
        try:
            index = json.loads(
                (root / "index.json").read_text(encoding="utf-8-sig", errors="strict")
            )
        except (OSError, UnicodeError, json.JSONDecodeError):
            rejected.append({"root_path": str(root), "reason": "lane_index_unreadable"})
            continue
        memory_id = str(hint.get("memory_id") or index.get("memory_id") or index.get("lane") or "")
        documents: list[dict[str, Any]] = []
        document_errors: list[dict[str, Any]] = []
        current_paths = [
            (Path(str(hint.get("meta_path") or root / "_META_INDEX.md")), "lane_meta", root),
            (root / "conversation_state.md", "conversation_state", root),
            (root / "memory_links.jsonl", "memory_links", root),
        ]
        for path, kind, declared_root in current_paths:
            document, error = _read_navigation_document(
                path,
                root=declared_root,
                kind=kind,
                query_terms=prompt_terms,
            )
            if document is not None:
                documents.append(document)
            elif error is not None:
                document_errors.append(error)

        ledger_root_text = str(hint.get("ledger_root_path") or "")
        if not ledger_root_text:
            ledger_info = index.get("conversation_ledger")
            if isinstance(ledger_info, dict):
                ledger_root_text = str(ledger_info.get("path") or "")
        ledger_root: Path | None = None
        ledger_index: Path | None = None
        ledger_snapshot: dict[str, Any] = {"status": "unknown", "reason": "ledger_root_missing"}
        if ledger_root_text:
            ledger_root = Path(ledger_root_text)
            ledger_index = Path(
                str(hint.get("ledger_index_path") or ledger_root / "_LEDGER_INDEX.md")
            )
            ledger_document, ledger_error = _read_navigation_document(
                ledger_index,
                root=ledger_root,
                kind="ledger_index",
                query_terms=prompt_terms,
            )
            if ledger_document is not None:
                documents.append(ledger_document)
            elif ledger_error is not None:
                document_errors.append(ledger_error)
            ledger_snapshot = _ledger_snapshot_status(ledger_root)
        else:
            document_errors.append(
                {"kind": "ledger_index", "path": "", "reason": "ledger_root_missing"}
            )

        selected_links: list[dict[str, Any]] = []
        links_path = root / "memory_links.jsonl"
        if links_path.is_file():
            try:
                links = [
                    json.loads(line)
                    for line in links_path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
                    if line.strip()
                ]
            except (OSError, UnicodeError, json.JSONDecodeError):
                links = []
                document_errors.append(
                    {"kind": "memory_links", "path": str(links_path), "reason": "link_parse_failed"}
                )
            candidates: list[tuple[int, dict[str, Any], str, str]] = []
            for link in links:
                if str(link.get("status") or "ACTIVE").upper() != "ACTIVE":
                    continue
                if str(link.get("link_type") or "") not in {"continuation", "reference"}:
                    continue
                if memory_id and str(link.get("to_memory_id") or "") == memory_id:
                    candidates.append(
                        (0, link, str(link.get("from_path") or ""), str(link.get("from_ledger_path") or ""))
                    )
                elif memory_id and str(link.get("from_memory_id") or "") == memory_id:
                    candidates.append(
                        (1, link, str(link.get("to_path") or ""), str(link.get("to_ledger_path") or ""))
                    )
            if candidates:
                _, link, linked_root_text, linked_ledger_root_text = sorted(candidates, key=lambda item: item[0])[0]
                selected_links.append(
                    {
                        "link_id": str(link.get("link_id") or ""),
                        "link_type": str(link.get("link_type") or ""),
                        "from_memory_id": str(link.get("from_memory_id") or ""),
                        "to_memory_id": str(link.get("to_memory_id") or ""),
                        "write_policy": str(link.get("write_policy") or ""),
                        "evidence_boundary": str(link.get("evidence_boundary") or ""),
                    }
                )
                linked_root = Path(linked_root_text)
                if linked_root_text and linked_root.is_dir():
                    document, error = _read_navigation_document(
                        linked_root / "_META_INDEX.md",
                        root=linked_root,
                        kind="linked_lane_meta",
                        query_terms=prompt_terms,
                    )
                    if document is not None:
                        documents.append(document)
                    elif error is not None:
                        document_errors.append(error)
                linked_ledger_root = Path(linked_ledger_root_text)
                if linked_ledger_root_text and linked_ledger_root.is_dir():
                    document, error = _read_navigation_document(
                        linked_ledger_root / "_LEDGER_INDEX.md",
                        root=linked_ledger_root,
                        kind="linked_ledger_index",
                        query_terms=prompt_terms,
                    )
                    if document is not None:
                        documents.append(document)
                    elif error is not None:
                        document_errors.append(error)

        accepted.append(
            {
                "memory_id": memory_id,
                "root_path": str(root.resolve()),
                "registry_path": str(hint.get("registry_path") or ""),
                "isolation": str(hint.get("isolation") or "route_declared"),
                "documents": documents,
                "document_errors": document_errors,
                "selected_links": selected_links,
                "ledger": {
                    "root_path": (
                        str(ledger_root.resolve())
                        if ledger_root is not None and ledger_root.is_dir()
                        else str(ledger_root or "")
                    ),
                    "index_path": str(ledger_index or ""),
                    "snapshot": ledger_snapshot,
                },
                "write_performed": False,
                "raw_payload_opened": False,
            }
        )
    if accepted:
        status = "resolved" if not rejected and all(not item["document_errors"] for item in accepted) else "partial"
    else:
        status = "not_requested" if not rejected else "unresolved"
    return {
        "status": status,
        "bundles": accepted,
        "rejected": rejected,
        "write_performed": False,
        "raw_payload_opened": False,
        "rule": "Read-only meta/state/link/ledger navigation; one explicit continuation hop maximum.",
    }


def _score(candidate: dict[str, Any], prompt: str, tool_text: str) -> tuple[int, str, list[str]]:
    query = _normalize(f"{prompt}\n{tool_text}")
    query_terms = _terms(query)
    score = -20 if candidate["navigation_only"] else 0
    reasons: list[str] = []
    confidence = "weak"
    record_id = _normalize(str(candidate["record_id"]))
    if record_id and record_id in query:
        score += 1000
        confidence = "exact_record_id"
        reasons.append("exact_record_id")

    direct_terms: set[str] = set()
    exact_direct = False
    for value in candidate["direct_values"]:
        normalized = _normalize(value)
        if not normalized:
            continue
        direct_terms.update(_terms(normalized))
        is_cjk_phrase = bool(re.fullmatch(r"[\u4e00-\u9fff]+", normalized))
        minimum_exact_length = 6 if is_cjk_phrase else 5
        if normalized not in GENERIC_TERMS and len(normalized) >= minimum_exact_length and normalized in query:
            score += 220 + min(len(normalized), 80)
            exact_direct = True
            reasons.append(f"exact_index_term:{value}")

    direct_overlap = sorted(query_terms.intersection(direct_terms))
    if direct_overlap:
        score += min(180, len(direct_overlap) * 18)
        reasons.append("index_overlap:" + ",".join(direct_overlap[:8]))

    content_terms = _terms("\n".join(candidate["all_values"]))
    content_overlap = sorted(query_terms.intersection(content_terms) - set(direct_overlap))
    if content_overlap:
        score += min(60, len(content_overlap) * 4)
        reasons.append("content_overlap:" + ",".join(content_overlap[:8]))

    if confidence != "exact_record_id" and exact_direct:
        confidence = "exact_index_term"
    elif confidence == "weak" and score >= DIRECT_SCORE and len(direct_overlap) >= 2:
        confidence = "strong_index_overlap"
    return score, confidence, reasons


def _display_text(record: dict[str, Any]) -> str:
    raw = record["raw"]
    for field in DISPLAY_FIELDS:
        values = _flatten_strings(raw.get(field))
        if values:
            return " ".join(values)
    return " ".join(record["direct_values"][1:])


def _materialize(candidate: dict[str, Any], score: int, confidence: str, reasons: list[str]) -> dict[str, Any]:
    semantic_meta = candidate.get("semantic_meta")
    semantic_store_root = candidate.get("semantic_store_root")
    if (
        confidence != "weak"
        and isinstance(semantic_meta, dict)
        and isinstance(semantic_store_root, str)
        and semantic_store_root
    ):
        record = materialize_memory_record(Path(semantic_store_root), semantic_meta)
        content = record.get("content") if isinstance(record.get("content"), dict) else {}
        meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
        status = record.get("status") if isinstance(record.get("status"), dict) else {}
        provenance = (
            record.get("provenance")
            if isinstance(record.get("provenance"), dict)
            else {}
        )
        payload = semantic_meta.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        selected_text = str(
            content.get("prevention_rule")
            or content.get("future_reuse_rule")
            or content.get("consumption_hint")
            or meta.get("summary")
            or content.get("event_summary")
            or content.get("details")
            or ""
        )
        return {
            "record_id": record["record_id"],
            "family": candidate["family"],
            "path": str(Path(semantic_store_root) / "records.jsonl"),
            "line": int(payload.get("line") or 0),
            "sha256": record["record_sha256"],
            "status": str(status.get("current_status") or status.get("state") or "unknown"),
            "source_tag": provenance.get("source_tag") or "local_memory_write",
            "belief_status": provenance.get("belief_status") or "recorded_observation",
            "confidence": record.get("confidence")
            or {"level": "bounded", "basis": confidence},
            "derived_from": record.get("evidence_refs"),
            "score": score,
            "score_method": "field_weighted_exact_and_lexical_v1",
            "match_confidence": confidence,
            "selection_reasons": reasons,
            "selected_text": selected_text,
            "navigation_only": False,
            "evidence_boundary": content.get("evidence_boundary"),
        }
    raw = candidate["raw"]
    status = str(raw.get("current_status") or raw.get("status") or raw.get("lifecycle") or "unknown")
    return {
        "record_id": candidate["record_id"],
        "family": candidate["family"],
        "path": candidate["path"],
        "line": candidate["line"],
        "sha256": _sha256(Path(candidate["path"])),
        "status": status,
        "source_tag": raw.get("source_tag") or ("memory_meta_index" if candidate["navigation_only"] else "lane_memory_record"),
        "belief_status": raw.get("belief_status") or "unverified_record",
        "confidence": raw.get("confidence") or {"level": "bounded", "basis": confidence},
        "derived_from": raw.get("derived_from") or raw.get("evidence_refs"),
        "score": score,
        "score_method": "field_weighted_exact_and_lexical_v1",
        "match_confidence": confidence,
        "selection_reasons": reasons,
        "selected_text": _display_text(candidate),
        "navigation_only": candidate["navigation_only"],
    }


def select_memory_context(
    route: dict[str, Any],
    *,
    prompt: str,
    tool_input_text: str = "",
    soft_target_records: int = SOFT_TARGET_RECORDS,
    query_type: str = "history_reason",
) -> dict[str, Any]:
    if query_type not in MEMORY_QUERY_TYPES:
        raise ValueError("unsupported_memory_query_type")
    hints = _route_field(route, "memory_source_hints", [])
    hints = hints if isinstance(hints, list) else []
    candidates: list[dict[str, Any]] = []
    source_receipts: list[dict[str, Any]] = []
    for hint in hints:
        if not isinstance(hint, dict):
            continue
        loaded, receipt = _load_source_hint(hint)
        candidates.extend(loaded)
        source_receipts.append(receipt)

    ranked: list[tuple[int, str, list[str], dict[str, Any]]] = []
    seen: set[tuple[str, str, int]] = set()
    for candidate in candidates:
        declared_query_types = candidate["raw"].get("query_types")
        if (
            isinstance(declared_query_types, list)
            and declared_query_types
            and query_type not in declared_query_types
        ):
            continue
        key = (str(candidate["record_id"]), str(candidate["path"]), int(candidate["line"]))
        if key in seen:
            continue
        seen.add(key)
        score, confidence, reasons = _score(candidate, prompt, tool_input_text)
        if score > 0:
            ranked.append((score, confidence, reasons, candidate))
    ranked.sort(key=lambda item: (item[0], not item[3]["navigation_only"]), reverse=True)

    exact = [item for item in ranked if item[1] in {"exact_record_id", "exact_index_term"}]
    direct = [item for item in ranked if item[1] != "weak"]
    preferred = exact or direct
    if preferred:
        chosen = preferred[:MAX_DIRECT_RECORDS]
        coverage_status = "selected_context_ready" if len(preferred) <= MAX_DIRECT_RECORDS else "semantic_review_required"
    else:
        chosen = ranked[: max(1, int(soft_target_records))]
        coverage_status = "semantic_review_required" if chosen else "no_match"

    selected = [_materialize(candidate, score, confidence, reasons) for score, confidence, reasons, candidate in chosen]
    semantic_review_candidates = [
        _materialize(candidate, score, confidence, reasons)
        for score, confidence, reasons, candidate in ranked
        if (score, confidence, reasons, candidate) not in chosen
    ][:MAX_DIRECT_RECORDS]
    return {
        "selected_records": selected,
        "semantic_review_candidates": semantic_review_candidates,
        "coverage_status": coverage_status,
        "direct_candidate_count": len(direct),
        "weak_candidate_count": len(ranked) - len(direct),
        "review_candidate_ids": [item[3]["record_id"] for item in ranked if item not in chosen][:8],
        "source_receipts": source_receipts,
        "soft_target_records": max(1, int(soft_target_records)),
        "expanded_for_direct_coverage": len(chosen) > max(1, int(soft_target_records)),
        "query_type": query_type,
    }


def _additional_context(
    records: list[dict[str, Any]],
    semantic_review_candidates: list[dict[str, Any]],
) -> tuple[str, bool, list[str]]:
    parts = [
        "CBH selected indexed memory for the model agent. Treat it as bounded context, preserve provenance, and open raw evidence before strong factual claims."
    ]
    omitted: list[str] = []
    for record in records:
        text = re.sub(r"\s+", " ", str(record.get("selected_text") or "")).strip()
        part = (
            f"[{record['record_id']}] status={record['status']} source_tag={record['source_tag']} "
            f"belief_status={record['belief_status']} source={record['path']}:{record['line']} text={text}"
        )
        prospective = "\n".join([*parts, part])
        if len(prospective) > CONTEXT_SOFT_TARGET_CHARS:
            omitted.append(str(record["record_id"]))
            continue
        parts.append(part)
    for record in semantic_review_candidates:
        text = re.sub(r"\s+", " ", str(record.get("selected_text") or "")).strip()
        part = (
            "Model semantic-review candidate (not preselected): "
            f"[{record['record_id']}] score={record['score']} source={record['path']}:{record['line']} text={text}"
        )
        prospective = "\n".join([*parts, part])
        if len(prospective) > CONTEXT_SOFT_TARGET_CHARS:
            omitted.append(str(record["record_id"]))
            continue
        parts.append(part)
    if omitted:
        parts.append("Context soft target reached; selected metadata remains available for: " + ", ".join(omitted))
    return "\n".join(parts), bool(omitted), omitted


def _task_local_correction_bundle(
    route: dict[str, Any],
    *,
    tool_input_text: str,
    selected_records: list[dict[str, Any]],
) -> dict[str, Any]:
    environment = str(_route_field(route, "execution_environment", "") or "")
    if not environment:
        environment = "powershell" if re.search(r"(?i)\bforeach\s*\(|\$[A-Za-z_]", tool_input_text) else "any"
    tool_surface = str(_route_field(route, "candidate_tool_surface", "") or "")
    if not tool_surface and tool_input_text:
        tool_surface = "shell_command"
    try:
        receipt = build_behavior_correction_receipt(
            stage="pretool",
            environment=environment,
            tool_role=str(_route_field(route, "tool_role", "unknown") or "unknown"),
            tool_surface=tool_surface,
            text=tool_input_text,
            execution_cwd=str(_route_field(route, "execution_cwd", "") or ""),
            target_binding_sha256=str(_route_field(route, "target_binding_sha256", "") or ""),
        )
    except CorrectionProfileRegistryError as exc:
        receipt = {
            "schema": "cbh.behavior_correction_gate_receipt.v1",
            "status": "unavailable",
            "decision": "no_match",
            "issues": [str(exc)],
            "scope": "current_event_only",
            "host_blocking": False,
        }
    receipt["selected_memory_record_ids"] = [
        str(record["record_id"])
        for record in selected_records
        if str(record.get("record_id") or "")
    ]
    receipt["automatic_long_term_memory_write"] = False
    receipt["automatic_policy_mutation"] = False
    receipt["host_blocking"] = False
    return receipt


def build_action_consumption(
    route: dict[str, Any],
    *,
    prompt: str,
    tool_input_text: str = "",
    query_type: str = "history_reason",
    soft_target_records: int = SOFT_TARGET_RECORDS,
    task_event: Mapping[str, Any] | None = None,
    task_capsule: Mapping[str, Any] | None = None,
    host_limits: Mapping[str, Any] | None = None,
    transport_cursor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    memory_need = str(_route_field(route, "memory_need", "none"))
    bindings = _route_field(route, "action_bindings", [])
    bindings = bindings if isinstance(bindings, list) else []
    binding_ids = {
        str(item.get("action"))
        for item in bindings
        if isinstance(item, dict) and item.get("action")
    }
    engineering_profiles_value = _route_field(route, "engineering_execution_profiles", [])
    engineering_profiles = (
        [str(value) for value in engineering_profiles_value if str(value)]
        if isinstance(engineering_profiles_value, list)
        else []
    )
    wants_engineering_execution = (
        "apply_engineering_execution_profile" in binding_ids and bool(engineering_profiles)
    )
    engineering_execution_receipt = (
        build_engineering_execution_receipt(engineering_profiles, task_event)
        if wants_engineering_execution
        else None
    )
    wants_external_retrieval = "perform_external_research_route" in binding_ids
    external_modes_value = _route_field(route, "external_need", [])
    external_modes = [
        str(mode)
        for mode in (external_modes_value if isinstance(external_modes_value, list) else [])
        if str(mode) and str(mode) != "none"
    ]
    if wants_external_retrieval and not external_modes:
        external_modes = ["general_web_cross_check"]
    external_retrieval_receipt = (
        build_external_retrieval_receipt(prompt, recommended_modes=external_modes)
        if wants_external_retrieval
        else None
    )
    wants_retrieval = memory_need != "none" or "retrieve_matching_memory" in binding_ids
    retrieval = (
        select_memory_context(
            route,
            prompt=prompt,
            tool_input_text=tool_input_text,
            soft_target_records=soft_target_records,
            query_type=query_type,
        )
        if wants_retrieval
        else {
            "selected_records": [],
            "semantic_review_candidates": [],
            "coverage_status": "not_requested",
            "direct_candidate_count": 0,
            "weak_candidate_count": 0,
            "review_candidate_ids": [],
            "source_receipts": [],
            "soft_target_records": max(1, int(soft_target_records)),
            "expanded_for_direct_coverage": False,
        }
    )
    selected = list(retrieval["selected_records"])
    semantic_review_candidates = list(retrieval["semantic_review_candidates"])
    wants_correction = bool(tool_input_text) or "prepare_task_local_correction_bundle" in binding_ids
    correction_bundle = (
        _task_local_correction_bundle(
            route,
            tool_input_text=tool_input_text,
            selected_records=selected,
        )
        if wants_correction
        else None
    )
    task_continuity_decision: dict[str, Any] | None = None
    task_transition: dict[str, Any] | None = None
    dynamic_reminders: list[dict[str, Any]] = []
    current_task_capsule: dict[str, Any] | None = None
    task_capsule_context = ""
    task_transport_receipt: dict[str, Any] | None = None
    if task_event is not None:
        task_continuity_decision = decide_task_continuity(
            route,
            task_event,
            task_capsule,
        )
        if task_capsule is None:
            if task_continuity_decision["decision"] != "dormant":
                current_task_capsule, task_transition = initialize_task_capsule(
                    route, task_event
                )
        else:
            task_transition = apply_task_event(task_capsule, task_event)
            current_task_capsule = task_transition["capsule"]
            dynamic_reminders = build_dynamic_reminders(
                current_task_capsule,
                task_transition,
            )
            if dynamic_reminders:
                current_task_capsule = dynamic_reminders[-1]["capsule_snapshot"]
                dynamic_reminders = [
                    {
                        key: value
                        for key, value in reminder.items()
                        if key != "capsule_snapshot"
                    }
                    for reminder in dynamic_reminders
                ]
        if current_task_capsule is not None:
            context_receipt = build_task_capsule_context(
                current_task_capsule,
                dynamic_reminders,
                host_limits=host_limits,
            )
            entry = context_receipt.get("entry")
            if isinstance(entry, Mapping):
                task_capsule_context = str(entry.get("value") or "")
            task_transport_receipt = {
                "delivery": context_receipt.get("delivery"),
                "char_count": context_receipt.get("char_count"),
                "cursor": dict(transport_cursor) if isinstance(transport_cursor, Mapping) else None,
            }
    elif isinstance(_route_field(route, "task_continuity_decision"), Mapping):
        task_continuity_decision = dict(_route_field(route, "task_continuity_decision"))
    conversation_navigation = _conversation_navigation_bundle(route, prompt)
    additional_context, context_over_soft_target, omitted = (
        _additional_context(selected, semantic_review_candidates)
        if selected or semantic_review_candidates
        else ("", False, [])
    )
    priority_context_parts: list[str] = []
    if external_retrieval_receipt is not None:
        exact_values = [
            item["raw_text"] for item in external_retrieval_receipt["exact_anchors"]
        ]
        source_routes = [
            item["source_route_id"]
            for item in external_retrieval_receipt["source_capability_candidates"]
        ]
        external_context = (
            "External retrieval near-action: "
            f"profile={external_retrieval_receipt['retrieval_profile']}; "
            f"exact_anchors={json.dumps(exact_values, ensure_ascii=False)}; "
            f"source_routes={json.dumps(source_routes, ensure_ascii=False)}. "
            "Preserve exact anchors, use matching source-native routes, bind evidence to each target, "
            "and do not treat one provider/index miss as verified absence."
        )
        additional_context = "\n".join(part for part in (additional_context, external_context) if part)
        context_over_soft_target = context_over_soft_target or len(additional_context) > CONTEXT_SOFT_TARGET_CHARS

    for bundle in conversation_navigation.get("bundles", []):
        for document in bundle.get("documents", []):
            navigation_context = (
                "Read-only conversation navigation (summary/index locates evidence; raw remains the fact source): "
                f"kind={document['kind']} source={document['path']} sha256={document['sha256']}\n"
                f"excerpt_mode={document['excerpt_mode']} omitted_chars={document['omitted_char_count']}\n"
                f"{document['excerpt']}"
            )
            additional_context = "\n".join(
                part for part in (additional_context, navigation_context) if part
            )
    context_over_soft_target = context_over_soft_target or len(additional_context) > CONTEXT_SOFT_TARGET_CHARS

    actions: list[dict[str, Any]] = []
    pending_user_confirmation: dict[str, Any] | None = None
    for binding in bindings:
        if not isinstance(binding, dict) or not binding.get("action"):
            continue
        action_id = str(binding["action"])
        if action_id == "await_scoped_user_confirmation":
            confirmation_request = _normalized_confirmation_request(
                binding.get("confirmation_request")
            )
            if confirmation_request is None:
                action_status = "deferred_to_model_agent"
                evidence = "semantic_confirmation_binding_required"
            else:
                action_status = "pending_user_confirmation"
                evidence = confirmation_request
                pending_user_confirmation = confirmation_request
        elif action_id == "retrieve_matching_memory":
            if retrieval["coverage_status"] == "selected_context_ready":
                action_status = "completed"
                evidence: Any = [item["record_id"] for item in selected]
            elif selected or semantic_review_candidates:
                action_status = "ready_for_model_semantic_selection"
                evidence = [
                    item["record_id"]
                    for item in [*selected, *semantic_review_candidates]
                ]
            else:
                action_status = retrieval["coverage_status"]
                evidence = []
        elif action_id == "prepare_task_local_correction_bundle":
            if correction_bundle is None or correction_bundle["decision"] == "no_match":
                action_status = "not_applicable_with_reason"
                evidence = "no_current_candidate_match"
            else:
                action_status = "completed"
                evidence = correction_bundle.get("candidate_key")
        elif action_id == "prepare_task_continuity_capsule":
            if current_task_capsule is None:
                action_status = "not_applicable_with_reason"
                evidence = "task_continuity_dormant_or_no_task_event"
            else:
                action_status = "completed"
                evidence = current_task_capsule.get("capsule_id")
        elif action_id == "apply_engineering_execution_profile":
            if engineering_execution_receipt is None:
                action_status = "not_applicable_with_reason"
                evidence = "engineering_execution_profile_not_routed"
            else:
                action_status = "completed"
                evidence = {
                    "schema": engineering_execution_receipt["schema"],
                    "profiles": engineering_execution_receipt["profiles"],
                    "result_schemas": {
                        profile: result.get("schema")
                        for profile, result in engineering_execution_receipt["results"].items()
                    },
                }
        elif action_id == "perform_external_research_route":
            action_status = "deferred_to_model_agent"
            evidence = {
                "receipt_schema": external_retrieval_receipt["schema"],
                "retrieval_profile": external_retrieval_receipt["retrieval_profile"],
                "coverage_status": external_retrieval_receipt["coverage_status"],
                "query_ids": [
                    item["query_id"] for item in external_retrieval_receipt["query_plan"]
                ],
                "pending_source_routes": [
                    {
                        "target_id": item["target_id"],
                        "source_route_id": item["source_route_id"],
                        "mode": item["mode"],
                        "activation_condition": item["activation_condition"],
                    }
                    for item in external_retrieval_receipt["source_capability_candidates"]
                ],
                "negative_evidence_boundary": external_retrieval_receipt["negative_evidence_boundary"],
            }
        elif action_id == "resolve_conversation_link":
            bundles = list(conversation_navigation.get("bundles") or [])
            resolved_links = [link for bundle in bundles for link in bundle.get("selected_links", [])]
            if conversation_navigation.get("status") in {"resolved", "partial"} and bundles:
                action_status = "completed" if resolved_links else "ready_for_model_semantic_selection"
                evidence = {
                    "memory_ids": [bundle.get("memory_id") for bundle in bundles],
                    "selected_link_ids": [link.get("link_id") for link in resolved_links],
                    "ledger_indexes": [bundle.get("ledger", {}).get("index_path") for bundle in bundles],
                }
            else:
                action_status = "deferred_to_model_agent"
                evidence = conversation_navigation.get("status")
        else:
            action_status = "deferred_to_model_agent"
            evidence = binding.get("completion_evidence")
        actions.append(
            {
                "action_id": action_id,
                "status": action_status,
                "completion_evidence": evidence,
            }
        )

    if pending_user_confirmation is not None:
        confirmation_context = (
            "高风险近动作边界：等待当前事件的一次性明确确认。"
            f"confirmation_request={json.dumps(pending_user_confirmation, ensure_ascii=False)}。"
            "先说明动作、精确目标、范围、影响、恢复方式和明确非目标；"
            "本 receipt 不授予权限、不保存许可，也不得自行把确认标记为已消费。"
        )
        priority_context_parts.append(confirmation_context)

    if task_capsule_context:
        priority_context_parts.append(task_capsule_context)

    if engineering_execution_receipt is not None:
        engineering_summary = {
            "profiles": engineering_execution_receipt["profiles"],
            "results": {
                profile: {
                    key: result.get(key)
                    for key in (
                        "status",
                        "migration_phase",
                        "frontier_step_ids",
                        "graph_issues",
                        "verdict",
                        "missing_evidence",
                        "runtime_invoker",
                        "issues",
                        "seam_status",
                    )
                    if result.get(key) not in (None, [], {})
                }
                for profile, result in engineering_execution_receipt["results"].items()
            },
            "authority_granted": False,
        }
        engineering_context = (
            "CBH engineering execution receipt (advisory, task-local): "
            + json.dumps(engineering_summary, ensure_ascii=False, separators=(",", ":"))
        )
        priority_context_parts.append(engineering_context)

    if priority_context_parts:
        additional_context = "\n".join(
            part for part in (*priority_context_parts, additional_context) if part
        )
        context_over_soft_target = (
            context_over_soft_target
            or len(additional_context) > CONTEXT_SOFT_TARGET_CHARS
        )

    effective_host_limits = (
        dict(host_limits)
        if isinstance(host_limits, Mapping)
        else {
            "max_chars": CONTEXT_SOFT_TARGET_CHARS,
            "max_tokens": 900,
            "max_items": 100,
        }
    )
    if additional_context:
        transport_plan = plan_transport(
            current_task_capsule,
            {
                "kind": "text",
                "original_chars": len(additional_context),
                "original_items": 1,
            },
            effective_host_limits,
        )
        context_page = page_result(additional_context, transport_plan, transport_cursor)
        additional_context = context_page["content"]
        task_transport_receipt = {
            "schema": context_page["schema"],
            "delivery": "complete" if context_page["complete"] else "continuation_required",
            "page_sha256": context_page["page_sha256"],
            "full_result_sha256": context_page["full_result_sha256"],
            "original_chars": context_page["original_chars"],
            "forwarded_chars": context_page["forwarded_chars"],
            "uncovered_chars": context_page["uncovered_chars"],
            "next_cursor": context_page["next_cursor"],
        }
        context_over_soft_target = context_over_soft_target or not context_page["complete"]

    continuity_control_in_first_page = (
        not task_capsule_context or task_capsule_context in additional_context
    )

    complete_statuses = {
        "completed",
        "not_applicable_with_reason",
        "ready_for_model_semantic_selection",
    }
    unconsumed_action_ids = [
        item["action_id"]
        for item in actions
        if item["status"] not in complete_statuses
    ]
    routing_status = str(_route_field(route, "routing_status", "classified"))
    execution_disposition = (
        "pending_user_confirmation"
        if pending_user_confirmation is not None
        else str(_route_field(route, "execution_disposition", "advisory_route_ready"))
    )

    return {
        "schema": SCHEMA,
        "status": retrieval["coverage_status"],
        "routing_status": routing_status,
        "execution_disposition": execution_disposition,
        "pending_user_confirmation": pending_user_confirmation,
        "execution_owner": "host_model_agent",
        "consumer_role": "bounded_context_selection_only",
        "selected_records": selected,
        "semantic_review_candidates": semantic_review_candidates,
        "semantic_review_owner": "host_model_agent",
        "task_local_correction_bundle": correction_bundle,
        "task_continuity_decision": task_continuity_decision,
        "engineering_execution_receipt": engineering_execution_receipt,
        "task_capsule": current_task_capsule,
        "task_transition": task_transition,
        "dynamic_reminders": dynamic_reminders,
        "task_capsule_context": task_capsule_context,
        "transport_receipt": task_transport_receipt,
        "external_retrieval_receipt": external_retrieval_receipt,
        "retrieval": {
            key: value
            for key, value in retrieval.items()
            if key not in {"selected_records", "semantic_review_candidates"}
        },
        "actions": actions,
        "unconsumed_action_ids": unconsumed_action_ids,
        "additional_context": additional_context,
        "context_char_count": len(additional_context),
        "context_soft_target_chars": CONTEXT_SOFT_TARGET_CHARS,
        "context_over_soft_target": context_over_soft_target,
        "continuity_control_in_first_page": continuity_control_in_first_page,
        "omitted_context_record_ids": omitted,
        "conversation_navigation": conversation_navigation,
        "boundary": "CBH selects compact indexed context; the model agent still interprets evidence, chooses tools, executes the task, and owns the final answer.",
    }


def _compact_record_metadata(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    return {
        key: record[key]
        for key in (
            "record_id",
            "family",
            "class",
            "status",
            "record_status",
            "path",
            "index_path",
            "sha256",
            "source_tag",
            "belief_status",
            "confidence",
            "score",
            "score_method",
            "match_confidence",
            "selection_reasons",
            "eligible_for_current_reuse",
            "linked_record_ids",
        )
        if key in record
    }


def _compact_runtime_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    external = receipt.get("external_retrieval_receipt")
    if isinstance(external, dict):
        external = {
            key: external[key]
            for key in (
                "schema",
                "retrieval_profile",
                "recommended_modes",
                "original_query",
                "original_query_preserved",
                "exact_anchors",
                "semantic_facets",
                "currentness_or_revision_required",
                "anchor_preservation_status",
                "query_plan",
                "source_capability_candidates",
                "target_coverage",
                "facet_coverage",
                "coverage_status",
                "fallback_state",
                "negative_evidence_boundary",
                "unresolved_facets",
            )
            if key in external
        }
    capsule = receipt.get("task_capsule")
    if isinstance(capsule, dict):
        capsule = {
            key: capsule.get(key)
            for key in (
                "schema",
                "capsule_id",
                "task_key_sha256",
                "lifecycle",
                "progress_revision",
                "objective",
                "current_stage",
                "remaining_work",
                "next_action",
                "next_action_reason",
                "blocking_condition",
                "unresolved_failures",
                "persistence",
            )
        }
    transition = receipt.get("task_transition")
    if isinstance(transition, dict):
        transition = {
            key: transition.get(key)
            for key in (
                "schema",
                "changed",
                "previous_lifecycle",
                "lifecycle",
                "progress_delta",
                "event_outcome",
                "transition_reasons",
                "event_type",
            )
        }
    return {
        "schema": "cbh.action_consumption_receipt.compact.v1",
        "output_profile": "compact_runtime",
        "status": receipt.get("status"),
        "routing_status": receipt.get("routing_status"),
        "execution_disposition": receipt.get("execution_disposition"),
        "pending_user_confirmation": receipt.get("pending_user_confirmation"),
        "execution_owner": receipt.get("execution_owner"),
        "consumer_role": receipt.get("consumer_role"),
        "selected_records": [
            _compact_record_metadata(record) for record in receipt.get("selected_records", [])
        ],
        "semantic_review_candidates": [
            _compact_record_metadata(record)
            for record in receipt.get("semantic_review_candidates", [])
        ],
        "semantic_review_owner": receipt.get("semantic_review_owner"),
        "task_local_correction_bundle": receipt.get("task_local_correction_bundle"),
        "task_continuity_decision": receipt.get("task_continuity_decision"),
        "engineering_execution_receipt": receipt.get("engineering_execution_receipt"),
        "task_capsule": capsule,
        "task_transition": transition,
        "dynamic_reminders": receipt.get("dynamic_reminders", []),
        "transport_receipt": receipt.get("transport_receipt"),
        "external_retrieval_receipt": external,
        "retrieval": receipt.get("retrieval", {}),
        "actions": receipt.get("actions", []),
        "unconsumed_action_ids": receipt.get("unconsumed_action_ids", []),
        "additional_context": receipt.get("additional_context", ""),
        "context_char_count": receipt.get("context_char_count", 0),
        "context_soft_target_chars": receipt.get("context_soft_target_chars"),
        "context_over_soft_target": receipt.get("context_over_soft_target", False),
        "continuity_control_in_first_page": receipt.get(
            "continuity_control_in_first_page", True
        ),
        "omitted_context_record_ids": receipt.get("omitted_context_record_ids", []),
        "conversation_navigation": receipt.get("conversation_navigation"),
        "boundary": receipt.get("boundary"),
    }


def _load_route(args: argparse.Namespace) -> dict[str, Any]:
    if args.route_json is not None:
        source = args.route_json
    elif args.route_file is not None:
        source = Path(args.route_file).read_text(encoding="utf-8-sig")
    else:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="strict")
        source = sys.stdin.read()
    route = json.loads(source)
    if not isinstance(route, dict):
        raise ValueError("route input must be a JSON object")
    return route


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    parser = argparse.ArgumentParser(description="Select bounded CBH memory context for a model agent.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--route-json")
    source.add_argument("--route-file")
    source.add_argument("--route-stdin", action="store_true")
    parser.add_argument("--receipt-mode", choices=("compact", "diagnostic"), default="compact")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--tool-input-text", default="")
    parser.add_argument(
        "--query-type",
        choices=sorted(MEMORY_QUERY_TYPES),
        default="history_reason",
    )
    args = parser.parse_args()
    route = _load_route(args)
    result = build_action_consumption(
        route,
        prompt=args.prompt,
        tool_input_text=args.tool_input_text,
        query_type=args.query_type,
    )
    if args.receipt_mode == "compact":
        result = _compact_runtime_receipt(result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
