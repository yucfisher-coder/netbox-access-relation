# 代码结构说明

本文档是**仓库导航**：说明每个目录和关键文件的职责，以及从哪里入手阅读或修改代码。
它回答"东西放在哪、怎么找到"；设计动机、数据模型和核心流程见
[`architecture.md`](architecture.md)，两者不重复。

## 一、仓库整体布局

本仓库以一个可分发的 NetBox 插件包为核心，并带有可选的 Docker 开发、生产与离线交付基础设施。
顶层目录按职责划分如下：

```
netbox-access-relation/
├── pyproject.toml          插件发行配置及运行时依赖（唯一依赖来源）
├── MANIFEST.in             sdist 打包清单
├── netbox_access_relations/ Django app（可导入的插件包）
├── docker/                 镜像构建文件（开发 / 生产 / 离线生产 Dockerfile 与入口脚本）
├── config/                 挂载或内置进容器的 NetBox 运行时配置（plugins.py）
├── scripts/                Linux/macOS 开发与发布脚本（bash）
│   └── windows/            Windows 等效脚本（PowerShell）
├── locks/                  锁定的依赖与镜像 digest（构建可复现）
├── docs/                   全部文档（需求 / 设计 / 部署 / 验收 / 发布）
├── .github/workflows/      CI 与发布流水线
├── docker-compose.yml      开发环境 Compose（唯一来源）
├── docker-compose.prod.yml 生产环境 Compose（唯一来源）
├── deploy.ps1              Windows 便捷封装（可选，内部即调用 docker compose）
├── .env.example            开发环境变量样例
└── .env.production.example 生产环境变量样例
```

> 历史上 `compose/` 目录与根目录曾并存两套 Compose，现已统一为根目录的 `docker-compose.yml`
> 与 `docker-compose.prod.yml`，bash 脚本、PowerShell 封装和 CI 都指向同一份文件。

## 二、为什么这样分层

| 关注点 | 放在哪 | 理由 |
|---|---|---|
| 插件业务代码 | 仓库根的 `netbox_access_relations/` 与 `pyproject.toml` | 可直接构建 wheel 或执行 `pip install .` |
| 部署基础设施 | 仓库根（`docker/`、`scripts/`、Compose、`config/`） | 服务于"在官方 NetBox 镜像里运行插件"，不属于插件本身 |
| 文档 | `docs/` | 按功能分组，单一归属，避免与代码混杂 |
| 锁定信息 | `locks/` | 依赖版本与镜像 digest 独立于源码，保证离线构建可复现 |

`pyproject.toml` 与 `netbox_access_relations/` 位于根目录，因而在任意兼容的 NetBox 环境中可直接执行
`pip install .` 或构建 wheel。Docker、Compose 和脚本是可选运行基础设施，不属于 Python 包的导入路径。

## 三、插件包内部结构

仓库根是标准 Python 发行根，`netbox_access_relations/` 是唯一的可导入 Django app：

```
netbox-access-relation/                 ← 发行根（distribution root）
├── pyproject.toml                      构建配置：包名、运行时依赖、打包规则
├── MANIFEST.in                          sdist 打包包含的文件
├── README.md / CHANGELOG.md / LICENSE  随发行包分发的元数据文档
└── netbox_access_relations/            ← 可导入的 Python 包（Django app）
    ├── __init__.py                     PluginConfig 声明（入口，见下）
    ├── models.py                       五个数据模型
    ├── migrations/                     数据库迁移（基线 0001～0005）
    ├── views.py / urls.py              Web 视图与路由
    ├── forms.py / tables.py / filtersets.py  列表页、表单、查询过滤
    ├── navigation.py / ui/panels.py    侧边栏菜单、详情页面板
    ├── api/                            REST API（serializers / views / urls）
    ├── services/                       业务逻辑层（被 Web、API、导入共用）
    ├── templates/                      Django 模板
    ├── signals.py                      Django 信号（地址变更重算共置）
    └── locale/zh/                      简体中文翻译
```

运行时依赖只在 `pyproject.toml` 的 `[project.dependencies]` 中声明；不维护第二份
`plugin_requirements.txt`，以免镜像构建与 wheel 安装产生版本漂移。开发工具依赖如有需要，应单独放在
`requirements-dev.txt` 或开发依赖组中。

## 四、关键入口与扩展点

从哪里读起：

1. **插件入口**：[`netbox_access_relations/__init__.py`](../netbox_access_relations/__init__.py)
   定义 `AccessRelationsConfig`（`name`、`base_url=access-relations`、版本兼容区间），并在 `ready()`
   中连接信号。NetBox 通过它发现并加载插件。
2. **数据模型**：[`models.py`](../netbox_access_relations/models.py)
   定义 `ApplicationSystem` / `SystemAlias` / `SystemAddress` / `AccessPolicy` / `PolicyService`。
3. **业务逻辑**：[`services/`](../netbox_access_relations/services) 是
   纯业务层，不依赖 HTTP。新增逻辑优先放这里，再由 Web/API/导入调用，保证行为一致。
4. **写入入口**：数据有三个写入路径——Web 表单（`forms.py`）、工作簿导入（`services/workbook_import.py`）、
   REST API（`api/`）。涉及唯一性等共享校验时，三处都要调用同一处服务层逻辑。
5. **配置挂载**：开发时 [`config/plugins.py`](../config/plugins.py) 被只读挂载进容器启用插件；
   生产镜像则在 [`docker/Dockerfile.prod`](../docker/Dockerfile.prod) 中内置该配置。

## 五、构建与产物

| 脚本 | 产物 / 作用 |
|---|---|
| `scripts/build` | 校验基础镜像 digest 后构建开发镜像 `netbox-access-relations-dev:local` |
| `scripts/release-build` | 构建生产镜像 `netbox-access-relations:<version>` |
| `scripts/release-package` | 生成 `dist/offline-release-<version>/`（含已构建镜像的离线包） |
| `scripts/release-source-package` | 生成 `dist/offline-source-release-<version>/`（源码 + wheelhouse，目标机构建） |
| `scripts/verify` | 本地基线验收：Compose 校验、镜像构建、插件装入验证、迁移无漂移检查 |

`dist/` 为构建产物，不入库。镜像与依赖的锁定值见 [`locks/`](../locks)。

## 六、阅读路径建议

- 想理解**为什么这样设计** → `architecture.md`
- 想**跑起来开发** → `development.md`
- 想**部署到生产 / 备份恢复** → `production-deployment.md`
- 想知道**每个目录是干什么的** → 本文档
