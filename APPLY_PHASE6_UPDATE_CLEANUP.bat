@echo off
setlocal
cd /d "%~dp0"
python tools\apply_phase6_update_cleanup.py
if errorlevel 1 (
  echo UPDATE cleanup failed.
  exit /b 1
)
echo UPDATE cleanup complete.
endlocal
