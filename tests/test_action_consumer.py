from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONSUMER_PATH = ROOT / "skills" / "embedded-harness" / "harness_action_consumer.py"


def load_consumer_module():
    spec = importlib.util.spec_from_file_location("cbh_harness_action_consumer", CONSUMER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load harness action consumer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_lane(root: Path) -> Path:
    lane = root / "conversation-lane"
    lane.mkdir(parents=True)
    (lane / "_META_INDEX.md").write_text(
        "# Current Conversation\n\nlane_state: ACTIVE\n",
        encoding="utf-8",
    )
    records = [
        {
            "record_id": "SOL-CUMC-CONCEPT-DISTRACTOR",
            "status": "ACTIVE",
            "retrieval_terms": ["CUMC", "记忆机制", "深度学习"],
            "summary": "A different memory-architecture naming decision.",
        },
        {
            "record_id": "CE-TOML-AUTO-UPDATE-DISTRACTOR",
            "status": "ACTIVE",
            "retrieval_terms": ["自动更新", "实际生效", "配置问题"],
            "summary": "A different client configuration incident.",
        },
        {
            "record_id": "ANCHOR-MEMORY-META-FIRST-RETRIEVAL",
            "status": "ACTIVE",
            "retrieval_terms": [
                "记忆机制中的检索机制",
                "复合自然语言检索",
                "memory meta index first",
            ],
            "exact_trigger": [
                "用户讨论记忆检索是否能在复杂任务中自动触发并把精确锚点交给模型",
            ],
            "anchored_meaning": "先读元摘要和索引，再把精确命中的有界上下文交给模型代理继续完成任务。",
            "source_tag": "shared_semantic_anchor",
            "belief_status": "user_confirmed_definition",
        },
    ]
    (lane / "decisions.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    (lane / "index.json").write_text(
        json.dumps(
            {
                "memory_id": "conversation:test-compound-retrieval",
                "lane_state": "ACTIVE",
                "record_families": {"decisions": "decisions.jsonl"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return lane


def test_compound_prompt_promotes_exact_anchor_from_candidates_to_selected_context(tmp_path: Path) -> None:
    consumer = load_consumer_module()
    lane = write_lane(tmp_path)
    prompt = (
        "关于我们的记忆机制中的检索机制，以及外部求索深度学习机制，"
        "是否能实际在触发时自动调用并实际生效。再次确认。"
    )
    route = {
        "memory_need": "index_only",
        "memory_source_hints": [
            {
                "lane": "current_conversation",
                "root_path": str(lane),
                "meta_path": str(lane / "_META_INDEX.md"),
                "isolation": "exact_active_conversation_lane",
            }
        ],
        "action_bindings": [
            {
                "action": "retrieve_matching_memory",
                "completion_evidence": "selected_record_id_and_provenance",
            },
            {
                "action": "perform_external_research_route",
                "completion_evidence": "source_ledger_or_citations",
            },
        ],
    }

    receipt = consumer.build_action_consumption(route, prompt=prompt)

    assert receipt["status"] == "selected_context_ready"
    assert receipt["execution_owner"] == "host_model_agent"
    assert receipt["selected_records"][0]["record_id"] == "ANCHOR-MEMORY-META-FIRST-RETRIEVAL"
    assert receipt["selected_records"][0]["source_tag"] == "shared_semantic_anchor"
    assert "ANCHOR-MEMORY-META-FIRST-RETRIEVAL" in receipt["additional_context"]
    actions = {item["action_id"]: item for item in receipt["actions"]}
    assert actions["retrieve_matching_memory"]["status"] == "completed"
    assert actions["perform_external_research_route"]["status"] == "deferred_to_model_agent"


def test_weak_only_match_keeps_semantic_review_boundary(tmp_path: Path) -> None:
    consumer = load_consumer_module()
    lane = write_lane(tmp_path)
    receipt = consumer.build_action_consumption(
        {
            "memory_need": "index_only",
            "memory_source_hints": [
                {"lane": "current_conversation", "root_path": str(lane)}
            ],
        },
        prompt="配置",
    )
    assert receipt["status"] == "semantic_review_required"
    assert receipt["semantic_review_owner"] == "host_model_agent"
    assert receipt["selected_records"]
    assert receipt["selected_records"][0]["record_id"] in receipt["additional_context"]


def test_source_hint_cannot_escape_declared_lane(tmp_path: Path) -> None:
    consumer = load_consumer_module()
    lane = write_lane(tmp_path / "inside")
    outside_meta = tmp_path / "outside.md"
    outside_meta.write_text("# outside", encoding="utf-8")
    receipt = consumer.select_memory_context(
        {
            "memory_source_hints": [
                {
                    "lane": "current_conversation",
                    "root_path": str(lane),
                    "meta_path": str(outside_meta),
                }
            ]
        },
        prompt="记忆机制中的检索机制",
    )
    assert receipt["coverage_status"] == "no_match"
    assert receipt["source_receipts"][0]["reason"] == "meta_outside_root"


def test_action_consumer_prepares_nonblocking_correction_for_real_foreach_regression() -> None:
    consumer = load_consumer_module()
    receipt = consumer.build_action_consumption(
        {
            "memory_need": "none",
            "execution_environment": "powershell",
            "candidate_tool_surface": "shell_command",
            "action_bindings": [
                {
                    "action": "prepare_task_local_correction_bundle",
                    "completion_evidence": "task_local_correction_bundle",
                }
            ],
        },
        prompt="Summarize the parser errors.",
        tool_input_text="foreach ($error in $errors) { $error.ErrorId } | Sort-Object -Unique",
    )

    bundle = receipt["task_local_correction_bundle"]
    assert bundle["decision"] == "rewrite_candidate"
    assert bundle["host_blocking"] is False
    assert bundle["scope"] == "current_event_only"
    action = next(item for item in receipt["actions"] if item["action_id"] == "prepare_task_local_correction_bundle")
    assert action["status"] == "completed"


def test_action_consumer_unmatched_candidate_is_silent_noop() -> None:
    consumer = load_consumer_module()
    receipt = consumer.build_action_consumption(
        {
            "memory_need": "none",
            "execution_environment": "powershell",
            "candidate_tool_surface": "shell_command",
        },
        prompt="List files.",
        tool_input_text="Get-ChildItem -LiteralPath .",
    )

    bundle = receipt["task_local_correction_bundle"]
    assert bundle["decision"] == "no_match"
    assert bundle["host_blocking"] is False
