@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul

rem #1819: opt-in Windows UAT of the real WHD Tk/3D performance harness.
rem NEVER run automated tests in the user's canonical working tree.
rem A temporary detached git worktree is removed after execution.
rem Do not touch production X or invoke a repository push.
set "ROOT=%~dp0.."
pushd "%ROOT%" || (echo Cannot open WHD repository root & exit /b 1)
where git >nul 2>&1 || (echo git not installed & popd & exit /b 1)
where python >nul 2>&1 || (echo Python not on PATH & popd & exit /b 1)

set "BRANCH="
for /f "usebackq delims=" %%B in (`git branch --show-current 2^>nul`) do set "BRANCH=%%B"
if /I not "%BRANCH%"=="localX" (
    echo This UAT must be started from the Windows localX branch; found "%BRANCH%".
    popd
    exit /b 2
)

set "SHA="
for /f "usebackq delims=" %%H in (`git rev-parse HEAD 2^>nul`) do set "SHA=%%H"
if not defined SHA (echo Unable to read localX HEAD & popd & exit /b 2)

echo WHD #1819: 3-Bay and 1-Bay real GUI cycles, 30 each.
echo Source localX HEAD: %SHA%
echo This will open visible Tk test windows and use real CPU/memory.
echo It will NOT change your localX checkout or formal X.
echo Ensure you have finished other WHD sessions before starting.
choice /C YN /N /M "Run isolated Windows UAT now? [Y/N]: "
if errorlevel 2 (echo Cancelled without changes. & popd & exit /b 0)

set "TOKEN=%RANDOM%_%RANDOM%"
set "ISOLATED=%TEMP%\WHD_1819_CHECKOUT_%TOKEN%"
set "RESULTS=%USERPROFILE%\Documents\WHD_1819_UAT_%TOKEN%"
if not exist "%RESULTS%" mkdir "%RESULTS%" || (popd & exit /b 1)

git worktree add --detach "%ISOLATED%" "%SHA%" >"%RESULTS%\worktree.log" 2>&1
if errorlevel 1 (
    echo Could not create isolated worktree. See "%RESULTS%\worktree.log".
    popd
    exit /b 3
)
popd

pushd "%ISOLATED%" || (echo Could not enter isolated worktree & exit /b 4)
python -c "import psutil, tkinter, matplotlib, ezdxf, shapely" >"%RESULTS%\dependencies.log" 2>&1
if errorlevel 1 (
    echo Missing Python GUI/benchmark dependencies. See "%RESULTS%\dependencies.log".
    set "STATUS=5"
    goto :cleanup
)
(
    echo kind=WINDOWS_MANUAL_UAT_NOT_LINUX_CI
    echo head_sha=%SHA%
    echo source_branch=localX
    echo x_published=NO
    echo samples_per_bay=1
    echo cycles_per_bay=30
) > "%RESULTS%\manifest.txt"
python -V >> "%RESULTS%\manifest.txt" 2>&1

rem The harness creates its own actual GUI application in this isolated worktree.
rem It writes complete per-worker JSONL, logs and the summarized JSON report.
python tools\whd_performance_baseline.py --samples 1 --cycles 30 --memory-interval-ms 50 --output "%RESULTS%\windows-real-gui.json" >"%RESULTS%\runner.log" 2>&1
set "STATUS=%ERRORLEVEL%"

:cleanup
popd
pushd "%ROOT%" >nul 2>&1
if not errorlevel 1 (
    git worktree remove --force "%ISOLATED%" >>"%RESULTS%\worktree.log" 2>&1
    popd
)
echo.
echo UAT result code: %STATUS%
echo Real report/logs: "%RESULTS%"
if not "%STATUS%"=="0" (
    echo UAT is NOT GREEN. Inspect the last completed JSONL and runner.log.
) else (
    echo UAT measurements captured. Review RSS trend and GUI errors before approval.
)
exit /b %STATUS%
