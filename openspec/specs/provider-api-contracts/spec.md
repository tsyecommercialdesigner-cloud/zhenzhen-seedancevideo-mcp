# provider-api-contracts Specification

## Purpose

为单一供应商的多个视频生成 API 定义可发现且独立的能力契约，使 Agent 能区分参数要求、操作支持情况与尚未核实的能力，并防止不可信或矛盾响应触发错误的任务副作用。

## Requirements

### Requirement: 能力声明与待核实标记

系统 SHALL 通过 api_id 选择已适配 API，提供摘要和按 API 查询的详细参数及操作能力；区分已支持、不支持、待核实，不提供任意 HTTP 请求透传。

#### Scenario: 资料尚缺
- **WHEN** 某 API 的模型、生成模式、素材规则或操作能力尚无已核实依据
- **THEN** 能力信息标记待核实，不默认支持或套用其他 API 的行为；不得把条件性规范当作供应商支持证明。

### Requirement: 无生成副作用预检

系统 SHALL 校验参数、素材条件及配置而不创建任务、不预留队列、不调用付费生成；未知参数或缺失必填参数明确报错。

#### Scenario: 已有本地样片事实
- **WHEN** 预检、正式接收或派发成片时，同连接绑定的本地任务库有唯一匹配远端ID的记录
- **THEN** 核对本地模型区域、draft参数和生成完成状态，已知不符则拒绝或派发前转待处理；接收时重新读取，不使用过时预检结论。相同连接绑定不代表已核验账号，7天起算未知仍提示；外部、跨绑定或多条匹配记录不猜测来源，重复请求不创建新任务。

#### Scenario: 预检与提交不同步
- **WHEN** 预检通过后容量、配置或素材发生变化
- **THEN** 正式提交重新检查，允许明确拒绝；预检结果不作为执行保证或必须的授权凭据。

#### Scenario: 无法估价
- **WHEN** 上游没有可靠费用依据
- **THEN** 不编造报价，预检通过不表示供应商必然接单。

### Requirement: 供应商响应关联与状态解释

系统 SHALL 只采纳能关联原任务且符合该 API 契约的状态；未知状态、关联错误和终态冲突不得被猜测成成功或失败。

#### Scenario: 任务关联错误
- **WHEN** 查询响应携带不同 task_id
- **THEN** 不更新目标任务、不下载响应产物，记录关联异常并转为待处理。

#### Scenario: 状态未知或回退
- **WHEN** 返回未知状态或契约未允许的生成中回到排队中
- **THEN** 保留最后已知事实、记录协议异常并停止自动推进，不凭猜测释放额度。

#### Scenario: 成功缺产物
- **WHEN** 上游声称成功但缺少必需产物信息
- **THEN** 不报告产物就绪；仅在已核实契约允许延迟出现时有界补查，否则待处理。

#### Scenario: 终态冲突
- **WHEN** 已确认终态后收到矛盾响应
- **THEN** 普通响应不覆盖终态、删除产物或重新占位；经显式核对可修正并保留历史，不触发重新生成。

### Requirement: 按语义分类错误

系统 SHALL 根据已核实 API 契约分类参数拒绝、鉴权、限流和暂时故障，不仅凭 HTTP 状态码推断是否接单。

#### Scenario: 提交遭限流
- **WHEN** 提交返回限流响应
- **THEN** 仅有可靠未创建任务证据时按未接单处理，否则按提交结果不明；不得盲目重提。

#### Scenario: 明确参数拒绝
- **WHEN** 证据确认上游拒绝且未接单
- **THEN** 记录字段摘要、释放生成占位，不自动改参数重试。

#### Scenario: 查询限流
- **WHEN** 查询或下载遇到可重试限流
- **THEN** 按已核实规则退避，适用时参考 Retry-After，同时遵守预算与期限。

#### Scenario: 配置级错误
- **WHEN** 鉴权失效或权限不足影响某 API
- **THEN** 停止无效重试并触发受影响 API 派发保护；不把已提交任务判定为生成失败。

### Requirement: 核对与取消能力受证据约束

系统 SHALL 仅在上游能力核实后提供幂等核对、任务关联、账号识别及取消；无依据时明确不支持或待核实并保留安全回退。

#### Scenario: 无法查证提交
- **WHEN** 上游不支持可靠请求关联或历史查询
- **THEN** 保持提交结果不明，不把查不到当作未创建，不直接绑定 Agent 提供的未经核验 task_id。

