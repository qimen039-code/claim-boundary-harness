from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


if sys.version_info < (3, 11):
    pytest.skip("tomllib requires Python 3.11+", allow_module_level=True)

import tomllib  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
AUTHORING = ROOT / "skills" / "embedded-harness" / "embedded_harness_policy.authoring.toml"
COMPILER = ROOT / "skills" / "embedded-harness" / "compile_policy_from_toml.py"


def test_policy_authoring_toml_is_machine_readable() -> None:
    payload = tomllib.loads(AUTHORING.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "cbh.policy_authoring.v1"
    assert payload["compiled_sections"]
    router = payload["router_decision_contract"]
    assert router["skill_audit_contract"]["minimum_risk"] == "R3"
    assert "skill_audit_gate" in router["skill_audit_contract"]["required_gates"]
    assert {"功能重叠", "长期未用", "可合并项"}.issubset(
        set(router["skill_audit_contract"]["redundancy_triggers"])
    )
    assert router["first_principles_contract"]["required_gate"] == "first_principles_gate"
    assert router["first_principles_contract"]["profile_values"] == [
        "none",
        "micro_constraints",
        "constraint_gate",
        "full_design",
    ]
    assert payload["runtime_enforcement"]["human_confirmation_permit"]["required_scope"] == "single_event"
    assert payload["runtime_enforcement"]["human_confirmation_permit"]["consume_on_pass"] is True
    assert payload["runtime_enforcement"]["human_confirmation_permit"]["used_ledger_env_var"] == "CBH_R5_PERMIT_USE_LEDGER"


def test_policy_authoring_toml_matches_runtime_json() -> None:
    result = subprocess.run(
        [sys.executable, str(COMPILER), "--check"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert payload["changed_tracked_paths"] == []
