# 需求地图

版本：2026-09-17

本文是轻量路由表，只用于选择开发任务所需的最小上下文。需求正文位于 `requirements/`，页面规格
位于 `ui/`，验收场景位于 `acceptance/`。本文不保存需求正文、实现状态或验证结果。

## 能力地图

```text
M0 NetBox 访问关系管理
├── M1 业务对象：区域、系统、地址、关系、服务项
├── M2 业务能力：区域解析、地址归并、有效期、服务匹配、导入导出
├── M3 查询呈现：业务系统、访问关系、服务查询、区域矩阵
├── M4 横切治理：权限、API、审计、事务、状态
└── M5 工程运维：环境、测试门禁、发布、备份恢复、数据安全
```

## 开发切片路由

“必读”是开始该切片前的最小集合；仅在涉及相应横切能力时读取“按需”。无需读取表中未列出的
其他领域文档。

| 开发切片 | 必读领域需求 | 按需领域需求 | UI 规格 | 验收标准 |
|---|---|---|---|---|
| 业务系统与别名 | `systems.md` | `authorization-api.md` | `common.md`、`business-systems.md` | `common.md`、`business-systems.md` |
| 系统地址与区域证据 | `addresses.md`、`zones.md` | `authorization-api.md` | `common.md`、`business-systems.md` | `common.md`、`business-systems.md` |
| 地址归并与合并部署 | `addresses.md`、`zones.md` | `import-export.md` | 无独立页面；涉及系统页时读 `business-systems.md` | `business-systems.md` |
| 访问关系 | `policies.md`、`services.md` | `zones.md`、`authorization-api.md`、`import-export.md` | `common.md`、`access-policies.md` | `common.md`、`access-policies.md` |
| 服务查询 | `services.md`、`query-presentation.md` | `policies.md`、`authorization-api.md`、`import-export.md` | `common.md`、`service-query.md` | `common.md`、`service-query.md` |
| 区域矩阵 | `zones.md`、`query-presentation.md` | `policies.md`、`services.md`、`authorization-api.md`、`import-export.md` | `common.md`、`zone-matrix.md` | `common.md`、`zone-matrix.md` |
| 工作簿导入 | `import-export.md` | `systems.md`、`addresses.md`、`zones.md`、`policies.md`、`services.md`、`authorization-api.md` | `common.md` 及入口所属页面 | `import.md` |
| 数据导出 | `import-export.md` | `authorization-api.md` 及被导出对象的领域文件 | `common.md` 及对应页面 | 对应页面验收文件 |
| REST API | `authorization-api.md` 及目标对象领域文件 | `import-export.md` | 无 | `api-permissions.md` |
| 发布与恢复 | `operations.md`、`scope.md` | 无 | 无 | `release.md` |

表内文件路径分别相对于 `requirements/`、`ui/` 和 `acceptance/`。

## 编号归属

| 编号前缀 | 唯一正文文件 |
|---|---|
| REQ-SCOPE | `requirements/scope.md` |
| REQ-ZONE | `requirements/zones.md` |
| REQ-SYS | `requirements/systems.md` |
| REQ-ADDR、REQ-MERGE | `requirements/addresses.md` |
| REQ-POL | `requirements/policies.md` |
| REQ-SVC | `requirements/services.md` |
| REQ-IMP、REQ-EXP | `requirements/import-export.md` |
| REQ-UI、REQ-QUERY、REQ-MATRIX | `requirements/query-presentation.md` |
| REQ-AUTH、REQ-API、REQ-AUDIT、REQ-TXN、REQ-STATE | `requirements/authorization-api.md` |
| REQ-OPS | `requirements/operations.md` |

编号一经使用不得改作其他含义。废止需求保留编号并在其唯一正文文件中标记，不重新分配。

## 基线来源

| 基线 | 领域文件 |
|---|---|
| R01 | `scope.md` |
| R02 | `zones.md` |
| R03 | `systems.md` |
| R04–R05 | `addresses.md`，横切规则见 `authorization-api.md` |
| R06 | `policies.md` |
| R07 | `services.md` |
| R08–R09 | `import-export.md`，横切规则见 `authorization-api.md` |
| R10 | `query-presentation.md`、`import-export.md` |
| R11 | `authorization-api.md` |
| R12 | `operations.md` |

R01–R12 是确认批次，REQ-* 是稳定追踪编号；两者是来源与拆分关系，不是两套并行需求。
