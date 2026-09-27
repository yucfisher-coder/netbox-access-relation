# Optional helper script - internally just calls standard docker compose commands.
# You do NOT need this script; you can run docker compose directly in the project root:
#
#   docker compose up -d                                            # dev environment
#   docker compose ps                                               # status
#   docker compose logs -f                                          # logs
#   docker compose down                                             # stop (keeps volumes)
#   docker compose --env-file .env.production -f docker-compose.prod.yml up -d   # production
#
# Script usage (optional):
#   .\deploy.ps1 init-env     generate .env with random secrets
#   .\deploy.ps1 dev up       same as: docker compose up -d --build
#   .\deploy.ps1 dev ps
#   .\deploy.ps1 dev logs
#   .\deploy.ps1 prod up      same as: docker compose --env-file .env.production -f docker-compose.prod.yml up -d
#   .\deploy.ps1 prod ps

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\windows\Common.ps1')

$REPO     = Get-RepoRoot
$ENV_FILE = Get-EnvFile
$PROD_ENV = Get-ProductionEnvFile

function Run-InRepo([string] $Preview, [scriptblock] $Block) {
    Assert-DockerRunning
    Write-Host ''
    Write-Host (">> " + $Preview) -ForegroundColor Cyan
    Push-Location $REPO
    try { & $Block } finally { Pop-Location }
}

$group = if ($args.Count -gt 0) { $args[0].ToLower() } else { 'help' }
$rest  = if ($args.Count -gt 1) { $args[1..($args.Count - 1)] } else { @() }

switch ($group) {
    'dev' {
        $sub = if ($rest.Count -gt 0) { $rest[0].ToLower() } else { 'ps' }
        $subArgs = if ($rest.Count -gt 1) { $rest[1..($rest.Count - 1)] } else { @() }
        if (-not (Test-Path $ENV_FILE)) { throw "Missing $ENV_FILE; run .\deploy.ps1 init-env first." }
        switch ($sub) {
            'up'   { Run-InRepo "docker compose up --build -d $($subArgs -join ' ')" { docker compose up --build --detach @subArgs } }
            'stop' { Run-InRepo "docker compose stop $($subArgs -join ' ')" { docker compose stop @subArgs } }
            'down' { Run-InRepo "docker compose down --remove-orphans $($subArgs -join ' ')" { docker compose down --remove-orphans @subArgs } }
            'ps'   { Run-InRepo "docker compose ps $($subArgs -join ' ')" { docker compose ps @subArgs } }
            'logs' { Run-InRepo "docker compose logs -f $($subArgs -join ' ')" { docker compose logs --follow @subArgs } }
            default { Write-Host 'dev subcommands: up stop down ps logs' }
        }
    }

    'prod' {
        $sub = if ($rest.Count -gt 0) { $rest[0].ToLower() } else { 'ps' }
        $subArgs = if ($rest.Count -gt 1) { $rest[1..($rest.Count - 1)] } else { @() }
        if (-not (Test-Path $PROD_ENV)) { throw "Missing $PROD_ENV; copy .env.production.example first." }
        switch ($sub) {
            'up' {
                Run-InRepo "docker compose --env-file .env.production -f docker-compose.prod.yml up -d $($subArgs -join ' ')" {
                    docker compose --env-file $PROD_ENV -f docker-compose.prod.yml up --detach @subArgs
                }
            }
            'stop' { Run-InRepo "docker compose --env-file .env.production -f docker-compose.prod.yml stop" { docker compose --env-file $PROD_ENV -f docker-compose.prod.yml stop @subArgs } }
            'ps'   { Run-InRepo "docker compose --env-file .env.production -f docker-compose.prod.yml ps" { docker compose --env-file $PROD_ENV -f docker-compose.prod.yml ps @subArgs } }
            'logs' { Run-InRepo "docker compose --env-file .env.production -f docker-compose.prod.yml logs -f" { docker compose --env-file $PROD_ENV -f docker-compose.prod.yml logs --follow @subArgs } }
            default { Write-Host 'prod subcommands: up stop ps logs' }
        }
    }

    'init-env' {
        if (Test-Path $ENV_FILE) { Write-Error ".env already exists; refusing to overwrite."; exit 1 }
        $lines = @(
            'NETBOX_HTTP_PORT=8000',
            'ALLOWED_HOSTS=localhost 127.0.0.1',
            'DB_NAME=netbox',
            'DB_USER=netbox',
            "DB_PASSWORD=$(New-RandomHex 24)",
            "REDIS_PASSWORD=$(New-RandomHex 24)",
            "REDIS_CACHE_PASSWORD=$(New-RandomHex 24)",
            "SECRET_KEY=$(New-RandomHex 48)",
            "API_TOKEN_PEPPER_1=$(New-RandomHex 48)",
            'SKIP_SUPERUSER=true',
            'CENSUS_REPORTING_ENABLED=false',
            'RELEASE_CHECK_URL='
        )
        [System.IO.File]::WriteAllLines($ENV_FILE, $lines)
        Write-Host "Created $ENV_FILE with random secrets." -ForegroundColor Green
    }

    'build'   { & (Join-Path $PSScriptRoot 'scripts\windows\build.ps1') }
    'backup'  { & (Join-Path $PSScriptRoot 'scripts\windows\backup.ps1') @rest }
    'restore' { & (Join-Path $PSScriptRoot 'scripts\windows\restore.ps1') @rest }

    default {
        Write-Host ''
        Write-Host 'Use docker compose directly (recommended) - no script needed:'
        Write-Host '  docker compose up -d                              dev environment'
        Write-Host '  docker compose ps / logs -f / down'
        Write-Host '  docker compose --env-file .env.production -f docker-compose.prod.yml up -d   production'
        Write-Host ''
        Write-Host 'This script is only a convenience wrapper:'
        Write-Host '  .\deploy.ps1 init-env | build | dev [up stop down ps logs] | prod [up stop ps logs] | backup | restore'
    }
}
