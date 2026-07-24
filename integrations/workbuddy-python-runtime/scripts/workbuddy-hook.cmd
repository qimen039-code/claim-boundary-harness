@echo off
setlocal

if "%AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT%"=="" (
  set "AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT=%~dp0.."
)

if "%PYTHON_BIN%"=="" (
  set "PYTHON_BIN=python"
)

if "%PYTHONUTF8%"=="" (
  set "PYTHONUTF8=1"
)

if "%PYTHONIOENCODING%"=="" (
  set "PYTHONIOENCODING=utf-8"
)

if "%PYTHONPATH%"=="" (
  set "PYTHONPATH=%AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT%"
) else (
  set "PYTHONPATH=%AGENT_MEMORY_LANE_WORKBUDDY_ADAPTER_ROOT%;%PYTHONPATH%"
)

"%PYTHON_BIN%" -m workbuddy_harness.hook_runner %* 2>nul
exit /b 0
