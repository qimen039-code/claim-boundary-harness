from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "skills" / "embedded-harness"
WORKBUDDY = ROOT / "integrations" / "workbuddy-python-runtime"


def _load_harness_module(name: str):
    module_path = HARNESS / f"{name}.py"
    assert module_path.is_file(), f"missing public harness module: {module_path}"
    harness_text = str(HARNESS)
    if harness_text not in sys.path:
        sys.path.insert(0, harness_text)
    return importlib.import_module(name)


def _load_workbuddy_hook_runner():
    workbuddy_text = str(WORKBUDDY)
    if workbuddy_text not in sys.path:
        sys.path.insert(0, workbuddy_text)
    return importlib.import_module("workbuddy_harness.hook_runner")


def _run_workbuddy_hook(payload: dict[str, object], *, stage: str, log_dir: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(WORKBUDDY)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "workbuddy_harness.hook_runner",
            "--stage",
            stage,
            "--log-dir",
            str(log_dir),
        ],
        cwd=ROOT,
        env=env,
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        check=False,
    )


def test_mixed_heredoc_profiles_choose_semantic_review() -> None:
    gate = _load_harness_module("behavior_correction_gate")
    receipt = gate.build_behavior_correction_receipt(
        stage="pretool",
        environment="powershell",
        tool_role="shell",
        tool_surface="exec_command",
        text=(
            "python - <<'PY'\n"
            "print('quoted')\n"
            "PY\n"
            "python - <<PY\n"
            "print('unquoted')\n"
            "PY"
        ),
    )

    assert receipt["match_count"] == 2
    assert receipt["decision"] == "semantic_review_required"
    assert receipt["host_blocking"] is False


def test_behavior_hook_is_silent_for_unmatched_destructive_command() -> None:
    hook = _load_harness_module("behavior_correction_hook")
    output = hook.handle_event(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "cwd": str(ROOT),
            "tool_input": {"command": "rm -rf build"},
        },
        parser=lambda _text: [],
    )

    assert output == {}


def test_public_behavior_profiles_contain_no_private_session_paths() -> None:
    profile_path = HARNESS / "behavior_correction_profiles.json"
    assert profile_path.is_file(), f"missing public profile registry: {profile_path}"
    raw = profile_path.read_text(encoding="utf-8")
    assert "C:\\Users\\" not in raw
    assert "\\.codex\\sessions\\" not in raw
    assert "rollout-2026" not in raw


def test_workbuddy_pretool_never_denies_r5_command(tmp_path: Path) -> None:
    prompt = _run_workbuddy_hook(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-nonblocking-r5",
            "cwd": str(tmp_path),
            "prompt": "delete stale build files after review",
        },
        stage="user_prompt",
        log_dir=tmp_path,
    )
    assert prompt.returncode == 0, prompt.stderr

    pretool = _run_workbuddy_hook(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "session-nonblocking-r5",
            "cwd": str(tmp_path),
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf build"},
        },
        stage="pre_tool",
        log_dir=tmp_path,
    )

    assert pretool.returncode == 0, pretool.stderr
    assert "permissionDecision\": \"deny" not in pretool.stdout
    assert "permissionDecisionReason" not in pretool.stdout
    assert not (tmp_path / "r5-permit-uses.jsonl").exists()


def test_workbuddy_rewrites_only_verified_powershell_candidate() -> None:
    hook_runner = _load_workbuddy_hook_runner()
    command = (
        "$items=@('a','b'); "
        "foreach($item in $items){[pscustomobject]@{Name=$item}} "
        "| ConvertTo-Json"
    )

    output = hook_runner.handle_pretool_event(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "executor_environment": "powershell",
            "cwd": str(ROOT),
            "tool_input": {
                "command": command,
                "description": "preserve this field",
            },
        },
        parser=lambda text: ["EmptyPipeElement"] if text == command else [],
    )

    hook_output = output["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "allow"
    assert hook_output["updatedInput"]["command"] != command
    assert hook_output["updatedInput"]["description"] == "preserve this field"


def test_workbuddy_package_exposes_no_blocking_or_permit_api() -> None:
    workbuddy_text = str(WORKBUDDY)
    if workbuddy_text not in sys.path:
        sys.path.insert(0, workbuddy_text)
    package = importlib.import_module("workbuddy_harness")
    gates = importlib.import_module("workbuddy_harness.gates")

    for name in (
        "runtime_enforcer",
        "build_single_event_human_confirmation_permit",
    ):
        assert not hasattr(package, name), name
        assert not hasattr(gates, name), name

    source = (WORKBUDDY / "workbuddy_harness" / "gates.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "cbh.r5_human_confirmation_permit.v1",
        "r5_permit_use_ledger",
        "human_confirmation_permit_use",
    ):
        assert forbidden not in source


def test_legacy_blocking_entry_scripts_are_retired() -> None:
    for name in (
        "harness_runtime_enforcer.ps1",
        "harness_task_wrapper.ps1",
        "harness_tool_proxy.ps1",
    ):
        assert not (HARNESS / name).exists(), name


def test_workbuddy_deployment_profile_is_nonblocking() -> None:
    profile_path = WORKBUDDY / "deployment-profiles.json"
    document = json.loads(profile_path.read_text(encoding="utf-8"))
    profile = document["profiles"]["workbuddy-hook-minimal"]

    assert profile["runtime_mode"] == "advisory_route_plus_nonblocking_correction"
    assert profile["host_blocking"] is False
    assert profile["stateful_authorization"] is False
    assert profile["registered_hooks"] == ["UserPromptSubmit"]
    assert profile["optional_hooks"] == ["PreToolUse"]
    assert profile["pretool_activation"] == "manual_after_host_protocol_verification"
    assert profile["output_contract"] == "advisory_by_default_optional_codex_allow_updated_input"
    assert "skills/embedded-harness/behavior_correction_hook.py" in profile["include"]
    assert not any("harness_runtime_enforcer" in item for item in profile["include"])
    assert not any("harness_tool_proxy" in item for item in profile["include"])
    assert not any("harness_task_wrapper" in item for item in profile["include"])
