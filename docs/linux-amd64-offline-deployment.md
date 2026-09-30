# Linux x86_64 (amd64) 离线部署指南

本文面向 **Linux x86_64 / amd64** 服务器的**离线生产部署**。全程不需要生产服务器访问互联网，
所有镜像和依赖在联网构建机上预先打包。当前版本 `1.2.0`。

> 如果需要从旧环境迁移数据，部署完成后参见 [生产部署、备份、恢复与迁移](production-deployment.md)。
> ARM64 部署请在 ARM 构建机上制作介质，流程相同但镜像架构不同。

## 一、前提条件

**生产服务器（离线）：**
- Linux x86_64 操作系统（已验证：Ubuntu 22.04 / Debian 12 / RHEL 9 系列）
- 已安装 Docker Engine 24+ 和 Docker Compose v2（`docker compose version` 输出 v2.x）
- 操作账户属于 `docker` 组或具有 sudo 权限
- 至少 2 核 CPU、4 GB 内存、20 GB 可用磁盘

**构建机（联网，必须同为 x86_64 架构）：**
- 已安装 Docker Engine 和 Docker Compose v2
- 能访问 Docker Hub 拉取基础镜像
- 已克隆本项目代码仓库

> 构建机和生产服务器的 CPU 架构必须一致（均为 amd64）。不要用 ARM 机器为 x86 生产环境打包，反之亦然。

## 二、在构建机制作离线部署包

以下命令在**联网的 x86_64 构建机**上，从项目根目录执行。

### 1. 拉取并校验基础镜像

```bash
# 拉取三个基础镜像（NetBox、PostgreSQL、Redis）
docker pull netboxcommunity/netbox:v4.7.0-5.1.1
docker pull postgres:18.6-alpine
docker pull redis:7.4.11-alpine
```

校验拉取的镜像 digest 与项目锁定值一致：

```bash
docker image inspect netboxcommunity/netbox:v4.7.0-5.1.1 \
  --format '{{join .RepoDigests "\n"}}'
```

应包含 `@sha256:1685e91c61bb4050089db2bb1603718820ae3ce0b266d4d069ff7c682f5d9c58`。
PostgreSQL 和 Redis 的锁定 digest 见 [locks/images.md](../locks/images.md)。

### 2. 构建生产镜像并打包

```bash
# 构建插件 wheel 和不可变生产镜像（自动检测本机架构为 amd64）
scripts/release-build

# 可选：执行完整验收（构建开发镜像并运行基线检查）
scripts/verify

# 打包离线部署包
scripts/release-package
```

生成的部署包目录：

```text
dist/offline-release-1.2.0/
├── images.tar              # 三个镜像的归档（netbox-access-relations、postgres、redis）
├── SHA256SUMS              # images.tar 的校验和
├── .env.production.example # 环境变量模板
├── compose/
│   └── production.yml      # 生产 Compose 文件
├── scripts/
│   ├── _common.sh
│   ├── production          # 启停封装（不删除数据卷）
│   ├── backup-production   # 备份脚本
│   └── restore-production  # 恢复脚本
├── docs/
│   └── production-deployment.md
└── locks/
    └── images.md
```

### 3. 传输到生产服务器

将整个 `dist/offline-release-1.2.0/` 目录原样传输到生产服务器，例如：

```bash
scp -r dist/offline-release-1.2.0 user@prod-server:/opt/
```

> 不要只复制 `images.tar`。不要把开发源码、`.env` 或真实密码传输到生产。

## 三、在生产服务器部署

以下命令在**离线生产服务器**上执行。假定部署包已放置到 `/opt/offline-release-1.2.0`。

### 1. 解压到位并校验

```bash
sudo mkdir -p /opt/netbox-access-relations
sudo cp -a /opt/offline-release-1.2.0/. /opt/netbox-access-relations/
cd /opt/netbox-access-relations

# 校验镜像归档完整性（必须全部通过）
sha256sum --check SHA256SUMS

# 导入镜像
docker load -i images.tar

# 确认三个镜像均已导入
docker image inspect netbox-access-relations:1.2.0 postgres:18.6-alpine redis:7.4.11-alpine >/dev/null \
  && echo "Images OK"
```

> 如果 `sha256sum --check` 失败或 `docker load` 报错，立即停止。不要在生产机联网拉取或换用同名镜像，应重新制作部署包。

### 2. 配置环境变量

```bash
cp .env.production.example .env.production
sudo chmod 600 .env.production
```

编辑 `.env.production`，替换所有 `REPLACE_WITH_...` 占位值。**必须修改**的关键字段：

| 变量 | 说明 | 示例 |
|---|---|---|
| `ALLOWED_HOSTS` | NetBox 访问域名或 IP | `netbox.example.com localhost 127.0.0.1` |
| `DB_NAME` | 数据库名 | `netbox` |
| `DB_USER` | 数据库用户 | `netbox` |
| `DB_PASSWORD` | 数据库密码 | 随机强密码 |
| `REDIS_PASSWORD` | Redis 队列密码 | 随机强密码 |
| `REDIS_CACHE_PASSWORD` | Redis 缓存密码 | 随机强密码 |
| `SECRET_KEY` | Django 密钥，至少 50 位 | `openssl rand -base64 60` 生成 |
| `API_TOKEN_PEPPER_1` | API token 加盐 | 随机字符串 |
| `NETBOX_PRODUCTION_IMAGE` | 应用镜像标签 | `netbox-access-relations:1.2.0` |
| `NETBOX_HTTP_PORT` | 宿主机监听端口 | `8000`（默认） |

