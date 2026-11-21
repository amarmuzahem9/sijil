# Run the Playwright e2e suite against an isolated, freshly created stack (Windows PowerShell).
# The stack and its volumes are always removed afterwards.
# Note: docker writes progress to stderr; in Windows PowerShell that must not be treated as an
# error, so failures are detected through $LASTEXITCODE only.
$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..')

$dc = @('compose', '-p', 'sijil-e2e', '-f', 'docker-compose.yml', '-f', 'docker-compose.e2e.yml')

function Invoke-Docker {
    param([string[]] $DockerArgs)
    & docker @DockerArgs 2>&1 | ForEach-Object { Write-Host "$_" }
    return $LASTEXITCODE
}

function Remove-E2eStack { & docker @dc --profile e2e down -v --remove-orphans 2>&1 | Out-Null }

$exitCode = 1
try {
    Remove-E2eStack
    if ((Invoke-Docker ($dc + @('up', '-d', '--build', '--wait', 'db', 'api', 'web', 'proxy')))[-1] -ne 0) {
        Write-Host 'e2e: stack failed to start'; exit 1
    }
    if ((Invoke-Docker ($dc + @('exec', '-T', 'api', 'python', '-m', 'app.cli', 'seed-demo', '--e2e')))[-1] -ne 0) {
        Write-Host 'e2e: seed-demo failed'; exit 1
    }
    $exitCode = (Invoke-Docker ($dc + @('--profile', 'e2e', 'run', '--rm', '--build', 'e2e') + $args))[-1]
}
finally {
    Remove-E2eStack
}
exit $exitCode
