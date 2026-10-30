@echo off
setlocal
pushd "%~dp0"
python tools\quick_test.py %*
set "WHD_QUICK_TEST_RC=%ERRORLEVEL%"
popd
exit /b %WHD_QUICK_TEST_RC%
