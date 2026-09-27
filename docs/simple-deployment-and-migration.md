# AMD64 部署与数据迁移（简版）

本文适用于在 Linux AMD64/x86_64 服务器上部署本项目。生产服务器通过 Docker Compose 直接启动；插件已经打入应用镜像，服务器不需要 Python、插件源码或 `pip install`。

> 本文使用版本 `1.0.3`。生产数据库、Redis 和媒体文件都保存在 Docker 卷中。**不要执行 `docker compose down -v`。**

## 一、准备部署包

在一台可联网的 **AMD64/x86_64 Linux 构建机**，从项目根目录执行：

```bash
docker pull netboxcommunity/netbox:v4.7.0-5.1.1
docker pull postgres:18.6-alpine
docker pull redis:7.4.11-alpine

scripts/release-build
scripts/verify
scripts/release-package
```

生成的目录为：

```text
dist/offline-release-1.0.3/
├── images.tar
├── SHA256SUMS
├── .env.production.example
├── compose/production.yml
└── scripts/
```

将整个 `offline-release-1.0.3` 目录原样复制到生产服务器。不要只复制 `images.tar`，也不要把开发目录、`plugins/` 源码、`.env` 或真实密码复制过去。

## 二、首次部署

以下示例假定部署包已复制到 `/opt/netbox-access-relations`。生产服务器需要已安装 Docker Engine 和 Docker Compose v2。

```bash
cd /opt/netbox-access-relations
sha256sum --check SHA256SUMS
docker load -i images.tar

cp .env.production.example .env.production
chmod 600 .env.production
```

编辑 `.env.production`，替换下列内容：

```text
ALLOWED_HOSTS=你的NetBox域名
DB_PASSWORD=数据库密码
REDIS_PASSWORD=Redis密码
REDIS_CACHE_PASSWORD=Redis缓存密码
SECRET_KEY=至少50位随机字符串
API_TOKEN_PEPPER_1=随机字符串
```

首次启动前创建数据卷，再以 Compose 启动：

```bash
scripts/production init-volumes

docker compose \
  --env-file .env.production \
  -f compose/production.yml \
  up -d
```

检查服务：

```bash
docker compose --env-file .env.production -f compose/production.yml ps
```

确认 `netbox`、`worker`、`postgres`、`redis`、`redis-cache` 都处于运行或健康状态后，再通过浏览器访问 NetBox。默认仅监听 `127.0.0.1:8000`；如需外部访问，应由同一服务器的 Nginx/Caddy 等反向代理提供 HTTPS。

## 三、迁移已有数据

### 从本项目旧服务器迁移

在**旧服务器**先创建备份。备份目录必须位于具有足够空间的目录中：

```bash
cd /opt/netbox-access-relations
scripts/backup-production /srv/netbox-backups
```

复制生成的时间戳目录到新服务器，例如：

```text
/srv/netbox-backups/20260926T120000Z/
├── database.dump
├── media.tar.gz
└── SHA256SUMS
```

新服务器完成“首次部署”并确认服务已经启动后，执行恢复：

```bash
cd /opt/netbox-access-relations
RESTORE_CONFIRM=restore-production-v1 \
  scripts/restore-production /srv/netbox-backups/20260926T120000Z
```

恢复会**完整替换新服务器当前的数据库和媒体文件**。恢复完成后，重新登录并检查业务系统、访问策略、服务查询、区域矩阵和附件。

> **恢复前注意 `ltree` 扩展**：NetBox 4.7 依赖 PostgreSQL 的 `ltree` 扩展。若恢复流程包含 `dropdb`/`createdb` 重建数据库（例如手工恢复），重建后 `ltree` 会丢失，需在导入数据前手动创建：
> ```bash
> docker compose --env-file .env.production -f compose/production.yml exec -T postgres \
>   psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS ltree"
> ```
> 本项目的 `scripts/restore-production` 已内置此步骤；手工恢复请参考 [手工恢复手册](manual-backup-reset-deploy.md)。

### 从其他 NetBox 环境迁移

先在隔离测试环境恢复并验证备份，再迁移生产环境。导入前必须确认：原 NetBox 版本、插件版本和数据库迁移版本与本项目兼容；不兼容时不能直接恢复数据库，应先制定升级/数据转换方案。

## 四、日常命令

```bash
# 查看状态
docker compose --env-file .env.production -f compose/production.yml ps

# 查看实时日志
docker compose --env-file .env.production -f compose/production.yml logs -f

# 正常停止（保留数据）
docker compose --env-file .env.production -f compose/production.yml stop

# 再次启动
docker compose --env-file .env.production -f compose/production.yml up -d
```

不要使用 `docker compose down -v`；`-v` 会删除数据库等持久化卷。

如需为迁移或恢复手工备份 PostgreSQL 与附件，或清空本机数据后从零验证，请使用 [迁移用的手工备份、恢复与本地重建](manual-backup-reset-deploy.md)。该手册不依赖本项目封装脚本。
