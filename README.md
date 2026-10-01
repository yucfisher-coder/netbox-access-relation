# NetBox Access Relations

> 目标：NetBox Community **4.7.0** + 独立 Python 插件；宿主机编辑、Compose 开发；生产安装 wheel 后构建不可变镜像。

插件发行根就是本仓库根目录：运行时依赖仅由 [`pyproject.toml`](pyproject.toml) 声明，Django app 位于
[`netbox_access_relations/`](netbox_access_relations)。因此可在任何兼容的 NetBox Python 环境中使用
`pip install .` 构建或安装插件；Docker、Compose 与脚本仅为本项目提供的可选开发和部署环境。

## 项目状态

当前发布版本 **1.3.0**。首个生产版本 **1.0.0** 已于 2026-09-22 完成发布门禁。当前包含 `ApplicationSystem`、`SystemAlias`、
`SystemAddress`、`AccessPolicy` 和 `PolicyService` 五个业务模型，数据结构基线固定为迁移
`0001`～`0006`。核心页面、导入、服务查询和区域矩阵已经实现；ARM64 不可变镜像、离线启动、
版本化生产卷和隔离恢复演练均已通过。部署到实际生产主机前仍须注入真实密钥、域名并按目标架构重建。

版本策略：不影响数据结构的修复和常规增强进入当前次版本的补丁版本（如 `1.3.0`）；涉及仓库结构、构建体系调整，或数据库模型/约束变化时进入新的次版本。

## 文档索引

### 需求与设计
- [当前需求确认稿](docs/requirements.md)
- [系统架构与设计](docs/architecture.md)

### 开发与结构
- [代码结构说明](docs/code-structure.md)
- [本地开发指南](docs/development.md)
- [兼容性矩阵](COMPATIBILITY.md)
- [贡献指南](CONTRIBUTING.md)

### 部署
- [Docker 部署（默认路径）](docs/docker-deployment.md)
- [严格离线部署、备份、恢复与迁移](docs/production-deployment.md)
- [Windows Docker Desktop 部署指南](docs/windows-docker-desktop-deployment.md)
- [Linux x86_64 (amd64) 严格离线部署指南](docs/linux-amd64-offline-deployment.md)

### 发布
- [离线源码构建发布脚本](scripts/release-source-package)
- [变更日志](CHANGELOG.md)
- [1.3.0 发布说明](docs/releases/1.3.0.md)
- [1.2.1 发布说明](docs/releases/1.2.1.md)
- [1.1.1 发布说明](docs/releases/1.1.1.md)
- [1.1.0 发布说明](docs/releases/1.1.0.md)
- [1.0.3 发布说明](docs/releases/1.0.3.md)
- [1.0.2 发布说明](docs/releases/1.0.2.md)
- [1.0.1 发布说明](docs/releases/1.0.1.md)
- [1.0.0 发布说明](docs/releases/1.0.0.md)

## 快速开始：本地开发（Linux/macOS）

```bash
scripts/init-env
scripts/dev up
scripts/dev logs
```

浏览器访问 `http://127.0.0.1:8000`。开发环境默认不创建超级用户；首次使用时运行 `docker compose exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py createsuperuser` 创建本地管理员账号。常用入口见 `scripts/dev help`。提交或里程碑前运行 `scripts/verify`，
它构建一次镜像并执行完整基线验收。这些脚本不会执行
`docker compose down -v`。首次启动前若尚无开发镜像，先运行一次 `scripts/build`（或直接 `docker compose up -d --build`）。

Windows 请使用 `.\deploy.ps1 init-env` 后直接运行 `docker compose up -d --build`；完整说明见[Windows Docker Desktop 部署指南](docs/windows-docker-desktop-deployment.md)。平台支持边界见[兼容性矩阵](COMPATIBILITY.md)：Linux/macOS/Windows 均支持 Docker 开发；已验证的生产目标为 Linux `amd64` 与 Linux `arm64` Docker 主机。

## 快速开始：Docker 部署

大多数部署只需在可联网的 Docker 主机上构建本项目的应用镜像，再以生产 Compose 启动服务：

```bash
cp .env.production.example .env.production
# 编辑 .env.production，填入域名与真实密钥
docker build -f docker/Dockerfile.prod -t netbox-access-relations:1.3.0 .
scripts/production init-volumes
scripts/production up
```

完整步骤、平台边界和升级注意事项见 [Docker 部署（默认路径）](docs/docker-deployment.md)。只有隔离网络、合规审计或需要在目标机从源码构建时，才需要使用[严格离线部署](docs/production-deployment.md)。

## 注意事项

`.env.example` 只包含占位值。`scripts/init-env` 在本地创建被 Git 忽略且权限为 `0600` 的 `.env`，不会把运行密钥写入仓库。

## CI/CD 与发布

- **PR 门禁**：`.github/workflows/ci.yml` 在每个 PR 上并行执行 Compose 配置校验、插件 wheel 构建，以及开发镜像构建（镜像构建同时验证插件 wheel 能装入真实 NetBox 运行环境）。
- **发布**：推送 `v*` 标签（如 `v1.3.0`）触发 `.github/workflows/release.yml`，构建 wheel 与生产镜像，将镜像推送到 `ghcr.io/<owner>/<repo>/netbox-access-relations:<version>`，并创建 GitHub Release 挂载 wheel、`SHA256SUMS` 与 `IMAGE_ID`。
- **离线完整交付包**仍在受控发布机上用 `scripts/release-package` / `scripts/build-offline-release` 生成，不依赖 CI。

## 许可与支持

本项目采用 [Apache-2.0 许可证](LICENSE)。请通过 [Issues](https://github.com/yucfisher-coder/netbox-access-relation/issues) 提交缺陷和功能建议；安全问题请遵循 [安全策略](SECURITY.md)。
