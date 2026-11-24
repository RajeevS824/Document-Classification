@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
set "LOG=%~dp0logs\setup.log"

call :log "==== SETUP STARTED ===="
call :log "Project folder: %~dp0"

REM ---------- find Python 3.9+
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  call :log "ERROR: Python was not found. Install Python 3.9 or newer from python.org and tick Add Python to PATH."
  goto :fail
)
call :log "Using Python launcher: %PY%"
%PY% --version >> "%LOG%" 2>&1
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >> "%LOG%" 2>&1
if errorlevel 1 (
  call :log "ERROR: Python 3.9 or newer is required."
  goto :fail
)

REM ---------- virtual environment
if exist "venv\Scripts\python.exe" (
  call :log "Virtual environment already exists - reusing it."
) else (
  call :log "Creating virtual environment in venv ..."
  %PY% -m venv venv >> "%LOG%" 2>&1
  if errorlevel 1 (
    call :log "ERROR: could not create the virtual environment."
    goto :fail
  )
)

call :log "Upgrading pip ..."
"venv\Scripts\python.exe" -m pip install --upgrade pip >> "%LOG%" 2>&1

call :log "Installing requirements - this can take several minutes ..."
"venv\Scripts\python.exe" -m pip install -r requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 (
  call :log "ERROR: installing requirements failed. See logs\setup.log for details."
  goto :fail
)

if not exist "data\uploads" mkdir "data\uploads"

REM ---------- optional model pre-download (run  setup.bat nomodel  to skip)
if /i "%~1"=="nomodel" (
  call :log "Skipping model download because nomodel was given. The app downloads it on first use."
) else (
  call :log "Downloading the Nutrient v1 model - about 2.2 GB, one time only ..."
  "venv\Scripts\python.exe" -m app.download_model >> "%LOG%" 2>&1
  if errorlevel 1 (
    call :log "WARNING: model download failed. The app still works with OCR keywords only and retries on first use."
  )
)

call :log "SETUP COMPLETED. Now run start.bat"
echo.
pause
exit /b 0

:fail
call :log "SETUP FAILED. Open logs\setup.log to see the reason."
echo.
pause
exit /b 1

:log
echo [%date% %time%] %~1
echo [%date% %time%] %~1 >> "%LOG%"
exit /b 0
