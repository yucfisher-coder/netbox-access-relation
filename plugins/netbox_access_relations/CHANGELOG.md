# Changelog

All notable changes to this project are documented in this file. The format is
based on Keep a Changelog, and releases follow Semantic Versioning.

## [Unreleased]

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
