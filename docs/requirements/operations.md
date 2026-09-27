# 开发、发布与数据安全

来源基线：R12。状态：已确认。

| ID | 需求 |
|---|---|
| REQ-OPS-001 | 固定 NetBox 4.7.0、netbox-docker 5.1.1、PostgreSQL 18.6 和 Redis 7.4.11 的明确版本或 digest。 |
| REQ-OPS-002 | 开发、测试、恢复和生产数据库相互隔离。 |
| REQ-OPS-003 | 测试覆盖规则、迁移、CRUD/API、权限、事务/并发、浏览器、wheel 安装和恢复；失败阻断发布。 |
| REQ-OPS-004 | 生产使用 wheel 和不可变镜像，不挂源码、不 editable、不联网安装，不启用调试配置。 |
| REQ-OPS-005 | 生产 PostgreSQL 和 media 使用 external、用途和代际明确的命名卷；禁止跨 PostgreSQL 大版本复用数据目录。 |
| REQ-OPS-006 | 升级前在隔离环境恢复备份并验收；生产备份覆盖数据库和 media，生成校验和并定期恢复验证。 |
| REQ-OPS-007 | 密钥运行时注入且不提交；SQL、工作簿、真实业务行和私有分析快照不进入 Git。 |
| REQ-OPS-008 | 禁止把 `docker compose down -v` 作为普通操作。 |
