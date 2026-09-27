# 生产离线部署、升级与恢复

本文适用于 `1.0.3` 的人工离线部署。首个生产版本为 `1.0.0`，数据结构基线为迁移 `0001`～`0005`；
本版本不包含迁移。不要把开发目录、真实密钥、数据库备份或业务工作簿放入发布介质。

> 按平台的快速部署指南：[Linux x86_64 (amd64) 离线部署](linux-amd64-offline-deployment.md) ｜
> [Windows Docker Desktop 部署](windows-docker-desktop-deployment.md)。本文是覆盖备份、恢复与升级的完整手册。

## 部署前提与边界

- 目标主机为 Linux，安装与目标 CPU 架构一致的 Docker Engine 和 Docker Compose v2；操作账户可使用 Docker。
- 生产主机不需要、也不应访问互联网。所有镜像和 Python 依赖在联网的受控构建机完成验证后导入。
- 发布固定为 NetBox `4.7.0` / netbox-docker `5.1.1`、PostgreSQL `18.6-alpine`、Redis `7.4.11-alpine`。各 OCI digest 见 [`locks/images.md`](../locks/images.md)。
- Compose 仅把 HTTP 绑定到 `127.0.0.1:8000`；由同机反向代理终结 TLS 并转发流量。不要直接暴露 PostgreSQL 或 Redis。

## 在联网构建机制作并验收介质

在与生产主机相同架构的干净构建机，先导入或拉取 `locks/images.md` 所列的三种基础镜像。执行：

```bash
scripts/release-build
scripts/verify
scripts/release-package
```

最后一个命令生成已构建运行镜像的 `dist/offline-release-1.0.3/`。这适用于生产机只导入并运行镜像的场景。

若生产机必须从源码构建，改为执行：

```bash
scripts/release-source-package
```

该命令必须在与生产主机相同的 `linux/amd64` 构建机上执行；不要用 ARM64 构建机为 x86 生产环境制作镜像归档。它生成 `dist/offline-source-release-1.0.3/`，内容包括：

- 插件完整源码、离线 Dockerfile、锁定依赖与 `setuptools==80.9.0` 的 wheelhouse；
- `images.tar`：NetBox 基础镜像、Python 构建镜像、PostgreSQL 与 Redis 运行镜像；
- Compose、构建/运行/备份脚本、环境变量样例、镜像锁和本手册；
- `SHA256SUMS`：包内每一个文件的 SHA-256，供目标机导入前逐项验证。

源码包不会包含已经构建好的应用镜像；它的生产构建脚本固定使用 `docker build --network=none`，因此不会拉取镜像、下载 Python 包或访问任何网络资源。

将整个 `offline-source-release-1.0.3` 目录以只读介质转交。交接记录至少包含发布版本、Git 提交、构建时间、目标架构、`images.tar` SHA-256、基础镜像 digest、构建人与复核人。不要以应用镜像 ID 代替 OCI digest；二者不是同一标识。

## 在离线生产主机安装

以下示例以 `/opt/netbox-access-relations` 为安装目录，`/mnt/release/offline-source-release-1.0.3` 为已挂载的源码构建介质。路径可调整，但 `.env.production` 权限必须为 `0600`。

```bash
sudo install -d -m 0750 /opt/netbox-access-relations
sudo cp -a /mnt/release/offline-source-release-1.0.3/. /opt/netbox-access-relations/
cd /opt/netbox-access-relations
sha256sum --check SHA256SUMS
docker load --input images.tar
scripts/build-offline-release
docker image inspect netbox-access-relations:1.0.3 postgres:18.6-alpine redis:7.4.11-alpine
sudo cp .env.production.example .env.production
sudo chmod 0600 .env.production
```

`sha256sum --check` 必须全部通过；`docker load`、`scripts/build-offline-release` 或 `docker image inspect` 失败时立即停止，不得联网拉取或换用同名镜像。离线构建脚本使用 `--network=none`，若它因缺少镜像或 wheel 失败，应重新制作完整介质，而不是在生产机补下载。若介质由其他平台构建，也必须停止：重新在目标架构构建、验收并导出。

编辑 `.env.production`，替换每个 `REPLACE_WITH_...` 占位值，至少确认 `ALLOWED_HOSTS` 是实际域名、
`NETBOX_HTTP_PORT` 未与本机服务冲突、`NETBOX_PRODUCTION_IMAGE=netbox-access-relations:1.0.3`，并保持
`CENSUS_REPORTING_ENABLED=false` 和空的 `RELEASE_CHECK_URL`。使用密码管理系统生成并保存 `DB_PASSWORD`、两个 Redis 密码、`SECRET_KEY` 与 `API_TOKEN_PEPPER_1`；不要把此文件复制回介质、Git 或工单。

