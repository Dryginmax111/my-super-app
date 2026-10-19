# ============================================================
#  Альтернатива setup_embedded.bat — PowerShell-версия.
#  Использование:  powershell -ExecutionPolicy Bypass -File tools\build_embedded.ps1
#  Опционально:    -PythonVersion 3.13.2 -OutDir runtime\embedded\python313
# ============================================================
param(
    [string]$PythonVersion = "3.13.2",
    [string]$OutDir = "$PSScriptRoot\..\runtime\embedded\python313",
    [string[]]$Packages = @("flask", "openpyxl")
)

$ErrorActionPreference = "Stop"
$tmp = Join-Path $env:TEMP "pyembed"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

# 1. Скачиваем embeddable zip
$url = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$zip = Join-Path $tmp "python-embed.zip"
if (-not (Test-Path $zip)) {
    Write-Host "[1/5] Download $url"
    Invoke-WebRequest -Uri $url -OutFile $zip
}

# 2. Распаковываем
Write-Host "[2/5] Unpack -> $OutDir"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Expand-Archive -Force $zip $OutDir

# 3. Правим ._pth: раскомментируем "import site" + добавляем Lib\site-packages
$pth = Get-ChildItem $OutDir -Filter "python3*._pth" | Select-Object -First 1
$content = @(
    "python$($PythonVersion.Split('.')[0])$($PythonVersion.Split('.')[1]).zip",
    ".",
    "Lib",
    "Lib\site-packages",
    "import site"
)
Set-Content $pth.FullName ($content -join "`r`n")
New-Item -ItemType Directory -Force -Path (Join-Path $OutDir "Lib\site-packages") | Out-Null

# 4. get-pip + установка библиотек
Write-Host "[3/5] Installing pip..."
$getpip = Join-Path $tmp "get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip
& (Join-Path $OutDir "python.exe") $getpip --no-warn-script-location

Write-Host "[4/5] Installing: $($Packages -join ', ') ..."
& (Join-Path $OutDir "python.exe") -m pip install --no-warn-script-location @Packages

# 5. Проверка
Write-Host "[5/5] Verification..."
& (Join-Path $OutDir "python.exe") -c "import flask, openpyxl; print('OK flask=', flask.__version__, ' openpyxl=', openpyxl.__version__)"
Write-Host "DONE: $OutDir\python.exe"
