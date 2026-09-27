# Development environment control on Windows (replaces scripts/dev bash script)
# Usage: .\scripts\windows\dev.ps1 <command> [args]
# Commands: up|stop|down|logs|restart-worker|shell|debug|makemigrations|migrate|status

. (Join-Path $PSScriptRoot 'Common.ps1')

Assert-DockerRunning

$command = if ($args.Count -gt 0) { $args[0] } else { 'help' }
$restArgs = if ($args.Count -gt 1) { $args[1..($args.Count - 1)] } else { @() }

switch ($command) {
    'up' {
        Invoke-DevCompose up --build --detach @restArgs
    }
    'stop' {
        Invoke-DevCompose stop @restArgs
    }
    'down' {
        Invoke-DevCompose down --remove-orphans @restArgs
    }
    'logs' {
        Invoke-DevCompose logs --follow @restArgs
    }
    'status' {
        Invoke-DevCompose ps @restArgs
    }
    'restart-worker' {
        Invoke-DevCompose restart worker
    }
    'shell' {
        Invoke-DevCompose exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py shell @restArgs
    }
    'debug' {
        Invoke-DevCompose run --rm --service-ports --entrypoint /opt/netbox/dev-entrypoint.sh netbox `
            /opt/netbox/venv/bin/python -m debugpy --listen 0.0.0.0:5678 --wait-for-client `
            /opt/netbox/netbox/manage.py runserver --noreload 0.0.0.0:8080
    }
    'makemigrations' {
        Invoke-DevCompose exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py makemigrations netbox_access_relations @restArgs
    }
    'migrate' {
        Invoke-DevCompose run --rm init /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate @restArgs
    }
    default {
        Write-Host "Usage: .\scripts\windows\dev.ps1 {up|stop|down|logs|status|restart-worker|shell|debug|makemigrations|migrate}"
        Write-Host "down preserves named volumes; this wrapper has no down -v command."
    }
}
