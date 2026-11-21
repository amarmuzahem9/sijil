# Merge gate (constitution Principle VIII): every check must pass. Windows PowerShell version.
# Requires the dev stack to be running: docker compose up -d
$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..')

$steps = @(
    @{ Name = 'ruff check (api)';  Cmd = @('compose', 'exec', '-T', 'api', 'ruff', 'check', '.') },
    @{ Name = 'ruff format (api)'; Cmd = @('compose', 'exec', '-T', 'api', 'ruff', 'format', '--check', '.') },
    @{ Name = 'pytest (api)';      Cmd = @('compose', 'exec', '-T', 'api', 'pytest') },
    @{ Name = 'eslint (web)';      Cmd = @('compose', 'exec', '-T', 'web', 'npm', 'run', 'lint') },
    @{ Name = 'typecheck (web)';   Cmd = @('compose', 'exec', '-T', 'web', 'npm', 'run', 'typecheck') },
    @{ Name = 'vitest (web)';      Cmd = @('compose', 'exec', '-T', 'web', 'npm', 'test') }
)

foreach ($step in $steps) {
    Write-Host "`n=== $($step.Name) ==="
    & docker @($step.Cmd) 2>&1 | ForEach-Object { Write-Host "$_" }
    if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: $($step.Name)"; exit 1 }
}

Write-Host "`n=== Playwright e2e (isolated stack) ==="
& (Join-Path $PSScriptRoot 'e2e.ps1')
if ($LASTEXITCODE -ne 0) { Write-Host 'FAILED: e2e'; exit 1 }

Write-Host "`nAll checks passed."
