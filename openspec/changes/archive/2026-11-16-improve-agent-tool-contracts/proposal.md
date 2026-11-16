# Proposal

## Why

Agent 无法从工具输入 Schema 发现请求字段，参数错误的诊断不够具体，容易反复试错和误解授权及费用。

## What Changes

- 公开生成和独立超分的结构化输入及模型能力查询指引。
- 提供脱敏、字段级参数诊断，区分缺字段和模型不支持。
- 澄清提示词优化授权、音频默认来源、价格未知及预检边界，保留已有字段兼容性。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `provider-api-contracts`: 公开请求结构、默认值和预检边界。
- `agent-task-observability`: 参数诊断和授权、费用语义。

## Impact

MCP 工具 Schema、参数校验、诊断及文档。保持供应商契约、生成授权、计费和默认行为不变，不调用真实供应商。
