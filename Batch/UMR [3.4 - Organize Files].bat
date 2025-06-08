@echo off
setlocal enabledelayedexpansion

set "UMR_ROOT=%~dp0.."
set "PYTHON=%UMR_ROOT%\Tools\Python\python.exe"
set "SCRIPT=%UMR_ROOT%\Scripts\UltimateMediaRenamer.py"

"%PYTHON%" "%SCRIPT%" organize run "%~1"
exit /b 0