## 首次启动与验收

```bash
cd /opt/netbox-access-relations
scripts/production init-volumes
scripts/production config --quiet
scripts/production up
scripts/production status
docker compose --env-file .env.production -f compose/production.yml ps
docker compose --env-file .env.production -f compose/production.yml exec -T netbox \
  /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate --check
```

在 Compose 源文件和 `.env.production` 中复核：应用镜像是 `1.0.3`、端口仅为 `127.0.0.1`、三个 volume 均为 external。不要把 `docker compose config` 的完整输出保存到日志或工单，它可能展开密钥。确认 `netbox`、`worker`、`postgres`、`redis` 与 `redis-cache` 均健康后，经反向代理执行：登录、业务系统、访问策略、服务查询、区域矩阵四个入口；创建一个可撤销的测试对象；确认后台 worker 完成对应任务。将 `scripts/production status`、镜像 inspect 输出、迁移检查和人工验收结果作为本次发布证据保存。

生产卷的默认名称分别为：

- `netbox-access-relations-prod-postgres18-v1`；
- `netbox-access-relations-prod-media-v1`；
- `netbox-access-relations-prod-redis-v1`。

PostgreSQL 主版本升级必须创建新代际卷，禁止把 PostgreSQL 18 数据目录直接挂载给其他主版本。
普通停止使用 `scripts/production stop`；禁止执行 `docker compose down -v`。

## 后续版本升级

1. 在升级窗口前执行一次备份，并在隔离环境用该备份完成恢复演练。
2. 在同架构联网构建机验收新版本，生成新的离线介质；不要在生产机执行 `scripts/release-build`。
3. 在生产机校验新介质、`docker load` 导入镜像，并先以 `scripts/production config` 审核新 Compose 配置。
4. 记录当前镜像标签与 `docker image inspect` 输出，执行 `scripts/production stop`，将 `.env.production` 中的 `NETBOX_PRODUCTION_IMAGE` 改为新标签，然后执行 `scripts/production up`。
5. 等待服务健康，执行 `manage.py migrate --check`、登录与核心功能验收；如果新版本含迁移，须在发布说明定义并执行迁移验收，不能假定可逆。

本次 `1.0.3` 没有迁移，且与 `1.0.0` 结构基线兼容。应用异常时只可切回与当前 schema 兼容的旧镜像；涉及数据库或 media 的回退必须使用升级前备份恢复。不得删除、重建或跨 PostgreSQL 主版本复用生产卷。

## 备份

迁移与恢复保留 PostgreSQL 的 custom-format dump、供人工查看的纯文本 SQL 导出，以及 NetBox `media` 附件归档。Redis 是缓存和任务队列，不备份、不迁移。手工 `pg_dump`、media 归档、校验和、恢复以及本地从零验证命令见 [迁移用的手工备份、恢复与本地重建](manual-backup-reset-deploy.md)。备份目录必须复制到独立存储。

## 隔离恢复演练

恢复会替换目标环境的数据库对象和 media 文件，只能指向隔离的恢复环境或经批准的生产恢复窗口。
在明确核对目标 Compose 项目和备份目录后运行：

```bash
RESTORE_CONFIRM=restore-production-v1 scripts/restore-production /绝对/备份目录
```

脚本先验证校验和，再停止应用进程、强制断开并重建目标数据库、恢复数据库与 media，最后重启应用。
因此目标数据库中的现有内容会被完整替换，不会与备份对象混合。完成后必须执行登录、迁移、
对象计数、核心查询、附件访问和后台任务验收。升级发布前应先用最近生产备份完成一次隔离恢复。

NetBox 4.7.0 的层级对象使用 PostgreSQL `ltree`。该固定版本生成的 post-data dump 在空
`search_path` 下重建触发器时会命中 PostgreSQL 的 `ltree` 运算符解析问题；恢复脚本因此把备份
分为 pre-data、data、post-data 三段，并只在 post-data 会话中显式设置 `public, pg_catalog`。
该兼容处理必须随 NetBox 升级重新验证，不能静默删除。

## 回滚

应用回滚只允许切换到与当前数据库迁移兼容的旧镜像。`1.0.0` 的结构基线固定为 `0005`；若未来
版本引入迁移，必须在发布说明中单独定义向前修复或备份恢复策略，不默认反向执行迁移。数据库或
media 需要回滚时使用发布前备份恢复，而不是复用或删除错误代际的数据卷。
