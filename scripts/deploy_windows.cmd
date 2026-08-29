@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_PATH=C:\GlassBox"
set "SERVICE_NAME=GlassBoxOrchestrator"
set "LEGACY_SERVICE_NAME=GlassBoxWorker"
set "PYTHON_EXE=python.exe"
set "NSSM_EXE=nssm.exe"
set "HEALTH_WAIT_SECONDS=30"

:parse_args
if "%~1"=="" goto validate_args
if /i "%~1"=="--source" goto arg_source
if /i "%~1"=="--commit" goto arg_commit
if /i "%~1"=="--run-id" goto arg_run_id
if /i "%~1"=="--root" goto arg_root
if /i "%~1"=="--service" goto arg_service
if /i "%~1"=="--legacy-service" goto arg_legacy_service
if /i "%~1"=="--python" goto arg_python
if /i "%~1"=="--nssm" goto arg_nssm
if /i "%~1"=="--health-wait" goto arg_health_wait
echo ERROR: Unknown or incomplete option: %~1
goto usage

:arg_source
set "SOURCE_PATH=%~2"
goto shift_two
:arg_commit
set "COMMIT_SHA=%~2"
goto shift_two
:arg_run_id
set "RUN_ID=%~2"
goto shift_two
:arg_root
set "ROOT_PATH=%~2"
goto shift_two
:arg_service
set "SERVICE_NAME=%~2"
goto shift_two
:arg_legacy_service
set "LEGACY_SERVICE_NAME=%~2"
goto shift_two
:arg_python
set "PYTHON_EXE=%~2"
goto shift_two
:arg_nssm
set "NSSM_EXE=%~2"
goto shift_two
:arg_health_wait
set "HEALTH_WAIT_SECONDS=%~2"
:shift_two
if "%~2"=="" (echo ERROR: Missing value for %~1.& exit /b 2)
shift
shift
goto parse_args

