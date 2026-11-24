@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
set "LOG=%~dp0logs\start.log"
set "PORT=%~1"
if "%PORT%"=="" set "PORT=8033"

call :log "==== START requested on port %PORT% ===="

if not exist "venv\Scripts\python.exe" (
  call :log "ERROR: the app is not set up yet. Run setup.bat first."
  echo.
  pause
  exit /b 1
)
if not exist "data\uploads" mkdir "data\uploads"

netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  call :log "ERROR: port %PORT% is already in use. Close the other program or run: start.bat 8001"
  echo.
  pause
  exit /b 1
)

call :log "Opening http://127.0.0.1:%PORT% in your browser in a few seconds ..."
start "" cmd /c "timeout /t 6 /nobreak >nul & start http://127.0.0.1:%PORT%"

call :log "Server is running. Close this window or press Ctrl+C to stop. Detailed log: logs\app.log"
"venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% >> "%LOG%" 2>&1
call :log "Server stopped."
echo.
pause
exit /b 0

:log
echo [%date% %time%] %~1
echo [%date% %time%] %~1 >> "%LOG%"
exit /b 0
