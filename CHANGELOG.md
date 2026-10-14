# Changelog

All notable changes to this project are documented in this file. The format is
based on Keep a Changelog, and releases follow Semantic Versioning.

## [Unreleased]

## [1.3.4] - 2026-10-14

### Fixed

- 修复工作簿确认导入时原生地址字段校验错误被错误绑定到上传表单，导致服务器异常的问题；失败时显示实际校验信息并回滚。
- IPAddress 导入必须显式填写掩码，IPRange 起止地址必须显式填写一致的掩码；保留原始掩码并在预检执行原生 IPAM 校验，更新模板说明和示例。

### Added

- 业务系统和访问关系列表支持复选框选择、批量修改及批量删除，沿用 NetBox 权限校验和关联保护。
- 补充单条删除、批量操作、权限和掩码导入回归测试。

### Notes

- 无新增数据库迁移，与 1.3.3 数据库结构兼容。

## [1.3.3] - 2026-10-13

### Fixed

- 同一访问关系的 ANY 服务与其他服务端口互斥，页面、API、模型校验与工作簿导入统一校验。

- 修复编辑访问关系时移除并替换最后一个服务项的保存顺序，保持至少一个服务项的事务校验；删除行不再阻止浏览器提交或在校验失败后重新出现。
- 补齐业务系统和访问关系编辑页的服务按钮、ANY 提示、影响提示与重复校验中英文翻译。

- 修复访问关系仅修改分类、业务系统仅修改名称时，未填写的内联新增行因时间戳误判而阻止保存的问题；保留并发修改校验。
- 业务系统地址状态按 NetBox 原生 Prefix、IPAddress、IPRange 类型提供选项，IPRange 不再出现容器状态。

- 服务查询与区域矩阵的导航、页面、筛选排序、区域状态及 CSV 导出随界面语言切换，补齐中英文翻译与回归覆盖。

- 统一 NetBox 4.7.2 官方 OCI 摘要，修正 Linux/macOS 与 Windows 构建校验对镜像索引和架构摘要的识别。
- 基线验证尊重自定义生产镜像标签，支持隔离的生产验证镜像；补充 Docker 资源命名与清理规则。

### Added

- 服务查询支持协议和端口升降序；端口按数字排序，URL、分页及 CSV 导出保留当前筛选与排序。

## [1.3.2] - 2026-10-11

### Changed

- README 以 Docker Compose 为部署入口，明确已有运行镜像可跳过构建、项目脚本可选，宿主机无需安装 Python。
- 集中维护镜像、备份与恢复的关键命令及参数，精简重复的离线和 Windows 部署说明。
- 离线源码交付包含已跟踪的完整项目，排除本机配置、密钥和业务数据。
- 生产 Compose 封装合并重复逻辑；回归测试使用独立 Compose 项目并自动清理。

### Fixed

- 备份暂停应用写入并记录兼容性元数据，恢复前校验备份；Windows 备份恢复改用二进制安全的文件复制。

### Notes

- 无新增数据库迁移，与 1.3.1 数据库结构兼容。

## [1.3.1] - 2026-10-02

### Fixed

- 将运行时、开发、生产与离线交付的 NetBox 基线统一升级到 4.7.2，使用官方锁定 OCI digest。
- API 和 XLSX 导入补充对象级权限校验；导入预检不再泄露不可见对象的存在性。
- CSV 导出转义公式前缀；XLSX 导入增加行数与单元格长度上限。
- 回归测试改用独立、固定命名的 Compose 项目，并在结束后自动清理其容器、网络与卷。

### Notes

- 本版本不包含数据库迁移，数据结构与 1.3.0 兼容。

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