#### Scenario: 取消能力未核实
- **WHEN** Agent 请求取消已提交任务
- **THEN** 不声称取消成功，不将请求静默转换为放弃跟踪。


### Requirement: 上游依赖核实边界

系统 SHALL 将下列依赖保持为待核实，取得依据前不宣称支持，且按本规范中不确定或不可用分支处理。

#### Scenario: 接口资料尚未核实
- **WHEN** 相关接口文档或能力证据尚未提供
- **THEN** 以下核实边界继续生效：用户提供的四份兼容端点样例已确认顶层 id/model/object/status、queued/in_progress/completed/failed、成功 metadata.url 及失败 error.code/message 的层级；2026-11-13一次Mini真实任务已提供data.status=SUCCESS、data.task_id、data.result_url及data.usage的完整封装证据，但其跨模型适用性、HTTP 错误响应、终态稳定性、幂等与历史核对、取消、身份核验、限流与重试、下载刷新／续传／校验仍待核实。样例不证明所有字段必填或所有模型已实测。不得把 /v1/videos 响应样例直接作为兼容端点解析契约，也不得将顶层 code=success 当作生成成功。

### Requirement: 固定供应商端点与鉴权

系统 SHALL 以 https://api.seedance.nz 为默认 Base URL，使用 POST /v1/video/generations 和 GET /v1/video/generations/{id}，提交 JSON 并采用 Authorization: Bearer API Key，密钥配置名为 ZHENZHEN_SEEDANCE_API_KEY；默认不切换 /v1/videos。api_id 表示本地能力契约，model 表示供应商模型，二者不得混同。

#### Scenario: 兼容端点优先
- **WHEN** Agent 通过生成或独立超分工具提交任务
- **THEN** 使用已选兼容端点，不因通用文档推荐新端点而自动切换；不使用供应商远程 MCP 的助手凭证替代 API Key。

### Requirement: 26 个生成模型清单

系统 SHALL 仅以以下 24 个常规模型和 2 个成片模型作为首期 Seedance 模型集合；保留版本、区域、档位和模式身份。独立 zhenzhen-upscaler 不计入 26 个，不因文档示例或新增模型自动扩容。

#### Scenario: 常规模型枚举
- **WHEN** 查询首期常规生成模型
- **THEN** 返回以下精确标识，global 为国际区域，不保证审核结果。

| 版本／区域／档位 | t2v | i2v | multi |
| --- | --- | --- | --- |
| 2.0 国内 standard | `seedance-2.0-standard-t2v` | `seedance-2.0-standard-i2v` | `seedance-2.0-standard-multi` |
| 2.0 国内 fast | `seedance-2.0-fast-t2v` | `seedance-2.0-fast-i2v` | `seedance-2.0-fast-multi` |
| 2.0 国内 mini | `seedance-2.0-mini-t2v` | `seedance-2.0-mini-i2v` | `seedance-2.0-mini-multi` |
| 2.0 国际 standard | `seedance-2.0-global-standard-t2v` | `seedance-2.0-global-standard-i2v` | `seedance-2.0-global-standard-multi` |
| 2.0 国际 fast | `seedance-2.0-global-fast-t2v` | `seedance-2.0-global-fast-i2v` | `seedance-2.0-global-fast-multi` |
| 2.0 国际 mini | `seedance-2.0-global-mini-t2v` | `seedance-2.0-global-mini-i2v` | `seedance-2.0-global-mini-multi` |
| 2.5 国内 standard | `seedance-2.5-standard-t2v` | `seedance-2.5-standard-i2v` | `seedance-2.5-standard-multi` |
| 2.5 国际 standard | `seedance-2.5-global-standard-t2v` | `seedance-2.5-global-standard-i2v` | `seedance-2.5-global-standard-multi` |

#### Scenario: 成片模型枚举
- **WHEN** 查询样片转成片模型
- **THEN** 仅返回 seedance-2.5-standard-draft-to-video 和 seedance-2.5-global-standard-draft-to-video；文档中 seedance-2.0-pro-t2v 等示例不加入集合。

### Requirement: 按生成模式限定输入

系统 SHALL 对 t2v、i2v、multi 分别声明有效输入；三类常规模型 prompt 均按具体页面网关必填。不得因通用参数表列出其他模式字段而扩大当前模型能力。

#### Scenario: 文生输入
- **WHEN** 请求 t2v
- **THEN** 要求 prompt，不接受 i2v 或 multi 专用素材参数。

