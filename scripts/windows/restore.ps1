# Restore production data on Windows (replaces scripts/restore-production bash script)
# Usage: $env:RESTORE_CONFIRM='restore-production-v1'; .\scripts\windows\restore.ps1 <backup-dir>

. (Join-Path $PSScriptRoot 'Common.ps1')

Assert-DockerRunning

if (-not $env:RESTORE_CONFIRM -or $env:RESTORE_CONFIRM -ne 'restore-production-v1') {
    Write-Error "Restore replaces current database objects and media files; set `$env:RESTORE_CONFIRM='restore-production-v1' first."
    exit 2
}

if ($args.Count -lt 1) {
    Write-Error "Usage: `$env:RESTORE_CONFIRM='restore-production-v1'; .\scripts\windows\restore.ps1 <backup-dir>"
    exit 2
}

$backupDir = (Resolve-Path $args[0]).Path
foreach ($f in @('database.dump', 'media.tar.gz', 'SHA256SUMS')) {
    if (-not (Test-Path (Join-Path $backupDir $f))) {
        Write-Error "Missing $(Join-Path $backupDir $f)"
        exit 2
    }
}

# Verify checksums
Push-Location $backupDir
try {
    $lines = Get-Content SHA256SUMS
    foreach ($line in $lines) {
        if ($line -match '^([0-9a-f]+)\s+(.+)$') {
            $expected = $matches[1]
            $file = $matches[2].Trim()
            $actual = (Get-FileHash -Algorithm SHA256 $file).Hash.ToLower()
            if ($actual -ne $expected) {
                Write-Error "Checksum mismatch for $file"
                exit 2
            }
        }
    }
    Write-Host "Checksums verified."
} finally {
    Pop-Location
}

# Stop application services
Invoke-ProductionCompose stop worker netbox

# Copy dump into postgres container
$dumpPath = Join-Path $backupDir 'database.dump'
Get-Content -Path $dumpPath -Raw -Encoding Byte | Invoke-ProductionCompose exec -T postgres sh -c 'cat > /tmp/netbox-restore.dump'

# Restore database in three sections (pre-data, data, post-data with search_path fix for ltree)
$pgScript = @'
set -e
dropdb --if-exists --force --username="$POSTGRES_USER" "$POSTGRES_DB"
createdb --username="$POSTGRES_USER" "$POSTGRES_DB"
psql --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" -c "CREATE EXTENSION IF NOT EXISTS ltree"
pg_restore --exit-on-error --no-owner --no-acl --section=pre-data --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" /tmp/netbox-restore.dump
pg_restore --exit-on-error --no-owner --no-acl --section=data --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" /tmp/netbox-restore.dump
pg_restore --no-owner --no-acl --section=post-data --file=- /tmp/netbox-restore.dump \
  | sed "s/SELECT pg_catalog.set_config('search_path', '', false);/SELECT pg_catalog.set_config('search_path', 'public, pg_catalog', false);/" \
  | psql --quiet --set=ON_ERROR_STOP=1 --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"
rm /tmp/netbox-restore.dump
'@

$pgScript | Invoke-ProductionCompose exec -T postgres sh -ec 'cat > /tmp/restore.sh && sh /tmp/restore.sh && rm /tmp/restore.sh'

# Restore media
$mediaPath = Join-Path $backupDir 'media.tar.gz'
Get-Content -Path $mediaPath -Raw -Encoding Byte | Invoke-ProductionCompose run --rm --no-deps -T netbox sh -c `
    'find /opt/netbox/netbox/media -mindepth 1 -delete; tar -C /opt/netbox/netbox/media -xzf -'

# Restart application
Invoke-ProductionCompose up --detach netbox worker

Write-Host "Restore completed from $backupDir. Run the release acceptance checks now."
