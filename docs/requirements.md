# 现行需求入口

基线版本：2026-09-13
状态：R01–R12 已由用户确认。

现行需求已经按领域拆分到 `requirements/`。开发时不要默认通读全部领域文件，应先从
`requirements-map.md` 选择对应开发切片的最小阅读集合。

## 领域需求

| 领域文件 | 内容 | 来源基线 |
|---|---|---|
| `requirements/scope.md` | 平台、首期范围和非目标 | R01 |
| `requirements/zones.md` | 安全区域来源、继承和解析 | R02 |
| `requirements/systems.md` | 业务系统和别名 | R03 |
| `requirements/addresses.md` | 系统地址、归并和合并部署 | R04–R05 |
| `requirements/policies.md` | 访问关系和有效期 | R06 |
| `requirements/services.md` | 服务项、端口和匹配 | R07 |
| `requirements/import-export.md` | 工作簿导入、事务、证据和数据导出 | R08–R10 |
| `requirements/query-presentation.md` | 页面入口、查询和区域矩阵 | R10 |
| `requirements/authorization-api.md` | 权限、API、审计、事务和状态边界 | R04、R09–R11 |
| `requirements/operations.md` | 开发、发布、恢复和数据安全 | R12 |

页面规格入口见 `ui-requirements.md`，验收标准见 `acceptance/`。

若领域文件之间出现冲突，先按 `requirements-map.md` 中的规范归属判断；无法消解时停止实现并
重新确认需求，不得用实现现状覆盖需求。

确认记录：2026-09-13，用户明确确认 R01–R12，并要求增加页面数据导出功能；2026-09-17，用户
进一步确认业务系统内批量地址维护、按操作渐进显示字段，以及业务系统/别名/地址的预检式批量导入。
同日补充确认：访问关系录入失败必须明确提示，访问关系列表与详情必须同时展示两端当前 IPAM 证据。
