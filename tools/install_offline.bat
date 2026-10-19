@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 866 >nul
title Embedded OFFLINE: Flask + openpyxl bez pip i internet

rem ============================================================
rem  V4.1. Raspakovka .whl idet cherez fail tools\unzip_wheels.py
rem  (ranee generirovalsya cheres echo i lomalsya).
rem  Pered zapuskom: raspakuyte oficialnyj embeddable arhiv
rem  Python 3.13 v papku runtime\embedded\<kakoe-u-godno-imya>
rem  i polozhite 9 .whl v tools\wheels
rem ============================================================

set "ROOT=%~dp0.."
set "WHEELS=%~dp0wheels"
set "SCRIPT=%~dp0unzip_wheels.py"

rem --- ishchem python.exe (hodit lyuboe imya papki: python_embed-3.13.0 i t.p.) ---
set "PYEXE="
for /d %%D in ("%ROOT%\runtime\embedded\python*") do if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
if not defined PYEXE for /d %%D in ("%ROOT%\runtime\embedded\*") do if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
if not defined PYEXE goto :no_py

for %%F in ("%PYEXE%") do set "PYDIR=%%~dpF"
set "SP=%PYDIR%Lib\site-packages"

echo Nashod: python.exe = %PYEXE%
echo.

echo [1/5] Pravim *_pth (vklyuchaem import site i site-packages)...
powershell -NoProfile -Command "$f=Get-ChildItem -Path '%PYDIR%' -Filter '*._pth' | Select-Object -First 1; if($f){$c=@(Get-Content $f.FullName); if($c -notcontains 'import site'){$c=@(($c | ForEach-Object {$_ -replace '^#import site','import site'})); if($c -notcontains 'import site'){$c+=,'import site'}}; if($c -notcontains 'Lib\site-packages'){$c+=,'Lib\site-packages'}; Set-Content -Path $f.FullName -Value $c -Encoding ASCII; Write-Host '   _pth updated'}else{Write-Host '   [!] ne nayden *_pth file'}"
if not exist "%SP%" mkdir "%SP%"

echo [2/5] Raspakovka wheels cherez python zipfile (skript unzip_wheels.py)...
if not exist "%SCRIPT%" goto :no_script
"%PYEXE%" "%SCRIPT%" "%WHEELS%" "%SP%"
if errorlevel 4 goto :wrongtag
if errorlevel 3 goto :incomplete
if errorlevel 2 goto :corrupt
if errorlevel 1 goto :err

echo [3/5] Proverka, cto vse 9 paketov na meste...
set "MISSING="
for %%P in (flask werkzeug jinja2 markupsafe itsdangerous click blinker openpyxl et_xmlfile) do if not exist "%SP%\%%P\__init__.py" set "MISSING=!MISSING! %%P"
if not "!MISSING!"=="" goto :incomplete
echo   vse 9 paketov na meste

echo [4/5] Proverka importa...
"%PYEXE%" -c "import tempfile,os; import flask, openpyxl; from openpyxl import Workbook; wb=Workbook(); wb.save(os.path.join(tempfile.gettempdir(),'t.xlsx')); print('OK flask   =', flask.__version__); print('OK openpyxl=', openpyxl.__version__)"
if errorlevel 1 goto :err

echo [5/5] Gutovo. Vse proveryki proydeny. Mohno zapuskat START.bat
echo ============================================================
pause
exit /b 0

:no_py
echo [ERROR] Ne nayden python.exe v %ROOT%\runtime\embedded\
echo Raspakuyte arhiv python-3.13.x-embed-amd64.zip v papku
echo   %ROOT%\runtime\embedded\  (mozno v papku s lyubym imenem,
echo   naprimer python_embed-3.13.0 - skript naydet sam)
pause
exit /b 1

:no_script
echo [ERROR] Ne nayden %SCRIPT%
echo Kladite vsye faily iz papki tools\ vmeste: install_offline.bat + unzip_wheels.py + wheels\
pause
exit /b 1

:corrupt
echo.
echo [ERROR] Kakoy-to .whl ne chitaetsya kak zip-arhiv (povrezhden).
echo Skachajte svyezhiye .whl zanovo (spisok i ssylki: tools\wheels\README_WHEELS.txt)
pause
exit /b 1

:wrongtag
echo.
echo [ERROR] V tools\wheels est .whl, ne podkhodyashie dlya Python 3.13.
echo Sm. stroki [NE TOT PYTHON] vyshe. Nuzhny fily s metkami cp313-cp313-win_amd64
echo (dlya binarnyh paketov) ili py3-none-any. SSylki: tools\wheels\README_WHEELS.txt
pause
exit /b 1

:incomplete
echo.
echo [ERROR] Rasarkovano menshe 9 arhivov ili net paketa:!MISSING!
echo Proverte, chto v %WHEELS% lezhat vse 9 .whl:
echo   flask werkzeug jinja2 markupsafe itsdangerous click blinker openpyxl et_xmlfile
pause
exit /b 1

:err
echo.
echo [ERROR] Ustanovka prervana. Sm. soobshchenie vyshe.
pause
exit /b 1
