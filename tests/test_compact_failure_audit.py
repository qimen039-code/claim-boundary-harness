from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import sys
from pathlib import Path


HARNESS = Path(__file__).resolve().parents[1] / "skills" / "embedded-harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from compact_failure_audit import compact_failure_rows, read_jsonl_window
from task_continuity import plan_transport


class CompactFailureAuditTests(unittest.TestCase):
    def test_failure_rows_support_hash_bound_continuation_when_plan_is_explicit(self) -> None:
        events = [
            {
                "agent_path": "/root/child",
                "tool": "shell_command",
                "signature": f"{index:064x}",
                "error_class": f"failure-{index}",
                "side_effects": "none",
                "recovered": True,
            }
            for index in range(7)
        ]
        plan = plan_transport(
            None,
            {"kind": "items", "original_items": len(events), "original_chars": 2000},
            {"max_chars": 1800, "max_items": 2},
        )
        rebuilt: list[dict] = []
        cursor = None
        while True:
            receipt = compact_failure_rows(
                events,
                max_rows=2,
                transport_plan=plan,
                cursor=cursor,
            )
            page = receipt["transport_page"]
            rebuilt.extend(page["items"])
            if page["next_cursor"] is None:
                break
            cursor = page["next_cursor"]

        self.assertEqual(7, len(rebuilt))
        self.assertEqual(
            [f"failure-{index}" for index in range(7)],
            [row["error_class"] for row in rebuilt],
        )
        canonical = json.dumps(rebuilt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            page["full_result_sha256"],
        )

    def test_synthetic_fixture_hashes_match_canonical_raw_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.jsonl"
            lines = [
                json.dumps({"type": "tool_call", "name": "web__run"}, separators=(",", ":")),
                json.dumps({"type": "tool_output", "status": "failed"}, separators=(",", ":")),
            ]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            rows = {row["line"]: row for row in read_jsonl_window(path, {1, 2})}
            self.assertEqual(
                hashlib.sha256(lines[0].encode("utf-8")).hexdigest(),
                rows[1]["sha256"],
            )
            self.assertEqual(
                hashlib.sha256(lines[1].encode("utf-8")).hexdigest(),
                rows[2]["sha256"],
            )

    def test_bounded_jsonl_window_preserves_raw_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "active.jsonl"
            first = json.dumps({"event": "ok"}, separators=(",", ":"))
            second = json.dumps({"event": "failed"}, separators=(",", ":"))
            with path.open("w", encoding="utf-8") as writer:
                writer.write(first + "\n")
                writer.write(second + "\n")
                writer.flush()
                rows = read_jsonl_window(path, {2})
            self.assertEqual(1, len(rows))
            self.assertEqual(2, rows[0]["line"])
            self.assertEqual(
                hashlib.sha256(second.encode("utf-8")).hexdigest(),
                rows[0]["sha256"],
            )
            self.assertNotIn("raw", rows[0])
            self.assertNotIn("parsed", rows[0])

    def test_recovered_failures_remain_and_network_side_effects_are_truthful(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.jsonl"
            trace.write_text("{}\n", encoding="utf-8")
            rows = compact_failure_rows(
                [
                    {
                        "agent_path": "/root/child",
                        "tool": "shell_command",
                        "signature": "a" * 64,
                        "error_class": "Object[]->DateTime",
                        "side_effects": "read_only_network_requests_before_local_shape_failure",
                        "recovered": True,
                        "raw_ref": f"{trace}:1",
                    }
                ]
            )
        self.assertEqual(1, len(rows))
        self.assertTrue(rows[0]["recovered"])
        self.assertIn("network", rows[0]["side_effects"])
        self.assertNotEqual("none", rows[0]["side_effects"])

    def test_compaction_rejects_ambiguous_booleans_and_invalid_signatures(self) -> None:
        base = {
            "agent_path": "/root",
            "tool": "shell_command",
            "signature": "a" * 64,
            "error_class": "failure",
            "side_effects": "none",
            "recovered": False,
        }
        with self.assertRaisesRegex(ValueError, "recovered"):
            compact_failure_rows([{**base, "recovered": "false"}])
        with self.assertRaisesRegex(ValueError, "signature"):
            compact_failure_rows([{**base, "signature": "not-a-hash"}])

        for signature in (int("1" * 64), "A" * 64):
            with self.subTest(signature=signature):
                with self.assertRaisesRegex(ValueError, "signature"):
                    compact_failure_rows([{**base, "signature": signature}])

    def test_missing_raw_refs_are_not_claimed_as_raw_log_bound(self) -> None:
        rows = compact_failure_rows(
            [
                {
                    "agent_path": "/root",
                    "tool": "shell_command",
                    "signature": "b" * 64,
                    "error_class": "failure",
                    "side_effects": "none",
                    "recovered": False,
                    "raw_ref": "C:/definitely-missing-trace.jsonl:1",
                }
            ]
        )
        self.assertEqual("semantic_review_required", rows[0]["evidence_status"])
        self.assertEqual("raw_ref_unverified", rows[0]["evidence_issue"])

    def test_raw_ref_requires_a_json_object_and_exposes_only_its_digest(self) -> None:
        base = {
            "agent_path": "/root",
            "tool": "shell_command",
            "signature": "d" * 64,
            "error_class": "failure",
            "side_effects": "none",
            "recovered": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            path.write_text("not-json\n", encoding="utf-8")
            invalid = compact_failure_rows(
                [{**base, "raw_ref": f"{path}:1"}]
            )[0]
            self.assertEqual("semantic_review_required", invalid["evidence_status"])
            self.assertEqual("raw_ref_unverified", invalid["evidence_issue"])
            self.assertFalse(invalid["raw_log_is_canonical"])

            raw_line = '{"event":"failed"}'
            path.write_text(raw_line + "\n", encoding="utf-8")
            verified = compact_failure_rows(
                [{**base, "raw_ref": f"{path}:1"}]
            )[0]
        self.assertEqual("raw_log_bound", verified["evidence_status"])
        self.assertTrue(verified["raw_log_is_canonical"])
        self.assertEqual(
            hashlib.sha256(raw_line.encode("utf-8")).hexdigest(),
            verified["raw_ref_sha256"],
        )
        self.assertNotIn("raw", verified)
        self.assertNotIn("parsed", verified)

        missing = compact_failure_rows([base])[0]
        self.assertEqual("semantic_review_required", missing["evidence_status"])
        self.assertEqual("raw_ref_missing", missing["evidence_issue"])
        self.assertFalse(missing["raw_log_is_canonical"])

    def test_payload_and_row_budgets_require_literal_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            path.write_text('{"event":"failed"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "include_payload"):
                read_jsonl_window(path, {1}, include_payload="false")

        event = {
            "agent_path": "/root",
            "tool": "shell_command",
            "signature": "e" * 64,
            "error_class": "failure",
            "side_effects": "none",
            "recovered": False,
        }
        with self.assertRaisesRegex(ValueError, "positive integer"):
            compact_failure_rows([event], max_rows=True)

    def test_row_and_side_effect_budgets_never_silently_truncate(self) -> None:
        event = {
            "agent_path": "/root",
            "tool": "shell_command",
            "signature": "c" * 64,
            "error_class": "failure",
            "side_effects": "x" * 300,
            "recovered": False,
        }
        row = compact_failure_rows([event])[0]
        self.assertTrue(row["side_effects_truncated"])
        self.assertIn("side_effects_uncovered", row)
        with self.assertRaisesRegex(ValueError, "max_rows"):
            compact_failure_rows([event, event], max_rows=1)


if __name__ == "__main__":
    unittest.main()