:validate_args
if not defined SOURCE_PATH goto usage
if not defined COMMIT_SHA goto usage
if not defined RUN_ID goto usage
echo(%COMMIT_SHA%| %SystemRoot%\System32\findstr.exe /r /x "[0-9a-fA-F][0-9a-fA-F]*" >nul || (echo ERROR: --commit must be hexadecimal.& exit /b 2)
if not "%COMMIT_SHA:~40,1%"=="" (echo ERROR: --commit must contain exactly 40 characters.& exit /b 2)
if "%COMMIT_SHA:~39,1%"=="" (echo ERROR: --commit must contain exactly 40 characters.& exit /b 2)
echo(%RUN_ID%| %SystemRoot%\System32\findstr.exe /r /x "[0-9][0-9]*-[0-9][0-9]*" >nul || (echo ERROR: --run-id must use NUMBER-NUMBER.& exit /b 2)
if not exist "%SOURCE_PATH%\backend\" (echo ERROR: Source backend directory not found.& exit /b 2)
if not exist "%SOURCE_PATH%\requirements.txt" (echo ERROR: Source requirements file not found.& exit /b 2)

for %%I in ("%SOURCE_PATH%") do set "SOURCE_PATH=%%~fI"
for %%I in ("%ROOT_PATH%") do set "ROOT_PATH=%%~fI"
set "RELEASES_ROOT=%ROOT_PATH%\releases"
set "RELEASE_ID=%COMMIT_SHA:~0,12%-%RUN_ID%"
set "RELEASE_PATH=%RELEASES_ROOT%\%RELEASE_ID%"
set "LOGS_PATH=%ROOT_PATH%\logs"
set "RELEASE_PYTHON=%RELEASE_PATH%\.venv\Scripts\python.exe"

sc query "%LEGACY_SERVICE_NAME%" 2>nul | %SystemRoot%\System32\findstr.exe /c:"RUNNING" >nul && (
  echo ERROR: Legacy service "%LEGACY_SERVICE_NAME%" is still running. Stop and disable it first.
  exit /b 1
)
if exist "%RELEASE_PATH%" (echo ERROR: Release already exists; refusing to overwrite it: %RELEASE_PATH%& exit /b 1)

mkdir "%RELEASE_PATH%" || exit /b 1
if not exist "%LOGS_PATH%" mkdir "%LOGS_PATH%" || exit /b 1
echo Preparing Glass Box release %RELEASE_ID%
xcopy "%SOURCE_PATH%\backend" "%RELEASE_PATH%\backend\" /e /i /q /y >nul || goto deploy_failed
copy /y "%SOURCE_PATH%\requirements.txt" "%RELEASE_PATH%\requirements.txt" >nul || goto deploy_failed
if exist "%SOURCE_PATH%\.python-version" copy /y "%SOURCE_PATH%\.python-version" "%RELEASE_PATH%\.python-version" >nul || goto deploy_failed

echo Creating isolated Python environment
call :run "%PYTHON_EXE%" -m venv "%RELEASE_PATH%\.venv" || goto deploy_failed
call :run "%RELEASE_PYTHON%" -m pip install --disable-pip-version-check --upgrade pip || goto deploy_failed
call :run "%RELEASE_PYTHON%" -m pip install --disable-pip-version-check -r "%RELEASE_PATH%\requirements.txt" || goto deploy_failed
echo Running release preflight checks
call :run "%RELEASE_PYTHON%" -m compileall -q "%RELEASE_PATH%\backend" || goto deploy_failed

set "SERVICE_EXISTED=0"
set "INSTALLED_NEW_SERVICE=0"
sc query "%SERVICE_NAME%" >nul 2>&1 && set "SERVICE_EXISTED=1"
if "!SERVICE_EXISTED!"=="1" (
  for /f "delims=" %%V in ('"%NSSM_EXE%" get "%SERVICE_NAME%" Application') do set "PREVIOUS_APPLICATION=%%V"
  if errorlevel 1 goto deploy_failed
  for /f "delims=" %%V in ('"%NSSM_EXE%" get "%SERVICE_NAME%" AppDirectory') do set "PREVIOUS_DIRECTORY=%%V"
  if errorlevel 1 goto deploy_failed
  for /f "delims=" %%V in ('"%NSSM_EXE%" get "%SERVICE_NAME%" AppParameters') do set "PREVIOUS_PARAMETERS=%%V"
  if errorlevel 1 goto deploy_failed
  net stop "%SERVICE_NAME%" /y >nul 2>&1
  call :wait_for_state STOPPED 30 || goto deploy_failed
) else (
  echo Installing NSSM service %SERVICE_NAME%
  call :run "%NSSM_EXE%" install "%SERVICE_NAME%" "%RELEASE_PYTHON%" -m backend.services.orchestrator || goto deploy_failed
  set "INSTALLED_NEW_SERVICE=1"
)

call :nssm_set Application "%RELEASE_PYTHON%" || goto rollback
call :nssm_set AppDirectory "%RELEASE_PATH%" || goto rollback
call :nssm_set AppParameters "-m backend.services.orchestrator" || goto rollback
call :nssm_set AppEnvironmentExtra "LOG_DIR=%LOGS_PATH%" || goto rollback
call :nssm_set AppStdout "%LOGS_PATH%\orchestrator-service-stdout.log" || goto rollback
call :nssm_set AppStderr "%LOGS_PATH%\orchestrator-service-stderr.log" || goto rollback
call :nssm_set AppRotateFiles 1 || goto rollback
call :nssm_set Start SERVICE_AUTO_START || goto rollback
net start "%SERVICE_NAME%" >nul || goto rollback
call :wait_for_state RUNNING 30 || goto rollback

echo Observing service health for %HEALTH_WAIT_SECONDS% seconds
timeout /t %HEALTH_WAIT_SECONDS% /nobreak >nul
sc query "%SERVICE_NAME%" | %SystemRoot%\System32\findstr.exe /c:"RUNNING" >nul || goto rollback

if exist "%ROOT_PATH%\current-release.txt" copy /y "%ROOT_PATH%\current-release.txt" "%ROOT_PATH%\previous-release.txt" >nul
>"%ROOT_PATH%\current-release.txt" echo %RELEASE_PATH%
copy /y "%SOURCE_PATH%\scripts\enter_release.cmd" "%ROOT_PATH%\Enter-GlassBox.cmd" >nul || goto rollback
>"%RELEASE_PATH%\release.json" echo {"commit_sha":"%COMMIT_SHA%","github_run":"%RUN_ID%","service":"%SERVICE_NAME%"}
echo Deployment healthy: commit=%COMMIT_SHA% release=%RELEASE_PATH% service=%SERVICE_NAME%
exit /b 0

:rollback
echo WARNING: Deployment failed. Attempting rollback.
net stop "%SERVICE_NAME%" /y >nul 2>&1
call :wait_for_state STOPPED 30 >nul 2>&1
if defined PREVIOUS_APPLICATION (
  "%NSSM_EXE%" set "%SERVICE_NAME%" Application "%PREVIOUS_APPLICATION%" >nul
  "%NSSM_EXE%" set "%SERVICE_NAME%" AppDirectory "%PREVIOUS_DIRECTORY%" >nul
  "%NSSM_EXE%" set "%SERVICE_NAME%" AppParameters "%PREVIOUS_PARAMETERS%" >nul
  net start "%SERVICE_NAME%" >nul
  call :wait_for_state RUNNING 30
) else if "%INSTALLED_NEW_SERVICE%"=="1" (
  "%NSSM_EXE%" remove "%SERVICE_NAME%" confirm >nul
)
exit /b 1

:deploy_failed
echo ERROR: Deployment preparation failed.
exit /b 1

:run
%*
if errorlevel 1 (echo ERROR: Command failed with exit code !errorlevel!: %*& exit /b 1)
exit /b 0

:nssm_set
"%NSSM_EXE%" set "%SERVICE_NAME%" %* >nul
exit /b %errorlevel%

:wait_for_state
set /a "WAIT_REMAINING=%~2"
:wait_loop
sc query "%SERVICE_NAME%" 2>nul | %SystemRoot%\System32\findstr.exe /c:"%~1" >nul && exit /b 0
if !WAIT_REMAINING! LEQ 0 exit /b 1
timeout /t 1 /nobreak >nul
set /a "WAIT_REMAINING-=1"
goto wait_loop

:usage
echo Usage:
echo   %~nx0 --source PATH --commit 40_CHAR_SHA --run-id NUMBER-NUMBER [options]
echo.
echo Options: --root PATH --service NAME --legacy-service NAME --python EXE --nssm EXE --health-wait SECONDS
exit /b 2
