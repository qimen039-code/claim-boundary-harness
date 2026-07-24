from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


HARNESS_ROOT = Path(__file__).resolve().parent
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))

from behavior_correction_gate import build_behavior_correction_receipt  # noqa: E402
from execution_feedback import CorrectionProfileRegistryError  # noqa: E402


SCHEMA = "cbh.model_context_consumption.v1"
SOFT_TARGET_RECORDS = 3
MAX_DIRECT_RECORDS = 8
CONTEXT_SOFT_TARGET_CHARS = 3200
DIRECT_SCORE = 60

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
    return route.get(name, default)


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
) -> dict[str, Any]:
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
    soft_target_records: int = SOFT_TARGET_RECORDS,
) -> dict[str, Any]:
    memory_need = str(_route_field(route, "memory_need", "none"))
    bindings = _route_field(route, "action_bindings", [])
    bindings = bindings if isinstance(bindings, list) else []
    binding_ids = {
        str(item.get("action"))
        for item in bindings
        if isinstance(item, dict) and item.get("action")
    }
    wants_retrieval = memory_need != "none" or "retrieve_matching_memory" in binding_ids
    retrieval = (
        select_memory_context(
            route,
            prompt=prompt,
            tool_input_text=tool_input_text,
            soft_target_records=soft_target_records,
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
    additional_context, context_over_soft_target, omitted = (
        _additional_context(selected, semantic_review_candidates)
        if selected or semantic_review_candidates
        else ("", False, [])
    )

    actions: list[dict[str, Any]] = []
    for binding in bindings:
        if not isinstance(binding, dict) or not binding.get("action"):
            continue
        action_id = str(binding["action"])
        if action_id == "retrieve_matching_memory":
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

    return {
        "schema": SCHEMA,
        "status": retrieval["coverage_status"],
        "execution_owner": "host_model_agent",
        "consumer_role": "bounded_context_selection_only",
        "selected_records": selected,
        "semantic_review_candidates": semantic_review_candidates,
        "semantic_review_owner": "host_model_agent",
        "task_local_correction_bundle": correction_bundle,
        "retrieval": {
            key: value
            for key, value in retrieval.items()
            if key not in {"selected_records", "semantic_review_candidates"}
        },
        "actions": actions,
        "additional_context": additional_context,
        "context_char_count": len(additional_context),
        "context_soft_target_chars": CONTEXT_SOFT_TARGET_CHARS,
        "context_over_soft_target": context_over_soft_target,
        "omitted_context_record_ids": omitted,
        "boundary": "CBH selects compact indexed context; the model agent still interprets evidence, chooses tools, executes the task, and owns the final answer.",
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    parser = argparse.ArgumentParser(description="Select bounded CBH memory context for a model agent.")
    parser.add_argument("--route-json", required=True)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--tool-input-text", default="")
    args = parser.parse_args()
    route = json.loads(args.route_json)
    result = build_action_consumption(
        route,
        prompt=args.prompt,
        tool_input_text=args.tool_input_text,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
