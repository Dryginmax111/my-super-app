@echo off
setlocal enabledelayedexpansion
chcp 866 >nul
title Tracker Server

set "ROOT=%~dp0"

rem --- Auto-detect embedded python.exe (any folder name under runtime\embedded) ---
set "PY="
for %%D in ("%ROOT%runtime\embedded\python_embed*" "%ROOT%runtime\embedded\python313" "%ROOT%runtime\embedded\*") do (
    if not defined PY if exist "%%~fD\python.exe" set "PY=%%~fD\python.exe"
)
if not defined PY if exist "%ROOT%runtime\embedded\python313\python.exe" set "PY=%ROOT%runtime\embedded\python313\python.exe"
if not defined PY if exist "%ROOT%runtime\python_embed*\python.exe" for %%P in ("%ROOT%runtime\python_embed*\python.exe") do set "PY=%%~fP"

set "CORE=%ROOT%core"

if not defined PY (
    echo [ERROR] Embedded Python ne najden v %ROOT%runtime\embedded\
    echo         Zapustite snachala tools\install_offline.bat ili tools\setup_embedded.bat
    pause
    exit /b 1
)

if not exist "%CORE%\run.py" (
    echo [ERROR] core\run.py ne najden
    pause
    exit /b 1
)

echo Using Python: !PY!
"!PY!" --version
if errorlevel 1 (
    echo [ERROR] Embedded Python ne zapuskaetsya
    pause
    exit /b 1
)

cd /d "%CORE%"

echo.
echo ============================================================
echo    T R E K E R   Z A D A C H   -  SERVER START
echo    http://localhost:5431/
echo    Stop: Ctrl+C  (or close this window)
echo ============================================================
echo.

rem --- Clear stale pyc caches (can hide old broken code after rollback) ---
if exist "%CORE%\__pycache__" rd /s /q "%CORE%\__pycache__"

"!PY!" "%CORE%\run.py"

echo.
echo Server stopped.
pause
endlocal
exit /b 0
