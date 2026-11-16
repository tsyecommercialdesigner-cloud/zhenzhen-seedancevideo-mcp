## ADDED Requirements

### Requirement: 不确定提示与可处理异常分开展示

系统 SHALL 保留现有 attention、needs_attention 筛选和 attention_count 语义，附加区分集合未核实提示与可处理异常的摘要，并允许 Agent 分页筛选可处理异常。

#### Scenario: 仅集合未知
- **WHEN** 任务仅有 ARTIFACT_SET_UNVERIFIED 且已发现产物均已就绪
- **THEN** 保留原异常记录及计数，同时将其列为非故障提示，新的可处理异常计数不包含此任务，指引查询已就绪产物而非反复重试下载。

#### Scenario: 同时存在其他异常
- **WHEN** 已发现产物均已就绪，任务同时有集合未核实及其他待处理原因
- **THEN** 集合未知单独列为提示，其他原因保持可处理、可筛选及计数；不因集合提示掩盖存储、清理、下载或状态冲突。

#### Scenario: 产物尚未全部就绪
- **WHEN** 集合未核实且没有已登记产物或任一已登记产物尚未 ready
- **THEN** 不按已就绪提示降级此任务；保留现有异常的可处理性和下载恢复指引。

#### Scenario: 旧客户端与分页
- **WHEN** 旧客户端按 needs_attention 分页或根据旧 attention_count 工作
- **THEN** 原筛选和计数不变；新增筛选使用有界分页、游标绑定筛选条件，不承诺跨页快照。

### Requirement: 业务错误保留可执行诊断

系统 SHALL 对已知业务错误输出与外层错误一致的稳定诊断码、正确阶段和安全的后续动作；未知异常仍使用脱敏兜底，不泄露原始请求、异常或敏感数据。

#### Scenario: 提示词优化授权缺失
- **WHEN** 提示词优化请求为 true 但没有有效授权
- **THEN** 返回 PROMPT_AUTHORIZATION_REQUIRED 的诊断并说明先取得用户明确同意；区分 allow_once 单次授权与查询及设置共享偏好，不自动开启偏好或暗示必须永久授权。

#### Scenario: 查询不存在任务
- **WHEN** 根据本地 task_id 查询或管理不存在的任务
- **THEN** 返回 TASK_NOT_FOUND 的诊断及安全找回指引；不显示 INTERNAL_ERROR，不暗示上游任务不存在或自动重新生成。

#### Scenario: 不适用的已知字段
- **WHEN** 成片请求包含不适用的 prompt、seconds 或 images
- **THEN** 安全指出一个实际不适用的已知字段及按模型查询能力的动作，不回显值；任意未知字段不无条件原样输出。

#### Scenario: 诊断查询与隐私
- **WHEN** Agent 根据诊断 ID 查询业务错误
- **THEN** 返回同一有界脱敏诊断和动作，密钥、提示词、签名 URL 和原始堆栈均不出现；不承诺提供原始日志或额外未保存事实。
