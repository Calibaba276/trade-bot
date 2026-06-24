@echo off
REM Launch the EURUSD strategy runner for Task Scheduler.
REM Redirects console output (incl. import-time tracebacks that occur BEFORE
REM the logger is configured) to logs\eurusd_console.log so nothing is silent.
REM %~dp0 is this script's folder; ".." is the repo root — no hardcoded path.
cd /d "%~dp0.."
if not exist logs mkdir logs
python -m backend.runners.eurusd >> logs\eurusd_console.log 2>&1
