# 兼容端点适配器（8.4）

CompatibilityAdapter 是内部组件，当前不会由生产 CLI 自动创建。解析依据四份用户响应与 2026-11-13 的一次 Mini 真实脱敏响应；本轮使用 MockTransport 回放及合成异常变体验证，没有新增真实调用。其他模型真实验收、HTTP 错误契约、退款／迟到结算、尾帧和完整产物集合继续分别跟踪。

## 已接通的路径

- prepare 读取任务接收时固定的有效参数副本，不重算默认值或优化授权。模型／api_id 使用现有注册表；未完成上传的 material_id／local_path 拒绝发送。上传准备可先通过 Scheduler 的 uploads 注入完成替换。
- submit 仅执行一次 POST /v1/video/generations；查询固定 GET /v1/video/generations/{id}。均使用统一 NetworkPolicy 的连接池、Bearer、代理／CA、期限和响应字节限制。适配器明确禁止重定向，不自动改用 /v1/videos，也不读取重定向后的接口响应。
- 查询 ID 只接受1–512位字母、数字、下划线或连字符，拒绝路径、查询串、片段及未知形式；这是一项保守本地安全边界，不宣称上游全部合法 ID 都已穷举。
- HTTP 2xx 只是本地进入解析的传输判断，不保证已创建任务；解析严格核对顶层 id、model、object、status。查询必须与持久化 remote_id 一致。HTTP 错误／网络超时不提供“明确未接单”证据，不重放 POST。
- queued／in_progress／completed／failed 经已有调度状态服务持久化。正常查询不耗失败预算，临时网络失败使用已有持久化预算；非法 JSON、ID不符及未知封装进入待处理。终态矛盾保留原已确认终态及冲突记录。

## 结果、错误和费用

metadata.url 保存为受保护的观察事实，成功但缺URL时保留 succeeded 并报告 RESULT_URL_UNAVAILABLE，不能冒充文件就绪。生成成功不等于下载已完成。

失败时持久化白名单 error_code，查询快照可返回 remote_error_code=video_generation_failed 或 REMOTE_TASK_FAILED；原始 message、源码、签名URL不会被保存为错误消息或透传。现有任务旧观察没有该字段时不编造错误码。

已核实查询封装要求 code=success、data.task_id 匹配已知远端 ID，并核对 data.properties.origin_model_name。data.id 为数值记录 ID，不参与关联；data.status=IN_PROGRESS/SUCCESS 分别归一为 in_progress/completed，data.progress 的百分数字符串转成数值。顶层 code 不能替代任务状态，未知封装／状态拒绝。提交响应同时携带 id/task_id 时必须一致。

SUCCESS 主视频读取 data.result_url；不从内层 content 或任意递归路径补猜。仅此完整查询封装的 data.usage.amount/currency 进入实扣，Decimal 直接从 JSON 数字解析，拒绝字符串金额、布尔值、负数和非有限数。币种保留返回的 ¥ 或三位大写字母，不把 ¥ 改成 CNY。不读内层 token usage、quota、price_estimate。字段缺失不补零、不覆盖此前完整费用；不完整费用记录为 incomplete。畸形费用明确协议错误，不自动修复或臆测。

观察保留 provider_status 原状态，费用记录保留 raw_status 与原响应 SHA-256，任务状态、主视频 URL 和费用在一个 SQLite 事务内提交；任何落账故障全体回滚。终态冲突仅留观察事实，不覆盖终态或费用。重复相同查询不累加金额、不重复费用证据、不推进业务版本。旧四份样例的费用仍不从额外片段猜测。

注入任务库后，适配器从关联 remote_id 的已持久化 completed 观察中提取已规范化的主视频 URL（metadata.url 或 data.result_url），返回主视频引用和 complete=false。下载沿用统一网络策略，不携带 API 凭据；格式取显式 output_format 或 URL 路径的 mp4/mov 扩展名，并校验实际容器。未知格式或冲突明确拒绝。主视频可独立 ready、复制到工作区或绝对路径，但任务保持 partial、artifact_set_status=unverified 和 ARTIFACT_SET_UNVERIFIED，不宣称完整交付，不触发输入素材自动清理。集合标记跨重启保存；重复查询不降级 partial。未注入数据库时仍保留门控。尾帧和完整集合继续待核实，生产 CLI 未启用真实供应商适配器。

## 验证

`tests/test_compatibility_adapter.py` 将实际适配器、统一网络层、SQLite与Scheduler串联，响应由合成传输返回。四份用户fixture保持原始来源；HTTP200为测试传输设定，不是新取得的上游状态码证据。覆盖精确路由、payload授权快照、失败／超时不重提、有限查询重试、ID关联、缺URL、真实脱敏SUCCESS回放、精确费用、重开数据库、事务回滚、未知费用不推测、终态冲突、错误脱敏及产物能力门控。

运行：`uv run --frozen pytest tests/test_compatibility_adapter.py tests/test_provider_response.py tests/test_network.py -q`。真实调用、真实Host验收及Git发布需另行授权，本轮不执行。


主视频协议复验：独立stdio客户端的提交、等待、主视频下载／复制，以及最后客户端退出、发布前后崩溃和下载待处理恢复，见[端到端验证说明](main-video-protocol-validation.md)。此为合成供应商、多进程协议证据；实际Host和供应商仍未验收。


## 2026-11-14 已观察尾帧

同一关联SUCCESS封装中的data.data.content.last_frame_url已作为受保护事实持久化，适配器将其登记为独立JPEG产物，下载、摘要、恢复与复制沿用原服务；响应摘要不暴露签名URL。实测URL后缀及outputType虽为png，字节为JPEG，因此采用.jpg并校验结构，不盲从标签。不支持的图像编码进入待处理；不在本次新增PNG解码或媒体加工。

manifest.complete仍为false：一次Mini任务返回视频和尾帧不能证明完整必需集合或全部模型支持。旧四份响应和缺尾帧响应仍兼容，主视频仍可单独交付；取得两项产物也不自动清理素材。隔离测试见test_provider_response、test_compatibility_adapter与test_artifacts新增尾帧案例。


## 样片ID与独立超分（2026-11-14）

新的contracts-observed证据确认独立zhenzhen-upscaler使用同一IN_PROGRESS/SUCCESS封装、结果及费用路径，原解析器无需改端点。2.5普通模型在已关联SUCCESS中返回data.data.content.draft=true及draft_task_id时，严格要求其等于查询目标ID，再随观察事务持久化；Queries.get/list/wait的快照可返回draft_task_id。缺失不猜测，矛盾ID报DRAFT_TASK_ID_MISMATCH，不自动创建成片、不作为外部账号或有效期核验凭据。

上传视频、超分、样片及两类只读错误有真实脱敏fixture；MockTransport与数据库重开验证均保持隔离。此组件仍不是生产默认启用或真实Host验收证明。


2026-11-14 13.5更新：真实Mini i2v、国内2.5样片及其成片经统一队列/MCP下载复制通过，累计8/10、23.760998/¥。新增已关联NOT_START→queued解析，保留原状态且不允许重提；未观察的SUBMITTED仍拒绝。原Mini任务解析待处理后通过同库重启及显式刷新恢复，未重复POST。三模型完整脱敏响应及持久化回放见generation-queue-observed，详见[专项验收](generation-queue-acceptance.md)。当前61/67、剩余6项，完整集合与其他未知项保持，业务主规范未同步，change未归档。
