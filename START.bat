@echo off
setlocal
chcp 65001 >nul
title Tracker Server

set "ROOT=%~dp0"
set "PY=%ROOT%runtime\embedded\python313\python.exe"
set "CORE=%ROOT%core"

if not exist "%PY%" (
    echo [ERROR] Embedded Python не найден:
    echo         %PY%
    echo.
    echo Проверьте, что папка runtime\embedded\python313 существует.
    pause
    exit /b 1
)

if not exist "%CORE%\run.py" (
    echo [ERROR] core\run.py не найден
    pause
    exit /b 1
)

echo Using Python:
"%PY%" --version
if errorlevel 1 (
    echo [ERROR] Embedded Python не запускается
    pause
    exit /b 1
)

cd /d "%CORE%"

echo.
echo =============================================
echo ЗАПУСК СЕРВЕРА - %RUNSCR%
echo =============================================
echo.

echo  ████████╗██████╗ ███████╗██╗  ██╗███████╗██████╗
echo  ╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
echo     ██║   ██████╔╝█████╗  █████╔╝ █████╗  ██████╔╝
echo     ██║   ██╔══██╗██╔══╝  ██╔═██╗ ██╔══╝  ██╔══██╗
echo     ██║   ██║  ██║███████╗██║  ██╗███████╗██║  ██║
echo     ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
echo.
echo   ███████╗ █████╗ ██████╗  █████╗  ██████╗██╗  ██╗
echo   ╚══███╔╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██║  ██║
echo     ███╔╝ ███████║██║  ██║███████║██║     ███████║
echo    ███╔╝  ██╔══██║██║  ██║██╔══██║██║     ██╔══██║
echo   ███████╗██║  ██║██████╔╝██║  ██║╚██████╗██║  ██║
echo   ╚══════╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
echo.
echo    ╔═══════════════════════════════════════════╗
echo    ║   Т  Р  Е  К  Е  Р      З  А  Д  А  Ч     ║
echo    ╚═══════════════════════════════════════════╝
echo.
echo ============================================================
echo   Порт: 5431
echo   Ctrl+C для остановки сервера
echo.

"%PY%" "%CORE%\run.py"

echo.
echo Сервер остановлен.
pause
endlocal
exit /b 0

