"""Bounded raw-log helpers for truthful root/child failure summaries."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from nested_tool_preflight import summarize_nested_tool_failure


def read_jsonl_window(
    path: str | Path,
    line_numbers: set[int],
    *,
    max_line_chars: int = 1_000_000,
    include_payload: bool = False,
) -> list[dict[str, Any]]:
    """Read only selected 1-based JSONL lines and stop after the last target."""

    if not isinstance(include_payload, bool):
        raise ValueError("include_payload must be a boolean")
    wanted = {int(line) for line in line_numbers if int(line) > 0}
    if not wanted:
        return []
    highest = max(wanted)
    found: list[dict[str, Any]] = []
    source = Path(path)
    with source.open("r", encoding="utf-8", errors="strict") as handle:
        for number, raw in enumerate(handle, start=1):
            if number > highest:
                break
            if number not in wanted:
                continue
            text = raw.rstrip("\r\n")
            if len(text) > max_line_chars:
                raise ValueError(f"selected JSONL line {number} exceeds max_line_chars")
            parsed = json.loads(text)
            row: dict[str, Any] = {
                "path": str(source),
                "line": number,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
            if include_payload:
                row["raw"] = text
                row["parsed"] = parsed
            found.append(row)
    missing = sorted(wanted - {row["line"] for row in found})
    if missing:
        raise ValueError(f"selected JSONL lines not found: {missing}")
    return found


def compact_failure_rows(
    events: Iterable[Mapping[str, Any]],
    *,
    max_rows: int = 100,
) -> list[dict[str, Any]]:
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows <= 0:
        raise ValueError("max_rows must be a positive integer")
    rows: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if index >= max_rows:
            raise ValueError("events exceed max_rows; increase the explicit budget")
        if not isinstance(event, Mapping):
            raise ValueError("each event must be an object")
        recovered = event.get("recovered")
        if not isinstance(recovered, bool):
            raise ValueError("recovered must be a boolean")
        raw_ref_value = event.get("raw_ref")
        if raw_ref_value is not None and not isinstance(raw_ref_value, str):
            raise ValueError("raw_ref must be a string or null")
        signature = event.get("signature")
        if not isinstance(signature, str):
            raise ValueError("signature must be a canonical lowercase SHA-256 hex digest")
        rows.append(
            summarize_nested_tool_failure(
                agent_path=str(event.get("agent_path") or "unknown"),
                tool_name=str(event.get("tool") or event.get("tool_name") or "unknown"),
                signature=signature,
                error_class=str(event.get("error_class") or "unknown"),
                raw_ref=raw_ref_value,
                side_effects=str(event.get("side_effects") or "unknown"),
                recovered=recovered,
            )
        )
    return rows
