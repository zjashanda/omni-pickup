@echo off
setlocal

set "SKILL_ROOT=%~dp0.."
set "OMNI_PYTHON=%SKILL_ROOT%\.venv\Scripts\python.exe"
set "OMNI_SCRIPT=%SKILL_ROOT%\src\OmniPickup.py"

if not exist "%OMNI_PYTHON%" (
    echo ERROR: .venv is required. Run this BAT from the published Skill directory. 1>&2
    exit /b 2
)
if not exist "%OMNI_SCRIPT%" (
    echo ERROR: OmniPickup.py was not found under the Skill directory. 1>&2
    exit /b 2
)

rem Wait for the ListenAI microphone, delay 5 seconds, then record continuously.
"%OMNI_PYTHON%" -X utf8 "%OMNI_SCRIPT%" ^
  --host-api wasapi ^
  --wait-device-name "麦克风 (UAC Audio)" ^
  --device-appear-delay 0 ^
  --sample-rate 16000 ^
  --channels 8 ^
  --bit-depth 16 ^
  %*
exit /b %ERRORLEVEL%
