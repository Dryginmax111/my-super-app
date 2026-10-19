@echo off
setlocal EnableExtensions
chcp 866 >nul
title Embedded Python + Flask + openpyxl

rem ============================================================
rem  Polnaya sborka portable embedded Python 3.13 s Flask i
rem  openpyxl v runtime\embedded\python313
rem  Zapuskat iz papki tools\
rem  Nuzhen internet
rem ============================================================

set "ROOT=%~dp0.."
set "PYDIR=%ROOT%\runtime\embedded\python313"
set "TMPDL=%TEMP%\pyembed"
set "VER=3.13.2"
set "URL=https://www.python.org/ftp/python/%VER%/python-%VER%-embed-amd64.zip"

echo.
echo [1/6] Skachivanie Python %VER% embeddable...
if not exist "%TMPDL%" mkdir "%TMPDL%"
if not exist "%TMPDL%\python-embed.zip" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%URL%' -OutFile '%TMPDL%\python-embed.zip'"
    if errorlevel 1 goto :err
)

echo [2/6] Raspakovka v %PYDIR% ...
if not exist "%PYDIR%" mkdir "%PYDIR%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%TMPDL%\python-embed.zip' -DestinationPath '%PYDIR%' -Force"
if errorlevel 1 goto :err

echo [3/6] Nastraiivaem python313._pth (site-packages)...
rem V defaultnom _pth stroka "import site" zakommentirovana (#import site).
rem Bez neye pip ne smozhet stavit pakety v Lib\site-packages.
(
echo python313.zip
echo .
echo Lib
echo Lib\site-packages
echo import site
) > "%PYDIR%\python313._pth"

if not exist "%PYDIR%\Lib\site-packages" mkdir "%PYDIR%\Lib\site-packages"

echo [4/6] Ustanovka get-pip.py ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%TMPDL%\get-pip.py'"
if errorlevel 1 goto :err
"%PYDIR%\python.exe" "%TMPDL%\get-pip.py" --no-warn-script-location
if errorlevel 1 goto :err

echo [5/6] Ustanovka Flask i openpyxl (s zavisimostyami)...
rem Polnyy nabor zavisimostey:
rem  Flask: werkzeug, jinja2, itsdangerous, click, blinker, MarkupSafe
rem  openpyxl: et-xmlfile
"%PYDIR%\python.exe" -m pip install --no-warn-script-location flask openpyxl
if errorlevel 1 goto :err

echo [6/6] Proverka sborki...
"%PYDIR%\python.exe" -c "import flask, openpyxl; print('OK  flask   =', flask.__version__); print('OK  openpyxl=', openpyxl.__version__)"
if errorlevel 1 goto :err

echo.
echo ============================================================
echo  Embedded gutov: %PYDIR%\python.exe
echo  Mohno zapuskat START.bat
echo ============================================================
pause
exit /b 0

:err
echo.
echo [ERROR] Sborka prervana. Sm. soobshchenie vyshe.
pause
exit /b 1
