## MODIFIED Requirements

### Requirement: 显式供应商执行模式

系统 SHALL 提供重启生效的 EXECUTION_MODE 配置，默认 provider 并在配置有效 API 密钥后启用发行入口的供应商执行；显式 local 仍可用，无效值拒绝，沿用配置优先级与冲突规则。

#### Scenario: 本地验收
- **WHEN** 使用 local 模式启动或查询
- **THEN** 不发起供应商或产物网络请求，可进行本地查询及已落盘产物复制。

#### Scenario: 升级和模式切换
- **WHEN** provider 模式读取没有持久供应商执行授权的旧任务或 local 任务
- **THEN** 保留事实与预算但阻断执行并提示未授权；重复提交不补授权。provider 模式新提交在接收事务固定授权，不再二次确认。

#### Scenario: 新安装默认启用
- **WHEN** 新安装填写有效 ZHENZHEN_SEEDANCE_API_KEY 且不显式设置模式，或使用新的默认模板
- **THEN** 启动为 provider，具备供应商调度能力；正式提交新任务即授权自动执行并可能收费，启动和只读检查不自动创建生成任务，不声称上游已探测可用。

#### Scenario: 原配置与升级
- **WHEN** 已安装的 .env 或其他更高优先级配置显式设置 local
- **THEN** 沿用 local，升级不覆写配置、密钥或任务库；解释更改配置并退出全部 Host、确认后端退出再重启的步骤。模式缺失时新默认生效，但仍保护旧任务授权。

#### Scenario: 隔离协议检查
- **WHEN** 在默认 provider 安装中运行本地协议检查
- **THEN** 检查使用独立临时状态和显式 local 配置及占位凭据，不依赖修改用户 .env、Host 或共享任务库，不请求供应商、不提交任务；报告本地协议通过不等于供应商可用。

## ADDED Requirements

### Requirement: Host 与服务统一名称

系统 SHALL 在 Codex Desktop、Claude Desktop、DeepSeek Harness Desktop 的安装配置示例及 MCP 服务身份中使用 `zhenzhen-seedancevideo-mcp`，保留已有命令、API 标识和任务库兼容性。

#### Scenario: 现有名称迁移
- **WHEN** 用户已有 seedance-video 或 zhenzhen-seedance-video 的 Host 配置项
- **THEN** 文档说明手动迁移及避免同一 Host 重复注册；不自动修改配置，不把旧名称的存在误判为独立任务库或供应商 API 名称变更。

#### Scenario: 三种 Host 的新配置
- **WHEN** 用户参照各 Host 示例配置服务
- **THEN** 服务配置名及 DSH 插件 id、serverName 均为统一名称；命令仍使用实际发行入口，所有 Host 同一 Windows 用户共享后端的边界不变。
