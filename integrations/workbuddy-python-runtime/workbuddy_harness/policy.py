from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_POLICY_PATH = Path(
    os.environ.get(
        "AGENT_MEMORY_LANE_POLICY",
        Path(__file__).resolve().parents[3] / "skills" / "embedded-harness" / "embedded_harness_policy.json",
    )
)


def load_policy(policy_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    path = Path(policy_path) if policy_path else DEFAULT_POLICY_PATH
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)
