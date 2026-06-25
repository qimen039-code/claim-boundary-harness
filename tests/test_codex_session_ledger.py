from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER_TOOL = ROOT / "skills" / "embedded-harness" / "codex_session_ledger.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("codex_session_ledger", LEDGER_TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sample_session(path: Path) -> None:
    write_jsonl(
        path,
        [
            {
                "timestamp": "2026-06-24T00:00:00Z",
                "type": "session_meta",
                "payload": {
                    "session_id": "00000000-0000-4000-8000-000000000001",
                    "id": "00000000-0000-4000-8000-000000000001",
                    "cwd": "C:/work/project",
                    "originator": "Codex Desktop",
                    "cli_version": "0.142.0",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-06-24T00:00:01Z",
                "type": "turn_context",
                "payload": {"turn_id": "turn-1", "cwd": "C:/work/project", "model": "gpt-5.5"},
            },
            {
                "timestamp": "2026-06-24T00:00:02Z",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "remember this conversation and link raw session"},
            },
            {
                "timestamp": "2026-06-24T00:00:03Z",
                "type": "event_msg",
                "payload": {
                    "type": "patch_apply_end",
                    "turn_id": "turn-1",
                    "success": True,
                    "changes": {"docs/example.md": {"type": "add", "content": "example"}},
                },
            },
            {
                "timestamp": "2026-06-24T00:00:04Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "turn_id": "turn-1",
                    "last_agent_message": "created ledger artifacts",
                },
            },
        ],
    )


def test_builds_lossless_pointer_ledger_from_codex_session(tmp_path: Path) -> None:
    tool = load_tool()
    session = tmp_path / "rollout-2026-06-24T00-00-00-00000000-0000-4000-8000-000000000001.jsonl"
    sample_session(session)
    output_dir = tmp_path / "ledger"
    result = tool.build_ledger(
        [session],
        output_dir,
        ledger_id="ledger:test",
        conversation_memory_id="conversation:test",
        conversation_memory_path="local-conversation-memory/test",
    )

    assert result["status"] == "pass"
    assert result["sessions"] == 1
    assert result["turns"] == 1
    assert result["segments"] == 1
    assert result["capsules"] == 1
    evidence = read_jsonl(output_dir / "evidence_refs.jsonl")
    assert {record["evidence_kind"] for record in evidence} >= {"user_message", "patch", "task_complete"}
    assert all(record["derived_from"]["line_start"] == record["derived_from"]["line_end"] for record in evidence)
    assert all(record["derived_from"]["sha256_16"] for record in evidence)
    capsules = read_jsonl(output_dir / "capsules.jsonl")
    assert capsules[0]["capsule_type"] == "event_domain_classification"
    assert capsules[0]["source_monitoring"]["classification_is_derivative"] is True
    assert set(capsules[0]["event_kinds"]) >= {"user_message", "patch", "task_complete"}
    assert capsules[0]["derived_from"]["segment_id"].startswith("SEG-")
    links = read_jsonl(output_dir / "links.jsonl")
    assert any(record["link_type"] == "raw_session_to_ledger" for record in links)
    assert any(record["link_type"] == "ledger_to_conversation_memory" for record in links)


def test_doctor_and_refresh_are_stat_first(tmp_path: Path) -> None:
    tool = load_tool()
    session = tmp_path / "rollout-2026-06-24T00-00-00-00000000-0000-4000-8000-000000000001.jsonl"
    sample_session(session)
    output_dir = tmp_path / "ledger"
    tool.build_ledger([session], output_dir, ledger_id="ledger:doctor")

    doctor = tool.doctor_ledger(output_dir)
    assert doctor["status"] in {"pass", "warn"}
    assert doctor["stale"] is False
    assert doctor["counts"]["capsules.jsonl"] == 1
    assert "raw session payload" in doctor["cost_boundary"]

    refresh = tool.refresh_ledger([session], output_dir, ledger_id="ledger:doctor")
    assert refresh["status"] == "pass"
    assert refresh["refreshed"] is False
    assert refresh["reason"] == "ledger_is_fresh"


def test_resolve_reads_only_selected_window_and_verifies_hash(tmp_path: Path) -> None:
    tool = load_tool()
    session = tmp_path / "rollout-2026-06-24T00-00-00-00000000-0000-4000-8000-000000000001.jsonl"
    sample_session(session)
    output_dir = tmp_path / "ledger"
    tool.build_ledger([session], output_dir, ledger_id="ledger:resolve")
    evidence = read_jsonl(output_dir / "evidence_refs.jsonl")
    ref_id = next(record["ref_id"] for record in evidence if record["evidence_kind"] == "user_message")

    resolved = tool.resolve_evidence(output_dir, ref_id, context_lines=1, max_chars_per_line=200)
    assert resolved["status"] == "pass"
    assert resolved["hash_match"] is True
    assert len(resolved["raw_window"]) <= 3
    assert "not the full session" in resolved["cost_boundary"]


def test_auto_refreshes_only_when_stat_check_is_stale(tmp_path: Path) -> None:
    tool = load_tool()
    session = tmp_path / "rollout-2026-06-24T00-00-00-00000000-0000-4000-8000-000000000001.jsonl"
    sample_session(session)
    output_dir = tmp_path / "ledger"
    tool.build_ledger([session], output_dir, ledger_id="ledger:auto")

    fresh = tool.auto_check(output_dir, session_paths=[session], refresh_on_stale=True, build_kwargs={"ledger_id": "ledger:auto"})
    assert fresh["action"] == "checked_only"

    with session.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": "2026-06-24T00:00:05Z", "type": "event_msg", "payload": {"type": "context_compacted"}}, ensure_ascii=False) + "\n")

    stale = tool.auto_check(output_dir, session_paths=[session], refresh_on_stale=True, build_kwargs={"ledger_id": "ledger:auto"})
    assert stale["status"] == "pass"
    assert stale["action"] == "refreshed_stale_ledger"


def test_compaction_creates_boundary_anchor_and_segment_flag(tmp_path: Path) -> None:
    tool = load_tool()
    session = tmp_path / "rollout-2026-06-24T00-00-00-00000000-0000-4000-8000-000000000001.jsonl"
    write_jsonl(
        session,
        [
            {
                "timestamp": "2026-06-24T00:00:00Z",
                "type": "session_meta",
                "payload": {"session_id": "00000000-0000-4000-8000-000000000001"},
            },
            {
                "timestamp": "2026-06-24T00:00:01Z",
                "type": "turn_context",
                "payload": {"turn_id": "turn-compact"},
            },
            {
                "timestamp": "2026-06-24T00:00:02Z",
                "type": "compacted",
                "payload": {"message": "lossy replacement summary"},
            },
            {
                "timestamp": "2026-06-24T00:00:03Z",
                "type": "event_msg",
                "payload": {"type": "context_compacted"},
            },
        ],
    )
    output_dir = tmp_path / "ledger"
    tool.build_ledger([session], output_dir, ledger_id="ledger:compact")

    segments = read_jsonl(output_dir / "segments.jsonl")
    assert segments[0]["compaction_boundary"] is True
    assert "compaction_boundary" in segments[0]["domain_tags"]
    anchors = read_jsonl(output_dir / "time_anchors.jsonl")
    assert any(anchor["anchor_type"] == "compaction_boundary" for anchor in anchors)
    evidence = read_jsonl(output_dir / "evidence_refs.jsonl")
    assert [record["evidence_kind"] for record in evidence].count("compaction") == 2
