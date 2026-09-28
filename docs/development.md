# 本地开发指南

本文档说明如何在本地把插件跑起来、改代码、调试和做提交前验收。面向插件开发者。
生产部署、备份与恢复见 [`production-deployment.md`](production-deployment.md)；
目录结构与各文件职责见 [`code-structure.md`](code-structure.md)。

## 一、前置条件

- Docker Engine 与 Docker Compose v2（Linux / macOS / Windows Docker Desktop 均可）。
- 开发镜像在与本机一致的 CPU 架构上构建（amd64 或 arm64）。
- Linux/macOS 用 `scripts/*`（bash）；Windows 用根目录的 `deploy.ps1` 或 `scripts/windows/*.ps1`。
  两套都指向同一份根目录 Compose。

## 二、初始化环境变量

`.env` 不入库，由脚本生成为权限 `0600` 的本地文件（含随机密钥）：

```bash
scripts/init-env        # Linux/macOS
```

```powershell
.\deploy.ps1 init-env   # Windows
```

脚本拒绝覆盖已存在的 `.env`。`.env.example` 仅为占位样例，请勿把真实密钥提交进仓库。

## 三、构建开发镜像

首次启动或基础镜像变更后，构建一次开发镜像。脚本会先校验本地基础镜像是否匹配
[`locks/images.md`](../locks/images.md) 锁定的 digest，不匹配则中止：

```bash
scripts/build
```

Windows 等效：`.\deploy.ps1 build`。

## 四、启动与日常操作

```bash
scripts/dev up          # 构建并后台启动（--build -d）
scripts/dev ps          # 查看状态（默认子命令）
scripts/dev logs        # 跟随日志
scripts/dev stop        # 停止（保留数据卷）
scripts/dev down        # 停止并移除容器（保留命名卷；本封装不提供 down -v）
scripts/dev shell       # 进入 netbox 容器的 Django shell
scripts/dev restart-worker
```

Windows 等效：`.\deploy.ps1 dev {up|stop|down|ps|logs}`。

启动后浏览器访问 `http://127.0.0.1:8000`（端口由 `.env` 的 `NETBOX_HTTP_PORT` 控制，默认 8000）。

### 工作原理

开发镜像 [`docker/Dockerfile.dev`](../docker/Dockerfile.dev) 基于官方 NetBox 镜像，
入口 [`docker/dev-entrypoint.sh`](../docker/dev-entrypoint.sh) 以**可编辑模式**安装插件
（`uv pip install --editable`），并把 `plugins/netbox_access_relations` 源码挂载进容器。
因此改 Python 代码后，`runserver` 会自动重载，无需重建镜像。

服务依赖链：`postgres / redis / redis-cache → netbox（启动时自动迁移）→ worker`，
worker 等 netbox 健康后才启动，避免迁移竞态。

## 五、调试

`scripts/dev debug` 以 debugpy 启动 netbox 并等待调试器连接（容器内 `0.0.0.0:5678`，
映射到宿主机 `127.0.0.1:5678`）：

```bash
scripts/dev debug
```

## 六、数据库迁移

数据结构基线固定为迁移 `0001`～`0005`。版本策略：`1.0.x` 只做不影响数据结构的增强；
涉及模型或约束变化的改动进入新的升级版本。

```bash
scripts/dev makemigrations   # 生成迁移（写入 plugins/.../migrations/）
scripts/dev migrate          # 应用迁移
```

提交前务必确认没有遗漏的迁移：

```bash
scripts/verify
```

`verify` 会在干净库上执行 `makemigrations --check --dry-run`，确保迁移文件与模型一致。

## 七、提交前验收

`scripts/verify` 是本地完整基线验收，依次：

1. 校验开发与生产两份 Compose 配置可正常展开；
2. 构建开发镜像与生产镜像；
3. 断言生产镜像内插件版本正确、且无残留的可编辑安装或临时 wheel；
4. 启动依赖服务并检查迁移无漂移。

全部通过才输出 `Baseline verification passed.`。该脚本**不会**执行 `docker compose down -v`。

## 八、构建生产与离线介质（可选）

需要在本机验证生产构建或制作离线交付包时：

```bash
scripts/release-build        # 构建生产镜像 netbox-access-relations:<version>
scripts/release-package      # 生成 dist/offline-release-<version>/（含已构建镜像）
scripts/release-source-package  # 生成 dist/offline-source-release-<version>/（源码包）
```

离线介质的制作与目标机部署流程见 [`production-deployment.md`](production-deployment.md)。
注意：生产离线镜像归档必须在与目标主机相同 CPU 架构的机器上制作。

## 九、提交规范

提交信息使用 Conventional Commits（如 `feat:`、`fix:`、`docs:`）。涉及数据结构的变更须在发布说明中
单独说明迁移影响；不得跨 PostgreSQL 主版本复用生产数据卷。
