# 供应商契约核实记录

2026-11-14本轮契约复核完成：按原完成判断交付1.2错误/证据映射与未知回退、1.5逐模型26行差异和来源台账、1.6已知不符拒绝/未知提示规则；修复实际MCP预检、接收事务与派发前未接入本地样片事实的问题，重新关闭6.3。全量546项隔离测试通过，当前65/67，剩余13.1干净Windows与13.3实际Agent Host验收。调查完成不等于供应商未知规则获证；详见docs/contract-review-closure.md及docs/model-contract-audit.json。本轮0次供应商请求、0次收费；历史13次，当前窗口5/10、余5，实扣47.020240/¥未变。未提交或推送Git，业务主规范未同步、change未归档。

以下续记保留各阶段状态；当前状态以上述复核为准。

## 当前剩余契约证据映射（2026-11-14）

单次优化补充：Mini t2v在4秒480p下enhance_prompt=true、MCP allow_once=true的统一队列真实闭环通过，实扣0.8028/¥，响应见optimization-queue-observed。发送参数、single_allow授权、前后不变偏好与后续default_false预检均有证据；不推导优化内部行为或质量提升。13.4最小矩阵完成，1.2/1.5/1.6规则性未知不受这一次成功影响。

Fast/Standard补充：global Fast i2v与国内2.0 Standard multi分别使用既有JPEG、JPEG+MP4在4秒480p且优化/音频关闭下通过真实队列闭环；响应见fast-multi-queue-observed。两者已有IN_PROGRESS/SUCCESS与data.usage完整证据，多模态另观察到NOT_START；费用分别1.504578/¥、2.14038/¥。3次上传引用与生成payload逐项一致。不从这两个单配置成功推导全时长枚举、seed范围、音频限制或2.5别名规则；1.2/1.5/1.6继续未完成。

国际版补充：global 2.5 t2v样片及对应成片现已在统一队列实测成功，完整响应见global-queue-observed，实际费用分别2.877682/¥、15.933802/¥。同账号/同global区域刚完成样片可关联成功；data.data.content.draft_task_id、data.result_url和data.usage沿用已确认路径。本次成片显式mp4，不能填补默认格式、7天起算、外部账号核验缺口。新增2次收费提交及26次查询，没有上传或错误探测；本次窗口2/10、余8，历史共10次。1.2/1.5/1.6保持未完成。

本节是当前状态；下方按日期保留调查历史，其中“尚无真实响应”等描述仅表示当时状态。此次只核对已有完整脱敏响应、账本和隔离测试，没有新增供应商请求。

| 任务/分支 | 可确认的已有证据 | 不能推出的结论及保守处理 |
| --- | --- | --- |
| 1.2 查询鉴权 | contracts-observed中的未鉴权GET返回401/error | 不能证明POST未接单；保留已有任务ID，不自动重提 |
| 1.2 查询缺失 | 同目录不存在ID的GET返回400/task_not_exist/data=null | 不等于远端生成失败、退款或确认未创建；查询错误进入有限预算/待处理 |
| 1.2 任务失败 | user-supplied/query-failed.json的failed/error | 是用户提供的任务终态样例，不是HTTP参数拒绝实测；不能推广为所有权限/额度错误 |
| 1.2 排队/成功 | generation-queue-observed的NOT_START、IN_PROGRESS、SUCCESS；四份顶层样例继续兼容 | NOT_START已关联远端ID，不能释放占位或重提；重复成功回放测试不证明长期终态稳定性 |
| 1.2 未明错误 | 尚缺兼容端点参数拒绝、权限、429/Retry-After、5xx完整记录 | HTTP状态不单独证明未接单；提交结果不明显式处理，查询有限重试；不人为制造限流 |
| 1.5 2.0时长 | 用户模型页排版有歧义；Mini t2v/i2v实际4秒请求成功 | 只确认该输入成功；4–15整段仍暂定，不能推广到Fast/Standard全枚举 |
| 1.5 seed | 用户页number；既有收费请求未测seed | 整数性/范围/默认仍未知；不能套用其他端点的-1..2147483647 |
| 1.5 媒体 | Mini i2v既有单张JPEG成功，超分既有MP4成功 | 未测2.0 multi音视频限制、国内Fast音频例外、2.5图片大小；单文件成功不能推导上限 |
| 1.5 别名组合 | 已批准canonical metadata.content入口；各模型条目见验收矩阵 | 未证明简写/混合别名的供应商合并顺序；继续拒绝混入，不扩大入口 |
| 1.6 样片ID | contracts-observed和generation-queue-observed：data.data.content.draft=true及draft_task_id；国内成片引用该已完成样片成功 | 已实现ID持久化与本地查询；不证明存在外部样片身份核验接口 |
| 1.6 身份/期限 | 同配置账号、同国内区域、刚完成样片→成片的实际成功链 | 不证明跨账号/跨区域拒绝或7天从创建/完成何时起算；已知不符拒绝、未知提示，不伪称已验证 |
| 1.6 格式 | 成片显式output_format=mp4，下载实际MP4/HEVC | 省略时默认及mov仍未验证；不补写推测默认 |

