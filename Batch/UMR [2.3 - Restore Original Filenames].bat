@echo off
setlocal enabledelayedexpansion

set "UMR_ROOT=%~dp0.."
set "PYTHON=%UMR_ROOT%\Tools\Python\python.exe"
set "SCRIPT=%UMR_ROOT%\Scripts\UltimateMediaRenamer.py"

"%PYTHON%" "%SCRIPT%" rename restore-original-batch "%~1"
exit /b 0
