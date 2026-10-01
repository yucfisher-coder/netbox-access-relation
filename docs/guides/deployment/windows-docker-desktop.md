# Windows Docker Desktop 部署指南

本文介绍如何在 **Windows + Docker Desktop** 环境下开发、评估或运行本项目（NetBox 访问关系插件 v1.3.0）。普通 Docker 部署先阅读[Docker 部署（默认路径）](docker.md)；本页保留 Windows 特有命令和边界说明。
项目根目录已提供标准的 `docker-compose.yml`（开发）和 `docker-compose.prod.yml`（生产），直接用 `docker compose` 命令即可运行，无需安装 Git Bash、WSL 或额外脚本。

> Windows Docker Desktop 是受支持的开发与评估环境；发布验证的生产目标是 Linux `amd64` 和 Linux `arm64` Docker 主机。Windows 主机运行的是 Docker 的 Linux 容器，不是原生 Windows NetBox 服务。

## 架构兼容性（arm64 / amd64）

本项目同时兼容 **linux/amd64** 和 **linux/arm64** 的 Docker 环境（含 Apple Silicon、ARM 服务器、x86 服务器），无需为不同架构修改配置：

- 所有基础镜像（NetBox、PostgreSQL、Redis、Python）在 `docker-compose.yml`、`docker-compose.prod.yml` 和 `docker/Dockerfile.*` 中均引用 **OCI 多架构清单（index digest）**，Docker 会自动拉取与本机 CPU 架构匹配的变体，无需手动指定 `platform`。
- 镜像与锁定 digest 见 [locks/images.md](../../../locks/images.md)，其中列出了每个镜像的 amd64 与 arm64 变体。
- 开发镜像、生产镜像在两种架构上均按本机原生构建：在 x86 机器上 `docker compose build` 得到 amd64 镜像，在 ARM 机器上得到 arm64 镜像。
- 生产离线部署需在**与目标主机相同架构**的机器上构建镜像归档（不要用 ARM 机为 x86 生产环境制作镜像，反之亦然）。
- 本项目不强制指定 `platform`，因此在 Docker Desktop（含 WSL2 后端）上默认为本机架构运行。

## 一、前置条件

1. **安装 Docker Desktop for Windows**
   - 下载地址：https://www.docker.com/products/docker-desktop/
   - 安装时启用 WSL 2 后端（推荐）或 Hyper-V 后端
   - 安装完成后启动 Docker Desktop，等待系统托盘图标变为稳定状态

2. **确认 Docker 可用**
   打开 PowerShell，执行：
   ```powershell
   docker --version
   docker compose version
   ```
   应输出 Docker 27+ 和 Compose v2+ 的版本号。

3. **（可选）PowerShell 执行策略**
   若运行 `.ps1` 脚本时报"禁止运行脚本"错误，以管理员身份执行一次：
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```
   `RemoteSigned` 允许本地脚本运行；从互联网下载并带有来源标记的脚本需要受信任签名或先按组织安全策略解除来源标记。

## 二、开发环境快速部署（推荐）

在项目根目录 `f:\netbox-access-relation` 打开 PowerShell。根目录的 `docker-compose.yml` 会被 `docker compose` 自动识别，`.env` 也会被自动加载。

```powershell
# 0.（首次）创建 .env 配置文件并填入密钥
Copy-Item .env.example .env

# 1. 拉取并构建（首次或代码变更后）
docker compose build

# 2. 启动全部服务（后台运行）
docker compose up -d

# 3. 查看容器状态（等待 netbox 变为 healthy）
docker compose ps