1.2、1.5、1.6保持未完成。剩余最小外部证据为：兼容端点错误的HTTP状态/相关头/完整脱敏JSON与是否创建的明确说明；上述逐模型参数约束的明确适用范围；样片有效期起算、外部核验方式与省略格式说明。不重复索取已提供的四份响应、SUCCESS/usage、尾帧路径、国内样片ID和显式mp4成功样例。两次剩余收费额度不能可靠解决这些规则性问题。

## 2026-11-13 调查

来源：[供应商公开 llms 文档](https://api.seedance.nz/docs/llms.txt)。本次只读取公开文档，没有上传素材、提交生成或查询真实任务。下载内容的 SHA-256 为 `2ABC0CD064B2203F8C8BC2D4FA8F60E089E02D4B8093A865508A1E9F89181B8A`；全文仅在被忽略的 `.cache/seedance-llms.txt` 供本地核对，不作为仓库发布文件。在线文档会更新，行号仅对应该快照。

| 任务 | 核查位置 | 本次结论与后续证据 |
| --- | --- | --- |
| 1.1 兼容端点响应 | 公开文档调查及随后用户提供的四份完整 JSON | 提交 queued、查询 in_progress/completed/failed 主链路结构已获用户契约证据；SUCCESS 与 data.usage 完整组合响应仍待核实，任务整体保持未完成，不借用其他端点封装。 |
| 1.4 上传 | 上传专节（556 行起） | 找到独立 multipart 上传示例和返回字段；仍需整理证据 fixture、限制适用性与过期语义，本项未勾选。 |
| 其余核实项 | 尚未完成逐项调查 | 继续沿用已批准 specs 中的待核实标记，不据本次下载宣称已核实。 |

2026-11-13 用户补充了提交后 queued 的完整 JSON，已保存为 `tests/fixtures/provider/user-supplied/submit-queued.json`，来源与限制见同目录 README。样例为 seedance-2.0-mini-t2v，顶层 id 为任务标识、status 为 queued，另含 object、model、progress 和 created_at；未提供 HTTP 状态码、响应头或字段必填性保证。不将其扩展成所有查询响应的解析结构。

同日用户又提供查询的处理中、成功和失败 JSON，已保存为同目录的 `query-in-progress.json`、`query-completed.json`、`query-failed.json`。字段证据如下：

| 路径／事实 | 样例 | 使用边界 |
| --- | --- | --- |
| 顶层 id、model、object | 四份样例 | id 关联请求任务；样例 object=video、model=seedance-2.0-mini-t2v，不代表所有模型均已实测 |
| 顶层 status | 四份样例 | queued、in_progress、completed、failed；不要以 code 或 progress 替代任务状态 |
| metadata.url | 处理中／成功 | 处理中为空字符串，成功含主视频签名 URL；不将空值作为可下载产物，默认响应与日志不暴露签名 |
| error.code、error.message | 失败 | video_generation_failed 与消息位于 error 对象；消息仍是不可信数据，按脱敏和有界诊断规则处理 |
| progress | 四份样例 | 0、50、100 是已提供值；失败也为 100，不说明成功，也不据样例推定完整取值范围 |
| created_at、completed_at | 提交／处理中／成功 | 失败样例没有这些字段，不能要求每次响应必有；时间单位等约束未额外确认 |

仍需核实 SUCCESS 及实际费用 data.usage 与任务 ID、产物字段共存时的完整响应；此前费用片段只证明费用字段语义。HTTP 参数拒绝／鉴权／限流等错误及状态码归任务 1.2，不能从 failed 任务响应推导。当前样例不含费用应记为未返回，不当作零，也不因此阻塞已确认成功的视频下载。

目前有四份用户提供的契约 fixtures，没有本项目实际请求取得的供应商响应，也没有将合成测试数据标成供应商证据。常规主链路字段已可据样例开展解析与隔离验证；任务 1.1 的剩余封装核实和任务 8.4 的完整验收仍不能勾选，不再把全部查询结构笼统标成未知。真实闭环另需满足既定契约和费用授权条件。

## 已实现的隔离解析边界

`provider_response.decode_response` 是纯解析器，未接入真实网络执行器。它限制响应字节数、拒绝重复 JSON 键和非有限数值、关联预期模型与远端 ID，按顶层 status 判断结果，不递归搜索 ID、不按 progress=100 判成功。失败时间字段可缺省；成功 URL 缺失或无效时保留 succeeded 事实并标记 RESULT_URL_UNAVAILABLE。签名 URL 不出现在 Observation 的 repr 中，下载时仍须实施独立网络安全检查。

SUCCESS 封装返回 SUCCESS_ENVELOPE_UNVERIFIED；不解码或猜测 data.usage。`charges.ActualCharge` 仅供以后核实后的适配器输入，当前只做合成数据的 Decimal 持久化验证，不能据其存在宣称费用接入完成。

`tests/test_provider_response.py` 覆盖四份用户样例和明确标注的合成异常，并通过注册的本地 HTTP 假服务收发实际字节。该测试中的 HTTP 200 是模拟传输条件，不是供应商状态码证据；依次送入成功和失败仅测试两种解析分支，不代表上游会这样变更终态。禁止真实网络的 fixture 始终生效。


## 第 1 组离线复核与上传证据（2026-11-13）

本轮只复核上文 SHA-256 对应的本地历史快照及用户对话契约，不重新访问网站，不调用供应商。文档可能已更新，以下不是当前在线文档或实际响应验证。上传专节原始 JSON 已提取到 tests/fixtures/provider/documented/upload-success.json，来源说明见同目录 README；没有将合成 HTTP 数据混入该证据目录。

| 任务 | 可定位的依据与复核结果 | 保留的未知／依赖 |
| --- | --- | --- |
| 1.1 | 用户四份 JSON，见前文逐字段表 | SUCCESS 与完整 data.usage 组合继续待核实；不改解析门控，8.4 保持未完成 |
| 1.2 | 快照上传专节 556–589 行提到上传超限 429；供应商其他模型的错误和 Retry-After 说明不属于 Seedance 兼容端点 | 无该端点完整错误封装、Retry-After、终态稳定性证据；HTTP 状态仅指导保护，不能证明生成未创建，本项未完成 |
| 1.3 | 对快照全文检索 idempot/幂等、历史、取消/cancel、账号、区域；逐项适用性见下表 | 调查已完成；全部条件能力保持未核实，不等于供应商确定不支持 |
| 1.4 | 上传专节明确 POST /v1/files/upload、Bearer、multipart file、示例 HTTP 200，完整顶层 url/file_type/size/expires_in | 文档核心响应证据已具备；精确过期起算、逐模型限额适用性和上游读取时机仍未知。调查记录完成不代表生产上传或真实验收完成 |
| 1.5 | 快照 /v1/videos 专节 366–409 行：4–15、seed -1..2147483647、2.0 图片30MB／视频50MB／音频50MB及国内Fast15MB候选信息 | 同段 i2v prompt 可选、seconds=-1 与用户兼容端点要求冲突，不搬运默认值、seed 范围或媒体限制到正式规则；2.5 图片及别名组合继续待核实 |
| 1.6 | 用户提供两区域样片／成片页面：本人、同区域、完成、7天、draft_task_id；mp4/mov 可选 | 7天起算点、外部样片核验、查询完整层级、默认格式没有充分证据；保留已知不符拒绝和未知提示，不创建自动链 |
| 1.7 | 用户 completed 样例给出 metadata.url；上传专节要求输入 URL 在执行期间可访问 | 输入 URL 期限不能充当输出期限；尾帧必需性、主视频下载鉴权、校验、刷新、续传仍待核实，ETag 不作摘要 |
| 1.8 | 用户独立超分页面及快照 518–552 行说明 MP4、约10分钟、目标分辨率及内部计费文字 | 完整兼容端点成功响应、精确上限、price-preview 调用职责仍未知；不推导费用、不新增估价／钱包请求 |

### 条件能力调查（1.3）

| 能力 | 本次证据适用性判断 | 启用条件／当前行为 |
| --- | --- | --- |
| 上游幂等 | 没有找到针对这两个 Seedance 兼容端点的幂等键保证 | 须取得明确键、作用域、重复请求和错误语义证据；当前仅本地 request_key 去重 |
| 历史反查 | 文档中的其他模型历史／任务接口不能视为 Seedance 提交反查 | 须能可靠关联账号、模型和原提交意图；当前 submission_lookup=false |
| 请求关联 | 顶层 id 是已返回 ID；其他 V2 接口的 X-Task-Id 不能套用 | 无 ID 时保持未知，不允许 Agent 任意绑定 ID 或声明已核实来重提 |
| 取消 | 快照有 MiniMax-H3 DELETE、Suno 等其他服务取消说明 | 不是 Seedance 取消契约；remote_cancel=false，未找到不写成“不支持” |
| 同账号识别 | 本人样片约束不提供账号识别端点或令牌主体比较证据 | account_identity=false；换钥接续不得仅凭调用方声明解锁 |
| 端点身份 | 固定 api.seedance.nz、固定兼容路径与模型区域为已知连接配置 | 不能据域名相同证明账号相同；跨账号／端点不盲目接管，缺可靠身份校验时继续门控 |

### 上传字段与边界（1.4）

- 上传请求字段为 file；图片 JPG/JPEG/PNG/WEBP、音频 MP3/WAV/FLAC、视频 MP4/AVI/MOV/MKV 是上传端点文档格式，不等于每个视频模型都接收。
- 单文件50MB、链接24小时、每令牌每分钟30次／每天10000次是快照文档口径。MB 的十进制／二进制解释、跨模型适用性及限流准确响应未知，不写成实测硬保证。
- HTTP 200 示例完整顶层字段：url 为临时引用、file_type 为 image、size 为3490、expires_in 为86400。其他媒体类型枚举由文档分类得到，尚无真实上传响应验证；未知字段不搜索嵌套 URL。
- expires_in 是提供的相对期限信息；缺失记未知，不默认补86400。不确认从请求开始、服务接收或响应生成起算；不由客户端接收时间推导保证可用至某时刻。
- “整个执行期间保持可访问”是输入要求，并不说明供应商何时下载或缓存；不能保证排队后一定读取成功，不能因链接过期重提已可能接单的生成。

### 已交付单次上传组件（8.3 部分）

uploads.upload_once 通过统一 NetworkPolicy 发送一次 multipart 请求，仅接受调用方持有的锁定二进制句柄，核对稳定摘要和大小；不发送本地路径／原文件名，不自行打开任意路径。响应有字节上限、重复键／非有限值拒绝、URL／大小／类型核对、敏感 URL repr 隐藏。上传失败或重定向拒绝不会产生生成 POST，也不会自动重试；可用格式与模型校验仍分开。

尚未接入生产后端；调用方素材登记／读取租约、uploads 表持久化、有限重试预算与退避、未提交过期重传、重启接续及请求素材位置替换仍须完成并验证，因此 8.3 保持未勾选。此次证据核实不放开真实供应商调用；SUCCESS 和费用完整响应仍待核实。


## 上传持久化实现续记（8.3）

已新增 UploadService、Scheduler 准备／提交事务复核和内部后端注入点；接收事件固定后缀，uploads 与 attempts 保存引用、预算、退避和逐次意图，无 schema 迁移。重启预算、过期同副本重传、已提交未知不重提和清理取消读取使用合成适配器隔离验证，详见 upload-preparation.md 和 implementation-progress.md。上节“尚未接线”是前一轮交付状态；本轮完成内部接线，不启用生产供应商生成适配器。契约证据范围不扩大，SUCCESS／完整费用仍待核实。


## 四份样例的提交／查询接线（8.4 部分）

CompatibilityAdapter 已将固定兼容路径、统一网络与 decode_response 接入 Scheduler，并用四份用户fixture及合成异常隔离验证。实际代码不切换/v1/videos，也拒绝API重定向；提交错误不构造未创建证明，查询关联持久化ID。失败白名单错误码进入观察事实及查询摘要，原始错误消息不透传。详见 compatibility-adapter.md。

本轮没有新增上游证据；SUCCESS、data.usage完整响应及HTTP错误语义继续待核实。8.4仍未勾选，生产默认不创建本适配器。完整产物集合门控不等于费用阻塞：已确认completed事实保留，artifact集合未核实时单独待处理。


## 2026-11-13 主视频引用与部分交付

已确认的 metadata.url 可通过内部 CompatibilityAdapter（注入任务库）接通主视频下载、持久化与复制。任务查询新增 artifact_set_status；完整集合未知时为 unverified，已就绪主视频可单独交付，任务保持 partial，保留 ARTIFACT_SET_UNVERIFIED 和输入托管副本。显式放弃仍按既有规则清理素材。测试 tests/test_main_video_delivery.py 使用合成传输覆盖下载、复制、403恢复、数据库重开、重复查询、格式和引用关联以及清理协调。四份样例仍是契约来源；尾帧／完整集合、SUCCESS、费用完整响应待核实，无真实调用证据。


## 2026-11-13 第1项真实SUCCESS／费用完整取证

用户明确允许最多10次收费测试，限最短允许时长与最低分辨率，覆盖第1项证据获取；此次专项授权覆盖必要查询，不等于原P01–P09矩阵全部获准。本轮使用用户级ZHENZHEN_SEEDANCE_API_KEY，通过既有NetworkPolicy固定兼容路径，不改变生产适配器或日常任务库。

仅1次POST seedance-2.0-mini-t2v：seconds="4"、480p、1:1、enhance_prompt=false、generate_audio=false，原创提示词为白色桌面上缓慢转动的小红色木块。4次同任务GET，第4次成功；无重提、素材上传或视频下载，未测试固定1080p的draft-to-video。其最低分辨率不同，不能擅自扩展本次480p探测。

| 路径 | 真实观察 |
| --- | --- |
| POST HTTP200 | 顶层id、task_id、model、status=queued |
| GET HTTP200 | 顶层code/message/data，非旧样例顶层status封装 |
| data.task_id | 与POST id一致；data.id是数值，不能替代task_id |
| data.status | 前3次IN_PROGRESS，第4次SUCCESS |
| data.result_url | 主视频URL；本次等于data.data.content.video_url；不打印签名 |
| data.usage | 最终amount=0.8028，currency原值为¥，未自行转换为ISO币种 |
| data.data.usage | token字段；不作为金额，也不使用quota／price_estimate推导实扣 |

完整脱敏JSON及来源元数据位于tests/fixtures/provider/live-observed。检查原／脱敏JSON键集合、层级、数组长度和叶值类型一致，检查原任务ID和配置密钥不出现在脱敏内容中，确认任务关联及两处结果URL相等。私有原始记录在.cache/paid-contract-probe，当前用户／SYSTEM ACL保护；不记录请求Authorization头。第4次响应已可靠保存后，控制台打印¥触发GBK UnicodeEncodeError；随后直接读取已保存记录核实，未重发请求。

本次文档参数核对来源https://api.seedance.nz/docs/llms.txt；未把其/v1/videos响应样例作为本次兼容端点证据。真实证据只覆盖一个Mini任务；其他模型、退款0、结算延迟、终态稳定性及字段必填性仍待核实。不为了凑齐10次重复付费，不保证再生成就会出现不同封装。

1.1基础响应取证完成，进度56/67；8.4尚未实现新封装解析，不能据此宣称MCP已支持真实完整闭环。13.5／13.6未完成；原矩阵其他真实操作仍未授权。无Git提交或推送，业务主规范未同步，change未归档。


## 8.4 解析接线（2026-11-13）

此前真实取证的三份 live-observed fixture 已接入纯解析器和 CompatibilityAdapter 的隔离回放；此前 user-supplied 四份继续兼容。本轮没有新增真实请求。查询关联使用 data.task_id，模型核对 properties.origin_model_name，IN_PROGRESS/SUCCESS 映射为 running/succeeded，data.result_url 写入受保护主视频事实，data.usage 精确落账；¥ 保持原值。内层 token 费用、quota、price_estimate 不进入实扣。详细行为见 compatibility-adapter.md。此实现不扩大一次 Mini 取证的适用证明，不关闭 1.2、1.5–1.8 或真实验收任务。


## 1.7 实际视频与尾帧（2026-11-14）

来源：tests/fixtures/provider/last-frame-observed（完整脱敏响应、provenance、下载摘要与ffprobe结果）。固定兼容端点；1次Mini4秒480p请求return_last_frame=true，3次查询成功，外层usage为0.8028/¥。两次产物GET使用既有NetworkPolicy，credential=false，HTTP200。视频823227字节H264/MP4、尾帧112496字节JPEG；二者640×640，视频4.041667秒。尾帧明确路径data.data.content.last_frame_url。不得把请求的480p写成实测480像素。

尾帧URL后缀.png、results.outputType=png，但Content-Type与实际字节是JPEG；实现以结构检查保存.jpg，不改变内容。新证据只支持这一已观察分支。主视频核心下载门槛满足，1.7完成；剩余逐项状态：完整/必需集合、跨模型支持、链接有效期和刷新待核实；Accept-Ranges=bytes仅响应声明，Range续传未测；统一网络策略允许受控重定向，但本次未记录精确跳转链，不能用DNS固定后的response.url差异证明重定向；本地SHA-256为下载校验摘要，不冒充供应商摘要或ETag语义。

本轮文档检查：https://api.seedance.nz/docs/llms.txt 声明return_last_frame但未给出完整尾帧路径，未把/v1/videos样例移植为兼容接口证据。未追加第二次收费任务，未执行完整26模型矩阵。


## 2026-11-14 样片与独立超分专项

完整证据tests/fixtures/provider/contracts-observed。本轮直接兼容POST两次，累计收费提交4/10。超分上传既有823227字节MP4，上传响应顶层url/file_type/size/expires_in/file_name，decode_upload接受；超分目标720p，无prompt/seconds，无额外price-preview，3次GET后成功，实扣0.875/¥。下载H264 MP4、960×960、4.041667秒。核心成功链路满足1.8；约10分钟及大小精确限制仍未知，成功只证明此次无需客户端额外price-preview。

2.5-standard-t2v样片draft=true、4秒480p，3次GET成功，2.688892/¥；data.data.content含draft=true、draft_task_id与原ID一致、video_url。下载H264 MP4、640×640、4.041667秒，未传output_format不能推断成片默认格式。7天起算及外部身份核验未测，1.6仍未完成。

两个只读负例：GET同一路径无鉴权返回401/error封装；GET构造的不存在ID返回400/code=task_not_exist/data=null。错误文本脱敏，不作为指令；两者均非提交证据，不能断言先前POST未创建。没有人为诱发429/5xx，没有退款/迟到结算证据。1.2继续未完成。

公开文档https://api.seedance.nz/docs/llms.txt复核了超分720p最低档及输入MP4、price-preview描述；没有找到需要客户端另外调用的明确步骤，实际直接提交成功与之分开记录。1.5的通用文档与逐模型参数页差异继续保留，不从其他模型seed规则推导Seedance范围。


2026-11-14 13.5更新：真实Mini i2v、国内2.5样片及其成片经统一队列/MCP下载复制通过，累计8/10、23.760998/¥。新增已关联NOT_START→queued解析，保留原状态且不允许重提；未观察的SUBMITTED仍拒绝。原Mini任务解析待处理后通过同库重启及显式刷新恢复，未重复POST。三模型完整脱敏响应及持久化回放见generation-queue-observed，详见[专项验收](generation-queue-acceptance.md)。当前61/67、剩余6项，完整集合与其他未知项保持，业务主规范未同步，change未归档。
