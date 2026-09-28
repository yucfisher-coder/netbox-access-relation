# 现行文档入口

更新时间：2026-09-28。

## 文档职责

| 文档 | 只回答 | 不包含 |
|---|---|---|
| `requirements.md`、`requirements/` | 产品必须做什么、不得做什么 | 实现状态、测试结果、开发待办 |
| `architecture.md` | 系统架构、模块划分、核心流程设计 | 需求正文、操作步骤 |
| `requirements-map.md` | 开发切片需要读取哪些最小文档集合 | 需求正文、实现差距、测试结论 |
| `ui-requirements.md`、`ui/` | 页面如何组织和交互 | 后端实现状态、测试结果 |
| `acceptance/*.md` | 满足需求必须通过哪些可观察场景 | 当前是否通过、如何实现 |
| `linux-amd64-offline-deployment.md`、`windows-docker-desktop-deployment.md` | 如何按平台部署 | 需求正文、业务规则 |
| `production-deployment.md` | 如何部署、备份、恢复与迁移 | 需求正文、业务规则 |
| `code-structure.md` | 仓库与代码放在哪、从哪里读起 | 设计动机、操作步骤 |
| `development.md` | 如何在本地跑起来、改代码、调试、验收 | 生产部署、需求正文 |

## 阅读路径

1. 开始开发任务：先从 `requirements-map.md` 选择开发切片。
2. 只读取该切片列出的 `requirements/` 领域文件。
3. 涉及页面时，再读取该切片列出的 `ui/` 文件。
4. 需要判断交付条件：阅读 `acceptance/`。
5. 部署、备份与恢复：阅读上述部署文档。
6. 新人上手：先读 `code-structure.md` 了解目录，再按 `development.md` 跑起本地环境。

任何信息只保留一个规范归属。其他文档需要该信息时使用链接或编号引用，不复制正文。需求状态、
实现状态和验证状态互相独立：需求已确认不代表已实现，已实现不代表已验证，单项验证通过也不代表
整体交付完成。
