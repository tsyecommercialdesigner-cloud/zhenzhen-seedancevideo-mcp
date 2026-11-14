# 模型与本地预检

规则版本为 `seedance-contract-2026-11-13.1`。`models.py` 固定 26 个 Seedance 模型，独立 `zhenzhen-upscaler` 不计入这 26 个。能力服务和无副作用预检已接入 MCP 工具；真实覆盖范围见 provider-acceptance-matrix.md，不能由工具可调用推断全部模型已实测。

| 模型族 | 区域 | 任务类型 | 分辨率 | 固定时长 |
| --- | --- | --- | --- | --- |
| seedance-2.0-standard-* | 国内／global | t2v、i2v、multi | 480p、720p、1080p、2k、4k、native1080p、native4k | 4–15 秒，暂定待核实 |
| seedance-2.0-fast-* | 国内／global | t2v、i2v、multi | 480p、720p、1080p、2k、4k | 同上 |
| seedance-2.0-mini-* | 国内／global | t2v、i2v、multi | 同 Fast | 同上 |
| seedance-2.5-standard-* | 国内／global | t2v、i2v、multi | 480p、720p、1080p、2k、4k、native1080p | 4–30 秒 |
| seedance-2.5-standard-draft-to-video | 国内／global | 样片转成片 | native1080p | 沿用样片，不发送 seconds |
| zhenzhen-upscaler | 供应商独立能力 | 视频超分 | 720p、1080p、2k、4k；默认 1080p | 输入约 10 分钟，精确边界待核实 |

国际模型在版本号后插入 `global-`，例如 `seedance-2.5-global-standard-i2v`。完整标识可调用 `capabilities(api_id="seedance-video")` 获取；指定 model_id 获取单模型详情，避免一次返回所有详细规则。未知模型和任意 HTTP API 标识拒绝，不因供应商增加模型自动扩容。

常规请求要求非空 prompt。t2v 禁止素材；i2v 要求有序 1–2 张图片，首帧在前、尾帧在后，格式 JPG/PNG/WEBP；2.0 i2v 已知单张 30MB，2.5 图片大小未知。URL 不依据扩展名伪称内容格式已验证，只有内部检查得到的 MediaFact 才作为证据。multi 必须使用非空 metadata.content，保留 image_url/video_url/audio_url 条目顺序，不接受混入 images、video_url、audio_urls 简写。

2.0 multi 最多 9 图、3 视频、3 音频，精确音视频时长和大小仍待核实。2.5 multi 最多 30 图、10 视频、10 音频，每段音视频 2–30 秒，总时长不超过 30 秒。已知时长超限拒绝；未知 URL 时长返回 REFERENCE_DURATION_UNVERIFIED，不下载素材来补齐预检。内部素材事实不能由 Agent 传“已验证”标志替代。

自动时长为 metadata.duration=-1，省略 seconds；明确同时提供固定 seconds 则拒绝。固定秒数必须是整数字符串，禁止 seconds="-1"。未提供时长时保留省略，不把示例 5 秒当默认。

2.5 i2v 仅允许 adaptive；其他普通模式允许 adaptive、16:9、9:16、1:1、4:3、3:4、21:9。2.5 multi 的 edit 要求参考视频、adaptive 和自动时长；extend 要求参考视频和 adaptive，但不自动加 -1；reference/auto 不改变公共约束，也不通过提示词猜模式。

2.5 常规模型 draft 默认 false；true 会将有效分辨率固定为 480p，并在 notices 返回 DRAFT_EFFECTIVE_RESOLUTION_480P，原请求另存。2.0 不接受 draft。成片要求 draft_task_id，本地已知账号、区域、完成状态、样片标志或有效期不符合时拒绝；未知时明确提示，7 天起算点仍待核实。成片不发送 prompt、素材、seconds 或 enhance_prompt；output_format 可选 mp4/mov，省略不填默认；return_last_frame 缺省保留继承语义，false 则保留 false。

本地事实接线：MCP预检、接收事务和真实适配器准备阶段读取同connection_binding下唯一匹配remote_id的源记录，核对区域、已固定draft参数和完成状态。外部/跨binding/多条匹配返回DRAFT_SOURCE_UNVERIFIED；账号与7天起算仍未核验，不把相同binding当账号证明。重复key返回原任务，派发前新发现已知不符转待处理。逐模型证据与边界见contract-review-closure.md和model-contract-audit.json。

超分恰好一条 video_url，已知非 MP4 拒绝，格式未知则明确未验证；不发送 prompt、seconds、enhance_prompt，也不调用 price-preview。精确时长和大小限制不使用推测值硬编码。

常规模型只填入明确默认 generate_audio=true、2.5 draft=false、enhance_prompt=false。优化 true 的用户授权须在任务接收时另行检查，参数构造成功不表示已获授权。seed 接受有限 number，整数要求、范围、默认值均未知。已观察SUCCESS及费用完整封装已接入；Mini尾帧路径已实测，跨模型尾帧支持和完整产物集合仍未知。远端取消、账号识别、提交反查、产物 URL 刷新继续待核实；本地能力校验不等于上游已实测。

调用 `preflight(request, configuration=已加载配置)` 返回有效参数、固定输出目录、未核实项和提示；不会创建任务、容量预留、上传或生成请求，不提供估价，不保证正式接收成功。正式提交必须重新验证配置、容量、素材和授权。

ParameterSnapshot 同时保存原始显式参数、有效 payload、规则版本和未核实项。序列化／恢复不重新调用规范化，不让后续默认值改写历史；未知规则版本明确拒绝。payload() 每次返回独立副本，调用方修改不改变存储快照。签名 URL 和提示词不进入对象 repr，实际持久化仍须由任务库的受保护存储管理。

验证命令：`uv run --frozen pytest tests/test_models.py tests/test_parameters.py tests/test_preflight.py`。测试覆盖全部模型身份、主要参数分支、未知标记、快照及无副作用预检；不调用真实供应商。
