#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT:-}" ]]; then
  if [[ -n "${CODEBUDDY_PROJECT_DIR:-}" ]]; then
    AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT="$CODEBUDDY_PROJECT_DIR/integrations/workbuddy-python-runtime"
  else
    AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  fi
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi

export PYTHONUTF8="${PYTHONUTF8:-1}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
export PYTHONPATH="$AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON_BIN" -m workbuddy_harness.hook_runner "$@"