# 4. 查看实时日志
docker compose logs -f
```

启动成功后，浏览器访问 **http://localhost:8000** 即可打开 NetBox。

> 以上就是标准 Docker 用法，`docker compose` 自动读取当前目录的 `docker-compose.yml` 和 `.env`。

### 开发环境常用命令

| 操作 | docker compose 命令 | 说明 |
|------|--------------------|------|
| 构建并启动 | `docker compose up -d --build` | 构建镜像并后台启动 |
| 停止 | `docker compose stop` | 停止容器，保留数据 |
| 移除容器 | `docker compose down` | 删除容器，**保留**数据卷 |
| 状态 | `docker compose ps` | 查看容器运行状态 |
| 日志 | `docker compose logs -f [服务名]` | 跟随日志，可指定服务 |
| 重启某服务 | `docker compose restart worker` | 例如重启 worker |
| 进入 shell | `docker compose exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py shell` | Django shell |
| 查看配置 | `docker compose config` | 查看变量展开后的完整配置 |

**注意**：不要使用 `docker compose down -v`，`-v` 会删除数据库等持久化卷。

## 三、生产环境部署

生产环境使用预构建镜像（`netbox-access-relations:1.3.0`），数据保存在 Docker 外部卷中。

### 1. 准备镜像

在联网机器上构建生产镜像（需先完成开发环境构建验证）：
```powershell
# 拉取基础镜像并构建生产镜像
docker pull netboxcommunity/netbox:v4.7.0-5.1.1
docker pull postgres:18.6-alpine
docker pull redis:7.4.11-alpine
docker build -f docker/Dockerfile.prod -t netbox-access-relations:1.3.0 .
```

### 2. 配置环境变量

```powershell
Copy-Item .env.production.example .env.production
notepad .env.production
```

编辑 `.env.production`，替换所有 `REPLACE_WITH_...` 占位值：
- `ALLOWED_HOSTS`：改为实际访问域名（如 `netbox.example.internal localhost 127.0.0.1`）
- `DB_PASSWORD`、`REDIS_PASSWORD`、`REDIS_CACHE_PASSWORD`：随机强密码
- `SECRET_KEY`、`API_TOKEN_PEPPER_1`：至少 50 位随机字符串

> 可在 PowerShell 中用以下命令生成随机值：
> ```powershell
> -join ((1..48) | ForEach-Object { '{0:x2}' -f (Get-Random -Max 256) })
> ```

### 3. 启动生产环境

生产 compose 文件是 `docker-compose.prod.yml`，使用 `.env.production`（需用 `--env-file` 显式指定，因为默认只自动加载 `.env`）。它的数据卷是 external，需先创建：

```powershell
# 创建外部数据卷（名称需与 .env.production 中 POSTGRES_VOLUME_NAME 等一致）
docker volume create netbox-access-relations-prod-postgres18-v1
docker volume create netbox-access-relations-prod-media-v1
docker volume create netbox-access-relations-prod-redis-v1

# 启动生产栈
docker compose --env-file .env.production -f docker-compose.prod.yml up -d

# 查看状态
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

默认仅监听 `127.0.0.1:8000`，建议在同一台机器上配置 Nginx/Caddy 反向代理并终结 HTTPS。

### 生产环境常用命令

把下面的 `COMPOSE_PROD` 看作固定前缀：`docker compose --env-file .env.production -f docker-compose.prod.yml`

| 操作 | 命令 | 说明 |
|------|------|------|
| 启动 | `docker compose --env-file .env.production -f docker-compose.prod.yml up -d` | 启动生产栈 |
| 停止 | `... stop` | 停止，保留数据 |
| 状态 | `... ps` | 查看容器状态 |
| 日志 | `... logs -f [服务名]` | 跟随日志 |
| 配置 | `... config` | 查看展开后的配置 |

## 四、备份与恢复

### 备份

```powershell
 # 备份到指定目录
.\scripts\windows\backup.ps1 D:\netbox-backups
```

每个备份目录包含：
- `database.dump`：PostgreSQL custom 格式（用于恢复）
- `database.sql`：纯文本 SQL（用于人工审阅）
- `media.tar.gz`：NetBox 上传附件
- `SHA256SUMS`：校验和

### 恢复

恢复会**完整替换**当前数据库和媒体文件，请确认目标环境正确：

```powershell
$env:RESTORE_CONFIRM = 'restore-production-v1'
.\scripts\windows\restore.ps1 D:\netbox-backups\20260926T120000Z
```

## 五、Docker Compose 命令

在项目根目录执行：

```powershell
# 开发环境
docker compose --env-file .env -f docker-compose.yml up -d
docker compose --env-file .env -f docker-compose.yml ps
docker compose --env-file .env -f docker-compose.yml logs -f

# 生产环境
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

## 六、Windows 特有注意事项

1. **Docker Desktop 必须先启动**
   脚本会检测 Docker 守护进程，未启动时报错提示。请先在开始菜单启动 Docker Desktop。

2. **文件路径**
   Compose 文件中的相对路径（如 `./netbox_access_relations`）在 Windows Docker Desktop 下可正常工作，
   Docker Desktop 会自动处理路径转换。无需修改为 Windows 路径格式。

3. **端口占用**
   默认 HTTP 端口为 `8000`。若被占用，编辑 `.env` 中的 `NETBOX_HTTP_PORT`。

4. **镜像拉取加速**
   若基础镜像拉取缓慢，可在 Docker Desktop → Settings → Docker Engine 中配置
   国内镜像源，或使用代理：
   ```powershell
   $env:HTTP_PROXY = 'http://127.0.0.1:7890'
   $env:HTTPS_PROXY = 'http://127.0.0.1:7890'
   docker compose up -d
   ```

## 七、平台一致性

开发与生产各只有一份 Compose 配置（根目录的 `docker-compose.yml` 与 `docker-compose.prod.yml`）。Linux、macOS 与 Windows Docker Desktop 都使用标准 `docker compose` 命令。
