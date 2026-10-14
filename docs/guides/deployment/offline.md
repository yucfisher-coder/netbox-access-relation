# 严格离线源码交付、升级与恢复

本文说明离线源码交付与断网构建。已有完整运行镜像时，导入后按 [Docker 部署](docker.md)启动即可；备份与恢复统一见[关键命令](commands.md)。当前版本为 `1.3.4`；数据结构基线为迁移 `0001`～`0006`，ANY 语义迁移已在 1.3.0 引入，本版本无新增迁移。

默认离线交付方式是把**完整项目源码、公共 Docker 基础镜像和锁定的 Python wheel**打包送入目标环境，再在目标架构上完全断网构建最终生产镜像。目标环境不需要访问 Docker Hub 或 PyPI；运行时镜像不挂载源码，也不联网安装依赖。不要把 `.env`、真实密钥、数据库备份或业务工作簿放入源码交付包。

## 部署前提与边界

- 目标主机为 Linux，安装与目标 CPU 架构一致的 Docker Engine 和 Docker Compose v2；操作账户可使用 Docker。
- 生产主机不需要、也不应访问互联网。所有公共镜像和 Python 依赖在联网的受控构建机下载、锁定、校验并导入离线介质。
- 发布固定为 NetBox `4.7.2` / netbox-docker `5.1.1`、PostgreSQL `18.6-alpine`、Redis `7.4.11-alpine`。各 OCI digest 见 [`locks/images.md`](../../../locks/images.md)。
- Compose 仅把 HTTP 绑定到 `127.0.0.1:8000`；由同机反向代理终结 TLS 并转发流量。不要直接暴露 PostgreSQL 或 Redis。

## 制作离线源码交付包

在与目标生产主机 CPU 架构相同的联网构建机上，按 [`locks/images.md`](../../../locks/images.md) 拉取并校验 NetBox、Python 构建器、PostgreSQL 和 Redis 公共镜像。然后从项目根目录运行：

```bash
scripts/verify
scripts/release-source-package
```

`scripts/release-source-package` 生成 `dist/offline-source-release-1.3.4/`，包括：

- Git 已跟踪的完整项目代码、文档、测试、配置和构建脚本（不包含 `.git`、本机 `.env` 或未跟踪文件）；
- `images.tar`：NetBox、Python 构建器、PostgreSQL 与 Redis 的公共基础镜像；
- `offline-wheelhouse/`：根据生产依赖锁下载的 Python wheel，包括插件构建所需的 setuptools；
- `SHA256SUMS`：离线包内各文件的校验和。

将整个目录以只读介质转交。交接记录至少包含发布版本、Git 提交、构建时间、目标架构、`images.tar` SHA-256、基础镜像 digest、构建人与复核人。amd64 与 arm64 必须分别在匹配架构的构建机上制作，不能把一种架构的镜像包用于另一种架构。不要以 Docker 镜像 ID 代替 OCI digest；二者不是同一标识。

## 在离线生产主机安装

以下示例以 `/opt/netbox-access-relations` 为安装目录，`/mnt/release/offline-source-release-1.3.4` 为已挂载的源码交付介质。路径可调整，但 `.env.production` 权限必须为 `0600`。

```bash
sudo install -d -m 0750 /opt/netbox-access-relations
sudo cp -a /mnt/release/offline-source-release-1.3.4/. /opt/netbox-access-relations/
cd /opt/netbox-access-relations
sha256sum --check SHA256SUMS
docker load --input images.tar
scripts/build-offline-release
docker image inspect netbox-access-relations:1.3.4 postgres:18.6-alpine redis:7.4.11-alpine
sudo cp .env.production.example .env.production
sudo chmod 0600 .env.production
```

`sha256sum --check` 必须全部通过；`docker load`、`scripts/build-offline-release` 或 `docker image inspect` 失败时立即停止，不得联网拉取或换用同名镜像。离线构建脚本使用 `--network=none`，若它因缺少镜像或 wheel 失败，应重新制作完整介质，而不是在生产机补下载。该脚本会用 wheelhouse 构建插件 wheel，并把 wheel 安装到最终 NetBox 镜像中；运行镜像不包含源码挂载或 editable 安装。

