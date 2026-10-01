# 系统架构与设计

本文档概述 NetBox Access Relations 插件的系统架构、核心设计决策和模块划分。
面向需要理解系统内部结构的开发者和运维人员。需求规格见 [`../requirements/README.md`](../requirements/README.md)，
部署操作见 [`../guides/deployment/offline.md`](../guides/deployment/offline.md)。

## 一、定位与边界

本插件是 NetBox Community **4.7.x** 的独立 Python 插件，不修改 NetBox 核心代码。
它通过 NetBox 官方扩展点（PluginConfig、模型注册、导航、UI 面板、REST API、过滤器集、信号）
实现业务系统、IPAM 地址关联、访问策略和安全区域矩阵的管理。

**不做的事：**
- 不替代 NetBox 原生 IPAM（Prefix / IPAddress / IPRange）的管理；插件只建立关联。
- 不管理防火墙或网络设备的实际配置；只记录访问关系的期望状态。
- 不实现认证/授权；完全复用 NetBox 的用户、角色和对象权限体系。

## 二、技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 宿主框架 | NetBox 4.7.x（Django 5.x） | 插件运行于 NetBox 进程内 |
| 数据库 | PostgreSQL 16+（生产锁定 18.6） | 使用 Django ORM，依赖 `ltree` 扩展（NetBox 核心所需） |
| 缓存/队列 | Redis 7.x | 两套实例：缓存（`redis-cache`）和任务队列（`redis`） |
| 前端 | NetBox 原生 UI（Bootstrap 5 + HTMX） | 不引入独立前端框架 |
| 工作簿导入 | openpyxl | XLSX 模板生成、预检和事务性导入 |
| 部署 | Docker + Docker Compose v2 | 开发镜像可编辑挂载；生产镜像不可变 |
| 兼容架构 | linux/amd64、linux/arm64 | 所有基础镜像使用多架构 digest |

## 三、数据模型

五个业务模型及其关系：

```
ApplicationSystem（业务系统）
  ├── SystemAlias（系统别名）── 1:N
  ├── SystemAddress（系统地址）── 1:N ──> Prefix / IPAddress / IPRange（NetBox 原生）
  ├── AccessPolicy（访问关系）── 作为源端 1:N
  └── AccessPolicy（访问关系）── 作为目标端 1:N
        └── PolicyService（策略服务项）── 1:N
```

### 派生字段（不允许手动编辑）

- `ApplicationSystem.is_co_located`：当系统与其他系统共享同一原生 IPAM 对象时自动标记为 `True`。
  由 [`co_location.py`](../../netbox_access_relations/services/co_location.py)
  在地址变更时事务性重算。
- `AccessPolicy.effective_status`：根据 `valid_from` / `valid_until` 和当前时间动态计算
  （upcoming / active / expired），不落库。

### 数据库约束（关键）

- 名称唯一：业务系统名和系统别名共用**不区分大小写**的唯一命名空间（DB 层 `Lower()` 唯一索引）。
- 地址目标互斥：每条 `SystemAddress` 恰好关联一个 Prefix、IPAddress 或 IPRange（CheckConstraint）。
- 访问关系端点互异：源系统和目标系统不能相同（CheckConstraint）。
- 有效期合法：`valid_until` 必须晚于 `valid_from`（CheckConstraint）。
- 服务项端口合法：ANY 或 1–65535 的闭区间（CheckConstraint）。

## 四、模块划分

```
netbox_access_relations/
├── __init__.py          # PluginConfig 声明、版本号
├── config.py            # 配置类别名（向后兼容）
├── models.py            # 五个数据模型定义
├── signals.py           # Django 信号：地址删除时重算共置
├── navigation.py        # NetBox 侧边栏菜单项注册
├── filtersets.py        # 列表/API 查询过滤器（含区域、IP、端口匹配）
├── forms.py             # Web 表单（含内联表单集、IPAM 原子写入）
├── tables.py            # 列表表格定义（含 CSV 导出格式）
├── views.py             # Web 视图（列表/详情/编辑/导入/区域矩阵）
├── urls.py              # Web URL 路由
├── api/                 # REST API（serializers / viewsets / urls）
├── services/            # 业务逻辑层（被 Web、API、导入共用）
│   ├── zones.py         # 安全区域解析
│   ├── co_location.py   # 共置标记维护
│   ├── ipam_writes.py   # 原生 IPAM 原子写入
│   ├── workbook_import.py  # XLSX 模板、预检、事务导入
│   └── address_ranges.py   # 地址区间合并（工具函数）
├── ui/panels.py         # 详情页属性面板定义
└── templates/           # Django 模板（自定义编辑页、导入页、矩阵页）
```

