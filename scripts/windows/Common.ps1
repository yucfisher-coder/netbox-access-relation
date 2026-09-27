# Common helpers for Windows Docker Desktop deployment
# Reusable across all Windows scripts.

$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}

function Get-EnvFile {
    return (Join-Path (Get-RepoRoot) '.env')
}

function Get-ProductionEnvFile {
    if ($env:PRODUCTION_ENV_FILE) { return $env:PRODUCTION_ENV_FILE }
    return (Join-Path (Get-RepoRoot) '.env.production')
}

function Test-EnvFile {
    $f = Get-EnvFile
    if (-not (Test-Path $f)) {
        throw "Missing $f; run .\scripts\windows\init-env.ps1 first."
    }
}

function Test-ProductionEnvFile {
    $f = Get-ProductionEnvFile
    if (-not (Test-Path $f)) {
        throw "Missing $f; copy .env.production.example to .env.production and inject secrets."
    }
}

function Get-DevComposeFile {
    return (Join-Path (Get-RepoRoot) 'compose\dev.yml')
}

function Get-ProductionComposeFile {
    return (Join-Path (Get-RepoRoot) 'compose\production.yml')
}

function Invoke-DevCompose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $Args)
    Test-EnvFile
    Push-Location (Get-RepoRoot)
    try {
        docker compose --env-file (Get-EnvFile) -f (Get-DevComposeFile) @Args
    } finally {
        Pop-Location
    }
}

function Invoke-ProductionCompose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $Args)
    Test-ProductionEnvFile
    $envFile = Get-ProductionEnvFile
    $env:PRODUCTION_ENV_FILE = $envFile
    Push-Location (Get-RepoRoot)
    try {
        docker compose --env-file $envFile -f (Get-ProductionComposeFile) @Args
    } finally {
        Pop-Location
    }
}

function New-RandomHex {
    param([int] $Bytes = 24)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $buffer = New-Object byte[] $Bytes
    $rng.GetBytes($buffer)
    $rng.Dispose()
    return ($buffer | ForEach-Object { $_.ToString('x2') }) -join ''
}

function Assert-DockerRunning {
    try {
        docker info *> $null
        if ($LASTEXITCODE -ne 0) { throw }
    } catch {
        throw "Docker Desktop is not running. Please start Docker Desktop and try again."
    }
}
