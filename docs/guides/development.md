# 本地开发指南

本文档说明如何在本地把插件跑起来、改代码、调试和做提交前验收。面向插件开发者。
生产部署、备份与恢复见 [`deployment/offline.md`](deployment/offline.md)；
目录结构与各文件职责见 [`../reference/repository-structure.md`](../reference/repository-structure.md)。

## 一、前置条件

- Docker Engine 与 Docker Compose v2（Linux / macOS / Windows Docker Desktop 均可）。容器运行目标为 `linux/amd64` 或 `linux/arm64`；Windows 与 macOS 的支持指 Docker Desktop 开发环境，不等同于原生宿主服务部署。
- 开发镜像在与本机一致的 CPU 架构上构建（amd64 或 arm64）。
- Linux、macOS 与 Windows Docker Desktop 都直接使用根目录的 `docker compose`；所有平台指向同一份 Compose 配置。

## 二、初始化环境变量

`.env` 不入库，由脚本生成为权限 `0600` 的本地文件（含随机密钥）：

```bash
cp .env.example .env
# 编辑 .env，替换所有 REPLACE_WITH_... 占位值
```

脚本拒绝覆盖已存在的 `.env`。`.env.example` 仅为占位样例，请勿把真实密钥提交进仓库。

## 三、构建开发镜像

首次启动或基础镜像变更后，构建一次开发镜像。脚本会先校验本地基础镜像是否匹配
[`locks/images.md`](../../locks/images.md) 锁定的 digest，不匹配则中止：

```bash
docker compose build netbox
```

## 四、启动与日常操作

```bash
docker compose up --build -d
docker compose ps
docker compose logs --follow
docker compose stop
docker compose down              # 保留命名卷
docker compose exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py shell
docker compose restart worker
```

启动后浏览器访问 `http://127.0.0.1:8000`（端口由 `.env` 的 `NETBOX_HTTP_PORT` 控制，默认 8000）。

### 工作原理

开发镜像 [`docker/Dockerfile.dev`](../../docker/Dockerfile.dev) 基于官方 NetBox 镜像，
入口 [`docker/dev-entrypoint.sh`](../../docker/dev-entrypoint.sh) 以**可编辑模式**安装插件
（`uv pip install --editable`），并把仓库根的发行元数据及 `netbox_access_relations`
源码挂载进容器。
因此改 Python 代码后，`runserver` 会自动重载，无需重建镜像。

服务依赖链：`postgres / redis / redis-cache → netbox（启动时自动迁移）→ worker`，
worker 等 netbox 健康后才启动，避免迁移竞态。

## 五、调试

以下命令以 debugpy 启动 netbox 并等待调试器连接（容器内 `0.0.0.0:5678`，
映射到宿主机 `127.0.0.1:5678`）：

```bash
docker compose run --rm --service-ports --entrypoint /opt/netbox/dev-entrypoint.sh netbox \
  /opt/netbox/venv/bin/python -m debugpy --listen 0.0.0.0:5678 --wait-for-client \
  /opt/netbox/netbox/manage.py runserver --noreload 0.0.0.0:8080
```

## 六、数据库迁移

数据结构基线固定为迁移 `0001`～`0006`。版本策略：`1.0.x` 只做不影响数据结构的增强；
涉及模型或约束变化的改动进入新的升级版本。

```bash
docker compose exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py makemigrations netbox_access_relations
docker compose run --rm init /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate
```

提交前务必确认没有遗漏的迁移：

```bash
scripts/verify
```

`verify` 会在干净库上执行 `makemigrations --check --dry-run`，确保迁移文件与模型一致。

### 自动化回归测试

执行以下命令运行 Django 回归测试：

```bash
scripts/test
```

测试代码位于仓库根目录的 `tests/`，只挂载到开发 Compose 容器；它不属于 Python 插件包，生产
Dockerfile 也不会复制它。CI 会运行该测试，并校验 wheel 中不包含测试目录。
每次测试使用固定的独立 Compose 项目 `netbox-access-relations-test`，结束时（包括失败时）自动删除
该项目的容器、网络与卷；测试数据库不会写入可复用的开发项目 `netbox-access-relations-dev`。

## 七、提交前验收

`scripts/verify` 是本地完整基线验收，依次：

1. 校验开发与生产两份 Compose 配置可正常展开；
2. 构建开发镜像与生产镜像；
3. 断言生产镜像内插件版本正确、且无残留的可编辑安装或临时 wheel；
4. 在隔离测试项目中启动临时依赖服务，检查迁移无漂移并运行 Django 回归测试，随后自动清理测试资源。

全部通过才输出 `Baseline verification passed.`。它不会清理开发或生产资源；仅测试项目会执行作用域限定的 `down --volumes`。

## 八、构建生产与离线源码交付包（可选）

需要在本机验证生产构建或制作离线交付包时：

```bash
scripts/release-build          # 构建生产镜像 netbox-access-relations:<version>
scripts/release-source-package # 打包完整源码、公共基础镜像和锁定 wheel
```

生产主机不能联网时，`release-source-package` 是标准交付方式：目标机从离线介质载入基础镜像、源码和 wheelhouse，并以 `--network=none` 构建最终镜像。离线介质的制作与部署流程见 [`deployment/offline.md`](deployment/offline.md)。构建包必须在与目标主机相同 CPU 架构的机器上制作。

## 九、提交规范

提交信息使用 Conventional Commits（如 `feat:`、`fix:`、`docs:`）。涉及数据结构的变更须在发布说明中
单独说明迁移影响；不得跨 PostgreSQL 主版本复用生产数据卷。
