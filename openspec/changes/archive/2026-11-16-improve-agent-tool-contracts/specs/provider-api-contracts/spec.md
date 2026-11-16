## ADDED Requirements

### Requirement: Agent 请求结构可发现

系统 SHALL 在生成、预检和超分工具的输入 Schema 声明请求字段、类型及嵌套结构，并指引按模型查询适用规则；不将所有模型错误地要求 prompt。

#### Scenario: 多种任务类型
- **WHEN** Agent 发现工具或查询指定模型能力
- **THEN** 可识别 model、seconds、metadata 和素材输入，成片及超分的不同必填条件，以及未核实限制。

#### Scenario: 上下文相关默认值
- **WHEN** Host 按 Schema 组装成片、超分或常规生成请求
- **THEN** 不因联合 Schema 默认值自动注入不适用的音频字段或覆盖共享提示词优化授权；通过文字和预检结果说明适用的默认行为。

### Requirement: 预检说明默认及费用边界

系统 SHALL 说明音频默认值及来源、优化授权的作用域、未知费用和预检不保证接收；保留原字段兼容性，不推导不可靠费用。

#### Scenario: 未显式设置音频
- **WHEN** 常规模型请求省略 generate_audio
- **THEN** 预检显示有效 true 及默认来源，提示提交可能收费且估价未知。
