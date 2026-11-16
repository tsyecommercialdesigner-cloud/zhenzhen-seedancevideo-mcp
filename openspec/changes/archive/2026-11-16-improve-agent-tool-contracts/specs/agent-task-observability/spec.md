## ADDED Requirements

### Requirement: 安全的字段级参数诊断

系统 SHALL 区分缺必填字段、不支持模型、未知字段和类型错误，提供有界安全字段位置与修正指引；不泄露提示词、素材路径、URL、凭据或原始异常。

#### Scenario: 参数名错误
- **WHEN** 请求使用 model_id 或顶层 ratio
- **THEN** 指明无效字段及正确的 model 或 metadata.ratio，参数诊断阶段标为 validate。

#### Scenario: 敏感字段值
- **WHEN** 参数值包含密钥、提示词或签名 URL
- **THEN** 诊断不回显值，仅返回安全结构信息。

### Requirement: 提示词优化授权范围明确

系统 SHALL 明确优化授权只控制提示词优化，provider 模式正式接收代表供应商执行授权，local 模式接收不授予之后的供应商执行授权；预检不产生任务，保持旧 authorization 字段兼容。

#### Scenario: 默认关闭优化
- **WHEN** 优化默认关闭且预检通过
- **THEN** 显示优化关闭和授权来源，不将其解释为禁止生成。