### 分层原则

- **services 层**是纯业务逻辑，不依赖 HTTP 请求/响应。被 Web 视图、API 视图和导入流程共用，
  保证行为一致性。
- **views / api** 只负责参数解析、权限校验和响应渲染，不直接写复杂业务逻辑。
- **models** 只定义数据结构和轻量校验（`clean()`），复杂派生逻辑委托给 services。

## 五、核心流程

### 5.1 安全区域解析

安全区域通过 Prefix 对象的自定义字段 `security_zone` 标记。解析规则：

1. 对一个 IP 地址/范围，在同一 VRF 内查找所有覆盖它的 Prefix。
2. 过滤出设置了 `security_zone` 的候选。
3. 取**最具体**（前缀长度最大）的候选。
4. 如果最具体的候选有多个且区域值不一致 → 标记为"歧义"。
5. 没有候选 → "未匹配"；有候选但都没设置区域 → "未设置"。

Prefix 对象可直接设置区域，也可从祖先 Prefix 继承。解析结果在每次查询时实时计算，不缓存。

### 5.2 共置标记维护

当 `SystemAddress` 被创建、修改或删除时：

1. `prepare_address_change` / `prepare_address_deletion` 锁定受影响的原生 IPAM 行和系统行。
2. `super().save()` 执行实际写入。
3. `recalculate_co_location` 重算所有受影响系统的 `is_co_located`。

全流程在一个数据库事务内完成，通过 `SELECT FOR UPDATE` 防止并发竞态。

### 5.3 XLSX 工作簿导入

两步式事务导入：

1. **上传 → 预检**：解析工作簿，在内存中构建 `ImportPlan`，返回预览（新增/跳过/错误）。
   不写数据库，不保存上传文件。
2. **确认 → 应用**：重新预检（防止文件在确认前被篡改），在一个事务中写入全部数据。
   任一行失败则整体回滚。

预检内容包括：名称冲突、权限检查、地址格式校验、VRF 匹配、端口范围合法性、
工作簿内待创建对象的相互冲突检查。

### 5.4 原生 IPAM 原子写入

`SystemAddress` 的保存可同时创建或更新关联的原生 IPAM 对象（Prefix/IPAddress/IPRange）。
由 [`ipam_writes.py`](../../netbox_access_relations/services/ipam_writes.py)
在一个事务中完成，并强制执行 NetBox 对象级权限（`restrict`）检查。

## 六、权限模型

完全复用 NetBox 的对象权限体系：

- 每个模型有标准的 `view` / `add` / `change` / `delete` 权限。
- 列表查询通过 `queryset.restrict(user, "view")` 自动过滤。
- 创建/更新原生 IPAM 对象时，额外检查 `ipam.add_*` / `ipam.change_*` 权限。
- 工作簿导入预检阶段检查所有必要权限，确认阶段事务内再次验证。

## 七、部署架构

### 开发环境（`docker-compose.yml`）

- 插件源码以可编辑模式挂载进容器（`uv pip install --editable`）。
- NetBox 使用 `runserver`（开发服务器），支持代码热重载。
- 数据卷为 Compose 管理的命名卷，`docker compose down` 不删除。

### 生产环境（`docker-compose.prod.yml`）

- 插件预构建进不可变镜像，运行时不挂载源码。
- 数据卷为**外部卷**（`external: true`），生命周期独立于 Compose 项目。
- PostgreSQL、Redis 均使用锁定 digest 的镜像。
- HTTP 仅绑定 `127.0.0.1`，由同机反向代理终结 TLS。

服务依赖链：`postgres / redis / redis-cache → netbox（自动迁移）→ worker`。
worker 依赖 netbox 健康后启动，避免迁移竞态。

## 八、可扩展性

- **新增模型**：在 `models.py` 定义后，NetBox 的 `get_model_urls` 自动生成 CRUD URL；
  补充 filtersets / forms / tables / serializers / panels 即可获得完整 UI 和 API。
- **新增导入类型**：在 `workbook_import.py` 的 `SYSTEM_SHEETS` / `POLICY_SHEETS` 扩展，
  或新增 kind 并实现对应的 `_preview_*` / `_apply_*`。
- **自定义区域规则**：修改 `services/zones.py` 的 `RULE_VERSION` 和解析逻辑，
  证据中会记录规则版本便于追溯。
