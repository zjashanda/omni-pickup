@echo off
set "SKILL_ROOT=%~dp0.."
set "OMNI_PYTHON=%SKILL_ROOT%\.venv\Scripts\python.exe"
if not exist "%OMNI_PYTHON%" (
    echo ERROR: .venv is required. Run from the published Skill directory. 1>&2
    exit /b 2
)
"%OMNI_PYTHON%" -X utf8 "%SKILL_ROOT%\src\OmniPickup.py" %*
exit /b %ERRORLEVEL%
