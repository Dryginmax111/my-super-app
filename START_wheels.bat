@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Tracker Server

set "ROOT=%~dp0"
set "PY="
for %%D in ("%ROOT%runtime\embedded\python_embed*" "%ROOT%runtime\embedded\python313" "%ROOT%runtime\embedded\*") do (
    if not defined PY if exist "%%~fD\python.exe" set "PY=%%~fD\python.exe"
)
if not defined PY if exist "%ROOT%runtime\embedded\python313\python.exe" set "PY=%ROOT%runtime\embedded\python313\python.exe"

set "CORE=%ROOT%core"

if not defined PY (
    echo [ERROR] Python not found. Check runtime\embedded\
    pause
    exit /b 1
)

if not exist "%CORE%\run.py" (
    echo [ERROR] core\run.py not found
    pause
    exit /b 1
)

echo [SYSTEM] Checking libraries (flask, openpyxl)...
"!PY!" -c "import flask, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Libraries are missing or broken!
    echo [SYSTEM] Starting offline installation from tools\wheels...
    
    if exist "%CORE%\tools\install_offline.bat" (
        call "%CORE%\tools\install_offline.bat"
    ) else if exist "%ROOT%\tools\install_offline.bat" (
        call "%ROOT%\tools\install_offline.bat"
    ) else (
        echo [ERROR] install_offline.bat not found in tools\ directory!
        pause
        exit /b 1
    )
    
    echo [SYSTEM] Re-checking libraries...
    "!PY!" -c "import flask, openpyxl" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Libraries still missing after offline install.
        echo Please check tools\wheels or run tools\setup_embedded.bat manually.
        pause
        exit /b 1
    )
    echo [SYSTEM] Libraries installed successfully.
)

cd /d "%CORE%"

echo.
echo ============================================================
echo    T R E K E R   Z A D A C H   -  SERVER START
echo    http://localhost:5431/
echo    Stop: close this window (X)
echo    Auto-restart: on crash / restart request
echo ============================================================
echo.

if exist "%CORE%\__pycache__" rd /s /q "%CORE%\__pycache__"

:loop
title Tracker Server - running
"!PY!" "%CORE%\run.py"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo [SERVER] exited with code %EXIT_CODE%. Restarting in 3 seconds...
echo    (Press Ctrl+C to stop the loop)
echo.
timeout /t 3 /nobreak >nul
goto loop