#### Scenario: 首尾帧输入
- **WHEN** 请求 i2v
- **THEN** 要求 images 为 1–2 张 JPG/PNG/WEBP 图片，第一张首帧、第二张尾帧；2.0 单张上限为 30MB，2.5 大小限制待核实；不接收 multi 专用字段。

#### Scenario: 多模态输入
- **WHEN** 请求 multi
- **THEN** 要求 prompt 及非空 metadata.content，按 image_url/video_url/audio_url 的嵌套 url 结构保持顺序；@Image N、@Video N 引用不得因规范化重排而改变。

### Requirement: 多模态素材数量与时长

系统 SHALL 按版本限制 multi 素材数量；对缺乏明确依据的别名合并、大小或时长约束标记待核实，不擅自丢弃素材或套用其他版本限额。

#### Scenario: 2.0 素材数量
- **WHEN** 提交任一 2.0 multi
- **THEN** 最多 9 图、3 视频、3 音频；通常 2–15 秒并非已确认硬限制，精确时长及文件限制继续核实。国内 Fast 音频 15MB 的通用文档例外保留待核实，不推广给 Mini、Standard 或国际版。

#### Scenario: 2.5 素材数量
- **WHEN** 提交任一 2.5 multi
- **THEN** 最多 30 图、10 视频、10 音频且总数不超过 50；每段音视频 2–30 秒，音视频合计不超过 30 秒；无法仅从 URL 得到时长时不伪称已校验。

#### Scenario: 素材入口冲突
- **WHEN** content 与顶层 images、metadata.video_url 或 metadata.audio_urls 同时提供
- **THEN** 本地契约明确报冲突并要求使用统一 content，不静默让 content 覆盖 images。简写字段已知会映射到 content，但组合及仅简写能否满足必填仍待核实；首期规范化入口采用 content，不发明合并规则。

### Requirement: 固定与自动时长参数

系统 SHALL 自动时长采用 metadata.duration=-1 并省略 seconds，不发送 seconds="-1"；固定 seconds 使用整数字符串。2.5 范围为 4–30 秒，2.0 4–15 秒仅为排版异常枚举的暂定解释，必须标记待核实。

#### Scenario: 自动模式
- **WHEN** 常规模型选择自动时长
- **THEN** 输出 metadata.duration=-1；如果请求同时明确固定 seconds 则报参数冲突，不静默忽略用户值。

#### Scenario: 固定时长差异
- **WHEN** 校验固定时长
- **THEN** 2.5 接受 "4" 至 "30"，拒绝范围外值；2.0 暂定 "4" 至 "15"，不将该推断或示例 "5" 记为已核实默认值。

### Requirement: 分辨率和比例矩阵

系统 SHALL 按版本及档位声明分辨率，保留 1080p 与 native1080p 区别；2.5 i2v 仅 adaptive，其他常规模型支持 adaptive、16:9、9:16、1:1、4:3、3:4、21:9。

#### Scenario: 分辨率枚举
- **WHEN** 校验普通非样片生成
- **THEN** 2.0 Standard 允许 480p/720p/1080p/2k/4k/native1080p/native4k；2.0 Fast/Mini 仅前五档；2.5 允许前五档和 native1080p，拒绝 native4k。2.5 的 480p/720p/native1080p 为原生，1080p/2k/4k 为超分档。

#### Scenario: 2.5 图生示例冲突
- **WHEN** 2.5 i2v 请求 ratio=16:9
- **THEN** 按参数表仅 adaptive 的明确约束拒绝，不用错误示例放宽、不静默改值；其他比例默认值未明确时保留省略。

### Requirement: 2.5 多模态模式约束

系统 SHALL 仅为 2.5 multi 支持 metadata.omni_reference_task_type=reference/edit/extend/auto；省略时由模型判断，不根据提示词自行切换模式。

#### Scenario: 编辑模式
- **WHEN** 显式选择 edit
- **THEN** 要求至少一个参考视频、ratio=adaptive、metadata.duration=-1，输出沿用参考视频时长；冲突参数明确拒绝。

#### Scenario: 延长模式
- **WHEN** 显式选择 extend
- **THEN** 要求参考视频和 ratio=adaptive，不擅自补入 edit 专属自动时长约束。

#### Scenario: 参考或自动
- **WHEN** 选择 reference、auto 或省略
- **THEN** reference 仍遵守公共比例与时长范围；auto 不预判为 edit。示例提示词含换人意图不构成显式 edit 参数。

### Requirement: 2.5 样片与独立成片

系统 SHALL 为六个 2.5 常规模型提供 metadata.draft，默认 false；开启后有效分辨率固定 480p。成片仅限两个 draft-to-video 模型，显式引用本人、同区域、已完成且 7 天有效期内的样片，不自动创建下一任务。

