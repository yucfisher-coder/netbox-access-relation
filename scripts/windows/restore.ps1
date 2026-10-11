# 生产数据全量恢复（Windows PowerShell）。会删除目标数据库和全部 media 文件。
# 用法：$env:RESTORE_CONFIRM='restore-production-v1'; .\scripts\windows\restore.ps1 <备份目录>

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
foreach ($f in @('database.dump', 'database.sql', 'media.tar.gz', 'SHA256SUMS')) {
    if (-not (Test-Path (Join-Path $backupDir $f))) {
        Write-Error "Missing $(Join-Path $backupDir $f)"
        exit 2
    }
}

# 默认拒绝没有版本与迁移基线的旧格式备份；必须由操作者显式确认后才允许。
$metadataPath = Join-Path $backupDir 'metadata.txt'
if (Test-Path $metadataPath) {
    if (-not (Select-String -Path $metadataPath -SimpleMatch 'backup_format=netbox-access-relations-backup-v2' -Quiet)) {
        Write-Error 'Unsupported backup metadata format.'
        exit 2
    }
} elseif ($env:RESTORE_ALLOW_LEGACY_BACKUP -ne '1') {
    Write-Error 'Legacy backup has no metadata.txt; set $env:RESTORE_ALLOW_LEGACY_BACKUP=''1'' only after manual compatibility review.'
    exit 2
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

# 所有校验完成后才停止应用，减少恢复失败时的业务中断窗口。
Invoke-ProductionCompose stop worker netbox

# docker cp 是二进制安全通道，不能用 PowerShell 文本管道传输 custom-format dump。
$dumpPath = Join-Path $backupDir 'database.dump'
$postgresId = (Invoke-ProductionCompose ps -q postgres | Select-Object -First 1).Trim()
if (-not $postgresId) { throw 'PostgreSQL container is not running.' }
& docker cp $dumpPath "${postgresId}:/tmp/netbox-restore.dump"
if ($LASTEXITCODE -ne 0) { throw 'Failed to copy database dump into PostgreSQL container.' }

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

# 用临时 Compose 容器挂载同一个 media volume，再以 docker cp 导入二进制 tar 包。
# 这样不会依赖 PowerShell 对原始字节流的处理方式。
$mediaPath = Join-Path $backupDir 'media.tar.gz'
$mediaContainer = (Invoke-ProductionCompose run --detach --no-deps --entrypoint sh netbox -c 'sleep 300' | Select-Object -Last 1).Trim()
if (-not $mediaContainer) { throw 'Failed to create temporary media restore container.' }
try {
    & docker cp $mediaPath "${mediaContainer}:/tmp/netbox-media.tar.gz"
    if ($LASTEXITCODE -ne 0) { throw 'Failed to copy media archive into temporary container.' }
    & docker exec $mediaContainer sh -ec 'find /opt/netbox/netbox/media -mindepth 1 -delete; tar -C /opt/netbox/netbox/media -xzf /tmp/netbox-media.tar.gz; rm /tmp/netbox-media.tar.gz'
    if ($LASTEXITCODE -ne 0) { throw 'Failed to restore media archive.' }
} finally {
    & docker rm --force $mediaContainer | Out-Null
}

# Restart application
Invoke-ProductionCompose up --detach netbox worker

Write-Host "Restore completed from $backupDir. Run the release acceptance checks now."
