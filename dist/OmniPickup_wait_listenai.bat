@echo off
setlocal

rem Use UTF-8 so the Chinese device name is passed to OmniPickup correctly.
chcp 65001 >nul
pushd "%~dp0"

if not exist "%~dp0OmniPickup.exe" (
    echo ERROR: OmniPickup.exe was not found in this directory. 1>&2
    popd
    exit /b 2
)

rem Wait for UAC Audio and record with the requested format.
"%~dp0OmniPickup.exe" --host-api wasapi ^
  --wait-device-name "麦克风 (UAC Audio)" ^
  --sample-rate 16000 ^
  --channels 8 ^
  --bit-depth 16 ^
  %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
