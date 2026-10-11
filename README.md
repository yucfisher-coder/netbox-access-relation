# NetBox Access Relations

> 目标：NetBox Community **4.7.2** + 独立 Python 插件；宿主机编辑、Compose 开发；生产安装 wheel 后构建不可变镜像。

插件发行根就是本仓库根目录：运行时依赖仅由 [`pyproject.toml`](pyproject.toml) 声明，Django app 位于
[`netbox_access_relations/`](netbox_access_relations)。因此可在任何兼容的 NetBox Python 环境中使用
`pip install .` 构建或安装插件；Docker、Compose 与脚本仅为本项目提供的可选开发和部署环境。

## 项目状态

当前发布版本 **1.3.2**。首个生产版本 **1.0.0** 已于 2026-09-22 完成发布门禁。当前包含 `ApplicationSystem`、`SystemAlias`、
`SystemAddress`、`AccessPolicy` 和 `PolicyService` 五个业务模型，数据结构基线固定为迁移
`0001`～`0006`。核心页面、导入、服务查询和区域矩阵已经实现；ARM64 不可变镜像、离线启动、
版本化生产卷和隔离恢复演练均已通过。部署到实际生产主机前须配置真实密钥、域名，并准备匹配目标架构的镜像。

版本策略：不影响数据结构的修复和常规增强进入当前次版本的补丁版本（如 `1.3.2`）；涉及仓库结构、构建体系调整，或数据库模型/约束变化时进入新的次版本。

## 文档索引

### 需求与设计
- [当前需求确认稿](docs/requirements/README.md)
- [系统架构与设计](docs/explanation/architecture.md)

### 开发与结构
- [代码结构说明](docs/reference/repository-structure.md)
- [本地开发指南](docs/guides/development.md)
- [兼容性矩阵](COMPATIBILITY.md)
- [贡献指南](CONTRIBUTING.md)
- [文档规范](docs/standards/documentation.md)

### 部署
- [Docker 部署（默认路径）](docs/guides/deployment/docker.md)
- [关键命令：镜像、备份与恢复](docs/guides/deployment/commands.md)
- [严格离线源码交付](docs/guides/deployment/offline.md)
- [Windows Docker Desktop 开发指南](docs/guides/deployment/windows-docker-desktop.md)

### 发布
- [变更日志](CHANGELOG.md)
- [1.3.2 发布说明](docs/releases/1.3.2.md)

## 快速开始：本地开发（Linux/macOS）

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f
```

浏览器访问 `http://127.0.0.1:8000`。开发环境默认不创建超级用户；首次使用时运行 `docker compose exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py createsuperuser` 创建本地管理员账号。提交或里程碑前运行 `scripts/verify` 执行完整基线验收。日常停止使用 `docker compose down`；不要使用 `docker compose down -v`。

Linux、macOS 与 Windows Docker Desktop 均使用相同的 `docker compose` 命令；Windows 特有说明见[Windows Docker Desktop 开发指南](docs/guides/deployment/windows-docker-desktop.md)。平台支持边界见[兼容性矩阵](COMPATIBILITY.md)：已验证的生产目标为 Linux `amd64` 与 Linux `arm64` Docker 主机。

## 快速开始：Docker 部署

部署由 **Docker Compose** 完成，项目脚本是可选工具。已有包含插件的应用镜像及 PostgreSQL、Redis 镜像，且均匹配目标 CPU 架构时，无需重新构建。

首次部署先准备 `.env.production`（填写真实密钥、域名）和生产数据卷，再启动：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

- 配置、数据卷、镜像构建及启动验收：[Docker 部署](docs/guides/deployment/docker.md)。
- 镜像导入导出、备份与恢复命令及参数：[关键命令](docs/guides/deployment/commands.md)。升级前备份数据库和附件，并演练恢复。
- 需要在目标机断网构建镜像时：[严格离线源码交付](docs/guides/deployment/offline.md)。若已准备完整运行镜像，导入后即可按普通 Compose 流程部署。

## 注意事项

`.env.example` 只包含占位值；复制为本地 `.env` 后填入运行密钥。`.env` 被 Git 忽略，不会进入仓库。

## CI/CD 与发布

- **PR 门禁**：`.github/workflows/ci.yml` 在每个 PR 上并行执行 Compose 配置校验、插件 wheel 构建，以及开发镜像构建（镜像构建同时验证插件 wheel 能装入真实 NetBox 运行环境）。
- **发布**：推送 `v*` 标签（如 `v1.3.2`）触发 `.github/workflows/release.yml`，构建 wheel 与生产镜像，将镜像推送到 `ghcr.io/<owner>/<repo>/netbox-access-relations:<version>`，并创建 GitHub Release 挂载 wheel、`SHA256SUMS` 与 `IMAGE_ID`。
- **离线源码交付包**在受控构建机上用 `scripts/release-source-package` 生成；目标机使用包内镜像和 wheel 完全断网构建，不依赖 CI。

## 许可与支持

本项目采用 [Apache-2.0 许可证](LICENSE)。请通过 [Issues](https://github.com/yucfisher-coder/netbox-access-relation/issues) 提交缺陷和功能建议；安全问题请遵循 [安全策略](SECURITY.md)。
