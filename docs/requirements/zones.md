# 安全区域与解析

来源基线：R02。状态：已确认。

| ID | 需求 |
|---|---|
| REQ-ZONE-001 | 安全区域使用 NetBox Prefix 的 `security_zone` 自定义字段，不建立插件内独立区域表。 |
| REQ-ZONE-002 | 字段不存在时可按已确认定义创建；已有定义不兼容时停止，不覆盖。 |
| REQ-ZONE-003 | Prefix 可直接设置一个区域；子 Prefix 继承最近的已设置祖先。 |
| REQ-ZONE-004 | IPAddress 从同 VRF 的最具体覆盖 Prefix 继承区域。 |
| REQ-ZONE-005 | IPRange 只有被同一区域完整覆盖时才继承区域。 |
| REQ-ZONE-006 | 未设置、未匹配、跨区域或同等候选歧义必须明确显示；不得从 Site、描述或工作簿区域猜测。 |

页面如何呈现区域证据由对应 `ui/` 文件定义；矩阵如何使用解析结果见
`query-presentation.md`，不得在这些文件中改变本文件的解析语义。
