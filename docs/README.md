# 文档导航

文档职责、写法与同步规则见[文档规范](standards/documentation.md)。本页只提供入口，不复制各文档的规范内容。

## 按目标阅读

| 目标 | 阅读入口 |
|---|---|
| 了解项目与最快启动方式 | [仓库 README](../README.md) |
| 开始一个业务开发任务 | [需求地图](requirements/map.md) → `requirements/` → `ui/`（如涉及页面）→ `acceptance/` |
| 理解设计取舍 | [系统架构与设计](explanation/architecture.md) |
| 找到代码和配置的位置 | [仓库结构参考](reference/repository-structure.md) |
| 本地开发、调试和验证 | [本地开发指南](guides/development.md) |
| 普通联网部署 | [Docker 部署](guides/deployment/docker.md) |
| 严格离线部署、恢复或迁移 | [严格离线部署](guides/deployment/offline.md) |
| 核对兼容性与镜像锁定 | [兼容性矩阵](../COMPATIBILITY.md) 与 [`locks/images.md`](../locks/images.md) |
| 查看历史变更与升级影响 | [`releases/`](releases/) 与 [变更日志](../CHANGELOG.md) |

需求状态、实现状态和验证状态互相独立：需求已确认不代表已实现，已实现不代表已验证，单项验证通过也不代表整体交付完成。