#### Scenario: 样片分辨率覆盖
- **WHEN** draft=true 且用户同时指定其他分辨率
- **THEN** 预检和接收摘要明确显示样片强制 480p，并固定有效值，不伪称按原分辨率生成；2.0 不支持 draft。

#### Scenario: 同区域成片
- **WHEN** 提交国内或国际成片模型
- **THEN** 要求 metadata.draft_task_id，分别对应同区域 2.5 draft 任务，分辨率仅 native1080p 且默认该值；不传 prompt、素材、seconds 或 enhance_prompt。

#### Scenario: 成片可选值
- **WHEN** 设置成片 metadata.output_format 或 return_last_frame
- **THEN** 格式仅 mp4/mov，默认格式未明确则保留省略；return_last_frame 省略表示继承样片，显式 false 与省略不同。

#### Scenario: 无法核对样片
- **WHEN** 本地已知样片未完成、非 draft、区域不同，或无法核实外部样片身份及有效期
- **THEN** 已知不符则拒绝；未知明确标为待核实，不伪造验证通过，不自动补做样片。7 天起算点继续待核实；国内2.5样片的data.data.content.draft_task_id已有完整实测证据，但该路径不提供外部身份或有效期保证。

### Requirement: 独立视频超分工具

系统 SHALL 提供独立于生成入口的超分 tool，固定 model=zhenzhen-upscaler，输入恰好一个 MP4；metadata.content 仅含一条 video_url，分辨率允许 720p/1080p/2k/4k，默认 1080p。

#### Scenario: 超分输入
- **WHEN** Agent 显式提交本地视频或 URL
- **THEN** 本地先托管上传换 URL，再建立独立异步任务；不要求 prompt 或 seconds，不发送占位文本，不启用 enhance_prompt。

#### Scenario: 超分限制和计费
- **WHEN** 查询或预检超分能力
- **THEN** 显示约 10 分钟上限，精确秒数、大小和边界待核实；不把生成模型的超分档当作同一操作或计费公式，不因 price-preview 文案增加未明确 API 调用。

### Requirement: 参数省略和未核实选项

系统 SHALL 常规模型 generate_audio 默认 true；seed、return_last_frame 等选项仅按已确认类型及适用模型声明，缺失的范围、默认值或支持性继续待核实，不以示例值填补。

#### Scenario: 未明确随机种子规则
- **WHEN** 查询 seed 能力
- **THEN** 显示资料声明 number，但整数约束、范围和默认值尚待核实，不从其他版本推导；不承诺相同 seed 必然复现。

#### Scenario: 尾帧条件支持
- **WHEN** 普通模型请求 return_last_frame
- **THEN** 公开其支持性待核实，不承诺一定返回尾帧或编造 URL；成片省略继承规则依独立契约保留。

### Requirement: 成功状态别名与费用片段

系统 SHALL 将任务状态 SUCCESS 和 completed 映射为生成成功，failed 映射为失败；保留原状态及出处，映射语义不代表完整兼容响应层级已核实。

#### Scenario: 费用示例不是完整响应
- **WHEN** 只收到 code=success、data.status=SUCCESS 和 data.usage 片段
- **THEN** 记录可关联的状态及费用证据，但不凭片段推断任务 ID 或结果 URL 路径，不报告产物就绪；queued/in_progress 的兼容端点层级、其他状态仍待完整示例核实。


#### Scenario: 实测尾帧标签与文件不同
- **WHEN** 已核实Mini响应的尾帧URL或outputType标签为png，但下载文件为JPEG
- **THEN** 按文件结构校验和JPEG原格式落盘，不以标签转码或宣称PNG支持；其他编码、模型及集合穷尽继续待核实。


#### Scenario: 样片ID已有完整查询证据
- **WHEN** 2.5常规模型已关联SUCCESS响应在data.data.content返回draft=true和匹配原任务的draft_task_id
- **THEN** 保存并在本地查询返回该样片ID，不自动创建成片；同账号、有效期起算及外部样片核验仍按待核实处理，缺失字段不猜测，矛盾ID拒绝。


#### Scenario: 已接单任务查询尚未开始
- **WHEN** 已知任务ID及模型匹配的兼容查询封装返回实测NOT_START
- **THEN** 归一为queued并保留原状态，继续按原预算跟踪和保留占位；不能将名称解释为未接单或允许重新提交，未观察的其他状态仍按待核实处理。
