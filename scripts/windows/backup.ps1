# 生产数据全量备份（Windows PowerShell）。
# 用 docker cp 复制容器内生成的文件，避免 Out-File 对 pg_dump / gzip 二进制流转码而损坏备份。
# 用法：.\scripts\windows\backup.ps1 [备份根目录]

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

# 只停止原本正在运行的 Web/worker；finally 中恢复原状态，确保数据库与附件处于同一写入窗口。
$runningServices = @(Invoke-ProductionCompose ps --services --filter status=running | Where-Object { $_ -in @('netbox', 'worker') })
try {
    if ($runningServices.Count -gt 0) {
        Write-Host "Stopping application writes: $($runningServices -join ', ')"
        Invoke-ProductionCompose stop @runningServices
    }

    # docker cp 是二进制安全通道。先在容器内写临时文件，复制到宿主机后立即清理。
    $postgresId = (Invoke-ProductionCompose ps -q postgres | Select-Object -First 1).Trim()
    if (-not $postgresId) { throw 'PostgreSQL container is not running.' }
    $dumpFile = Join-Path $backupDir 'database.dump'
    $sqlFile = Join-Path $backupDir 'database.sql'
    Invoke-ProductionCompose exec -T postgres sh -ec 'pg_dump --format=custom --no-owner --no-acl --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" > /tmp/netbox-backup.dump; pg_dump --format=plain --no-owner --no-acl --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" > /tmp/netbox-backup.sql'
    & docker cp "${postgresId}:/tmp/netbox-backup.dump" $dumpFile
    if ($LASTEXITCODE -ne 0) { throw 'Failed to copy database.dump from PostgreSQL container.' }
    & docker cp "${postgresId}:/tmp/netbox-backup.sql" $sqlFile
    if ($LASTEXITCODE -ne 0) { throw 'Failed to copy database.sql from PostgreSQL container.' }
    Invoke-ProductionCompose exec -T postgres rm -f /tmp/netbox-backup.dump /tmp/netbox-backup.sql

    # 应用已停止，改用临时容器访问同一 media volume；临时容器无端口暴露，也不启动 Web 服务。
    $netboxTemp = (Invoke-ProductionCompose run --detach --no-deps --entrypoint sh netbox -c 'sleep 300' | Select-Object -Last 1).Trim()
    if (-not $netboxTemp) { throw 'Failed to create temporary NetBox backup container.' }
    try {
        $mediaFile = Join-Path $backupDir 'media.tar.gz'
        & docker exec $netboxTemp tar -C /opt/netbox/netbox/media -czf /tmp/netbox-media.tar.gz .
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create media archive.' }
        & docker cp "${netboxTemp}:/tmp/netbox-media.tar.gz" $mediaFile
        if ($LASTEXITCODE -ne 0) { throw 'Failed to copy media.tar.gz from temporary container.' }

        # 元数据只记录兼容性事实，不记录密码或 SECRET_KEY；也会被 SHA-256 覆盖。
        $metadataFile = Join-Path $backupDir 'metadata.txt'
        $metadataLines = @(
            'backup_format=netbox-access-relations-backup-v2'
            "created_utc=$timestamp"
            'postgres_service=postgres'
            'netbox_service=netbox'
            'media_path=/opt/netbox/netbox/media'
            "postgres_version=$(Invoke-ProductionCompose exec -T postgres postgres --version)"
            "netbox_version=$(& docker exec $netboxTemp /opt/netbox/venv/bin/python -c 'import netbox; print(netbox.__version__)')"
            'migration_plan:'
            (& docker exec $netboxTemp /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py showmigrations --plan)
        )
        # 显式使用无 BOM 的 UTF-8 与 LF；Bash sha256sum 可直接校验 Windows 创建的清单。
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllLines($metadataFile, [string[]]$metadataLines, $utf8NoBom)
    } finally {
        & docker rm --force $netboxTemp | Out-Null
    }

    # SHA256SUMS 与 Bash 脚本保持相同的两空格格式，恢复时可跨平台校验。
    $sums = @()
    foreach ($f in @('database.dump', 'database.sql', 'media.tar.gz', 'metadata.txt')) {
        $hash = (Get-FileHash -Algorithm SHA256 (Join-Path $backupDir $f)).Hash.ToLower()
        $sums += "$hash  $f"
    }
    $ascii = New-Object System.Text.ASCIIEncoding
    [System.IO.File]::WriteAllText((Join-Path $backupDir 'SHA256SUMS'), (($sums -join "`n") + "`n"), $ascii)
} finally {
    if ($runningServices.Count -gt 0) {
        Invoke-ProductionCompose up --detach @runningServices
    }
}

Write-Host "Backup completed: $backupDir"
Write-Host "Files: database.dump, database.sql, media.tar.gz, metadata.txt, SHA256SUMS"
