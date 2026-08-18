param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ForwardArgs
)

$skillRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$omniPython = Join-Path $skillRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $omniPython)) {
    Write-Error ".venv is required. Run from the published Skill directory."
    exit 2
}

& $omniPython -X utf8 (Join-Path $skillRoot "src\OmniPickup.py") @ForwardArgs
exit $LASTEXITCODE
