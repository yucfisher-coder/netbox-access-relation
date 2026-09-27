# 发布与恢复验收场景

范围：REQ-SCOPE、REQ-OPS。

| ID | 场景 | 预期结果 | 需求 |
|---|---|---|---|
| AC-REL-001 | 检查构建输入 | 上游、数据库和缓存版本或 digest 与锁定文件一致 | REQ-OPS-001 |
| AC-REL-002 | 运行完整发布验证 | 需求规定的测试类别全部执行，任一失败阻断发布 | REQ-OPS-003 |
| AC-REL-003 | 在无源码和无网络环境安装生产制品 | wheel 和不可变镜像可完成安装启动，未启用调试或 editable | REQ-OPS-004 |
| AC-REL-004 | 检查生产卷 | PostgreSQL 与 media 使用用途和代际明确的 external 卷 | REQ-OPS-005 |
| AC-REL-005 | PostgreSQL 跨大版本升级 | 使用新数据目录，不复用旧主版本目录 | REQ-OPS-005 |
| AC-REL-006 | 在隔离环境恢复生产备份 | 数据库和 media 恢复、校验和及验收通过 | REQ-OPS-002、REQ-OPS-006 |
| AC-REL-007 | 检查制品和 Git 内容 | 不含密钥、SQL、工作簿、真实业务行或私有分析快照 | REQ-OPS-007 |
| AC-REL-008 | 执行普通停止或清理流程 | 不调用 `docker compose down -v`，不删除持久卷 | REQ-OPS-008 |
