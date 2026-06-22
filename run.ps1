$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $key, $value = $line.Split("=", 2)
        $key = $key.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        if ($key -and -not [Environment]::GetEnvironmentVariable($key, "Process")) {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

$python = "C:\Users\annet\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path (Join-Path $PSScriptRoot ".opcuator-venv\Scripts\python.exe")) {
    $python = Join-Path $PSScriptRoot ".opcuator-venv\Scripts\python.exe"
} elseif (Test-Path (Join-Path $PSScriptRoot ".venv\Scripts\python.exe")) {
    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
} elseif (-not (Test-Path $python)) {
    $python = "python"
}

$hostValue = if ($env:REST_HOST) { $env:REST_HOST } else { "0.0.0.0" }
$portValue = if ($env:REST_PORT) { $env:REST_PORT } else { "9500" }

$env:PYTHONPATH = Join-Path $PSScriptRoot "src"
& $python -m uvicorn opcuator.main:app --host $hostValue --port $portValue
} finally {
    Pop-Location
}
