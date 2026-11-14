# Zhenzhen Seedance Video MCP

Windows 本地 stdio MCP Server，同一 Windows 用户的多个 Agent Host 共享任务后端、持久化队列与产物。

目标版本 **0.1.0.dev1**，预期标签 `v0.1.0.dev1`；发布和最终提交待确认。本地生命周期、任务管理和文件交付已有隔离验证，供应商 SUCCESS／实扣及代表性真实闭环已有独立证据。默认发行入口为 local，显式配置 provider 并重启后新提交才可付费执行；旧 local 任务不自动补授权。已有干净 Windows 安装及实际 Host 跨 Host 主视频交付证据；完整产物集合仍待核实。Job 生命周期调查已关闭，启动器结束可能连带终止后端，兼容性限制尚未修复。具体范围及未验证项见[验证记录](docs/verification-add-local-video-generation-service.md)。

- 安装、配置、升级和回滚：[MANUAL.md](MANUAL.md)
- 工具及恢复：[Agent 工具手册](docs/agent-tools.md)
- 验证范围：[实施记录](docs/implementation-progress.md)
- 仓库：https://github.com/tsyecommercialdesigner-cloud/zhenzhen-seedancevideo-mcp

技术栈：uv 管理 Python 3.12.14、MCP SDK 2.3.0、httpx2 2.16.0。仅 Windows 正式支持；本地 stdio，不提供远程 HTTP MCP 服务。当前无 Resources 或 Prompts，能力由 Tools 提供。

开发检查：`uv run --frozen pytest`、`uv run --frozen ruff check .`、`uv run --frozen ruff format --check .`、`uv build`。启动及工具调用不安装或升级依赖。local模式不调用供应商；provider模式的新正式提交授权自动执行完整闭环。详见[执行保护](docs/production-entry-validation.md)。
