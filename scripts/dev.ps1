param(
    [ValidateSet('Setup', 'Start', 'Stop', 'Reset', 'Verify')]
    [string]$Action = 'Start',
    [ValidatePattern('^[a-z0-9][a-z0-9_-]*$')]
    [string]$Project = 'camera-rental-qa-lab',
    [ValidateRange(1024, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

function New-LocalSecret {
    $bytes = New-Object byte[] 32
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($bytes) } finally { $random.Dispose() }
    return [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
}

function Invoke-Compose {
    & docker compose @composeOptions @args
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed (exit $LASTEXITCODE)." }
}

Push-Location (Join-Path $PSScriptRoot '..')
try {
    $envFile = '.env'
    if ($Action -in @('Reset', 'Verify')) {
        $suffix = [Guid]::NewGuid().ToString('N').Substring(0, 8)
        $Project = "$Project-$suffix"
        $envFile = Join-Path ([IO.Path]::GetTempPath()) "$Project.env"
    }
    if ($Action -ne 'Stop' -and -not (Test-Path -LiteralPath $envFile)) {
        $secret = New-LocalSecret
        $dbPassword = New-LocalSecret
        @("DJANGO_SECRET_KEY=$secret", "POSTGRES_PASSWORD=$dbPassword", "APP_PORT=$Port", 'DJANGO_DEBUG=0') |
            Set-Content -LiteralPath $envFile -Encoding Ascii
    }
    if ($Action -eq 'Setup') { return }
    if (-not (Test-Path -LiteralPath $envFile)) { throw 'Run Setup or supply the saved environment first.' }

    $composeOptions = @('--env-file', $envFile, '-p', $Project)
    if ($Action -eq 'Stop') {
        Invoke-Compose down
        return
    }

    if ($Action -in @('Reset', 'Verify')) {
        Write-Host "Isolated Compose project: $Project. Environment file: $envFile"
    }
    Invoke-Compose config --quiet
    Invoke-Compose up --build --wait

    if ($Action -eq 'Verify') {
        Invoke-Compose exec -T web python manage.py check
        Invoke-Compose exec -T web python manage.py makemigrations --check --dry-run
        Invoke-Compose exec -T web python manage.py test
        Invoke-Compose exec -T web python scripts/smoke.py
    }
} finally {
    Pop-Location
}
