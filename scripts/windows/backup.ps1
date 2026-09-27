# Backup production data on Windows (replaces scripts/backup-production bash script)
# Usage: .\scripts\windows\backup.ps1 [backup-root-dir]

. (Join-Path $PSScriptRoot 'Common.ps1')

Assert-DockerRunning

$repoRoot = Get-RepoRoot
$backupRoot = if ($args.Count -gt 0) { $args[0] } else { Join-Path $repoRoot 'backups' }
$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$backupDir = Join-Path $backupRoot $timestamp

if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

Write-Host "Writing backup to $backupDir"

# database.dump
$dumpFile = Join-Path $backupDir 'database.dump'
Invoke-ProductionCompose exec -T postgres sh -c `
    'exec pg_dump --format=custom --no-owner --no-acl --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"' `
    | Out-File -FilePath $dumpFile -Encoding ascii

# database.sql
$sqlFile = Join-Path $backupDir 'database.sql'
Invoke-ProductionCompose exec -T postgres sh -c `
    'exec pg_dump --format=plain --no-owner --no-acl --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"' `
    | Out-File -FilePath $sqlFile -Encoding ascii

# media.tar.gz
$mediaFile = Join-Path $backupDir 'media.tar.gz'
Invoke-ProductionCompose exec -T netbox tar -C /opt/netbox/netbox/media -czf - . `
    | Out-File -FilePath $mediaFile -Encoding ascii

# SHA256SUMS
Push-Location $backupDir
try {
    $sums = @()
    foreach ($f in @('database.dump', 'database.sql', 'media.tar.gz')) {
        $hash = (Get-FileHash -Algorithm SHA256 $f).Hash.ToLower()
        $sums += "$hash  $f"
    }
    $sums | Out-File -FilePath 'SHA256SUMS' -Encoding ascii -NoNewline
} finally {
    Pop-Location
}

Write-Host "Backup completed: $backupDir"
Write-Host "Files: database.dump, database.sql, media.tar.gz, SHA256SUMS"
