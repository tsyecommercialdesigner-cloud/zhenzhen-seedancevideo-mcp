# Proposal

## Why

供应商生成成功且已发现产物全部落盘时，集合仍待核实的任务长期显示 downloading、partial，Agent 容易误认为仍在下载；业务授权和任务查询错误的诊断又可能退化为内部错误，误导处理。

## What Changes

- 为已发现产物就绪、完整集合未知提供明确的附加展示状态和分类，保留旧 stage、delivery、待核实标记和清理边界。
- 区分需要用户处理的故障与集合待核实提示，兼容已有异常列表与计数；对既有任务和跨 Host 重启提供一致查询。
- 为已确认的优化授权缺失、任务不存在及不适用字段提供脱敏、可操作的诊断；保持单次和共享授权的区别。
- 三款 Host 的配置示例和 MCP 服务标识统一为 `zhenzhen-seedancevideo-mcp`，提供旧名称迁移说明，不自动修改现有 Host 配置。
- 默认启用 provider；用户配置 API 密钥后即可接入并提交，保留显式 local 和无生成副作用的本地协议检查。
- 通过隔离验证和文档明确范围；供应商完整集合、实际 Host 新 Schema 表现仍待核实。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `video-artifact-delivery`：表达已发现产物就绪、集合未知，保留交付和清理约束。
- `agent-task-observability`：新增分类展示和可信业务错误诊断。
- `runtime-configuration`：默认 provider、原有配置与历史任务的兼容，以及 Host 统一命名和安全的检查方式。

## Impact

影响任务查询、等待、异常列表、服务状态、诊断、配置默认值、安装手册和协议检查。新增响应字段，不新增需要数据库迁移的任务阶段；默认 provider 是执行行为变更，正式提交可能产生费用。保留旧任务授权边界和已有显式 local 配置；不自动改写用户 Host、`.env` 或历史任务。实际供应商调用、强制确认集合、自动清理素材和全量模型实测不在本次规划范围。
