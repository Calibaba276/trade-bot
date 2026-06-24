@echo off
REM Launch the LiquiditySweep strategy runner for Task Scheduler.
REM Redirects console output (incl. import-time tracebacks that occur BEFORE
REM the logger is configured) to logs\liquidity_sweep_console.log so nothing is silent.
REM %~dp0 is this script's folder; ".." is the repo root — no hardcoded path.
cd /d "%~dp0.."
if not exist logs mkdir logs
python -m backend.runners.main >> logs\liquidity_sweep_console.log 2>&1
