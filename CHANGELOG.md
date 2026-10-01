# Changelog

All notable changes to this project are documented in this file. The format is
based on Keep a Changelog, and releases follow Semantic Versioning.

## [Unreleased]

## [1.3.0] - 2026-10-01

### Added

- 服务查询按相同协议与端口表达式聚合，展示关联目标系统和访问关系，并支持当前筛选结果导出。
- ANY 统一为覆盖全部 TCP/UDP 端口的全协议服务；新增迁移 `0006_global_any_services` 规范化既有 ANY 记录并限制每条访问关系只有一个 ANY。

### Changed

- 访问关系编辑、详情、列表和 XLSX 导入模板统一使用全协议 ANY 语义；导入 ANY 时协议列可留空。

### Notes

- 从 1.2.x 升级必须执行 `manage.py migrate`，再重启 NetBox web 与 worker。

## [1.2.1] - 2026-09-30

### Fixed

- 修复 Windows PowerShell 运维封装仍引用已删除 `compose/` 目录的问题，统一使用根目录 Compose 文件。
- 恢复 Linux/macOS bash 脚本的可执行位。

### Changed

- 明确插件包、Docker 开发环境和已验证 Linux 生产环境的跨平台支持边界。

### Notes

- 本版本不包含数据库迁移，数据结构基线仍为 `0001`～`0005`，可直接从 `1.2.0` 升级。

## [1.2.0] - 2026-09-30

### Changed

- 修正 CI 与发布工作流的 wheel 构建目录，恢复从仓库发行根构建插件包。
- 补齐入口文档、兼容性矩阵与发布索引，并统一部署示例、脚本和镜像标签到 `1.2.0`。

### Notes

- 本版本不包含数据库迁移，数据结构基线仍为 `0001`～`0005`，可直接从 `1.1.1` 升级。

## [1.1.1] - 2026-09-29

### Fixed

- 修复访问关系手动录入时，`PrimaryModelForm.clean()` 未返回字典而触发 500 错误页的问题；字段校验失败时保留在表单页并显示校验信息。

### Changed

- 访问关系的服务项编辑器为每一行增加“移除服务”操作。新增的多余行可在提交前移除；编辑既有关系时可标记服务项删除。界面始终保留至少一行可编辑服务项。

### Notes

- 本版本不包含数据库迁移，数据结构基线仍为 `0001`～`0005`，可直接从 `1.1.0` 升级。

## [1.1.0] - 2026-09-28

### Changed

- 合并 Compose 定义：删除 `compose/` 目录，以根目录 `docker-compose.yml` / `docker-compose.prod.yml` 为唯一来源；bash 脚本、PowerShell 封装与 CI 同步指向根目录文件。
- 整理文档体系：将备份/恢复/迁移相关内容合并为单一运维手册 `production-deployment.md`，新增 `code-structure.md`（代码结构）与 `development.md`（本地开发指南）。

### Removed

- 删除无人引用的 `config/plugins-disabled.py`。
- 精简 `locks/images.md` 中过时的本地镜像 ID 与失败构建记录。

### Notes

- 本版本不包含数据库迁移，数据结构基线仍为 `0001`～`0005`，与 `1.0.0` 兼容。

## [1.0.3] - 2026-09-26

### Changed

- 在业务系统列表中展示关联 IP 地址和可选 VRF，并优化名称、IP 信息和描述列的布局。

### Fixed

- 预加载业务系统关联地址，避免列表渲染时产生 N+1 查询。

## [1.0.2] - 2026-09-26

### Changed

- 在访问关系列表中展示具体服务能力，并将服务项、分类和 IPAM 信息列调整为更易读的布局。
- 将安全区域结果融入源端和目标端 IPAM 信息，移除独立的访问区域列。

### Fixed

- CSV 导出采用 Excel 兼容的 UTF-8 BOM；访问关系导出的 IPAM 信息移除安全区域和地址类型描述，服务项使用真实换行。

## [1.0.1] - 2026-09-26

### Fixed

- Reject conflicting pending IP ranges and duplicate IP addresses during XLSX import preview, before NetBox native validation runs.

### Added

- Community release documentation and package metadata.

## [1.0.0] - 2026-09-22

### Added

- Business systems, aliases, and NetBox IPAM address associations.
- Security-zone resolution evidence and co-location markers.
- Directional, time-bounded access policies and TCP/UDP services.
- Permission-aware service queries, zone matrices, and CSV exports.
- Versioned XLSX preview and transactional import workflows.
- NetBox-native UI, object permissions, change logging, and REST API routes.
- English and Simplified Chinese localization.

### Compatibility

- NetBox 4.7.x and Python 3.12 or later.
