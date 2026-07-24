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
    lifecycle = router["correction_lifecycle_contract"]
    assert lifecycle["schema"] == "cbh.correction_lifecycle_contract.v1"
    assert lifecycle["objective_order"] == [
        "real_effectiveness_and_required_components",
        "minimum_sufficient_implementation",
        "execution_time_and_token_efficiency",
        "surface_simplicity",
    ]
    assert "postcondition_verification" in lifecycle["stages"]
    assert "task_local_retirement" in lifecycle["stages"]
    correction = payload["runtime_enforcement"]["behavior_correction_contract"]
    assert correction["schema"] == "cbh.behavior_correction_contract.v1"
    assert correction["migration_hook"]["host_blocking"] is False
    assert correction["migration_hook"]["stateful"] is False
    assert correction["migration_hook"]["ambiguous_behavior"] == "no_output_original_input_unchanged"


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
