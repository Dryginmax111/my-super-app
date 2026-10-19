# ============================================================
#  Proverka gotovnosti embedded-sborki.
#  Ispolzovanie:  powershell -ExecutionPolicy Bypass -File tools\check_embedded.ps1
# ============================================================
param(
    [string]$OutDir = "$PSScriptRoot\..\runtime\embedded\python313"
)

$py = Join-Path $OutDir "python.exe"
if (-not (Test-Path $py)) { Write-Host "FAIL: net faila $py"; exit 1 }

Write-Host "Python:"; & $py --version

# ._pth dolzhen soderzhat "import site" (bez #) i Lib\site-packages
$pth = Get-ChildItem $OutDir -Filter "python3*._pth" | Select-Object -First 1
$c = Get-Content $pth.FullName
if ($c -notmatch '^\s*import site\s*$') { Write-Host "FAIL: v ._pth zakommentirovan import site"; exit 1 }
if ($c -notcontains 'Lib\site-packages') { Write-Host "WARN: v ._pth net stroki Lib\site-packages (pip mozhet stavit ne tuda)" }

& $py -c @"
import os, tempfile
import flask, openpyxl
from openpyxl import Workbook
p = os.path.join(tempfile.gettempdir(), '_check.xlsx')
wb = Workbook(); wb.active['A1'] = 'ok'; wb.save(p); os.remove(p)
print('OK flask   =', flask.__version__)
print('OK openpyxl=', openpyxl.__version__)
"@
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: imports ne prohodiat"; exit 1 }
Write-Host "ALL GOOD"
