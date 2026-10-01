# Docker 部署（默认路径）

本文是本项目面向大多数用户的部署入口：在可访问镜像仓库和 PyPI 的 Docker 主机上，构建一个包含插件的 NetBox 应用镜像，再由 Compose 启动 NetBox、PostgreSQL 和 Redis。

这不是离线部署流程。需要隔离网络、可审计源码构建或通过移动介质交付时，请使用[严格离线部署](production-deployment.md)。

## 适用范围

- Linux `amd64` / `arm64` Docker 主机适合生产使用。
- macOS 和 Windows 使用 Docker Desktop 运行 Linux 容器，适合开发、演示和评估；并非本项目验证过的生产宿主机。
- Docker Engine（或 Docker Desktop）和 Docker Compose v2 必须已安装并可用。

容器镜像会按主机架构自动选择 `linux/amd64` 或 `linux/arm64` 变体。生产发布前，仍应在同一架构的环境中完成构建与验收。

## 1. 取得代码并创建生产配置

克隆或解压本项目源码，在项目根目录创建仅供本机使用的配置文件：

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

编辑 `.env.production`，至少替换所有 `REPLACE_WITH_...` 值，并设置：

- `ALLOWED_HOSTS`：实际访问域名或 IP；
- `DB_PASSWORD`、`REDIS_PASSWORD`、`REDIS_CACHE_PASSWORD`；
- `SECRET_KEY`、`API_TOKEN_PEPPER_1`；
- `NETBOX_HTTP_PORT`：未被宿主机占用的本地端口。

保持 `CENSUS_REPORTING_ENABLED=false` 和空的 `RELEASE_CHECK_URL`。不要提交 `.env.production`。

## 2. 构建应用镜像

```bash
docker build \
  --file docker/Dockerfile.prod \
  --tag netbox-access-relations:1.3.0 \
  .
```

这个镜像以锁定的 NetBox `v4.7.0-5.1.1` 为基础，并将本插件及其运行时 Python 依赖装入镜像。构建时 Docker 会按需取得 NetBox 和 Python 构建镜像；Compose 启动时会取得锁定的 PostgreSQL 和 Redis 镜像。基础镜像 digest 见 [`locks/images.md`](../locks/images.md)。

如果使用不同的应用镜像标签，必须同步设置 `.env.production` 的 `NETBOX_PRODUCTION_IMAGE`。

## 3. 创建数据卷并启动

```bash
scripts/production init-volumes
scripts/production up
scripts/production status
```

Windows PowerShell 可直接执行对应的 `docker volume create` 和 `docker compose --env-file .env.production -f docker-compose.prod.yml up -d`；详见[Windows Docker Desktop 指南](windows-docker-desktop-deployment.md)。

首次启动时等待 `netbox` 变为 `healthy`，再确认迁移状态：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T netbox \
  /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate --check
```

默认 HTTP 仅绑定到 `127.0.0.1:8000`。生产环境应使用同机 Nginx、Caddy 或现有网关终结 TLS 并反向代理；不要直接向公网暴露数据库或 Redis。

## 日常操作

```bash
scripts/production status
scripts/production logs
scripts/production stop
scripts/production up
```

这些封装命令不会删除数据卷。不要运行 `docker compose down -v`，否则会删除数据库、附件或 Redis 持久化数据。

## 升级与备份

升级前先备份并在隔离环境演练恢复。完整的备份、恢复、迁移和严格离线交付说明见[生产部署、备份、恢复与迁移](production-deployment.md)。
