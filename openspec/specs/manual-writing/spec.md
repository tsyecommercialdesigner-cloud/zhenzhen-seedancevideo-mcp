# manual-writing Specification

## Purpose

为可复用 MCP Server 成员手册定义内容、安装、配置及验收要求，保证说明与当前实现、OpenSpec 和交付证据一致，不把示例中的目标或特定项目事实误写为通用能力。

详细实施说明见 [guide.md](guide.md)。

## Requirements

### Requirement: 文档职责与结构
项目 SHALL 以 README 提供概述和安装入口，以 MANUAL 覆盖环境、初始化、可用性测试、客户端配置、排障、文件、资源、功能、注意事项和 FAQ；详细规则单一维护。

#### Scenario: 文档职责与结构验收
- **WHEN** 项目缺少某项能力
- **THEN** 明确不适用、未实现或未验证，不虚构操作或把目标写为事实。

### Requirement: 参数与可复制示例
项目 SHALL 从实际仓库、代码、锁与验证记录填写版本、完整 SHA、入口、服务名、凭据字段和兼容范围；通用模板用明确占位符，消费项目手册提供完整可复制命令。

#### Scenario: 参数与可复制示例验收
- **WHEN** 参数来自用户或操作具有副作用
- **THEN** 说明输入方式、前置条件、运行环境、预期结果、失败处理及授权边界，不嵌入秘密或编造值。

### Requirement: 安装与日常启动
项目 SHALL 默认从实际 GitHub 仓库获取 CI 通过的发布版本，Windows 默认 D:\MCP\<project_name>；保持项目目录原名，锁定安装及必要构建，日常启动复用环境。

#### Scenario: 安装与日常启动验收
- **WHEN** 安装目录或入口变更
- **THEN** 同步安装、启动、Host 和 .env 示例；Python 使用 uv --directory 与 --no-sync，Node 使用实际入口绝对路径，不依赖 Host cwd。

### Requirement: 凭据来源
项目 SHALL 固定读取实际项目根 .env，逐字段按文件、进程、Windows 当前用户环境的顺序仅在缺失时回退；只交付空密钥 .env.example。

#### Scenario: 凭据来源验收
- **WHEN** 字段为空、非法、重复或文件读取解析失败
- **THEN** 报错且不回退旧密钥；升级保留用户 .env 及权限，后端密钥与 Host 认证分别说明。

### Requirement: 本地 Host 适配
项目 SHALL 成员手册仅提供本地 stdio 接入，按实际支持的 Host 提供配置片段和保留式合并说明；DSH 覆盖适用的 web、desktop、multica profile。

#### Scenario: 本地 Host 适配验收
- **WHEN** 配置已有服务或某 Host 不支持能力
- **THEN** 保留无关配置并避免重复实例，明确不适用；沿用本模板不列 Host 配置目录及快捷打开命令的范围。

### Requirement: 协议与业务说明
项目 SHALL 依据实现和实际发现描述 Tools、Resources、Prompts、参数、错误、权限、费用及适用的超时取消幂等恢复行为。

#### Scenario: 协议与业务说明验收
- **WHEN** 仅模板解析或替身检查通过
- **THEN** 不得据此宣称协议、真实 Host 或供应商验收通过；按实际版本分别记录结果。

### Requirement: 升级回滚与可选交付
项目 SHALL 记录版本并保护用户配置和私有数据，切换后重新锁定安装、构建和验证；数据恢复按实际兼容性处理，ZIP 仅明确需要时交付。

#### Scenario: 升级回滚与可选交付验收
- **WHEN** 制作成员 ZIP
- **THEN** 验证唯一 <project_name>/ 顶层目录及白名单，直接解压到 D:\MCP 形成项目目录，排除秘密及开发资料。

### Requirement: 维护与验收证据
项目 SHALL 随变更核对主规范、实现、链接和示例，按影响执行适用验证，报告通过、失败、不适用及未验证范围。

#### Scenario: 维护与验收证据验收
- **WHEN** 修改手册或无法执行实际验收
- **THEN** 验证可解析示例并记录限制，不擅自修改用户 Host 或发起收费操作。
