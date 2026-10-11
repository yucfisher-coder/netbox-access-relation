# 直接命令：镜像、备份与恢复

本文命令适用于 Linux Bash，在项目根目录执行，不依赖 `scripts/`。Windows PowerShell 的重定向行为不同，请使用 [Windows 指南](windows-docker-desktop.md)。

## 镜像准备与部署的边界

**镜像齐备后，部署由 Docker Compose 完成，不需要在目标机器构建镜像或安装 Python 依赖。** 目标机器仍需 Docker Compose v2、生产 Compose 文件、配置和数据卷。镜像必须匹配目标 CPU 架构；应用镜像必须包含插件，不能用原始 NetBox 镜像代替。

宿主机不需要安装 Python。源码构建由 Python 构建镜像打包 wheel，再安装到自带 Python 的 NetBox 基础镜像；联网构建自动获取这些镜像，离线源码构建须提前准备。直接部署最终应用镜像时无需单独的 Python 镜像。

- 构建机器：按 [Docker 部署指南](docker.md#2-构建应用镜像)构建应用镜像。`--file` 指定 Dockerfile，`--tag` 指定本地镜像名和版本，末尾 `.` 指定构建上下文（项目根目录）。默认构建最终的 `runtime` 阶段。
- 联网部署：应用镜像先构建或加载；PostgreSQL、Redis 可由 Compose 获取。
- 离线部署：提前准备 Compose 引用的全部镜像，通过 `docker image save --output images.tar <镜像引用…>` 导出，再在目标主机执行 `docker image load --input images.tar`。镜像引用和 digest 以 [Compose 文件](../../../docker-compose.prod.yml)为准；严格离线源码构建见 [离线指南](offline.md)。

准备 `.env.production` 和 external 数据卷后，日常启动只需：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

`--env-file` 指定 Compose 的变量来源，`-f` 指定生产编排文件，`up -d` 在后台创建或更新服务。应用容器另通过 Compose 的 `env_file` 读取配置；若换用其他配置文件，还须设置 `PRODUCTION_ENV_FILE` 指向它。当前应用服务的 `pull_policy: never` 要求应用镜像已在本机。

首次部署的数据卷创建、密钥设置、访问入口和健康检查见 [Docker 部署指南](docker.md)。若更改了卷名，应创建配置中指定的卷。已有数据卷不能当作备份。

## 定义命令简写

下面的 `dc` 是当前终端的 Bash 函数，只省略重复参数，不需要保存脚本：

```bash
dc() { docker compose --env-file .env.production -f docker-compose.prod.yml "$@"; }
dc config --quiet
```

## 备份数据库与附件

在维护窗口执行，逐条确认成功后继续；任何导出失败都不能将该目录视为有效备份。

```bash
backup_dir="$PWD/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
# 暂停应用写入，使数据库与附件处于同一维护窗口。
dc stop netbox worker
dc exec -T postgres sh -c 'exec pg_dump --format=custom --no-owner --no-acl --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"' > "$backup_dir/database.dump"
dc run --rm --no-deps -T --entrypoint tar netbox -C /opt/netbox/netbox/media -czf - . > "$backup_dir/media.tar.gz"
# 记录镜像引用及本地镜像 ID，另外记录插件版本与迁移基线。
dc config --images > "$backup_dir/images.txt"
dc images > "$backup_dir/image-ids.txt"
dc run --rm --no-deps -T --entrypoint /opt/netbox/venv/bin/python netbox /opt/netbox/netbox/manage.py showmigrations --plan > "$backup_dir/migrations.txt"
(cd "$backup_dir" && sha256sum database.dump media.tar.gz images.txt image-ids.txt migrations.txt > SHA256SUMS)
dc up -d netbox worker
```

`pg_dump --format=custom` 生成供 `pg_restore` 使用的备份；`--no-owner --no-acl` 不携带原库的对象所有者和授权。单引号使数据库名和用户名在容器内读取，不依赖宿主机导出环境变量。`exec -T` 关闭伪终端，适合文件重定向。

`run --rm --no-deps` 创建用完即删的临时容器，不启动依赖；`--entrypoint tar` 直接归档附件卷。`-C` 指定附件目录，`-czf -` 将 gzip 归档输出到标准输出，再由宿主机保存。Redis 缓存和任务队列不纳入业务备份；应先等待重要后台任务结束。

若中途失败，排查后重新备份，并按备份前的运行状态恢复服务；上述示例假设 `netbox` 和 `worker` 原本都在运行。将完整目录复制到独立存储；生产配置和密钥另行加密保管，恢复时需要原有密钥。

## 恢复数据库与附件

**以下命令删除目标业务库和现有附件。** 先备份目标环境，在隔离环境演练；核对备份镜像、插件版本和迁移记录，优先使用原版本恢复，再按升级流程迁移。不要把新版数据库恢复给旧版应用。以下备份目录为上节直接命令生成的格式，与封装脚本要求的元数据格式不同。

先设置真实备份路径并检查文件；校验失败立即停止：

```bash
backup_dir=/absolute/path/to/backup
(cd "$backup_dir" && sha256sum --check SHA256SUMS)
dc config --quiet
dc up -d postgres redis redis-cache media-init
dc exec -T postgres sh -c 'pg_isready -q -d "$POSTGRES_DB" -U "$POSTGRES_USER"'
```

等待数据库就绪后停止应用并导入。恢复命令失败时保持应用停止，排查后重试：

```bash
dc stop netbox worker
dc exec -T postgres sh -c 'cat > /tmp/netbox-restore.dump' < "$backup_dir/database.dump"
dc exec -T postgres sh -ec '
  dropdb --if-exists --force --username="$POSTGRES_USER" "$POSTGRES_DB"
  createdb --username="$POSTGRES_USER" "$POSTGRES_DB"
  psql --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" -c "CREATE EXTENSION IF NOT EXISTS ltree"
  pg_restore --exit-on-error --no-owner --no-acl --section=pre-data --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" /tmp/netbox-restore.dump
  pg_restore --exit-on-error --no-owner --no-acl --section=data --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" /tmp/netbox-restore.dump
  pg_restore --no-owner --no-acl --section=post-data --file=- /tmp/netbox-restore.dump \
    | sed "s/SELECT pg_catalog.set_config('\''search_path'\'', '\'''\'', false);/SELECT pg_catalog.set_config('\''search_path'\'', '\''public, pg_catalog'\'', false);/" \
    | psql --quiet --set=ON_ERROR_STOP=1 --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"
  rm /tmp/netbox-restore.dump
'
```

`dropdb --force` 断开目标库连接并删除库；`createdb` 创建空库。分三段恢复结构、数据和约束，并修正最后阶段的 `search_path`，沿用本项目对 NetBox `ltree` 触发器的兼容处理。`--exit-on-error` 和 `ON_ERROR_STOP=1` 使恢复遇错停止。

数据库恢复成功后替换附件；确认目标卷正确再执行：

```bash
dc run --rm --no-deps -T --user 0:0 --entrypoint sh netbox -ec 'find /opt/netbox/netbox/media -mindepth 1 -delete; tar -C /opt/netbox/netbox/media -xzf -; chown -R 999:0 /opt/netbox/netbox/media; chmod 0775 /opt/netbox/netbox/media' < "$backup_dir/media.tar.gz"
dc up -d netbox worker
dc ps
dc exec -T netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate --check
```

附件以 root 恢复后按 Compose 的 `media-init` 规则设置权限。启动后等待 `netbox` 为 `healthy`，检查登录、插件数据、附件访问和后台作业。备份不包含待执行的 Redis 任务；恢复到已有环境时需单独核对残留队列，避免旧任务修改恢复后的数据。

现有 `scripts/backup-production`、`scripts/restore-production` 仍可选用，它们增加了元数据、校验及部分错误处理；直接命令由操作者负责逐步检查与恢复服务。
