# Production environment control on Windows (replaces scripts/production bash script)
# Usage: .\scripts\windows\production.ps1 <command> [args]
# Commands: init-volumes|config|up|stop|status|logs

. (Join-Path $PSScriptRoot 'Common.ps1')

Assert-DockerRunning

$command = if ($args.Count -gt 0) { $args[0] } else { 'help' }
$restArgs = if ($args.Count -gt 1) { $args[1..($args.Count - 1)] } else { @() }

switch ($command) {
    'init-volumes' {
        Test-ProductionEnvFile
        # Load volume names from env file
        $envFile = Get-ProductionEnvFile
        $pgVol = 'netbox-access-relations-prod-postgres18-v1'
        $mediaVol = 'netbox-access-relations-prod-media-v1'
        $redisVol = 'netbox-access-relations-prod-redis-v1'
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^POSTGRES_VOLUME_NAME=(.+)$') { $pgVol = $matches[1].Trim() }
            if ($line -match '^MEDIA_VOLUME_NAME=(.+)$') { $mediaVol = $matches[1].Trim() }
            if ($line -match '^REDIS_VOLUME_NAME=(.+)$') { $redisVol = $matches[1].Trim() }
        }
        docker volume create $pgVol | Out-Null
        docker volume create $mediaVol | Out-Null
        docker volume create $redisVol | Out-Null
        Write-Host "Created volumes: $pgVol, $mediaVol, $redisVol"
    }
    'config' {
        Invoke-ProductionCompose config @restArgs
    }
    'up' {
        Invoke-ProductionCompose up --detach @restArgs
    }
    'stop' {
        Invoke-ProductionCompose stop @restArgs
    }
    'status' {
        Invoke-ProductionCompose ps @restArgs
    }
    'logs' {
        Invoke-ProductionCompose logs --follow @restArgs
    }
    default {
        Write-Host "Usage: .\scripts\windows\production.ps1 {init-volumes|config|up|stop|status|logs}"
        Write-Host "This wrapper never removes production volumes."
    }
}
