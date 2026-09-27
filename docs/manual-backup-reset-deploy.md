# 迁移用的手工备份、恢复与本地重建

本项目沿用 NetBox Docker 的迁移原则：只备份两项不可替代的数据。

1. PostgreSQL custom-format dump，用于可靠恢复；
2. PostgreSQL 纯文本 SQL，用于直接查看或审阅数据；
3. NetBox `media` 目录（上传的附件）。

Redis 是缓存和任务队列，不迁移也不恢复；镜像、Compose 文件和 `.env.production` 是部署配置，应当从经过验证的发布介质或版本控制中重新取得，而不是塞进数据备份。本手册不依赖项目包装脚本。

这与 NetBox 官方的[复制 NetBox 实例说明](https://netbox.readthedocs.io/en/stable/administration/replicating-netbox/)一致：导出 PostgreSQL，再复制 media 文件。

以下命令在项目（或离线发布包）根目录执行，并假定 `.env.production` 已配置。示例把备份放在项目的 `backups/20260926` 目录；它被 Git 忽略，但迁移前仍须把整个目录复制到另一台机器或独立磁盘。

## 备份

```bash
mkdir -p backups/20260926
```

暂停 NetBox Web 和 worker，避免导出数据库与归档附件期间有新的写入；数据库服务保持运行：

```bash
docker compose --env-file .env.production -f compose/production.yml stop netbox worker
```

连续导出数据库的两种格式，再归档 `media` 卷。`database.dump` 用于恢复；`database.sql` 是可直接用文本编辑器或 `less` 查看的 SQL 文件。

```bash
docker compose --env-file .env.production -f compose/production.yml exec -T postgres sh -c \
  'exec pg_dump --format=custom --no-owner --no-acl --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"' \
  > backups/20260926/database.dump

docker compose --env-file .env.production -f compose/production.yml exec -T postgres sh -c \
  'exec pg_dump --format=plain --no-owner --no-acl --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"' \
  > backups/20260926/database.sql

docker compose --env-file .env.production -f compose/production.yml run --rm --no-deps --entrypoint tar netbox \
  -C /opt/netbox/netbox/media -czf - . \
  > backups/20260926/media.tar.gz
```

上面命令中的 `$POSTGRES_DB` 和 `$POSTGRES_USER` 不需要你填写；它们是 PostgreSQL 容器从 `.env.production` 自动读取的数据库名称和用户。

生成并检查校验和，然后将这个时间戳目录复制到独立存储：

```bash
(cd backups/20260926 && shasum -a 256 database.dump database.sql media.tar.gz > SHA256SUMS)
(cd backups/20260926 && shasum -a 256 -c SHA256SUMS)
ls -lh backups/20260926
docker compose --env-file .env.production -f compose/production.yml up -d
```

一个可用于迁移的备份目录只有以下三个文件：

```text
20260926T120000Z/
├── database.dump
├── database.sql
├── media.tar.gz
└── SHA256SUMS
```

## 在新环境恢复

先使用相同（或已验证兼容）的 NetBox 与 PostgreSQL 版本，在目标主机部署并启动一个空实例。确认 `.env.production` 的密码和 `SECRET_KEY` 已设置、`postgres` 已健康，然后复制备份目录到目标主机。恢复会替换目标环境中现有的数据库与附件。

```bash
(cd backups/20260926 && shasum -a 256 -c SHA256SUMS)
docker compose --env-file .env.production -f compose/production.yml stop netbox worker
docker compose --env-file .env.production -f compose/production.yml cp backups/20260926/database.dump postgres:/tmp/netbox-restore.dump
```

重建数据库并恢复 dump。重建库后 `ltree` 扩展会随 `dropdb` 一起丢失，**必须在导入前手动建好**（虽然 SQL 脚本里通常自带 `CREATE EXTENSION`，但提前创建可避免任何意外，例如 `pg_restore` 分阶段恢复或 `search_path` 调整导致扩展未生效）。最后一段为 NetBox 4.7.0 的 `ltree` 触发器保留正确的 `search_path`：

```bash
docker compose --env-file .env.production -f compose/production.yml exec -T postgres sh -ec '
  dropdb --if-exists --force --username="$POSTGRES_USER" "$POSTGRES_DB"
  createdb --username="$POSTGRES_USER" "$POSTGRES_DB"
  psql --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" -c "CREATE EXTENSION IF NOT EXISTS ltree"
  pg_restore --exit-on-error --no-owner --no-acl --section=pre-data --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" /tmp/netbox-restore.dump
  pg_restore --exit-on-error --no-owner --no-acl --section=data --dbname="$POSTGRES_DB" --username="$POSTGRES_USER" /tmp/netbox-restore.dump
  pg_restore --no-owner --no-acl --section=post-data --file=- /tmp/netbox-restore.dump \
    | sed "s/SELECT pg_catalog.set_config('\\''search_path'\\'', '\\'''\\'', false);/SELECT pg_catalog.set_config('\\''search_path'\\'', '\\''public, pg_catalog'\\'', false);/" \
    | psql --quiet --set=ON_ERROR_STOP=1 --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"
  rm /tmp/netbox-restore.dump
'
```

清空目标的 `media` 内容并解压备份，最后重新启动应用：

```bash
docker compose --env-file .env.production -f compose/production.yml run --rm --no-deps -T netbox sh -c \
  'find /opt/netbox/netbox/media -mindepth 1 -delete; tar -C /opt/netbox/netbox/media -xzf -' \
  < backups/20260926/media.tar.gz

docker compose --env-file .env.production -f compose/production.yml up -d
docker compose --env-file .env.production -f compose/production.yml exec -T netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate --check
docker compose --env-file .env.production -f compose/production.yml ps
```

恢复后通过浏览器检查关键对象、附件下载与后台任务。数据库 dump 能导入、文件能解压，只代表恢复步骤完成；不代表业务验收完成。

若只需人工核对数据，可以直接查看纯文本导出，不必恢复：

```bash
less backups/20260926/database.sql
```

## 本机从零验证

若目的是验证空数据部署，而非恢复迁移数据，完成备份后只需停止栈、删除这套 Compose 明确引用的 external volumes，再重新创建并启动。以下是本项目的默认卷名；若你在 `.env.production` 改过卷名，请把三处名称替换为实际名称。

```bash
docker volume inspect \
  netbox-access-relations-prod-postgres18-v1 \
  netbox-access-relations-prod-media-v1 \
  netbox-access-relations-prod-redis-v1
docker compose --env-file .env.production -f compose/production.yml down --remove-orphans
docker volume rm netbox-access-relations-prod-postgres18-v1 netbox-access-relations-prod-media-v1 netbox-access-relations-prod-redis-v1
docker volume create netbox-access-relations-prod-postgres18-v1
docker volume create netbox-access-relations-prod-media-v1
docker volume create netbox-access-relations-prod-redis-v1
docker compose --env-file .env.production -f compose/production.yml up -d
```

不要使用 `docker compose down -v` 或 `docker volume prune`：两者不如指定这三个卷名清晰。之后运行 `docker compose --env-file .env.production -f compose/production.yml ps` 和上述 `migrate --check`，并登录验证即可。