编辑 `.env.production`，替换每个 `REPLACE_WITH_...` 占位值，至少确认 `ALLOWED_HOSTS` 是实际域名、
`NETBOX_HTTP_PORT` 未与本机服务冲突、`NETBOX_PRODUCTION_IMAGE=netbox-access-relations:1.3.4`，并保持
`CENSUS_REPORTING_ENABLED=false` 和空的 `RELEASE_CHECK_URL`。使用密码管理系统生成并保存 `DB_PASSWORD`、两个 Redis 密码、`SECRET_KEY` 与 `API_TOKEN_PEPPER_1`；不要把此文件复制回介质、Git 或工单。

## 首次启动与验收

```bash
cd /opt/netbox-access-relations
docker volume create netbox-access-relations-prod-postgres18-v1
docker volume create netbox-access-relations-prod-media-v1
docker volume create netbox-access-relations-prod-redis-v1
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T netbox \
  /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate --check
```

在 Compose 源文件和 `.env.production` 中复核：应用镜像是 `1.3.4`、端口仅为 `127.0.0.1`、三个 volume 均为 external。不要把 `docker compose config` 的完整输出保存到日志或工单，它可能展开密钥。确认 `netbox`、`worker`、`postgres`、`redis` 与 `redis-cache` 均健康后，经反向代理执行：登录、业务系统、访问策略、服务查询、区域矩阵四个入口；创建一个可撤销的测试对象；确认后台 worker 完成对应任务。将 `docker compose ... ps`、镜像 inspect 输出、迁移检查和人工验收结果作为本次发布证据保存。

生产卷的默认名称分别为：

- `netbox-access-relations-prod-postgres18-v1`；
- `netbox-access-relations-prod-media-v1`；
- `netbox-access-relations-prod-redis-v1`。

PostgreSQL 主版本升级必须创建新代际卷，禁止把 PostgreSQL 18 数据目录直接挂载给其他主版本。
普通停止使用 `docker compose --env-file .env.production -f docker-compose.prod.yml stop`；禁止执行 `docker compose down -v`。

## 后续版本升级

1. 在升级窗口前执行一次备份，并在隔离环境用该备份完成恢复演练。
2. 在同架构联网构建机验收新版本，运行 `scripts/release-source-package` 生成新的完整离线源码介质；不要在生产机下载镜像或依赖。
3. 在生产机校验新介质、`docker load` 导入镜像，并先以 `docker compose --env-file .env.production -f docker-compose.prod.yml config` 审核新 Compose 配置。
4. 记录当前镜像标签与 `docker image inspect` 输出，执行 `docker compose --env-file .env.production -f docker-compose.prod.yml stop`，将 `.env.production` 中的 `NETBOX_PRODUCTION_IMAGE` 改为新标签，然后执行 `docker compose --env-file .env.production -f docker-compose.prod.yml up -d`。
5. 等待服务健康，执行 `manage.py migrate --check`、登录与核心功能验收；如果新版本含迁移，须在发布说明定义并执行迁移验收，不能假定可逆。

`1.3.4` 不包含新的数据库迁移；其 schema 与 `1.3.0` 相同。升级后不可假定可直接切回 `1.2.x`。应用异常时只可切回与当前 schema 兼容的镜像；涉及数据库或 media 的回退必须使用升级前备份恢复。不得删除、重建或跨 PostgreSQL 主版本复用生产卷。

## 备份、恢复与迁移

数据库与附件的直接命令、参数及恢复验收见[关键命令](commands.md)。迁移其他 NetBox 实例前，先核对 NetBox、插件及迁移版本，并在隔离环境验证恢复。

项目也提供可选的 Bash 工具，包含暂停写入、校验和、兼容性元数据及恢复处理：

```bash
scripts/backup-production /srv/netbox-backups
# 会完整替换目标数据库与附件；先备份目标并核对兼容性。
RESTORE_CONFIRM=restore-production-v1 scripts/restore-production /srv/netbox-backups/实际备份目录
```

脚本生成的备份包含 `database.dump`、供审阅的 `database.sql`、`media.tar.gz`、`metadata.txt` 和 `SHA256SUMS`。恢复脚本默认要求 v2 元数据；与直接命令生成的备份格式不同，不应混用。脚本参数及覆盖变量见文件内注释。完整备份须复制到独立存储，配置与密钥另行加密保存。

## 回滚

应用回滚只允许切换到与当前数据库迁移兼容的旧镜像。`1.0.0` 的结构基线固定为 `0005`；若未来
版本引入迁移，必须在发布说明中单独定义向前修复或备份恢复策略，不默认反向执行迁移。数据库或
media 需要回滚时使用发布前备份恢复，而不是复用或删除错误代际的数据卷。
