# 区域矩阵页面验收场景

范围：REQ-MATRIX、REQ-ZONE、REQ-QUERY、REQ-AUTH、REQ-EXP、REQ-STATE。

| ID | 场景 | 预期结果 | 需求 |
|---|---|---|---|
| AC-MATRIX-001 | 一条关系覆盖多个源/目标区域组合 | 进入每个实际组合，但同一单元格只计数一次 | REQ-MATRIX-001～002 |
| AC-MATRIX-002 | 地址区域未设置、未匹配或歧义 | 三种状态分别成行或列，不合并为“其他” | REQ-ZONE-006、REQ-MATRIX-003、REQ-STATE-001 |
| AC-MATRIX-003 | 点击非零单元格 | 进入关系下钻并保留矩阵筛选及源/目标区域 | REQ-MATRIX-004、REQ-QUERY-002 |
| AC-MATRIX-004 | 点击异常区域单元格 | 下钻显示解析状态、原因及可追溯地址/Prefix | REQ-ZONE-006、REQ-MATRIX-004 |
| AC-MATRIX-005 | 点击零值单元格 | 不提供无意义下钻 | REQ-MATRIX-004 |
| AC-MATRIX-006 | 受限用户查看矩阵和下钻 | 聚合前应用权限，计数与下钻对象范围一致 | REQ-AUTH-001～003 |
| AC-MATRIX-007 | 单元格合计大于去重关系总数 | 页面同时显示两种口径并解释差异 | REQ-MATRIX-002 |
| AC-MATRIX-008 | 导出当前矩阵 | CSV 包含区域组合、关系数和筛选条件说明 | REQ-EXP-001、REQ-AUTH-001 |
| AC-MATRIX-009 | 在桌面、中等宽度和窄屏查看筛选区 | 字段分别按四列、两列和单列排列；标签、控件与操作按钮横纵对齐且无截断或重叠 | REQ-MATRIX-005 |