生成随机值的命令：

```bash
openssl rand -base64 48   # 生成 64 字符随机字符串
```

> 保持 `CENSUS_REPORTING_ENABLED=false` 和 `RELEASE_CHECK_URL` 为空。`.env.production` 包含密钥，权限必须为 `0600`，不要提交到 Git。

### 3. 创建数据卷并启动

生产环境使用三个**外部 Docker 卷**，需先手动创建（生命周期独立于 Compose 项目）：

```bash
scripts/production init-volumes
```

这会创建以下卷（名称可在 `.env.production` 中覆盖）：

- `netbox-access-relations-prod-postgres18-v1` — 数据库数据
- `netbox-access-relations-prod-media-v1` — NetBox 上传附件
- `netbox-access-relations-prod-redis-v1` — Redis 持久化

启动全部服务：

```bash
scripts/production up
```

### 4. 验证服务状态

```bash
scripts/production status
```

等待 `netbox` 变为 `healthy`（首次启动约 30–60 秒，需执行数据库迁移）。确认以下五个容器均健康：

| 容器 | 作用 |
|---|---|
| `postgres` | PostgreSQL 18.6 数据库 |
| `redis` | 任务队列（RQ） |
| `redis-cache` | 缓存（tmpfs，不持久化） |
| `netbox` | Web 应用 + 自动迁移 |
| `worker` | 后台任务处理 |

查看启动日志：

```bash
scripts/production logs
```

确认迁移已完成：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T netbox \
  /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate --check
```

### 5. 访问

默认 HTTP 仅绑定 `127.0.0.1:8000`（容器内 8080）。浏览器访问：

```
http://127.0.0.1:8000
```

**生产环境强烈建议**在同一台服务器上配置 Nginx / Caddy 反向代理，终结 HTTPS 后转发到 `127.0.0.1:8000`。不要直接将容器端口暴露到公网。

## 四、日常运维命令

所有命令在部署目录 `/opt/netbox-access-relations` 下执行。`scripts/production` 是安全封装，**不会**执行 `docker compose down -v`。

```bash
# 查看状态
scripts/production status

# 查看实时日志（可加服务名：logs netbox / logs worker）
scripts/production logs

# 停止服务（保留所有数据）
scripts/production stop

# 启动服务
scripts/production up

# 审核 Compose 配置展开结果
scripts/production config
```

等价的原生 `docker compose` 命令（效果相同）：

```bash
COMPOSE="docker compose --env-file .env.production -f docker-compose.prod.yml"
$COMPOSE ps
$COMPOSE logs -f
$COMPOSE stop
$COMPOSE up -d
```

> ⚠️ **禁止**使用 `docker compose down -v`，`-v` 会删除数据库等持久化卷，导致数据丢失。
> 如需停止并移除容器（保留卷），使用 `$COMPOSE down`（不带 `-v`）。

## 五、备份与恢复

### 备份

```bash
scripts/backup-production /srv/netbox-backups
```

每个备份目录包含：
- `database.dump` — PostgreSQL custom 格式（用于恢复）
- `database.sql` — 纯文本 SQL（用于人工审阅）
- `media.tar.gz` — NetBox 上传附件
- `SHA256SUMS` — 校验和

备份目录应复制到独立存储。Redis 是缓存和队列，不备份。

### 恢复

恢复会**完整替换**当前数据库和媒体文件，只能指向隔离环境或经批准的恢复窗口：

```bash
RESTORE_CONFIRM=restore-production-v1 \
  scripts/restore-production /srv/netbox-backups/20260926T120000Z
```

> NetBox 4.7 依赖 PostgreSQL `ltree` 扩展。`scripts/restore-production` 已自动处理重建扩展。
> 手工恢复命令见 [生产部署、备份、恢复与迁移](production-deployment.md) 的“手工恢复（新环境）”一节。

## 六、升级

1. 在升级窗口前执行一次完整备份。
2. 在同架构（amd64）联网构建机上验收新版本，生成新的离线部署包。
3. 生产机校验新包、`docker load` 导入新镜像。
4. `scripts/production stop` → 修改 `.env.production` 中 `NETBOX_PRODUCTION_IMAGE` 为新标签 → `scripts/production up`。
5. 等待健康，执行 `migrate --check` 和功能验收。

如新版本含数据库迁移，须按该版本发布说明执行迁移验收，不能假定可逆。

## 七、常见问题

**Q: `docker compose` 提示找不到配置文件？**
A: 必须在部署目录内执行，且使用 `-f docker-compose.prod.yml --env-file .env.production` 指定文件。`scripts/production` 封装已自动处理。

**Q: netbox 容器一直重启，日志显示数据库连接失败？**
A: 检查 `postgres` 容器是否 healthy，`.env.production` 中 `DB_PASSWORD` 等是否与 postgres 容器初始化时一致。首次创建后修改密码不会自动生效，需重建卷。

**Q: 如何修改监听端口？**
A: 编辑 `.env.production` 中的 `NETBOX_HTTP_PORT`，然后 `scripts/production up` 重新创建容器。

**Q: 如何确认当前镜像架构？**
A: `docker image inspect netbox-access-relations:1.2.0 --format '{{.Architecture}}'` 应输出 `amd64`。
