@echo off
set "GLASSBOX_RELEASE_ROOT=%GLASSBOX_ROOT%"
if not defined GLASSBOX_RELEASE_ROOT set "GLASSBOX_RELEASE_ROOT=C:\GlassBox"
set "GLASSBOX_MARKER=%GLASSBOX_RELEASE_ROOT%\current-release.txt"

if not exist "%GLASSBOX_MARKER%" (
  echo ERROR: No active Glass Box release marker exists at %GLASSBOX_MARKER%.
  echo Complete a successful deployment first.
  exit /b 1
)

set /p "GLASSBOX_RELEASE="<"%GLASSBOX_MARKER%"
if not exist "%GLASSBOX_RELEASE%\" (
  echo ERROR: The active Glass Box release directory does not exist: %GLASSBOX_RELEASE%
  exit /b 1
)
if not exist "%GLASSBOX_RELEASE%\.venv\Scripts\activate.bat" (
  echo ERROR: The active release virtual environment is missing.
  exit /b 1
)

cd /d "%GLASSBOX_RELEASE%" || exit /b 1
call ".venv\Scripts\activate.bat" || exit /b 1
echo Glass Box release: %GLASSBOX_RELEASE%
echo Virtual environment activated.
echo WARNING: Do not start another orchestrator while the GlassBoxOrchestrator service is running.
echo Stop the service first if you need an interactive engine session.
