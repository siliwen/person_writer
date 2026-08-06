$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BundledPython = "C:\Users\songw\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $VenvPython) {
    $PythonExe = $VenvPython
} elseif (Test-Path -LiteralPath $BundledPython) {
    $PythonExe = $BundledPython
} else {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
    & $PythonExe -c "import lxml, docx" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "缺少依赖。请先运行 setup.ps1，再重新启动。"
    }
}

Set-Location -LiteralPath $ProjectDir
& $PythonExe server.py --host 127.0.0.1 --port 8765
