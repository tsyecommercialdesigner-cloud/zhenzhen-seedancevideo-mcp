# Tasks

## 1. 产物状态与任务查询

- [x] 1.1 在一致的任务快照中派生 `display_stage`：仅远端成功、集合未核实、已登记产物非空且全部 ready 时返回 `downloaded_unverified`；以隔离测试覆盖常规生成、超分、多产物及空集合，确认原 stage、delivery 和集合状态不变。
- [x] 1.2 将展示状态接入任务详情、按 request_key 找回、分页和有界等待；用多客户端隔离测试验证同一版本下结果一致，receiving/not_found 不伪造任务状态，状态变化可唤醒等待。
- [x] 1.3 覆盖未完成、下载失败、文件缺失／删改、放弃和其他异常并存场景；验证不掩盖故障、不自动重新下载或生成、不改变原产物及现有素材清理条件。
- [x] 1.4 用既有状态库夹具及跨 Host 重启测试验证历史任务无需批量迁移即可派生展示状态，重启与重复查询不增版本、不重置预算或触发新副作用；记录实际验证范围。

## 2. 提示分类与异常查询

- [x] 2.1 增加 `advisory_reasons`、`actionable_reasons` 和按任务去重的 `actionable_attention_count`；测试仅已就绪集合未核实、其他异常并存、未全部就绪及未知原因的保守分类。
- [x] 2.2 增加 `actionable_only` 分页筛选与筛选绑定游标；测试多 Host、分页及游标误用，并验证原 `attention`、`needs_attention` 和 `attention_count` 兼容不变。
- [x] 2.3 根据已登记产物与实际异常修正 `allowed_actions`：全部已就绪时提供产物查询／核验／复制指引，不仅因 partial 建议无目标下载重试；隔离测试确认失败或可恢复下载仍有恢复动作。
- [x] 2.4 更新 Agent 工具说明，解释新展示状态、提示与异常分类、旧字段兼容及素材保留；检查文档示例与工具实际响应一致。

## 3. 业务诊断

- [x] 3.1 为 `PROMPT_AUTHORIZATION_REQUIRED` 增加正确阶段、摘要和动作，测试用户明确同意后的单次 `allow_once` 与共享偏好路径，以及不自动设置共享授权。
- [x] 3.2 为 `TASK_NOT_FOUND` 增加本地任务不存在的诊断与按原 request_key 找回指引；测试查询和管理工具，不将其推断为远端不存在或自动重提。
- [x] 3.3 为成片请求中不适用的 `prompt`、`seconds`、`images` 返回安全的已知字段位置；测试多字段及未知字段，保持稳定错误码且不回显输入值。
- [x] 3.4 测试诊断记录和按 ID 反查的一致性、长度限制与旧记录回退；注入密钥、提示词、路径、签名 URL 和异常文本，确认均不泄露，并更新诊断使用说明。
- [x] 3.5 区分可信业务异常来源与未知异常，即使未知异常文本或伪造 code 恰好等于已知错误码也安全兜底；为已公开业务错误码提供与外层一致的脱敏诊断并验证兼容性。
- [x] 3.6 为工具业务错误设置正确的诊断阶段；覆盖清理操作拒绝及其他受影响阶段，保证错误码、阶段和按 ID 反查一致。

## 4. 默认 provider 与隔离检查

- [x] 4.1 更新配置代码和 `.env.example` 为默认 provider；测试新安装、缺失模式、显式 local／provider、无效模式与安装目录 `.env` 优先级，并验证缺失密钥明确拒绝、未探测时不声称上游可用。
- [x] 4.2 用隔离任务库及合成适配器测试升级与重启：显式 local 保持不变，旧 local／未授权任务不自动派发或因重复 request_key 获授权；已授权任务按原规则恢复，新 provider 接收固定执行授权。
- [x] 4.3 改造发行包协议检查，使用独立临时配置根、local 模式、占位凭据和临时状态，排除继承的业务密钥及冲突变量；测试真实安装目录存在 provider `.env` 时仍不接入真实后端、不修改配置或任务库、不发起供应商请求。
- [x] 4.4 更新安装、升级、配置与排障说明：填写 API 密钥后默认 provider 可提交并可能收费；说明显式 local 保留、配置优先级、全部 Host 退出后重启及已授权任务恢复；校验本地协议检查示例与实际入口。

## 5. Host 命名

- [x] 5.1 将 MCP initialize 服务名称更新为 `zhenzhen-seedancevideo-mcp`；通过隔离 stdio 协议测试核对名称，并验证启动命令、`seedance-video` API 标识、模型 ID 和共享任务库身份不变。
- [x] 5.2 统一 Codex Desktop、Claude Desktop 和 DeepSeek Harness Desktop 配置示例，包含 DSH 的插件 id 和 serverName；检查 TOML、JSON、YAML 语法及入口参数，不修改用户实际 Host 配置。
- [x] 5.3 补充旧 `seedance-video`／`zhenzhen-seedance-video` 配置项的手动迁移与避免重复注册说明；核对命名变化不被描述为 API 标识或任务库变更，实际 Host 适配范围保留未验证状态。

## 6. 跨功能隔离验收与收尾

- [x] 6.1 使用合成适配器和隔离 MCP 客户端完成 provider 默认配置、任务提交、已发现产物就绪但集合未知、跨 Host 查询与复制的端到端测试；断言未触发真实供应商、未错误清理素材或重提任务。
- [x] 6.2 运行适用的全量隔离测试、`uv run --frozen ruff check .`、`uv run --frozen ruff format --check .`、构建及 `openspec validate "clarify-artifact-status-and-diagnostics" --type change --strict`；记录命令、结果、版本及未覆盖范围。
- [x] 6.3 测试前扫描并记录本任务临时资源，测试结束或失败后保留最小脱敏证据、清理专属目录并复扫；记录遗留处理。实际 Host 新 Schema 展示、供应商完整产物集合及真实供应商调用继续标记为未验证。
