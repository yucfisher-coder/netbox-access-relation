# NetBox Access Relations

> 目标：NetBox Community **4.7.0** + 独立 Python 插件；宿主机编辑、Compose 开发；生产安装 wheel 后构建不可变镜像。

## 项目状态

当前发布版本 **1.1.0**。首个生产版本 **1.0.0** 已于 2026-09-22 完成发布门禁。当前包含 `ApplicationSystem`、`SystemAlias`、
`SystemAddress`、`AccessPolicy` 和 `PolicyService` 五个业务模型，数据结构基线固定为迁移
`0001`～`0005`。核心页面、导入、服务查询和区域矩阵已经实现；ARM64 不可变镜像、离线启动、
版本化生产卷和隔离恢复演练均已通过。部署到实际生产主机前仍须注入真实密钥、域名并按目标架构重建。

版本策略：不影响数据结构的常规增强进入 `1.0.x`；涉及仓库结构、构建体系调整，或数据库模型/约束变化时进入新的次版本（如 `1.1.0`）。

## 文档索引

### 需求与设计
- [当前需求确认稿](docs/requirements.md)
- [系统架构与设计](docs/architecture.md)

### 开发与结构
- [代码结构说明](docs/code-structure.md)
- [本地开发指南](docs/development.md)

### 部署
- [Linux x86_64 (amd64) 离线部署指南](docs/linux-amd64-offline-deployment.md)
- [Windows Docker Desktop 部署指南](docs/windows-docker-desktop-deployment.md)
- [生产部署、备份、恢复与迁移（完整版）](docs/production-deployment.md)

### 发布
- [离线源码构建发布脚本](scripts/release-source-package)
- [1.1.0 发布说明](docs/releases/1.1.0.md)
- [1.0.1 发布说明](docs/releases/1.0.1.md)
- [1.0.0 发布说明](docs/releases/1.0.0.md)

## 快速开始

```bash
scripts/init-env
scripts/dev up
scripts/dev logs
```

浏览器访问 `http://127.0.0.1:8000`。常用入口见 `scripts/dev help`。提交或里程碑前运行 `scripts/verify`，
它构建一次镜像并执行完整基线验收。这些脚本不会执行
`docker compose down -v`。首次启动前若尚无开发镜像，先运行一次 `scripts/build`（或直接 `docker compose up -d --build`）。

## 注意事项

`.env.example` 只包含占位值。`scripts/init-env` 在本地创建被 Git 忽略且权限为 `0600` 的 `.env`，不会把运行密钥写入仓库。

## CI/CD 与发布

- **PR 门禁**：`.github/workflows/ci.yml` 在每个 PR 上并行执行 Compose 配置校验、插件 wheel 构建，以及开发镜像构建（镜像构建同时验证插件 wheel 能装入真实 NetBox 运行环境）。
- **发布**：推送 `v*` 标签（如 `v1.1.0`）触发 `.github/workflows/release.yml`，构建 wheel 与生产镜像，将镜像推送到 `ghcr.io/<owner>/<repo>/netbox-access-relations:<version>`，并创建 GitHub Release 挂载 wheel、`SHA256SUMS` 与 `IMAGE_ID`。
- **离线完整交付包**仍在受控发布机上用 `scripts/release-package` / `scripts/build-offline-release` 生成，不依赖 CI。
