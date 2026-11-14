# 实施记录

## 2026-11-13：CLI 恢复和工程基础

OpenSpec 原全局包目录 `C:\nvm\installs\v24.21.0\node_modules\@fission-ai\openspec` 返回拒绝访问。普通及提升执行环境均无法读取 ACL，takeown 和 icacls 修复也失败，未成功更改原包权限；底层原因尚未确定。

已将 OpenSpec 2.0.0 安装到 `%LOCALAPPDATA%\OpenSpecCLI`，在用户 PATH 前置该目录，原 PATH 备份保存在该目录的 `user-path-before-repair.txt`。旧包保留，未删除或重装整个 Node 环境。新入口的 version、list、status、instructions apply 均退出 0；既有进程可能仍继承旧 PATH，应重启终端或直接使用新入口。

任务 2.1：建立 src 包、Python 3.12.14 固定版本和 CLI 模式入口。`uv lock`、`uv sync --frozen`、依赖版本检查及入口 `--version` 均退出 0。锁定 mcp 2.3.0、httpx2 2.16.0；入口仅骨架，stdio/backend 明确失败，不代表业务服务可用。uv 的跨盘硬链接提示已回退复制，不影响安装成功。

此记录不代表供应商、实际 Host 或完整服务验收通过。真实供应商调用尚未执行。

任务 2.2：加入 pytest、pytest-asyncio、Ruff，AGENTS.md 已改为真实命令。最小入口测试 3 passed；Ruff 检查和格式检查退出 0，`uv build` 生成 wheel 与 sdist，退出 0。

任务 2.3：加入清理环境、临时状态根、网络保护、假 HTTP 服务、可控时钟及故障注入设施。首次使用系统 pytest 临时目录时报拒绝访问，改为 `.cache/test-runs/<随机标识>`，不触碰旧目录。随后修正 Windows asyncio 内部 socketpair 被误拦的问题，仅对标准库创建内部回环连接的调用开放。复验 7 passed，代码／格式检查退出 0；假服务线程在 fixture 结束时关闭。

任务 3.1：配置加载、不可变快照、默认数值、路径与网络配置语法校验已实现；未接入后端握手、数据库或网络策略执行器。配置测试 24 passed，累计 31 passed；包括环境优先级、固定 `.env`、不插值、缺密钥／空值、别名不生效、输出与状态分离、无效数值和配置 repr 不含密钥／代理密码。

任务 1.1：公开资料核查尚不能完成所选兼容端点的完整响应契约，保持未完成。详情见 `docs/provider-contract-evidence.md`；已请求用户补充脱敏样例，不凭其他端点的响应实现猜测解析。

当前进度 4/67，仅 2.1、2.2、2.3、3.1 已勾选。服务尚不可用于视频生成；本轮未提交或推送 Git，未同步主规范或归档。

## 2026-11-13：按用户要求恢复 Nvm 入口

复查 `C:\nvm\.nodejs\openspec.exe --version` 已正常返回 2.0.0，原 EPERM 的底层原因仍未确认。已恢复安装前的用户 PATH，使用 npm 指定独立 prefix 卸载此次安装的 OpenSpec 及依赖（共 57 个包），核对剩余文件后移除 `%LOCALAPPDATA%\OpenSpecCLI` 目录及其中 PATH 备份。未卸载或修改 Nvm 管理的包。

最终检查：独立安装目录不存在，用户 PATH 不再包含该目录；`openspec` 解析至 Nvm 原入口，版本检查和本 change 的 OpenSpec 严格校验均通过。此前独立安装说明仅作为历史记录，不再是当前使用方式；已有终端若保留旧 PATH，应重启以刷新环境。

## 2026-11-13：补充查询契约证据

用户提供提交 queued 及查询 in_progress、completed、failed 的完整 JSON，已登记为四份 user-supplied fixtures；主链路的顶层 id/status、metadata.url、error.code/message 已明确。任务 1.1 剩余 SUCCESS／data.usage 完整封装待核实，暂不勾选；费用未返回不阻止成功视频下载。未执行真实请求，未将用户样例等同运行验收。

## 2026-11-13：继续本地实施与响应隔离测试

本次继续使用 Nvm 管理的 OpenSpec。新增完成任务 3.2–3.5、4.1–4.4、6.1，当前 13/67；本节取代前文历史进度数字。

- 配置快照冲突仅返回配置名；未指定客户端值沿用后端，不热更新。Windows SID ACL 与 DPAPI 私有 HMAC 凭据绑定已验证，换钥／端点没有账号核验证据时仍阻止旧任务接续。
- 诊断先白名单过滤及凭据过滤，再限长；长堆栈、HTML、嵌套凭据、签名 URL 不进入日志。独立 JSONL 轮转、按 ID 有界读取、重启查询均有测试。配置说明与无真实密钥示例位于 configuration.md 和 configuration.env.example。
- SQLite 使用专用线程、事务、WAL／FULL／外键及有界写队列；记录覆盖任务、接收、尝试、观察、素材、上传、产物、清理、偏好、事件、诊断和费用证据。既有损坏／空白／过新库明确拒绝；取消等待不撤销已经接收的事务。
- 正交状态和 version／epoch 支持本地取消、放弃及迟到事实；提交意图和占位同事务持久化。故障门阻止新增写入和副作用；必须核对未决意图后解除，不能按内存结果释放额度。副作用开始标记持久化，重复同 attempt 不再次执行。
- 实扣只保存已核实输入的 Decimal 文本与币种、原状态、证据摘要；重复不累加，缺失不记零，迟到费用不改变产物就绪。此模块仅有合成输入测试，SUCCESS 与费用完整上游响应仍待核实，解析器没有启用费用读取。
- 26 个 Seedance 模型和独立超分注册表已逐项测试。四份用户样例的严格解析及本地 HTTP 字节测试已实现，8.4 仍未完成，因为真实适配及剩余封装未完成。

当前仍是模块级实现：stdio/backend CLI 保持明确未实施的返回，尚未接入共享进程、完整调度、上传下载或 MCP 工具。存储门与状态服务的跨模块调度验收属于后续任务，不以当前单元测试替代。schema_version=1 为尚未发布的初始 schema；没有生产任务库迁移。本轮不调用真实供应商、不提交或推送 Git、不同步主规范或归档。

最终验证：`uv run --frozen pytest -q` 为 120 passed；`uv run --frozen ruff check .`、`uv run --frozen ruff format --check .`、`uv build`、`openspec validate add-local-video-generation-service --type change --strict`、`git diff --check` 均退出 0。wheel/sdist 构建成功。测试使用临时状态根及假网络，不代表实际 Host、真实供应商或端到端业务验收。

## 2026-11-13：模型预检、所有权、RPC 与离线维护

本轮新增完成 4.5、5.1、5.2、6.2、6.3、6.4，进度由 13/67 更新为 **19/67**。4.2 的状态回退缺陷及 5.2 的关闭缺陷经重新打开、修复和回归验证后重新完成；未将未实施任务勾选。

- 常规参数按 24 个模型校验输入模式、时长、分辨率、比例、素材数量及 2.5 edit/extend 条件；2.0 时长暂定、seed 范围、素材未知格式／时长仍明确标注。样片固定 480p，成片保留缺省继承并拒绝已知不符合的样片，独立超分只接受一条视频。没有素材加工、自动样片链或 price-preview 调用。
- 参数快照保存显式输入和有效参数，恢复不重新应用默认值。只读能力查询和预检已有模块接口，不创建任务、预留、文件或请求；授权仍需在任务接收时校验，正式提交必须重新预检。模型矩阵见 model-preflight.md。
- startup/owner 稳定 Win32 独占句柄和 PID／创建时间核对已实现。四个真实 Windows 子进程同时竞争，仅一个获得所有权；旧进程存活、权限不足和 PID 复用均有测试。不强杀、不删除锁文件。
- 本地 RPC 绑定 127.0.0.1 随机端口，256 位令牌、协议握手、配置冲突、长度前缀 JSON、帧／连接／在途限制与受 ACL 保护的发现信息已验证。未鉴权连接不进入处理器。完整 stdio 前端、隐藏后端拉起、Job Object、心跳租约和有限收尾尚待后续任务，见 local-rpc.md。
- 数据库初始化加入历史标记；存在历史而主库丢失时拒绝重建。离线 SQLite backup／integrity_check 隔离测试通过，恢复后未知任务和占位保留。数据字典和人工离线备份注意事项见 storage-recovery.md；未触碰生产库或执行生产备份。
- 修复 running→queued 回退：保留 running 和占位，保存观察并标记 REMOTE_STATE_REGRESSION，需要显式处理。修复 RPC 关闭等待顺序：先关闭连接并回收处理器，再等待 server.wait_closed，避免有连接时关闭挂起。

验证过程曾发现锁上下文重复 acquire 和 RPC 关闭等待顺序问题，失败结果未计为通过；均已修复，重新验证。最终 `uv run --frozen pytest -q` 为 **212 passed**，退出 0；Ruff 检查、格式检查、uv build、OpenSpec 严格校验及 git diff --check 均退出 0。构建 wheel/sdist 成功；检查未发现本仓库遗留 pytest Python 进程。

SUCCESS 与费用完整响应仍待核实，1.1 和 8.4 保持未完成。所有新测试仅用本地数据、回环 RPC 和测试子进程，没有真实供应商请求、实际 Host 接入或端到端生成验收。本轮未提交／推送 Git，未同步主规范或归档。

## 2026-11-13：隐藏后端、Host 租约与有限退出

本轮完成任务 **5.3、5.4、5.5**，进度 **22/67**。stdio 入口已使用 MCP SDK v2 的 MCPServer，当前只提供 get_service_status 转发。完整业务工具集 12.1 和实际 Host 验收 13.3 均未完成。

- 固定虚拟环境解释器／模块／绝对 cwd 隐藏启动，无 shell 和密钥 argv。先挂起写启动身份记录，再恢复执行；实际后端与启动器以随机启动标识关联。测试发现 Windows 虚拟环境启动器和工作进程 PID 不同，已修正错误的 PID 等同假设，设计也补充该实现依据。
- 验证真实 Windows Job Object 的允许／禁止脱离分支。允许时，关闭测试 Host 的 kill-on-close Job 后 B 仍可调用同一后端；禁止时返回 BACKEND_LAUNCH_OR_JOB_INCOMPATIBLE，不伪称启动成功。比较的是具体 Host Job，不把 Python 启动器自身的 Job 误判为原 Host Job。
- LeaseManager 用单调时钟处理心跳、EOF、半开失效、无 Host 派发门、宽限重连、不可逆 draining 和有限收尾。读取派发状态不会丢失待关闭的过期连接。RPC 返回后端有效心跳间隔；客户端按该值保持租约。
- 两个 RPC 客户端共享后台；A 断开 B 继续，最后一个连接退出后后台结束，随后重启产生新实例。SDK v2 stdio 客户端完成 initialize、list_tools、get_service_status 和退出；这是模拟协议客户端验收，不是实际 Agent Host 配置验收。
- 后端启动读取持久化占位，将 active 未决 intent 保守转 needs_attention 并记录业务事件，保留已有原因、预算、远端未知和占位。连续两次重启没有重复递增版本或产生第二次提交。正常任务的自动查询／下载恢复、完整停机阶段协调仍属于任务 9.6，保持未完成。
- local-rpc.md 更新正常接入、退出和启动故障路径；configuration.md 更新当前可用范围。CLI 对嵌套启动异常只输出静态错误码，不透传 SDK 异常组或堆栈。未执行生成请求；状态明确 generation_execution=not_implemented、provider=unverified。

验证过程先后发现 Win32 常量所属模块、虚拟环境启动器 PID 关联和 Job 测试对象选择问题；失败未算通过，已修复后复验。最终 `uv run --frozen pytest -q` 为 **224 passed**，退出 0。Ruff、格式检查、uv build、OpenSpec 严格校验和 git diff --check 均退出 0；wheel/sdist 成功生成。进程检查未发现遗留的本项目 Python 后端。所有运行目录、任务库和进程都属于隔离测试，未修改实际 Host 或生产状态。

SUCCESS、费用完整响应及其他上游未知项继续待核实。本轮未调用真实供应商，未提交或推送 Git，未同步主规范或归档。

## 2026-11-13：任务接收、素材托管、去重与提示词优化授权

本轮完成 **7.1–7.5**，进度由 22/67 更新为 **27/67**。

- 新增 AdmissionService 与 Windows 素材接收模块：接收前登记容量和文件预留，受控复制、SHA-256、任务／素材／授权快照同事务落账后才返回 accepted。源文件句柄拒绝并发写入／删除，复制前后检查身份变化；外部 URL 仅保留引用及原签名。用户输入和超分原产物不被移动或删除。
- 同 key 合并在途接收，持久化内容身份用于跨连接与重启去重；同路径换内容冲突，满队列找回已有任务不占新容量。旧显式身份重放不重新应用当前默认值或授权偏好，等价显式默认值可返回原任务。
- 持久化总是允许／撤销与单次授权声明；默认关闭，单次显式 false 优先，成片／超分不适用。最终接收事务重新读取偏好，复制期间撤销会影响新接收任务，失败写入不确认授权。
- MCP 调用取消仅结束等待，接收由后端继续完成或清理。修复先登记 intent 和 repairing 门控，仅允许同摘要、同大小补回未提交输入；已提交任务拒绝。修复失败不开放派发，旧取消／放弃状态不被恢复。
- stdio 新增 submit_video、upscale_video、find_task_by_request_key、get/set_prompt_optimization_policy、repair_task_materials。真实隔离子进程与 SDK v2 客户端验证提交、另一个连接找回、重启找回与偏好持久化、素材修复响应。完整工具集任务 12.1 仍未完成。
- 设计补充接收输入形状、内部 material_id 引用、事件快照和修复门控；使用现有 schema，无自动迁移。操作说明见 task-admission.md。自动调度仍未实现，接收 queued 不等于上游已提交。

验证中发现并修复 pywin32 常量所属模块、测试重启数据库实例未关闭、SDK v2 无参数 dict 返回类型不生成 structured_content 等问题。早期失败和未退出的测试运行均未计为通过；本轮四个遗留 pytest 工作进程按已核对 PID／命令行清理后重新验证。

最终实际执行：

- `uv run --frozen pytest -q`：**242 passed in 25.67s**，退出 0。
- `uv run --frozen ruff check src tests`：All checks passed，退出 0。
- `uv run --frozen ruff format --check src tests`：43 files already formatted，退出 0。
- `uv build`：wheel 和 sdist 构建成功，退出 0。
- `openspec validate add-local-video-generation-service --type change --strict`：valid，退出 0。
- `git diff --check`：退出 0；仅有 Git 的 LF/CRLF 提示。

所有测试使用隔离状态根、合成密钥、Windows 本地文件和回环 RPC，没有真实供应商调用或生产任务库访问。SUCCESS 与费用完整响应继续待核实，1.1／8.4 不勾选；上传、下载、调度、终态清理、完整工具集及实际 Host／真实闭环验收仍按任务清单推进。本轮没有 Git 提交／推送，也未同步主规范或归档。

## 2026-11-13：统一网络策略与合成调度／恢复

本轮完成 **8.1、8.2、8.5、9.1–9.5、9.7**，进度由 27/67 更新为 **36/67**。任务 9.6 仅有提交／跟踪恢复和有限关闭的部分证据，下载／发布／清理跨阶段恢复尚未完成，保持未勾选。8.3／8.4 及相应上游核实项继续未完成。

交付：

- NetworkPolicy 使用 httpx2 异步池、连接／空闲／池等待时限和阶段总期限；统一显式代理、绕过和 CA，禁用环境代理。真实本地 HTTP／HTTP 代理／TLS／HTTPS 代理测试通过。系统根加附加 CA 同时用于目标和 HTTPS 代理，不关闭验证或静默直连。
- 逐跳验证公网 DNS 地址并固定 IP，保留 Host／TLS SNI；客户端按 origin 和鉴权用途分离。跨 origin 不转发 Bearer 或 Cookie，403 不补密钥重试，HTTPS 不降级，循环／跳数有界，POST 不自动重定向。内部测试例外不开放为环境变量或 MCP 参数。
- 新增内部 ProviderFailure、Capabilities 和 NotCreatedEvidence。HTTP 状态只能用于保守错误分类／保护，不能证明未接单；远端取消、核对、URL 刷新和账号识别默认仍为 CAPABILITY_UNVERIFIED。既有凭据绑定校验继续生效。
- Scheduler 的合成自动 runner 覆盖有限准备、可派发 FIFO、API／模型保护、共用额度和无 Host 门控；准备完成先后不改变派发顺序。保护持久化，新增接收检查保护，已有请求找回不受阻。
- 提交 intent 和占位先落账，发送前、发送后及返回 ID 未落账故障均不自动重提。只有内部核实能力提供证明后，显式 retry_not_created 才可开始新尝试，旧 intent 与证明保留。
- 查询预算、抖动退避、轮次及事件历史持久化；正常进度不耗错误预算，耗尽／超时保留 ID、占位与素材。请求时限、工具等待与跟踪期限分离；单调时钟防止进程内回拨延长期限。排队等待查询槽时再次核对期限，允许已发出的查询有限收尾。
- 单次刷新合并、新预算恢复、重复恢复不叠加、放弃后恢复重新占位、管理版本冲突及旧 epoch 迟到结果均有隔离测试。刷新成功转 downloading/pending，不声称文件就绪；真实下载器尚未完成。
- 生成跟踪恢复测试实际关闭并重开 SQLite，验证预算／退避不重置、原输出目录固定、降低额度不取消已有任务、绑定不兼容保留额度、恢复原配置仍需显式恢复；有限关闭取消挂起查询。生产后端仍没有绑定真实适配器，health 的 generation_execution 保持 not_implemented。

文档：新增 network-policy.md、scheduling-recovery.md；design 补充 IP 固定与 TLS 名称隔离、HTTPS 代理证书上下文、预算和保护持久化方式。fixtures/network 为 .NET 本地生成的合成证书及私钥，明确标注，不安装系统信任、不含生产凭据。

验证过程曾发现 HTTP 代理不接受 proxy_ssl_context 的库约束，已改为只对 HTTPS 代理传入，并通过实际 HTTPS 代理测试；早期失败不计通过。复核修正了恢复原绑定后的显式恢复和成功刷新对相关查询异常的消退。

最终实际执行，均退出 0：

- `uv run --frozen pytest -q`：**288 passed in 32.45s**。
- `uv run --frozen ruff check src tests`：All checks passed。
- `uv run --frozen ruff format --check src tests`：49 files already formatted。
- `uv build`：wheel／sdist 成功。
- `openspec validate add-local-video-generation-service --type change --strict`：valid。
- `git diff --check`：通过，仅 LF/CRLF 提示。

没有真实供应商调用、生产任务操作、实际 Agent Host 验收或完整视频落盘交付。SUCCESS 与费用完整响应继续待核实，1.1／8.4 不勾选；没有 Git 提交／推送，未同步主规范或归档。


## 2026-11-13：主规范导入与配置规则修订（仅文档）

将用户提供的 manual-writing、git-collaboration、engineering-practices 共 8 个 Markdown 文件迁移到 openspec/specs 对应目录。迁移前核对源／目标 SHA-256 一致，避免在 change/specs 下把完整规范当作 delta；其他八项业务 delta 未同步到主规范。指南引用的 python-practices／typescript-practices 尚未提供，改为明确的待导入路径说明，不创建虚构文档。

用户确认采用实际安装目录 .env，优先级为文件 > 进程环境 > Windows 当前运行用户环境 > 声明默认值，仅字段缺失回退。同步修订 proposal、runtime-configuration delta、design；配置实现、冲突判定及配置指南／空密钥示例需要迁移，任务 3.1、3.2、3.5 重新打开，进度从 36/67 调整为 33/67。现有代码仍按旧规则运行，历史测试结果不证明新要求通过。docs/configuration.md 顶部已标明该差异。

本轮仅进行文档及规划调整：主规范严格校验 3/3 通过，change 严格校验通过；未运行业务测试、未修改实现或用户真实 .env，未执行 Git 暂存／提交／推送，未归档 change。


## 2026-11-13：安装目录配置规则实施（3.1、3.2、3.5）

已完成并重新勾选 3.1、3.2、3.5，总进度 36/67。config.py 根据模块与已知安装布局定位安装根；逐字段读取安装目录 .env、进程环境、只读 HKCU\Environment，再采用默认值。仅缺失回退，空值、非法值、重复字段、解析／读取错误明确拒绝；禁止插值，状态根不移动。CLI 输出稳定脱敏配置错误。RPC 使用前端已解析显式项比较，不重读后端文件覆盖来值；已运行快照、既有连接和任务输出快照保持不变。

configuration.md 与空密钥 configuration.env.example 已同步。未填写密钥时示例明确失败；测试仅在临时副本填入合成密钥后验证加载。设计补充源码、项目 .venv wheel、独立虚拟环境三种定位规则及全局未知布局拒绝理由。测试通过注入安装根与用户环境读接口隔离真实配置；子进程以测试专用 sitecustomize 保持相同隔离，不改用户注册表或真实 .env。

实际执行（仓库根，所有最终命令退出 0）：

- 定向配置／文档／RPC／隐藏后端验证：58 passed；最后新增 RPC 文件变更回归及 CLI 错误输出后，配置／文档／CLI／RPC 定向 57 passed。
- `uv run --frozen pytest -q --basetemp .cache/config-policy-final`：306 passed，32.51s。覆盖文件优先、逐字段回退、注册表读替身、无插值、重复／非法／空值／读取失败、不同 cwd／安装布局、配置冲突和快照、Windows 隐藏后端与 stdio 协议；实际 Agent Host 及真实用户环境集成不由这些测试替代。
- `uv run --frozen ruff check src tests`：通过；`uv run --frozen ruff format --check src tests`：49 files already formatted。
- `uv build --out-dir .cache/config-policy-build`：sdist 与 wheel 构建成功；未执行干净安装或发布验收。
- `openspec validate add-local-video-generation-service --type change --strict`：通过；`openspec validate --specs --strict`：3/3 通过；`git diff --check`：通过。

SUCCESS 与费用完整响应继续待核实，未勾选 1.1／8.4；没有真实供应商调用、Git 暂存／提交／推送或归档。本轮未新增主规范同步，沿用此前已导入的三项主规范；八项业务规范仍为 change delta。

收尾：核对 pytest current 符号链接均指向本轮测试目录内后，先移除链接，再清理本轮 5 个隔离测试目录；保留构建产物于 .cache/config-policy-build。未清理历史测试目录或用户数据。


## 2026-11-13：产物下载、持久化与复制交付（第 10 组）

完成 10.1–10.5，总进度 41/67。新增 artifacts.py 与 artifact_files.py：独立下载并发、流式临时写入、长度／容器／摘要检查，持久化重试预算及发布意图，原子发布后 ready 登记；恢复核对设备／文件身份与摘要，不认领不明同名文件。未完成传输在恢复时消耗剩余预算，耗尽等待显式恢复，不因重启无限重试。部分产物保留；全部必需产物 ready 才设置清理 pending（清理执行仍未完成）。

产物服务提供分页清单、基本存在性检查、显式摘要验证及版本化下载恢复。外部删改不自动下载；恢复保留其他就绪产物，默认拒绝覆盖，明确 overwrite 后才在新文件完整时替换。复制接受本地绝对路径或显式工作区相对路径，拒绝越界、UNC、驱动器相对路径、ADS、保留名及重解析点；Windows 祖先目录句柄防删除／替换竞争，源只读锁与临时副本摘要保护原文件。取消发布前保全旧目标，发布后响应丢失不回删。

Scheduler 支持可选注入产物服务及内部 adapter.artifacts(row)，网络门关闭时不启动下载。合成适配器测试完成成功任务到落盘并可复制的组合；没有接入真实供应商或开放任意 URL 下载。正式后端业务工具接线仍属于第 12 组；第 9.6 完整恢复、11 组清理及 13 组真实验收未勾选。1.7 的上游产物证据仍待核实，本轮仅完成本地文件机制和合成集合验证。设计细化与 docs/artifact-delivery.md 已更新。

最终验证按最新 AGENTS.md 执行，以下命令均退出 0：

- `uv run --frozen pytest --basetemp .cache/artifact-final-complete -q`：333 passed，35.33s；新增产物测试 27 项，包括本地 HTTP、合成断流、限额／空间故障、重试耗尽、部分成功、发布前后中断、登记失败后数据库重开、同名同内容不误认、外部同大小改动、默认及显式覆盖、目录替换竞争、取消与响应丢失。真实容器解码／内容质量不在基本结构检查范围。
- `uv run --frozen ruff check .`：All checks passed；`uv run --frozen ruff format --check .`：92 files already formatted（含 Markdown 示例）。
- `uv build`：sdist 与 wheel 构建成功，保留 dist 内产物；`uv run --frozen zhenzhen-seedance-video --version`：0.1.0.dev0，不代表完整业务服务验收。
- OpenSpec change 严格校验、三项主规范严格校验及 `git diff --check`：通过。

中间发现并修复：并发目标创建被底层包装为素材错误，现返回产物交付错误；下载并发测试改为事件同步避免时间偶然性；数据库重开测试未关闭新实例导致 pytest 打印通过后无法退出，已修复夹具并结束本轮三个遗留测试进程，再取得最终正常退出的全量证据。中间未正常退出的计数不作为最终通过记录。

SUCCESS 和费用完整响应仍待核实，1.1／8.4 不勾选；未调用真实供应商，未进行实际 Agent Host 验收，未执行 Git 暂存／提交／推送。主规范未新增同步，change 未归档。
收尾：已核对并清理本轮 8 个隔离测试目录及其 pytest current 链接，工作区 pytest 进程复查为 0；保留源码、fixtures、验证记录及 dist 构建产物，未触及真实用户配置或任务库。


## 2026-11-13：素材清理、有限重试与恢复（第 11 组）

完成 11.1、11.2、11.3，总进度 44/67。新增 cleanup_rules.py、material_readers.py、cleanup.py；任务终态／放弃事实与清理授权在同一事务保存，启动扫描补齐已满足条件的待办。清理循环已接入本地后端。生成成功待下载和未放弃的未知任务保留素材；明确放弃未知任务仍清理，不修改生成事实。

每任务读取协调器阻止新读取，通知线程停止、取消异步操作并等待句柄结束；上传准备及素材修复共用该协调器，支持嵌套读取。删除限定登记 root/material_id.input，固定目录祖先、独占打开文件，校验大小及摘要后通过同一 Windows 文件句柄标记删除；不跟随链接、不递归删除、不接受任意工具路径。完成后登记 cleaned，并核对已终止的修复 intent；不会重建被清理副本。

清理预算在首次处理时固定，每次尝试前持久化消耗及预算事件。文件占用、权限和路径异常有限退避，耗尽显示 MATERIAL_CLEANUP_FAILED；重启不重置，零预算的中断记录仅允许核对文件已经不存在。删除后保存失败保留 deleting，恢复可补记完成。显式版本化重试只重置已有失败清理待办，不改变远端终态或生成视频。新增 docs/material-cleanup.md，并更新设计细化、产物交付／调度恢复／隔离测试说明。

最终验证按最新 AGENTS.md 执行，以下命令均退出 0：

- `uv run --frozen pytest --basetemp .cache/cleanup-complete -q`：355 passed，35.57s。
- 新增清理测试 22 项，覆盖全部触发及保留条件、原文件／超分输入保留、文件占用预算耗尽、数据库重开预算保留、显式重试版本冲突、越界／链接／内容变更拒绝、删除后落账失败、已不存在补记、零预算中断、存储故障前不删、读取线程和修复竞争、嵌套读取。定向清理测试 22 passed；接收／调度／Windows 后端／任务状态回归 59 passed。
- `uv run --frozen ruff check .`：All checks passed；`uv run --frozen ruff format --check .`：97 files already formatted。
- `uv build`：sdist 与 wheel 构建成功，保留 dist 产物；`uv run --frozen zhenzhen-seedance-video --version`：0.1.0.dev0。
- OpenSpec change 严格校验通过，三项主规范严格校验 3/3 通过，`git diff --check` 通过。

真实上传及上游取消仍未接入，本轮取消事实仅用合成状态验证清理条件；SUCCESS 与完整费用响应继续待核实，1.1／8.4 不勾选。第 9.6 跨阶段统一恢复验收、第 12 组完整工具接线及实际 Host／供应商验收仍未完成。未调用真实供应商，未执行 Git 暂存／提交／推送；未新增主规范同步，change 未归档。
收尾：本轮 6 个隔离测试目录及其 pytest current 链接已核对后清理，工作区 pytest 进程复查为 0；保留验证记录、源码、fixtures 和 dist 构建产物，未操作真实用户配置或任务库。


## 2026-11-13：MCP 工具接线、查询与有界等待（第 12 组）

完成 12.1–12.5，OpenSpec 每项复查进度由 44/67 递增至 49/67。新增 tools.py 统一业务门面、queries.py 查询层；SDK v2 stdio 注册全部设计工具，生成／超分入口独立，类型生成输入与结构化输出 schema。refresh、verify、copy 以及可能记录外部文件变化的 list_artifacts 均不标注只读。生产后端复用本地接收、产物、清理与诊断；需要真实适配器的操作明确门控，合成适配器只在测试构造注入。

一致数据库事务返回任务、授权、有效参数、费用和产物数量摘要。签名游标绑定筛选与 sequence，非消费异常名单跨客户端可见；响应按字节预算分页。wait_task 按单调时间有界复查业务版本，查询后到等待前的变化立即返回；仅观察时间不唤醒，可靠进度变化提升版本。错误使用稳定码及有界诊断，不输出原堆栈、提示词、签名 URL；存储故障读结果标 stale，额度显示真实占用与非负可用值。

内部 RPC 增加仅限 wait_task／copy_artifact 的取消控制；接收和管理请求不因等待者取消撤销。复制取消继续等待线程句柄收尾，发布前保全旧目标。两客户端重复恢复不叠加轮次，冲突响应保留最新版本。新增 docs/agent-tools.md，更新设计和现有运行／交付／清理说明。

最终验证（命令正常退出 0）：

- `uv run --frozen pytest -q --basetemp .cache/tools-final`：363 passed，42.49s；新增 8 项真实 SDK v2 stdio 协议隔离测试，覆盖全部工具发现／调用、完整合成闭环、两个客户端分页和异常可见、预算与故障摘要、取消接收等待／管理响应丢失、复制取消、重复恢复和版本冲突、进度与时间戳等待差异。此前全量 362 passed 后补充进度专测，再取得本次最终结果。
- `uv run --frozen ruff check .`：All checks passed；`uv run --frozen ruff format --check .`：101 files already formatted。
- `uv build`：sdist 与 wheel 成功；`uv run --frozen zhenzhen-seedance-video --version`：0.1.0.dev0。
- change 严格校验通过，三项主规范严格校验 3/3 通过；`git diff --check` 通过。

中间协议测试发现普通 dict 返回声明未产生结构化输出，修正为 dict[str, Any] 后通过；故障注入夹具的只读属性赋值和复制 hook 名称已修正并复验。失败运行不计为通过。

未核实：SUCCESS、完整费用响应、上传／远端取消等上游细节；生产适配器、9.6 统一恢复和第 13 组实际 Host／供应商验收仍未完成。未调用真实供应商，未执行 Git 暂存／提交／推送。主规范本轮未同步，change 未归档。

收尾：清理本轮六个固定隔离目录 tools-runtime、tools-protocol、tools-races、tools-copy-cancel、tools-full、tools-final。清理脚本读取目录链接的 DirectoryName 时出现非终止错误；删除目标已限制为 .cache 的上述直接子目录，链接用无 Recurse 的 LiteralPath 删除。随后使用 ErrorActionPreference=Stop 重新检查，六个目录均不存在，工作区 pytest 进程为 0，git diff --check 退出 0。保留源码、fixtures、记录和 dist；未操作真实用户配置或任务库。


## 2026-11-13：统一启动恢复与有限停机（9.6）

完成 9.6，进度 50/67。新增 lifecycle.py，将恢复屏障置于 RPC 发现信息发布之前，复用接收、调度、产物和清理恢复；替换生产后端按所有未结束 intent 一律冻结任务的逻辑。占位根据任务事实事务重建，已知 ID 续接、未知提交保留，降额度不取消已有任务，身份不兼容保留占位，原输出路径、查询及清理预算不重置。生产适配器仍未安装，无真实网络生成。

协调器统一统计后台阶段和内部 shield 工作；serve_until_idle 同时考虑 RPC 与后台空闲，draining 后不再启动新后台工作，退出复用同一剩余期限而非每阶段另等一轮。期满取消 I/O，保留未完成 intent，等待文件／数据库安全收尾。恢复耗时不消耗首次 Host 连接的宽限期。设计和 scheduling-recovery／local-rpc 说明同步更新。

实际验证（均正常退出 0）：

- `uv run --frozen pytest -q --basetemp .cache/lifecycle-full`：371 passed，45.48s。
- 新增 8 项 lifecycle 测试：真实 SQLite 关闭重开，跨阶段已知／未知提交、准备 FIFO、降额度占位重建、退避预算及旧目录、身份切换、停止状态保持、下载发布前后恢复与清理、跟踪过期与清理耗尽不重置、恢复失败不启动工作、无 Host 门与有限关闭。使用合成适配器和本地假 HTTP；既有 Windows 隐藏后端及 stdio 协议回归也包含在全量结果。
- `uv run --frozen ruff check .`：All checks passed；`uv run --frozen ruff format --check .`：103 files already formatted。
- `uv build`：sdist／wheel 成功；`uv run --frozen zhenzhen-seedance-video --version`：0.1.0.dev0。
- change 严格校验通过，主规范 3/3 通过，`git diff --check` 通过。

SUCCESS 和费用完整响应继续待核实，8.3／8.4 及第 13 组真实交付验收尚未完成。本轮不调用真实供应商，不执行 Git 暂存／提交／推送；主规范未新增同步，change 未归档。

收尾：核对归属和 pytest current 链接后清理本轮三个隔离目录 lifecycle-first、lifecycle-stages、lifecycle-full，清理命令退出 0，工作区 pytest 进程复查为 0。保留源码、fixtures、验证记录与 dist 构建产物，未触及真实用户配置或任务库。


## 2026-11-13：安装交付与 Windows 多客户端集成（13.1 部分、13.2 完成）

完成 13.2，总进度 51/67。13.1 保持未勾选：本轮完成当前 Windows 上的全新解包目录／独立虚拟环境安装，未取得全新 Windows OS/VM 验收证据。当前实现未发布，不编造正式标签、CI 结果或提交 SHA。

交付 README.md、MANUAL.md、根目录空 .env.example；安装命令使用 uv sync --frozen --no-dev，日常命令使用 --no-sync。手册明确安装目录配置、同用户共享、实际 Host 未验收、升级保护私有配置、程序回滚与数据恢复区别。新增源码包根目录 only-include 白名单；sdist 54 个文件、wheel 36 个文件，检查无 tests、缓存和私有 .env。构建产物保留于 dist，测试包不进入正式发布。

全新目录从本轮源码包解包，独立 .venv 通过冻结离线安装（使用现有 uv 包缓存，不借用仓库 .venv），安装包实际入口完成 stdio 工具发现／接收及空 Resources／Prompts 检查；模块位置位于解包项目中。注册表输入被测试 bootstrap 隔离，未替换安装目录解析。确认隐藏后端正常退出，再移除测试安装副本，任务库和输出 canary 仍在隔离用户数据根。旧备份演练在停止窗口使用 SQLite backup／integrity_check，随后原库产生提交；恢复副本加离线 BACKUP_RESTORE_REVIEW_REQUIRED 屏障后不会重复派发。过新 schema=999 拒绝及未知占位备份测试纳入全量回归。

内部 runtime 构造器支持测试依赖注入，CLI 不提供开关；tests/synthetic_backend.py 使用真实所有权、RPC、生命周期、工具和关闭逻辑，作为独立 Windows 进程运行。两个独立 stdio 前端验证并发去重、跨客户端复制与 SHA-256；只强制结束测试创建的前端进程树，后端继续服务；配置冲突仅拒绝新客户端，宽限重连保持后端 PID。准备、提交后、ID 落账后、下载发布前／后五个位置真实进程退出后恢复，断言合成提交计数为 1；结果不明仍占位且不重提。子进程存储故障门阻止新接收，内部核对恢复后完成落盘。

中间发现并修复两个问题：sdist 普通 include 模式匹配到嵌套测试目录，改用根 only-include 后包检查通过；Windows 发现文件短暂读取会阻挡 os.replace，现只对本地元数据 PermissionError 作最多 10 次、间隔 10ms 重试，持久拒绝仍失败且旧记录保留，不重试任何付费请求。新增定向测试覆盖成功重试和预算耗尽。初次失败不算验收通过。

最终实际验证（退出 0）：

- `uv run --frozen pytest -q --basetemp .cache/install-full`：381 passed，100.46s。
- 安装与独立进程定向测试：9 passed，52.37s；全量另包含元数据发布有限重试测试。
- `uv run --frozen ruff check .`：All checks passed；`uv run --frozen ruff format --check .`：108 files already formatted。
- `uv build`：sdist／wheel 成功；入口版本检查：0.1.0.dev0。
- change 严格校验通过，主规范 3/3 通过，`git diff --check` 通过。独立进程夹具均 wait 结束，额外进程复查为 0。

SUCCESS 和完整费用响应继续待核实；生产适配器与真实供应商、实际 Agent Host 验收未完成。本轮无真实供应商调用，无 Git 暂存／提交／推送；主规范未新增同步，change 未归档。13.1 的干净系统验收保留未完成，不以本机虚拟环境替代。

收尾：核对四个固定测试根及 pytest current 链接后，清理 install-integration、install-clean、install-second、install-full；命令退出 0。保留 README、MANUAL、空配置示例、测试源码、脱敏验证记录和 dist 交付物，未操作真实用户状态或 Host 配置。最终构建后在 dist/SHA256SUMS.txt 保存本地资产摘要，该文件不是发布证明。


## 验收矩阵与交付证据（13.4／13.7）

2026-11-13：本轮只完成不依赖真实调用的交付准备。新增 docs/provider-acceptance-matrix.md：9 个未授权／未执行候选案例，覆盖两个 api_id、2.0 三档及三种输入、2.5 两区域样片／成片、edit、独立超分、上传及优化授权；逐项列出 26 模型，其中 8 个进入候选、18 个仅契约覆盖。素材／提示词、调用及费用上限均待明确，真实允许调用数为 0。13.4 保持未勾选，不能把计划编制等同授权完成。

新增 docs/delivery-evidence.md，八项 capability 分别关联实现入口、测试文件、使用说明及限制；修正 proposal 中旧的全响应未知及尚无实现／tasks 说明，并将 design 的规划阶段状态更新为实施证据入口。未改变已批准功能范围；SUCCESS、费用完整组合、上传／样片／尾帧等剩余接口细节仍待核实。无生产业务代码改动。

实际执行结果：

| 命令／核查 | 退出结果与关键输出 |
| --- | --- |
| `uv run --frozen pytest -q --basetemp .cache/acceptance-evidence` | 0；381 passed in 101.30s；含四份用户样例解析、合成网络／调度／产物、安装及 Windows 多进程测试 |
| `uv run --frozen ruff check .` | 0；All checks passed |
| `uv run --frozen ruff format --check .` | 0；110 files already formatted |
| `uv build` | 0；构建源码包与 wheel；文档收尾后再构建更新本地 dist |
| `uv run --frozen zhenzhen-seedance-video --version` | 0；0.1.0.dev0 |
| `openspec validate add-local-video-generation-service --type change --strict` | 0；change valid |
| `openspec validate --specs --strict` | 0；3 passed, 0 failed；这是既有三项工作规范，不表示八项业务规范已同步 |
| `git diff --check` | 0；无输出 |
| 一次性本地 Python 文档核对 | 0；26 模型与 VIDEO_MODELS 精确相等，9 案例唯一，8 视频候选加 1 独立超分，8 capability 的规范／代码／测试及文档链接存在 |

测试 fixture 负责等待其创建的子进程退出。本轮 .cache/acceptance-evidence 已按绝对范围与重解析点核查后删除，仅移除该目录内 pytest current 符号链接及本轮临时资源。额外 WMI 进程盘点两次均返回“调用已取消”（退出 1），因此本轮没有独立进程扫描为零的证据，不把该盘点记录为通过；没有强杀其他进程。构建产物保留在 dist，摘要见 dist/SHA256SUMS.txt，属于未提交工作区的开发构建，不是发布验收。

13.7 的证据映射、检查与限制披露已完成，可勾选；总进度 52/67。1.x、8.3、8.4 及 13.1、13.3–13.6 的未完成判断仍保留。未调用真实供应商，没有真实费用、SUCCESS 或实际 Host 新证据；不提交／推送 Git，不发布、不同步八项业务主规范、不归档。


## 契约核实与单次上传（第 1 组／8.3）

2026-11-13：仅离线复核已有 llms.txt 快照（摘要与先前记录一致）和用户契约。1.3 完成条件能力调查与逐项门控说明，1.4 完成上传核心文档响应证据、格式及限额／期限未知边界记录；两项勾选后进度54/67。1.1/1.2/1.5–1.8 保留缺口，尤其 SUCCESS 和完整费用组合不解析、不视为已核实。

新增 tests/fixtures/provider/documented/upload-success.json 与来源说明（原始文档省略号 URL，不是真实请求）；新增 uploads.py 内部单次 multipart 组件与严格解析。大小／摘要不符不发送，成功核对 url/file_type/size，expires_in 缺失保留未知，不默认86400、不推导保证到期时间；URL 不进入 repr。无生产接线、无隐式重试、无生成副作用。8.3 的持久化预算／退避、过期引用更新、重启和清理协调接线仍未完成，保持未勾选。

首次新增测试发现测试配置遗漏临时 LOCALAPPDATA 和 fixture 路径依赖当前目录，结果4失败、13错误、6通过；已改为 tmp_path 和基于 __file__ 的路径。定向复验 `uv run --frozen pytest tests/test_uploads.py -q --basetemp .cache/upload-targeted-fixed`：退出0，23 passed in 0.24s。

首次全量 `uv run --frozen pytest -q --basetemp .cache/upload-full`：退出1，403 passed、1 failed in 125.26s。失败为既有 Windows 集成测试 taskkill /T /F 返回“调用已取消”，不是上传解析失败。修复测试强制退出方式：独立后端事先启动，只用测试自身 Popen 保留的 Windows 进程句柄终止其独立前端，不枚举／终止其他进程，不依赖 WMI 和 PID 重用。13.2 对应用例缺陷在本轮修复并重新验证，不把初次失败抹掉。定向复验 `uv run --frozen pytest tests/test_windows_integration.py::test_two_frontends_dedup_copy_conflict_and_forced_frontend_exit -q --basetemp .cache/upload-process-fix`：退出0，1 passed in 8.59s。

其他实际检查：Ruff check 退出0 All checks passed；Ruff format --check 退出0，113 files already formatted；uv build 退出0，源码包和wheel构建成功；入口 --version 退出0为0.1.0.dev0；OpenSpec change严格校验退出0；三项主规范严格校验3 passed；git diff --check退出0。文档收尾后再次构建并刷新本地摘要。全量修复后复验与清理结果续记如下。


修复后全量 `uv run --frozen pytest -q --basetemp .cache/upload-regression`：退出0，**404 passed in 101.97s**。所有本轮测试目录 upload-targeted、upload-targeted-fixed、upload-full、upload-process-fix、upload-regression 已在绝对范围和重解析点校验后清理，失败原因和复验结果保留于本记录。测试所拥有进程由 fixture 等待收尾；本轮不再以已知失败的 WMI 扫描作零遗留证明，未操作其他进程。

本轮完成1.3、1.4调查任务并部分推进8.3，进度54/67；SUCCESS／完整费用响应继续待核实。全程未调用真实供应商、未提交或推送Git、未同步业务主规范或归档。dist 为本地开发构建，最终摘要更新于 dist/SHA256SUMS.txt，不视为正式发布证据。


## 上传预算、恢复与调度接线（8.3）

2026-11-13：新增 UploadService，复用 uploads／attempts／task_events 保存逐素材、连接身份绑定的引用、预算、发送意图和退避。首次固定1+UPLOAD_RETRIES次尝试；发送前扣减，进程重启／网络恢复／链接过期不重置，有限指数退避带抖动。退避中的素材跳过候选选择，其他可派发任务继续；不占生成额度。成功返回只更新临时引用，不改变任务有效参数与请求摘要。

接收事件保存后缀；上传使用已登记副本、锁定句柄及共享 MaterialReaders，统一 NetworkPolicy 和存储副作用门。缺后缀旧记录、缺 expires_in、回拨时钟、永久错误或预算耗尽转待处理。expires_at 为上传开始时间加实际 expires_in 的本地保守截止，不是供应商精确有效期保证。Scheduler 在生成提交事务内复查引用，过期不能生成intent；已提交未知、取消或放弃不重传／重提。迟到上传引用可保存为 discarded，但不能恢复自动执行。

Scheduler 新增内部 uploads 注入，启动恢复上传 intent 且保持预算；run_backend 提供内部 upload_factory。生产默认仍无完整生成适配器，不因本轮修改开始访问供应商。无数据库 schema 变更或隐式迁移。说明见 docs/upload-preparation.md；SUCCESS 与费用完整响应继续待核实。

定向验证：初版上传＋持久化测试30 passed；补充鉴权保护、时钟回拨、Host离开、存储故障与迟到结果后35 passed；实际 upload_once＋MockTransport 的 multipart/429/成功与调度贯通后，持久化测试13 passed。进一步补充退避不阻挡后继任务及抖动后，`uv run --frozen pytest tests/test_upload_service.py tests/test_uploads.py -q --basetemp .cache/upload-durable-final-target` 退出0，37 passed in 1.05s。所有数据均为合成或已有文档fixture，未进行真实调用。

首轮全量 `uv run --frozen pytest -q --basetemp .cache/upload-durable-full` 退出0，417 passed in104.77s；该结果对应补充退避候选测试之前的版本，最终版本另行全量复验。初次Ruff发现SQL长行、导入顺序及测试同步Path检查，修正后 `uv run --frozen ruff check .` 退出0；format --check退出0，最终116 files already formatted。uv build退出0；入口 --version退出0为0.1.0.dev0；OpenSpec change严格校验退出0，主规范严格校验3 passed；git diff --check退出0。最终复验与收尾结果续记如下。


最终全量 `uv run --frozen pytest -q --basetemp .cache/upload-durable-final`：退出0，**418 passed in 106.73s**。8.3已勾选，CLI确认55/67。当前未启用生产供应商生成适配器；没有真实上传、生成、查询或下载调用，没有Git提交／推送。

本轮六个 upload-durable-* 指定测试目录已按绝对路径与重解析点校验后清理，保留文档fixture及验证结论。测试拥有的进程由fixture等待退出；未使用WMI作额外零遗留证明，也未强杀无关进程。最终文档更新后构建并刷新 dist/SHA256SUMS.txt；本地产物不代表发布验收。八项业务主规范未同步、change未归档。


## 四份响应样例的兼容适配接线（8.4部分）

2026-11-13：新增CompatibilityAdapter，通过既有NetworkPolicy执行固定兼容端点提交／查询并调用decode_response。prepare使用任务接收快照，不重算优化授权／默认值；未替换本地素材拒绝发送。API请求拒绝重定向，不切换/v1/videos；查询ID限安全路径字符。HTTP状态仅用于保守传输分类，不证明未接单；POST无自动重试，临时查询错误使用既有预算。

四种已确认状态与URL通过Scheduler持久化；失败白名单错误码写入观察事实并在Queries摘要显示，原始message不存为错误内容、不透传。成功缺URL保留succeeded并待处理；终态冲突保留已确认事实。完整产物集合尚未核实时ARTIFACT_SET_UNVERIFIED进入待处理而不终止后台循环；费用缺失本身不阻止记录生成成功。SUCCESS与完整费用组合仍待核实，不解码费用、不默认记零。

本轮所有传输为MockTransport合成响应，四份用户fixture未改动；HTTP200仅测试设定。生产CLI默认仍无完整供应商执行器，未发送真实请求。8.4因缺SUCCESS／费用核心剩余证据仍保持未勾选，进度55/67；不将内部接线等同供应商验收。

实际定向测试：首次适配器21 passed；加入失败码／冲突／费用边界后，适配器＋解析器43 passed in1.68s；加入端点重定向保护及网络回归后，`uv run --frozen pytest tests/test_compatibility_adapter.py tests/test_provider_response.py tests/test_network.py -q --basetemp .cache/compatibility-redirect`退出0，63 passed in2.45s。

首轮全量 `uv run --frozen pytest -q --basetemp .cache/compatibility-full`退出0，441 passed in97.75s（补充API重定向保护前版本）。最终版本另行复验，结果续记。Ruff check退出0 All checks passed；format --check退出0，最终119 files already formatted；uv build退出0；入口 --version退出0为0.1.0.dev0；OpenSpec change严格校验退出0；三项主规范严格校验3 passed；git diff --check退出0。


最终全量 `uv run --frozen pytest -q --basetemp .cache/compatibility-final`退出0，**442 passed in116.11s**。五个本轮compatibility-*指定测试目录已核对绝对范围与重解析点后清理；fixture和验证结论保留。测试自有进程由fixture收尾，不使用WMI额外声明零遗留。最终文档更新后重新构建，开发包摘要更新至dist/SHA256SUMS.txt。

8.4部分完成，仍因SUCCESS及费用完整响应缺口保持未勾选，总进度55/67。未发送真实供应商请求，未提交或推送Git，未同步八项业务主规范或归档；本地构建不作为正式发布证明。


## metadata.url 主视频交付（8.4部分继续）

2026-11-13：内部 CompatibilityAdapter 注入任务库后，从已关联 remote_id、无终态冲突的 completed 观察读取主视频 URL。新增 ArtifactManifest 和事务内 task_events 集合完整性标记，避免把单个已确认视频冒充全部必需产物。格式来源为显式 output_format 或 URL 路径；不从签名查询参数推断，实际下载继续验证容器、长度与摘要。下载不携带 API 凭据，列表和任务快照不暴露签名 URL。

主视频 ready 后可经既有复制工具交付，原产物保留；任务 delivery=partial、artifact_set_status=unverified、ARTIFACT_SET_UNVERIFIED 跨数据库重开保存，不进入完整交付终态，不自动清理输入副本。显式放弃仍按已有规则清理。重复成功刷新保持 partial；成功恢复所有已知下载后移除已解决的产物错误，但保留集合未知标记。设计与产物 delta spec、tasks、适配器／交付／工具／证据文档已更新。未同步业务主规范，未归档。

实际验证：首次定向组合58 passed/1 failed，为测试误读复制响应sha256字段；改为实际size_bytes及内容验证。随后8 passed/1 failed揭示重复刷新将partial降为pending，已修复Scheduler和TaskState。补充畸形URL测试首次9 passed/1 failed：解析器已提前拒绝URL，错误为RESULT_URL_UNAVAILABLE，修正测试期望，不放宽生产校验。

全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/main-video-full` 退出0，451 passed in109.11s。该轮收集时新增测试为9项；之后补充畸形URL防御、事件版本取最新值，最终定向 `uv run --frozen pytest tests/test_main_video_delivery.py -q --tb=short --basetemp .cache/main-video-final2` 退出0，10 passed in0.89s。未把补充后的测试数冒充全量结果。

`uv run --frozen ruff check .` 退出0；`uv run --frozen ruff format --check .` 退出0，121 files already formatted。change与engineering-practices、git-collaboration、manual-writing三项主规范严格校验均退出0。版本入口退出0，0.1.0.dev0；git diff --check退出0。构建结果及临时目录收尾见下文。

本轮只使用合成传输与四份用户样例；未调用真实供应商，未提交或推送Git。尾帧／完整产物集合、SUCCESS、费用完整响应仍待核实；生产CLI未启用供应商适配器。8.4继续未勾选，55/67，不将主视频部分交付视为完整供应商验收。

构建 `uv build` 退出0，源码包与wheel生成成功；六个本轮 main-video-* 指定临时目录在绝对路径和重解析点校验后删除，保留fixture与记录。测试进程由fixture收尾，不宣称额外WMI零遗留验证。文档收尾后重建并刷新dist/SHA256SUMS.txt；本地开发包不代表正式发布。


## 主视频 MCP 工具与跨客户端重启复验（9.6／12／13.2）

2026-11-13：新增 tests/main_video_backend.py 和 tests/test_main_video_protocol.py，复用独立后端启动fixture及真实MCP SDK stdio客户端；请求经前端、RPC、Tools、Scheduler、CompatibilityAdapter、NetworkPolicy、SQLite和ArtifactService。四份用户fixture未改写；测试返回的成功URL替换为合成站点，API与视频字节均由MockTransport提供，不产生外部HTTP请求。测试安装根、用户环境与LOCALAPPDATA隔离；生成POST不使用生产密钥。

首次 `uv run --frozen pytest tests/test_main_video_protocol.py -q --tb=short --basetemp .cache/main-protocol-target` 退出1，3 passed/1 failed in38.35s。发布前崩溃重启后等待交付超时；离线核对任务为succeeded/pending、artifact为pending，但auto_mode=needs_attention且只有ARTIFACT_SET_UNVERIFIED。这是Lifecycle启动时将全部attention当作阻断原因造成。9.6重新打开，设计补充只对原active且成功任务的集合未知说明作非阻断处理；保留原needs_attention／abandoned及其他错误门控。测试对发布前恢复的下载次数也按既有“不发布中断临时文件，预算内重新下载”契约改为2；发布后仍为1，不将两种阶段混同。

修复后 `uv run --frozen pytest tests/test_main_video_protocol.py tests/test_lifecycle.py -q --tb=short --basetemp .cache/main-protocol-recovery` 退出0，13 passed in32.93s。五个协议场景包含：两个独立stdio前端接续、正常最后Host退出并重启、跟踪中重启、发布前后崩溃恢复、403待处理后新客户端显式下载重试。协议工具覆盖submit/get/find/wait/list/verify/copy/retry，文件摘要一致，复制默认冲突／显式覆盖／相对和绝对路径验证通过。已知主视频ready仍是任务partial和集合unverified；费用not_returned，原产物保留，响应无签名URL或视频Base64。

该轮脱敏请求计数（submit/query/download）：跨前端并已就绪重启1/2/1；403后重试1/1/2；发布前崩溃1/1/2；发布后崩溃1/1/1；跟踪中正常退出重启1/4/1。query次数受轮询时序影响，测试不把该次数设为上游协议保证；每任务submit固定断言1。后端正常退出码0，故障注入退出91；fixture通过持有的Popen句柄等待所拥有进程退出，不做WMI全局扫描或强杀无关进程。

其后补充五种启动授权回归：active集合未知可续、原needs_attention保留、abandoned保留、额外下载耗尽错误阻断、连接身份不兼容阻断，均纳入最终全量测试。详细场景与证据边界见[主视频协议验证](main-video-protocol-validation.md)。实际Agent Host验收13.3仍未完成；尾帧／完整产物集合、SUCCESS和费用完整响应待核实，8.4不勾选。无真实供应商调用、Git提交或推送；业务主规范未同步，change未归档。


最终全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/main-protocol-full` 退出0，462 passed in142.59s，包含全部新增协议及启动授权回归。9.6修复后重新勾选，恢复55/67。`uv run --frozen ruff check .` 退出0 All checks passed；`uv run --frozen ruff format --check .` 退出0（该次输出124 files already formatted）；版本入口退出0为0.1.0.dev0。change及三项工作主规范严格校验均退出0，git diff --check退出0。`uv build`退出0；独立检查wheel/sdist确认不含tests或测试后端。文档收尾后重建并刷新dist/SHA256SUMS.txt，仅本地开发构建，不代表远端CI或发布。

收尾：三个本轮main-protocol-*测试目录在绝对路径和嵌套重解析点校验后已删除；保留测试源码、fixtures和脱敏验证记录。所有测试拥有的后端进程均经fixture句柄等待退出；未使用WMI扫描作全机零遗留声明，未触碰用户Host配置或生产数据。


## 本地素材到主视频交付的完整 MCP 隔离验证

2026-11-13：新增tests/test_material_protocol.py，扩展仅测试使用的main_video_backend.py注入真实UploadService及合成HTTP传输。没有修改生产执行策略或开启真实供应商。已有设计与specs保持原义，tasks追加7.1–7.3／8.3／9.6／10／12／13.2的集成证据，仍55/67；8.4及实际Host验收13.3不勾选。

通过独立MCP stdio客户端提交mini-i2v本地图片，两个客户端按同request_key去重，托管完成后修改原件；multipart请求核对原始托管字节、内部文件名及Bearer，生成payload仅含上传URL、不含local_path或material_id。实际CompatibilityAdapter使用样例JSON的明确合成模型/URL替换；不改变原fixture、不据替换认定真实i2v接口已核实。下载不附API凭据。主视频list/verify/copy经真实协议交付并校验SHA-256，任务partial、集合unverified、费用not_returned，输入副本保留，没有正常完成清理任务。

三种跨进程接续：上传响应未落账（退出91）、上传引用已落账但生成未提交（退出91）、生成处理中最后客户端退出（后端正常退出0）。新客户端按request_key找回，由新后端继续。离线只读检查已退出后端的隔离数据库：task/material/upload各一条，material_id和有效参数不变，上传尝试历史及剩余预算不重置。

定向命令 `uv run --frozen pytest tests/test_material_protocol.py -q --tb=short --basetemp .cache/material-protocol-target` 退出0，3 passed in19.33s。脱敏请求计数upload/submit/query/download分别为2/1/1/1、1/1/1/1、1/1/4/1；查询次数仅为该次观察，不作为固定协议保证。每任务只生成一次，已保存且有效的上传引用不重复上传。首次Ruff指出跨进程文件门的ASYNC110抑制注释放错行，已修正到while行；后续Ruff通过，没有忽略生产代码检查。

验证范围详见[素材完整流程验证](material-protocol-validation.md)。所有HTTP均MockTransport，素材和视频均为合成字节；不证明内容质量、真实供应商接受性或实际Host兼容。尾帧／完整集合、SUCCESS、费用完整响应继续待核实。测试隔离生产密钥、用户环境、安装.env与LOCALAPPDATA；后端由fixture持有句柄等待退出，未用WMI全机扫描或强杀无关进程。无真实调用、Git提交或推送，八项业务主规范未同步，change未归档。

最终全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/material-protocol-full` 退出0，465 passed in155.83s。Ruff check退出0；format --check退出0（126 files already formatted）；版本入口退出0，0.1.0.dev0；change及engineering-practices、git-collaboration、manual-writing三项主规范严格校验均退出0；git diff --check退出0。uv build退出0，wheel／源码包生成成功，独立检查确认不含tests及测试后端。文档收尾后重建和刷新dist/SHA256SUMS.txt，本地开发构建不代表正式发布或远端CI。

收尾：本轮material-protocol-target及material-protocol-full两个指定测试目录已在绝对路径／重解析点校验后删除，保留测试源码、fixtures和脱敏证据。测试拥有的后端均由fixture等待退出；未宣称额外全机进程扫描结果。


## 上传失败、有限重试、过期重传与清理协议验证

2026-11-13：新增tests/test_upload_failure_protocol.py，扩展仅测试main_video_backend.py的合成500／短期引用场景，生产代码未改变。真实MCP客户端经独立stdio进程调用现有提交、查询、等待、找回、核验、复制及abandon_task，复用真实UploadService和后端恢复。全部HTTP由MockTransport处理，不读取生产凭据／任务库；不更改原契约fixtures。

定向 `uv run --frozen pytest tests/test_upload_failure_protocol.py -q --tb=short --basetemp .cache/upload-protocol-target` 退出0，4 passed in30.21s。首次失败后成功和两次失败耗尽都恰好上传2次，前者生成1次、后者0次；重启预算仍0，上游恢复不自动复活耗尽任务。过期场景上传2次、生成1次，原件删除仍从托管副本恢复，原参数／摘要和预算历史不变。上传在途由第二客户端放弃后cleanup done、只删托管副本、原件保留，重启abandoned，上传1次、生成0次。故障退出仅过期引用场景使用测试退出91，其他后端经有限关闭退出；fixture持有的进程句柄负责收尾。

新增说明在docs/upload-preparation.md，tasks及delivery-evidence更新；55/67不变。没有新增上传预算重置工具或放宽未知提交重试。尾帧／完整集合、SUCCESS、完整费用继续待核实，真实Host13.3和真实供应商验收未执行。无真实调用、Git提交或推送，业务主规范未同步，change未归档。

最终全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/upload-protocol-full` 退出0，469 passed in195.35s。Ruff check退出0；format --check退出0，127 files already formatted；版本入口退出0为0.1.0.dev0。change及engineering-practices、git-collaboration、manual-writing严格校验均退出0，git diff --check退出0。uv build退出0，独立检查wheel／源码包不含tests或测试后端；文档收尾后重建并刷新dist/SHA256SUMS.txt，未发布正式版本。

收尾：upload-protocol-target及upload-protocol-full在绝对路径及嵌套重解析点校验后已删除，保留测试源码、fixtures和脱敏证据。fixture等待测试拥有的进程退出；未使用WMI全机扫描作零遗留声明，未修改用户Host配置或生产数据。


## 多素材部分成功、失败恢复与并发去重协议验证

2026-11-13：扩展仅测试main_video_backend.py，新增tests/test_multi_material_protocol.py，生产逻辑未修改。两种场景均使用三张不同内容的本地图片和mini-multi请求；真实MCP客户端／stdio／RPC／后端上传调度，合成HTTP响应。首项成功后次项500，成功引用不丢弃，第三项保持待上传。可恢复场景在失败落账后退出91，耗尽场景有限重试后正常关闭；新后端下两个新客户端同时重放同key，沿用同一任务及素材。修改提示词的同key冲突拒绝。

定向 `uv run --frozen pytest tests/test_multi_material_protocol.py -q --tb=short --basetemp .cache/multi-protocol-target` 退出0，2 passed in16.76s。之后补充每项剩余预算、三份不同摘要和副本存在性断言，纳入最终全量。可恢复路径素材上传次数1/2/1、生成与下载各1，MCP复制摘要一致；耗尽路径1/2/0、生成与下载0。第一项成功上传整条记录保持不变，第二项预算不重置；参数快照和素材ID集合不变，一任务三副本，原件保留。完整集合未知时仍partial、不触发输入清理。

说明已补入docs/upload-preparation.md，tasks和delivery-evidence同步。范围仅三图multi隔离验证，不声称音视频混合全部实测或实际Host／供应商验收。尾帧／完整集合、SUCCESS和完整费用继续待核实；55/67保持，8.4和13.3不勾选。未调用真实供应商，未提交或推送Git，未同步业务主规范或归档。

最终全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/multi-protocol-full` 退出0，471 passed in201.97s，包含补充预算与副本断言。Ruff check及format --check退出0（128 files already formatted）；版本入口退出0为0.1.0.dev0；change及三项工作主规范严格校验均退出0；git diff --check退出0。uv build退出0，wheel／源码包独立检查不含tests与测试后端；文档收尾后重建并刷新dist/SHA256SUMS.txt，仅本地开发构建。

收尾：multi-protocol-target和multi-protocol-full两个本轮目录经绝对路径及重解析点校验后已删除，保留测试源码、fixtures和脱敏记录；fixture通过持有句柄等待本次后端退出，未作WMI全机零遗留声明，未修改用户Host配置或生产数据。


## 混合图片、视频、音频的完整 MCP 协议验证

2026-11-13：扩展tests/test_multi_material_protocol.py与仅测试main_video_backend.py；生产代码、契约fixtures及业务设计不变。新增PNG／MP4／MP3和MP4／MP3／PNG两种排列，各覆盖次项失败后崩溃恢复与重试耗尽后正常重启，共新增4个参数化场景。合成标记字节仅验证类型传递与流程，不声称可解码媒体、时长限制或内容质量已验证。

上传核对multipart内部文件名、MIME和对应字节，响应按素材类型返回file_type；生成payload严格匹配三项typed URL的原始顺序。两独立stdio客户端跨后端重启并发重放仍一任务三副本，首项成功记录完整复用，失败项预算延续。恢复分支1/2/1次上传、生成和下载各1次，MCP list/verify/copy摘要一致；耗尽分支1/2/0、生成下载0，重启仍待处理。保持托管副本和原件、任务参数与素材身份，集合未知不清理。

任务证据已更新，仍55/67；8.4、实际Host13.3与真实验收保持未完成。尾帧／完整产物集合、SUCCESS及费用完整响应继续待核实。全部HTTP由MockTransport处理，无真实供应商请求、Git提交或推送；八项业务主规范未同步，change未归档。

定向 `uv run --frozen pytest tests/test_multi_material_protocol.py -q --tb=short --basetemp .cache/mixed-protocol-target` 退出0，6 passed in49.11s（既有三图2项、新增混合4项）。Ruff check和format --check退出0，128 files already formatted；版本入口退出0为0.1.0.dev0。change与engineering-practices、git-collaboration、manual-writing三项主规范严格校验及git diff --check均退出0。

最终全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/mixed-protocol-full` 退出0，475 passed in235.05s。uv build退出0；独立检查wheel与源码包不包含tests或测试后端。文档收尾后重建并刷新dist/SHA256SUMS.txt，仅本地开发构建，不代表发布或远端CI。

收尾：清理命令因检测到重解析点退出1，未执行删除；mixed-protocol-target和mixed-protocol-full保留在.cache下，避免递归清理沿链接影响其他位置；保留测试源码与脱敏记录。fixture等待所拥有后端进程退出，不作WMI全机零遗留声明，不修改用户Host配置或生产数据。


## 2026-11-13 混合素材过期重传与在途管理协议验证

新增 tests/test_mixed_lifecycle_protocol.py，扩展仅测试 main_video_backend.py。PNG／MP4／MP3三份合成标记字节经真实stdio、RPC、共享后端和UploadService推进；HTTP完全由MockTransport提供，不证明媒体编码、时长或真实供应商接受性。生产实现与已批准需求设计不变。

- 视频或音频引用分别设置合成1秒有效期；三项上传记录持久化、尚未生成时注入退出91。到期后删除测试原件，新Host客户端找回任务，后端仅重传过期项并使用新URL，其他两项完整记录复用；素材上传计数分别1/2/1和1/1/2，生成与主视频下载各1次，MCP核验复制SHA-256一致。过期项预算扣减1，素材身份、摘要、参数快照不变，托管副本保留。
- 首项成功、第二项视频上传在途、第三项尚未上传时，另一客户端分别调用cancel_task与abandon_task。清理等待上传读取结束后删除全部三份托管副本，原件保留；计数1/1/0、生成下载0。新后端及新客户端仍显示本地取消或abandoned、cleanup done，不复活上传。旧uploading记录按恢复规则核对为pending，原预算和URL不变、attempt为reconciled；pending不构成新的执行授权。

主视频就绪仍partial、完整集合unverified、费用not_returned，不触发完整交付清理；取消／显式放弃按各自既有规则清理。尾帧／完整产物集合、SUCCESS、完整费用继续待核实。任务8.3、9.6、11、12／13.2补充协议证据，55/67保持；8.4和实际Host13.3及真实验收仍未完成。无真实供应商调用、Git提交或推送，业务主规范未同步，change未归档。

首次定向命令 `uv run --frozen pytest tests/test_mixed_lifecycle_protocol.py -q --tb=short --basetemp .cache/mixed-lifecycle-target` 退出1，2 passed/2 failed in28.96s。失败为测试误要求uploads整行跨启动完全不变；代码既有恢复规则将uploading改pending并核对attempt，未复活任务。已修正断言为检查该状态转换、预算及引用不变，并要求reconciled历史；生产代码未改。

修正后定向 `uv run --frozen pytest tests/test_mixed_lifecycle_protocol.py -q --tb=short --basetemp .cache/mixed-lifecycle-recheck` 退出0，4 passed in28.96s。Ruff check／format --check退出0（129 files already formatted），入口版本0.1.0.dev0退出0；change及三项工作主规范严格校验、git diff --check均退出0。

最终全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/mixed-lifecycle-full` 退出0，479 passed in263.16s。uv build退出0；wheel／源码包独立检查排除tests及测试后端。文档收尾后重建并刷新dist/SHA256SUMS.txt，仅本地开发包。

收尾检查退出0：mixed-lifecycle-target、mixed-lifecycle-recheck、mixed-lifecycle-full均检测到重解析点，因此保留于.cache下，未递归删除。fixture通过持有句柄等待其后端进程退出，不作全机WMI零遗留声明，不修改用户Host配置或生产数据。


## 2026-11-13 混合素材清理失败、有限重试与显式恢复

新增tests/test_mixed_cleanup_protocol.py，测试后端在真实delete_copy前注入第二项视频副本的CLEANUP_FILE_BUSY_OR_DENIED，其他项仍执行真实受控删除。PNG／MP4／MP3均为合成标记字节；上游由MockTransport处理，生产清理逻辑及业务设计未改。

取消与放弃各覆盖两种路径：首项已上传、第二项上传在途时管理操作触发清理，第一项删除成功，第二项失败。

- 剩余预算路径：失败落账后后端退出91，新客户端接入新后端，沿用剩余1次预算及退避，最终删除计数1/2/1，失败项剩余预算0。
- 耗尽路径：有限尝试2次后failed、MATERIAL_CLEANUP_FAILED，其他两项完成。后端正常退出，模拟故障解除后重启仍failed、预算0且删除次数不增加。过期版本retry_material_cleanup被拒绝；新版本显式恢复只重试失败项，最终计数1/3/1，重新授予的2次预算使用1次后剩1。已完成清理记录不变，完成后重复恢复不增加删除。

通过MCP查询、找回、等待与retry_material_cleanup核对异常消退、cleanup done及取消／放弃状态延续。重启前后cleanup_id、任务参数保持，原件全部保留、托管副本最终全部移除；上传1/1/0，生成和下载均0，不因清理恢复复活生成。此处busy/denied是测试注入，不宣称实测所有Windows占用／ACL故障来源；实际删除仍走Windows句柄路径。

尾帧／完整产物集合、SUCCESS与完整费用响应继续待核实；实际Agent Host及真实供应商验收未完成。补充11.1／11.2、9.6及12／13.2证据，55/67保持，8.4和13.3不勾选。无真实调用、Git提交或推送，业务主规范未同步，change未归档。

定向 `uv run --frozen pytest tests/test_mixed_cleanup_protocol.py -q --tb=short --basetemp .cache/mixed-cleanup-target` 退出0，4 passed in43.82s。Ruff check与format --check退出0（130 files already formatted）；版本入口退出0为0.1.0.dev0；change与三项工作主规范严格校验、git diff --check均退出0。

最终全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/mixed-cleanup-full` 退出0，483 passed in304.05s。uv build退出0；wheel／源码包检查确认不含tests或测试后端，文档收尾后重建并刷新dist/SHA256SUMS.txt。仅本地开发构建，不代表发布或远端CI。

本轮收尾检查退出0：mixed-cleanup-target和mixed-cleanup-full均发现重解析点，因此保留在.cache中，未递归删除。fixture等待所拥有后端进程退出，不作WMI全机零遗留声明。未修改用户Host配置或生产数据。


## 2026-11-13 混合素材删除／落账窗口崩溃恢复

新增tests/test_mixed_cleanup_crash_protocol.py，扩展仅测试main_video_backend.py。在三份PNG／MP4／MP3托管输入清理时，于第二项视频的删除调用前、或Windows实际删除完成后而cleanup_jobs尚未标done时注入进程退出91。第一项已完成，剩余项按登记待办恢复；成功删除计数与delete_copy调用次数分开记录，避免把不存在文件的核对误计为重复删除。上游全为MockTransport，输入为合成标记字节，生产实现与已批准设计不变。

四种场景组合两个崩溃窗口与剩余预算1／0。剩余1使用显式放弃触发；剩余0使用本地取消触发，并先注入一次忙碌错误消耗预算，不能用不允许的CLEANUP_RETRIES=0配置构造状态。

- 删除前崩溃：记录deleting但副本仍存在。有预算时重启续删；预算0时不调用删除，MCP显示MATERIAL_CLEANUP_FAILED，必须retry_material_cleanup重新授权预算后才完成。
- 删除完成未落账：记录仍deleting、副本已不存在。新Host客户端找回任务，由新后端核对并补记done；预算0仅核对缺失、不再次调用delete_copy。预算1路径可调用既有delete_copy核对缺失，不发生第二次实际删除。

所有场景各副本实际删除恰好1次；原件完整保留，cleanup_id和任务参数固定，已done记录不变。MCP get/find/wait/retry可观察恢复，完成后重复恢复不新增删除。取消／放弃事实不变，上传1/1/0、生成与下载0，不因清理恢复复活任务。断电、OS文件系统损坏或实际Host兼容不在此合成进程崩溃证据范围。

补充11.1／11.2、9.6、12／13.2证据，55/67保持；8.4及实际Host13.3仍未完成。尾帧／完整集合、SUCCESS和费用完整响应待核实。未调用真实供应商、未提交或推送Git，业务主规范未同步，change未归档。

首次定向 `uv run --frozen pytest tests/test_mixed_cleanup_crash_protocol.py -q --tb=short --basetemp .cache/cleanup-crash-target` 退出1，2 passed/2 failed in15.45s；失败因测试配置CLEANUP_RETRIES=0非法，后端拒绝启动。改为合法预算1并先发生一次失败，形成真实可达的deleting／remaining_budget=0；未放宽生产配置规则。

修正后定向 `uv run --frozen pytest tests/test_mixed_cleanup_crash_protocol.py -q --tb=short --basetemp .cache/cleanup-crash-recheck` 退出0，4 passed in35.49s。Ruff check／format --check退出0（131 files already formatted），版本入口0.1.0.dev0退出0；change及三项工作主规范严格校验、git diff --check退出0；uv build退出0。

最终全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/cleanup-crash-full` 退出0，487 passed in347.31s。wheel／源码包独立检查排除tests及测试后端；文档收尾后重建并刷新dist/SHA256SUMS.txt，仅本地开发构建，不代表发布或远端CI。

收尾检查退出0：cleanup-crash-target、cleanup-crash-recheck、cleanup-crash-full均存在重解析点，保留在.cache下，未递归删除。fixture等待测试拥有的后端进程退出，不作WMI全机零遗留声明，未修改用户Host配置或生产数据。


## 2026-11-13 多客户端并发清理恢复、版本冲突与幂等

新增tests/test_cleanup_concurrency_protocol.py，分别以取消／放弃触发PNG、MP4、MP3混合输入清理。视频副本删除发生合成忙碌错误并耗尽预算，其他两项完成。测试专用Cleanup.due门仅暂停执行扫描，不持有清理锁、不替换真实retry方法，便于确定性观察恢复事务；生产代码未改。

第一后端退出后，第二后端由两个独立stdio客户端接入：两份旧版本请求均返回VERSION_CONFLICT，删除计数不变；两份同一当前版本并发恢复返回同一pending快照，业务版本只增加1。后端退出后的隔离库确认同一cleanup_id仅获得2次新预算，无额外清理记录。

第三后端启动后，两客户端再次用原恢复版本重放请求，因已无failed待办而幂等返回当前pending，不增加版本或重置预算。解除测试执行门后只有失败视频副本再删一次；done后两客户端重复恢复仍不增加版本或删除。最终删除调用计数1/3/1，恢复后预算剩1，已完成的两项清理记录完全不变，用户原件保留，三份托管副本均删除。

版本冲突针对需要改变失败状态的旧版本请求；已pending／done重复恢复按既有设计无操作返回，不将所有旧版本重放都误记为冲突。取消／放弃事实及有效参数保留，上传1/1/0、生成下载0。测试跨三个真实后端进程和多组独立stdio客户端，不代表实际Agent Host产品验收。

补充11.2、9.6、12.4／13.2证据，55/67保持。尾帧／完整产物集合、SUCCESS和完整费用继续待核实；8.4及实际Host13.3未完成。仅合成传输，未调用真实供应商、提交或推送Git，未同步业务主规范或归档。

定向 `uv run --frozen pytest tests/test_cleanup_concurrency_protocol.py -q --tb=short --basetemp .cache/cleanup-concurrency-target` 退出0，2 passed in34.17s。Ruff check／format --check退出0（132 files already formatted），版本入口0.1.0.dev0退出0；change及三项工作主规范严格校验退出0。

最终全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/cleanup-concurrency-full` 退出0，489 passed in369.72s。git diff --check及uv build退出0；wheel／源码包检查排除tests和测试后端，文档收尾后重建并刷新dist/SHA256SUMS.txt，仅本地开发构建。

收尾检查退出0：cleanup-concurrency-target与cleanup-concurrency-full均存在重解析点，因此保留于.cache，未递归删除。fixture等待所拥有后端退出，不作WMI全机零遗留声明；未修改用户Host配置或生产数据。


## 2026-11-13 清理持久化失败与存储故障保护

检查发现Lifecycle.run对已置storage_fault的后台StorageError直接传播并退出后端，不符合故障时仍提供只读诊断的边界；9.6重新打开，并先补充design。现仅在数据库已触发存储保护时捕获该异常、保留只读RPC和健康查询，既有故障门阻止新副作用；其他异常仍传播，不自动清除故障。正常重启仍先核对已有状态再恢复。

新增tests/test_cleanup_storage_protocol.py，测试后端FaultDatabase在真正SQLite事务回调执行后、COMMIT前注入sqlite3.OperationalError，实际Database执行回滚并设置storage_fault，不直接伪造健康标志。两种场景分别为第二项视频清理intent写入失败、删除完成后complete事务写入失败；第一项已完成、第三项未执行。合成图片／视频／音频经MCP接收与上传，显式放弃触发清理。

两个客户端验证health.storage_fault／stale、本地查询及有界等待可用，retry_material_cleanup和新submit_video均返回STORAGE_FAULT，后端保持在线，无后续删除或生成下载。故障前失败intent回滚为new且视频副本存在；完成补记失败回滚为deleting且文件已不存在，不报告done。正常停止后读取隔离库，新后端启动核对后才续做，任务ID／参数不变、未创建被拒绝的新任务。

intent路径最终删除调用1/1/1、失败项恢复后预算剩1；complete路径1/2/1，其中第二次是不存在文件核对、预算剩0。全部托管副本最终删除，原件保留，放弃状态延续、上传1/1/0、生成下载0。注入的是事务体末尾异常，不宣称模拟所有COMMIT错误、磁盘断电或SQLite损坏；实际Host和供应商未验收。

尾帧／完整集合、SUCCESS及完整费用响应继续待核实。无真实供应商调用、Git提交或推送，业务主规范未同步，change未归档。

定向 `uv run --frozen pytest tests/test_cleanup_storage_protocol.py tests/test_lifecycle.py -q --tb=short --basetemp .cache/cleanup-storage-target` 退出0，15 passed in20.47s。初次编辑命令因默认GBK读取中文文件失败，未写入；改显式UTF-8完成。初次Ruff发现测试SQL行过长，拆分字符串后Ruff check及format --check通过（133 files already formatted）。

最终全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/cleanup-storage-full` 退出0，491 passed in386.12s。9.6修复后重新勾选，55/67。版本入口、change及三项工作主规范严格校验、git diff --check和uv build均退出0；wheel／源码包检查排除tests及测试后端。文档收尾后重建并刷新dist/SHA256SUMS.txt，仅本地开发构建。

收尾检查退出0：cleanup-storage-target和cleanup-storage-full均存在重解析点，保留在.cache下，未递归删除。fixture等待所拥有后端退出，不作全机WMI零遗留声明，未修改用户Host配置或生产数据。


## 2026-11-13 存储故障下并发查询、管理拒绝与重复恢复

扩展tests/test_cleanup_storage_protocol.py的intent／complete两种事务故障场景：两个独立stdio客户端各自并发调用健康、任务详情、列表、请求标识找回和有界等待，确认故障标记、滞后快照及版本一致。两客户端同时调用取消、放弃、恢复跟踪、重试提交、重试下载、重试素材清理和单次刷新，共14个管理请求，均须返回STORAGE_FAULT，任务版本与副作用计数不变。

首次定向失败发现部分工具先报CAPABILITY_UNVERIFIED或ARTIFACT_LINK_REFRESH_UNVERIFIED，掩盖已发生的存储故障。重新打开12.3并补充design后，在Tools handler的非只读入口统一检查storage_fault；保留底层事务／副作用检查，不自动清除故障。只读工具仍可用。

故障后第二后端核对并完成清理，双客户端使用故障前旧版本重放清理恢复请求，按done幂等规则返回当前版本。第三后端再次启动并发重放，cleanup_jobs、material_copies及任务版本与上一后端退出时完全一致；intent路径预算剩1，complete路径剩0，没有补充预算。删除调用维持1/1/1或1/2/1（后者含缺失文件核对），上传1/1/0，生成下载0，用户原件保留，任务不复活。

本轮使用合成适配器及独立stdio客户端，不代表实际Agent Host产品验收或真实磁盘损坏验收。尾帧／完整产物集合、SUCCESS与完整费用响应继续待核实；无真实供应商调用、Git提交或推送，业务主规范未同步，change未归档。

首次定向2 failed in10.91s；两次缩小诊断各1 failed（5.58s／5.53s），定位管理错误优先级不一致。修复后 `uv run --frozen pytest tests/test_cleanup_storage_protocol.py tests/test_tools.py -q --tb=short --basetemp .cache/storage-concurrency-recheck` 退出0，10 passed in38.61s。Ruff check及format --check退出0（133 files already formatted）；版本入口0.1.0.dev0，change与三项工作主规范严格校验、git diff --check退出0。

全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/storage-concurrency-full` 退出0，491 passed in402.27s。12.3修复验证后重新勾选，恢复55/67。uv build退出0；最终文档收尾后重建、检查wheel／源码包排除tests与测试后端，并刷新dist/SHA256SUMS.txt，仅本地开发构建。

已结束的storage-concurrency-target、storage-concurrency-diagnose、storage-concurrency-diagnose2、storage-concurrency-recheck目录检测到重解析点，保留于.cache，未递归删除。fixture等待所拥有后端退出，不作全机零进程遗留声明，未修改用户Host配置或生产数据。

全量目录storage-concurrency-full收尾检查同样发现重解析点，保留于.cache，未递归删除。


## 2026-11-13 启动后清理恢复再次发生存储故障

扩展tests/test_cleanup_storage_protocol.py，在intent／complete两种原场景上增加repeat_fault参数（新增2项）。第一后端故障并退出后，仅重新启用测试注入标记；不编辑任务库或重置预算。第二后端启动核对后，由Host接入恢复待办执行，第二次在清理意图／完成事务回调后、提交前注入SQLite错误。该证据针对启动后的待办恢复执行，不声称覆盖RPC公布前的startup scan写入故障。

两个独立stdio客户端接入同一发现记录中的后端，健康显示host_count=2、storage_fault和stale；按ID查询和按请求标识找回的版本一致、清理未冒充done。并发显式恢复均拒绝为STORAGE_FAULT。再次退出后验证同一cleanup_id和原已完成项保留：intent回滚仍new、原预算不变；complete回滚仍deleting、剩余预算0。

随后第三后端完成清理，第四后端验证重复操作幂等；预算最终intent为1、complete为0。complete零预算仅核对已删除文件补记，不再调用删除；删除调用总数保持1/1/1或1/2/1。托管副本删除、用户原件保留，上传1/1/0、生成下载0，放弃任务不复活。

本轮发现find_task_by_request_key遗漏stale字段，重新打开12.3并补充design后，在工具只读返回中补齐标记（含已接收、接收中和未找到结果），原字段和语义保留。生产调度与重试策略未改变。

尾帧／完整产物集合、SUCCESS与完整费用响应继续待核实；无真实供应商调用、Git提交或推送。业务主规范未同步，change未归档；合成客户端不代表实际Agent Host产品验收。

首次定向退出1，2 failed/2 passed in44.77s：测试错误地把Windows虚拟环境启动器PID当成后端PID，改为核对发现记录中的实际PID。第二次定向退出1，2 failed/2 passed in45.76s：暴露请求标识找回响应遗漏stale，按上述方式修复。

修复后定向 `uv run --frozen pytest tests/test_cleanup_storage_protocol.py tests/test_tools.py -q --tb=short --basetemp .cache/recovery-fault-fixed` 退出0，12 passed in73.06s。Ruff check和format --check退出0（133 files already formatted），git diff --check退出0。

首次全量退出1，492 passed/1 failed in432.34s：test_sdk_v2_stdio_frontend_connects_shared_backend的旧断言要求找回响应与提交响应完全相等，新增stale字段导致失败。修订为先明确断言stale为False，再比较其余全部原字段；未删除原一致性验证。

更新旧断言时曾引入缩进错误，Ruff报错且pytest收集阶段2 errors in1.00s；随即修正缩进后重新执行检查，未记录为通过。

第二次完整全量（.cache/recovery-fault-verified）退出1，492 passed/1 failed in442.25s；同一测试的重启后响应相等断言也需包含stale。补齐该处后 `uv run --frozen pytest tests/test_runtime.py -q --tb=short --basetemp .cache/recovery-fault-runtime` 退出0，6 passed in24.22s。生产代码在两轮全量间未继续改动；最后仅改测试断言，未第三次运行全量，不把两次失败的全量记作全绿。当前已知失败均已定向复验通过，12.3恢复勾选，55/67。

Ruff check／format --check再次通过（133 files already formatted）；版本入口0.1.0.dev0、change及三项工作主规范严格校验均退出0。uv build成功；收尾文档后再次构建并检查wheel／源码包排除tests和测试后端，更新dist/SHA256SUMS.txt，仅本地开发构建。

定向target／recheck／fixed与第一次全量full测试目录存在重解析点，保留在.cache；收集失败的final目录不存在。fixture等待测试拥有后端退出，不作全机零进程遗留声明，未修改用户Host配置或生产数据。

最终verified全量目录及runtime定向目录也因重解析点保留，未递归删除。


## 2026-11-13 RPC 公布前启动清理扫描故障

tests/test_cleanup_storage_protocol.py新增startup_scan两项参数场景：先构造混合素材清理意图写入失败（副本仍在）或完成写入失败（已删除未落账），原后端退出后启动新后端，在CleanupService.scan.collect实际事务回调之后、提交之前注入SQLite OperationalError。测试夹具支持预期启动失败并等待自己启动的进程退出；RPCServer.start增加仅测试调用标记，生产代码未改变。

断言故障启动非零退出，清理扫描注入确实发生，RPC start从未调用、旧discovery字节保持不变，不将旧发现记录视作新后端就绪。退出后SQLite可重新打开，cleanup_jobs和material_copies逐行不变，清理预算不重置，文件存在性与故障前一致，上传／生成／下载／删除计数不增加。没有对真实Host发起失败连接或容许前端自动拉起另一个后端，以免混淆被测启动失败路径。

启动恢复按阶段提交，并非整个流程一个事务：清理扫描之前已完成的上传恢复可把uploading改为pending，保留其他全部字段及预算。测试明确比较这一合法变化，而非要求整库回滚。随后正常启动证明所有权和资源已释放，两个独立stdio客户端找回原任务并观察清理完成；再一次重启重放恢复请求，清理记录、预算和副本记录不变。intent最终预算1，complete为0，删除调用分别1/1/1和1/2/1，原件保留、放弃任务不复活。

本轮补充9.6、11.1／11.2、13.2证据，未改变设计和生产策略。尾帧／完整产物集合、SUCCESS及完整费用响应保持待核实；无真实供应商调用、Git提交或推送，未同步业务主规范或归档。此为合成事务故障与进程测试，不代表真实磁盘损坏或实际Agent Host产品验收。

首次Ruff报两处异步测试中的阻塞Path.exists，改为asyncio.to_thread后通过，未在失败后执行pytest。首次定向退出1，4 passed/2 failed in71.88s，原因是断言要求上传表也完全不变；修订为明确验证uploading→pending恢复以及其余字段不变。

修正后定向 `uv run --frozen pytest tests/test_cleanup_storage_protocol.py -q --tb=short --basetemp .cache/startup-scan-recheck` 退出0，6 passed in87.97s。Ruff check／format --check通过（133 files already formatted），版本入口0.1.0.dev0、change与三项工作主规范严格校验及git diff --check均退出0。

全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/startup-scan-full` 退出1，493 passed/2 failed in454.88s。两项既有协议测试失败：发现文件轮询瞬间PermissionError；另一个多素材测试预期合成崩溃91却得到正常退出0，且无requests.jsonl，符合接入前宽限期耗尽的迹象（不宣称唯一根因）。夹具在原10秒轮询期限内对PermissionError／FileNotFoundError重试，多素材测试单独把合成宽限期从2秒调整为5秒，不改变生产默认值。13.2暂重新打开，等待相关协议文件复验。

辅助collect-only命令曾因下游Select-Object提前关闭管道产生OSError，不计入任何测试通过证据。Ruff check及format --check在夹具修订后通过（133 files already formatted）。

夹具修订后 `uv run --frozen pytest tests/test_main_video_protocol.py tests/test_multi_material_protocol.py tests/test_cleanup_storage_protocol.py -q --tb=short --basetemp .cache/startup-scan-regression` 退出0，17 passed in188.20s，包含全量失败的两项。最后只有测试夹具／配置修改，没有生产代码修改；未再次运行全量，不宣称最终全量全绿。13.2复验后重新勾选，55/67。

本轮target、recheck、full、regression测试目录均存在重解析点，保留于.cache，未递归删除。fixture等待自己启动的进程退出，不作全机零遗留声明，未修改用户Host配置或生产数据。

收尾执行uv build、wheel／源码包测试文件排除检查及SHA256SUMS更新，均属本地开发构建。OpenSpec严格校验、git diff --check再次验证；不代表发布或远端CI。


## 2026-11-13 夹具修订后全量隔离复验

按最新AGENTS.md复跑 `uv run --frozen pytest -q --tb=short --basetemp .cache/full-recheck-tests`，退出0，495 passed in462.20s（7分42秒）。覆盖上轮发现文件读取重试、合成Host接入宽限期调整，以及RPC公布前清理扫描故障／后续恢复场景；本轮没有新增代码或测试改动。此前全量失败及定向复验记录保留，本次追加完整通过证据，不回写历史结果。

Ruff check退出0；format --check退出0（133 files already formatted）；版本入口退出0，0.1.0.dev0；change和engineering-practices、git-collaboration、manual-writing主规范严格校验均退出0。git diff --check通过。文档收尾后执行uv build、wheel／源码包排除tests和测试后端检查，刷新dist/SHA256SUMS.txt，均为本地开发构建，不代表发布或远端CI。

13.2与13.7验证记录补齐，进度保持55/67。尾帧／完整产物集合、SUCCESS与完整费用响应及其他上游待核实项保持原状态；实际Agent Host和真实供应商验收未完成。未调用真实供应商、提交或推送Git，未同步业务主规范，change未归档。

full-recheck-tests测试目录检测到重解析点，保留在.cache中，未递归删除。fixture等待所拥有后端退出，不作全机零进程遗留声明；未修改用户Host配置或生产数据。


## 2026-11-13 剩余12项梳理与离线安装切换

新增docs/remaining-work.md逐项区分已有交付、离线增量和外部完成门槛；新增docs/windows-host-acceptance.md供干净Windows／实际Host逐步记录，初始均未执行。未将未知契约、候选调用或模拟客户端标为真实证据。

扩展tests/test_installation.py：同一开发源码包二次解包，各自uv冻结离线安装到独立.venv；复制测试.env后候选安装启动并找回原任务，再回切原安装。检查实际导入路径、任务ID／版本／数量、无新增attempt、.env原字节和外部产物不变，删除测试安装后数据仍在。只验证同版本切换，不宣称跨版本schema兼容或干净OS验收；生产实现未改变。

`uv run --frozen pytest tests/test_installation.py -q --tb=short --basetemp .cache/remaining-install-target`退出0，2 passed in31.94s。Ruff check通过，format --check退出0（135 files already formatted）；版本入口0.1.0.dev0，change及三项工作主规范严格校验、git diff --check通过。

原12项仍有未满足的外部完成条件，保持55/67。尾帧／完整集合、SUCCESS及费用完整响应保持待核实，实际Host、干净OS与真实供应商未验收。本轮不调用真实供应商，不提交／推送Git，不同步业务主规范或归档。

最终全量 `uv run --frozen pytest -q --tb=short --basetemp .cache/remaining-full`退出0，495 passed in479.12s。新增文档本地链接检查通过。文档收尾后uv build、包内容检查与SHA256SUMS更新；保留本地开发构建边界，不代表发布或真实供应商支持。

remaining-install-target与remaining-full目录检测到重解析点，保留在.cache，未递归删除。用例内已只删除其创建的两个安装副本，并验证外部状态／产物保留。未修改用户Host配置，未操作日常生产状态。


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

取证后隔离回归：`uv run --frozen pytest tests/test_provider_response.py tests/test_compatibility_adapter.py -q --tb=short --basetemp .cache/paid-evidence-regression`退出0，44 passed in2.81s。Ruff check／format --check通过（136 files already formatted），OpenSpec change严格校验及git diff --check通过。本轮不改运行时代码，未重跑全量或发布构建；44项回归不代表新封装已接线。


## 2026-11-13 8.4 双封装解析、实扣及事务持久化

使用 openspec-apply-change，按仓库 AGENTS.md 核对状态与指引。将四份旧样例与本次已有 live-observed 真实脱敏样例接入同一兼容适配器；没有新增真实供应商调用，无 Git 提交／推送。

- 新查询只按 code=success/data 封装读取 data.task_id，核对已保存 ID 和 properties.origin_model_name。IN_PROGRESS/SUCCESS 归一状态，保留原 provider_status；不读数值 data.id 或递归查找 ID。POST id/task_id 同时存在时核对一致。
- 主视频 data.result_url 归一到原产物事实／manifest 路径，旧 metadata.url 继续兼容。尾帧及完整集合仍 unverified，不因主视频存在自动清理素材或声称全部产物就绪。
- data.usage 金额用 JSON Decimal 解码后以文本持久化，原币种 ¥ 不替换为 CNY。内层 token usage、quota、price_estimate 不参与实扣。缺值不补零、不覆盖旧完整费用；畸形字段严格拒绝，错误只含静态代码。
- 状态／URL／费用共用单事务。费用写入后注入存储故障证明整笔回滚；成功回放后关闭并重新打开数据库证明金额、币种及主视频引用持久化。重复响应不累计金额、不增加业务版本；终态冲突不采纳费用。
- 72 项定向测试通过（3.40s）：`uv run --frozen pytest tests/test_provider_response.py tests/test_compatibility_adapter.py tests/test_charges.py -q --tb=short --basetemp .cache/response-wiring-targeted`，退出0。首次格式检查发现新增测试行过长，格式化后检查通过；最早53项旧回归和71项扩展回归也通过，最终定向为72项。
- Ruff check 与 format --check 通过，136 files already formatted；版本入口输出0.1.0.dev0；change及engineering-practices/git-collaboration/manual-writing三份主规范严格校验通过，git diff --check通过。
- uv build成功，wheel40条／sdist66条归档项，检查未包含tests、main_video_backend和paid-contract-probe。这是本地构建，不是发布或真实Host验收。
- targeted临时目录存在重解析点而保留，未递归删除；原始私有取证记录未动。业务主规范未同步，change未归档。8.4完成后CLI确认57/67、剩余10项；其他模型适用、退款／迟到结算及1.2、1.5–1.8保持待核实。

全量隔离回归：`uv run --frozen pytest -q --tb=short` 退出0，514 passed in 510.04s（8分30秒）；日志位于被忽略的 `.cache/response-wiring-full-test.txt`。该命令使用完整测试集及既有网络隔离设施，不包含新增真实供应商请求。记录完成后重新运行 uv build 和校验，并刷新 dist/SHA256SUMS.txt。


## 2026-11-14 1.7 产物收费取证与JPEG尾帧实现

用户授权10次以内、最短可允许时长及最低分辨率。按现有已核实Mini模型使用4秒480p，1:1，return_last_frame=true，音频/优化false，提示词沿用无敏感内容的白桌红木块。先持久化提交intent，仅1次POST，3次GET后SUCCESS；费用0.8028/¥原样记录。视频与尾帧各1次无Bearer GET成功，共2次下载；不追加收费任务、不重新生成，不修改用户日常数据库或Host配置。

真实证据：data.data.content.last_frame_url，主视频data.result_url；外层data.usage。视频823227字节、H264 MP4，尾帧112496字节JPEG；ffprobe均640×640，视频4.041667秒。URL后缀与outputType为png不代表实际编码。SHA-256及非敏感下载头、ffprobe输出、完整脱敏JSON和来源摘要位于tests/fixtures/provider/last-frame-observed；原始媒体及完整响应留在当前用户/SYSTEM ACL保护的.cache/artifact-probe-20261114，Git忽略。内部DNS固定后的response.url差异不能作为重定向证据，最初采集标记已更正为未核实。

实现先补充design及产物spec：只在已关联SUCCESS封装读取尾帧HTTPS路径，持久化到观察事实，适配器返回独立JPEG引用；复用下载、发布、摘要、有限重试、复制及恢复。JPEG结构校验不引入新依赖或图像加工。完整集合仍complete=false；不因两项下载完成提前清理，不把一次Mini结果推广到26模型。无schema变更。

验证：定向`uv run --frozen pytest tests/test_provider_response.py tests/test_compatibility_adapter.py tests/test_artifacts.py -q --tb=short --basetemp .cache/last-frame-targeted`退出0，96 passed in3.75s。覆盖真实脱敏回放、路径保护、两项引用、JPEG下载/复制/恢复、partial保留素材、损坏或实际PNG拒绝。初次静态检查发现测试中同步文件读取，改为asyncio.to_thread后通过。真实下载文件结构检查初次使用相对路径被LOCAL_ABSOLUTE_PATH_REQUIRED拒绝，改为绝对路径后MP4/JPEG均通过，无重复下载。

Ruff check/format --check退出0（137 files already formatted），版本入口0.1.0.dev0；change与三份工作主规范严格校验通过。1.7按其主视频核心证据+未知能力逐项记录完成，CLI确认58/67、剩余9项。主规范业务同步未执行，change未归档，无Git提交或推送。公开文档https://api.seedance.nz/docs/llms.txt仅作参数核对，兼容端点证据以实际响应为准。

全量`uv run --frozen pytest -q --tb=short`退出0：520 passed in485.31s（8分5秒），日志.cache/last-frame-full-test.txt。公开证据JSON与密钥/签名扫描通过；targeted目录因重解析点保留。uv build、最终Ruff及OpenSpec校验通过；构建包排除tests、取证脚本与私有媒体，刷新dist/SHA256SUMS.txt。该全量测试不新增真实请求；本轮真实调用固定为1次生成、3次查询、2次下载。


## 2026-11-14 剩余9项梳理与累计授权取证

按最新AGENTS及openspec-apply-change核对58/67、剩余9项。本轮优先1.8独立超分和1.6样片，另为1.2取得只读错误。保守把前两轮各1次收费提交都计入累计10次；本轮新增2次，累计4/10，剩余最多6。每次POST先独占持久化intent、不重放，台账docs/paid-test-ledger.json包含intent摘要、实际费用与累计数量。没有为了用满次数继续测试。

实际操作：上传此前生成的823227字节/4.041667秒MP4一次；独立超分720p一次，无prompt/seconds；国内2.5样片4秒480p一次，draft=true，优化/音频false。各3次GET后SUCCESS，各无Bearer下载一次。超分实际960×960 H264 MP4、4.041667秒，实扣0.875/¥；样片640×640 H264 MP4、4.041667秒，实扣2.688892/¥。本轮合计3.563892/¥，累计观测5.169492/¥，按原币种不推导公式。没有调用额外price-preview或创建成片。

只读负例2次：GET未带鉴权401/error；不存在任务GET为400/task_not_exist。没有制造限流/服务异常，也没有参数错误POST或取消。这些不能证明原提交未创建，隔离测试仍保持已知queued与额度。完整原始响应/媒体在ACL保护且Git忽略的.cache/contracts-round-20261114，公开fixtures为tests/fixtures/provider/contracts-observed，私有字符串和数值脱敏、保持键/层级/类型。

1.8核心兼容成功链路已核实，精确上限和内部结算机制未知项继续标注；本次直接POST成功只证明此次无需客户端额外price-preview步骤。1.6新增data.data.content.draft_task_id完整路径，已接通纯解析、观察持久化、本地查询及重开数据库；未解决7天起算/外部身份/成片默认格式，不勾选。1.2、1.5及13.1/13.3–13.6保持未完成；直接取证脚本不能冒充统一队列真实验收或实际Host。剩余8项明细已更新docs/remaining-work.md。

定向命令`uv run --frozen pytest tests/test_provider_response.py tests/test_compatibility_adapter.py tests/test_uploads.py -q --tb=short`退出0，95 passed in2.57s。新回放覆盖超分/样片提交查询、费用/样片ID重开持久化、非法样片ID拒绝及真实查询错误不判生成失败。Ruff check/format --check通过（138 files already formatted），版本入口0.1.0.dev0，change及三份工作主规范严格校验、git diff --check通过。无Git提交/推送、无业务主规范同步或归档。

首次全量退出1：526 passed、1 failed，514.99s。失败为test_two_frontends_dedup_copy_conflict_and_forced_frontend_exit读到delivery=none。只读检查对应隔离库发现只有accepted事件、queued/not_submitted、无attempt；发现文件launch_id非空，表明前端自动拉起了普通无适配器后端。合成后端的2秒无Host宽限窗口过短，不能据此诊断供应商或样片解析失败。

按缺陷规则重新打开13.2。本测试单独将宽限期设5秒，并在前端接入前保存无launch_id的合成后端发现记录，接入后断言PID匹配且启动进程仍存活。初次断言直接比较Popen.pid失败（7.66s），因为Windows虚拟环境启动器PID不等于实际解释器PID；已改成发现记录中的实际PID。定向复验退出0，1 passed in11.49s，路径.cache/contracts-host-regression-2。生产默认值不变，未将简单增加交付等待当作修复。

正在运行修复后的全量回归；结束前13.2不记为通过，最终结果随后补充。


修复后全量`uv run --frozen pytest -q --tb=short`退出0，527 passed in572.27s（9分32秒），日志.cache/contracts-round-full-retest.txt。13.2恢复完成，最终59/67、剩余8项；首次失败日志.cache/contracts-round-full-test.txt与对应隔离库保留用于复查，两个定向回归目录保留，未递归删除重解析点资源。原始供应商证据及媒体保留于私有缓存，输入原件SHA-256复核未变，公开fixture通过密钥/签名扫描。

最终uv build、Ruff check/format --check、OpenSpec change严格校验及git diff --check通过；wheel/sdist检查排除tests与.cache/私有媒体，dist/SHA256SUMS.txt已刷新。本轮无额外真实调用，总预算仍4/10。业务主规范未同步，change未归档，无Git提交或推送。


## 2026-11-14 13.6 独立超分统一队列真实闭环

按用户授权复用既有4.041667秒原创MP4，以最低720p新增一次收费提交。真实MCP stdio客户端调用upscale_video→get_task/list_artifacts→copy_artifact；生产run_backend组合CompatibilityAdapter、UploadService、NetworkPolicy及调度/下载/持久化组件。隔离安装目录和LOCALAPPDATA，沿用凭据但不修改用户Host配置。首次夹具错误导入UploadService导致启动失败、尚无网络请求；改用upload_service模块及新隔离目录后成功，生产代码未改动。

证据：1次素材上传、1次收费提交、13次查询、1次完成的下载；同请求标识重复提交返回同任务，数据库仅1个任务/submit attempt/费用观察。MCP复制的SHA-256与产物一致，输入原件和托管副本摘要不变。输出H264 MP4、960×960、4.041667秒、1043959字节；生成SUCCESS、费用confirmed=0.875/¥。完整产物集合未核实，delivery=partial且托管副本保留。退出客户端后后端返回0。详见upscaler-queue-acceptance.md及JSON；原始响应、数据库、媒体留在ACL保护且Git忽略的.cache/upscale-queue-20261114-run2。

账本累计5/10，剩余最多5次，累计观测实扣6.044492/¥。13.6勾选，openspec instructions apply复核60/67、剩余7项。不冒充实际Agent Host、跨Host重启、人工画面质量或完整矩阵验收。无Git提交/推送；业务主规范未同步，change未归档。

已执行退出0：uv run --frozen ruff check .；uv run --frozen ruff format --check .（138 files already formatted）；uv run --frozen zhenzhen-seedance-video --version（0.1.0.dev0）；uv build；change及engineering-practices/git-collaboration/manual-writing严格校验；git diff --check。wheel40项、sdist67项，不含tests/.cache/私有媒体或验收脚本；dist/SHA256SUMS.txt已刷新。公开证据密钥与签名扫描通过。全量`uv run --frozen pytest`退出0，527 passed in578.53s（9分38秒），日志.cache/upscale-queue-full-test.txt。测试使用隔离合成服务，不新增真实供应商调用。


## 2026-11-14 13.5 常规生成、样片与成片统一队列

用户在确认已有旧样片仅为直接接口取证后，明确选择新生成最低参数样片并显式提交成片。新增3次收费提交：Mini i2v复用原JPEG首帧，4秒480p/adaptive；国内2.5 t2v样片4秒480p/draft=true；成片引用本轮draft_task_id，唯一允许native1080p、显式mp4、return_last_frame=false，不传新prompt/素材/seconds。普通和样片优化/音频关闭。独立request_key，均经真实stdio MCP/生产统一队列完成下载复制。

初次Mini任务POST成功，GET返回此前未实测NOT_START。解析器按规则转needs_attention，已知ID/占位/素材均保留。8.4重新打开，先修订design及provider-api-contracts场景，再添加NOT_START→queued，保持ID/模型关联检查、不作为未接单证据，不开放未观察的SUBMITTED。首次定向测试72 passed/1 failed（8.14s），原因是新增测试误将数据库facts.provider_status当成公开查询字段；修正测试读取实际持久化事实后73 passed（7.67s）。同一任务库重启，MCP按原请求找回并显式refresh_task获取SUCCESS，继续下载复制，无重复收费提交。

样片成功并复制后，由客户端独立显式提交成片，后者实际出现NOT_START→IN_PROGRESS→SUCCESS，新解析路径正常推进。三份输出摘要与对应服务原产物一致，input原件及托管副本保留，样片和成片未相互覆盖；最终后端正常退出0。常规/样片实际H264、640×640、4.041667秒；成片HEVC、1440×1440、4.041667秒。容器与ffprobe检查不代表人工播放或内容质量验收。完整集合仍unverified/partial，不提前清理。

实测1次上传、3次收费POST、13次同任务查询、3次完成下载；实扣分别0.8028、2.688892、14.224814/¥，本轮17.716506/¥，累计8/10、23.760998/¥，剩余最多2次。每次收费前持久化独占intent及收费账本。私有原始证据在.cache/generation-queue-20261114，公开完整脱敏fixtures在tests/fixtures/provider/generation-queue-observed；专项报告及摘要见generation-queue-acceptance.md/JSON。没有额外price-preview、取消、身份或历史接口。

新增三类真实响应回放、费用/样片ID重开库持久化和未观察SUBMITTED拒绝测试后，`uv run --frozen pytest tests/test_compatibility_adapter.py tests/test_provider_response.py -q --tb=short`退出0，77 passed in6.92s。8.4恢复完成，13.5勾选，CLI复核61/67、剩余6项。Ruff check/format --check通过（140 files already formatted），版本入口0.1.0.dev0、uv build、change严格校验、git diff --check退出0。首次全量uv run --frozen pytest退出1，531 passed、1 failed in600.77s，日志.cache/generation-queue-full-test.txt。失败是合成多素材测试，详情见下续记。主规范业务同步和归档未执行，无Git提交推送。


补充检查：公开fixture/文档通过当前密钥、真实任务ID、产物URL与签名扫描；输入JPEG SHA-256与此前last_frame-download.json一致。wheel40项、sdist69项，不含tests/.cache/.env或私有媒体，dist/SHA256SUMS.txt已刷新。三份工作主规范严格校验通过，业务主规范仍未同步。


全量失败排查：test_partial_upload_concurrent_dedup_restart[False-images]期望故障退出91但实际0。只读检查隔离目录.cache/test-runs/60d0e8ce373747c9a7d36b33c3b88b07/test_partial_upload_concurrent0发现discovery.launch_id非空、任务仅queued/not_submitted、attempts=0且无假服务requests.jsonl，确认原合成后端先正常退出，stdio前端自动拉起普通无适配器后端。13.2重新打开。该参数化测试新增pinned_start，在两个stdio客户端启动期间持有经鉴权的真实RPC租约并核验发现记录PID；二者接入后立即释放临时租约，首次和重启均使用。不再仅增加宽限秒数；生产运行策略未变。当前定向及全量复验完成前不恢复13.2完成标记。


租约夹具修订后，uv run --frozen pytest tests/test_multi_material_protocol.py -q --tb=short退出0，6 passed in77.96s；Ruff及change校验通过。再次启动全量uv run --frozen pytest，日志.cache/generation-queue-full-retest.txt；完成前13.2保持打开。没有新增真实供应商请求，账本仍8/10。


最终全量复验`uv run --frozen pytest`退出0：532 passed in591.48s（9分51秒），日志.cache/generation-queue-full-retest.txt。13.2恢复完成；13.5已完成，最终61/67、剩余6项。未再新增真实请求，累计8/10与23.760998/¥不变。业务主规范未同步，change未归档，无Git提交或推送。

最终文档落账后复跑Ruff check/format（141 files already formatted）、版本入口、uv build、change严格校验及git diff --check均退出0；最终wheel40项、sdist71项，排除私有证据并刷新dist/SHA256SUMS.txt。

## 2026-11-14 剩余六项与13.4矩阵复核

本轮仅修改文档/收费账本复核元数据，未修改运行代码或测试。1.2、1.5、1.6更新当前证据映射，明确GET错误不能证明POST未接单、成功单配置不能证明参数全范围、显式mp4不能证明默认格式。13.4矩阵重写为26模型当前逐项状态：4个局部真实、22个仅契约/隔离，超分独立记录；候选最低参数及两次剩余额度的互斥关系明确。另纠正model-preflight早期“工具未接线/SUCCESS未解析”描述。六项仍未全部满足，61/67不变，不更改验收标准。

实际执行：
- `uv run --frozen pytest tests/test_models.py tests/test_parameters.py tests/test_preflight.py tests/test_provider_response.py tests/test_compatibility_adapter.py tests/test_uploads.py -q --tb=short`：退出0，210 passed in34.34s，隔离网络。
- `uv run --frozen ruff check .`：All checks passed；`uv run --frozen ruff format --check .`：141 files already formatted。
- `uv run --frozen zhenzhen-seedance-video --version`：0.1.0.dev0；`uv build`成功。
- `openspec validate add-local-video-generation-service --type change --strict`通过；`git diff --check`通过，暂存区为空。
- 使用Python核对矩阵26个模型与注册表集合完全一致、4个已观察模型、8笔Decimal实扣合计23.760998及¥币种、余量2次；通过。构建wheel40项、sdist71项，排除tests/.cache/.env，刷新dist/SHA256SUMS.txt。

本轮没有重跑全量测试；最近全量532通过为前一轮记录，不能冒充本轮结果。本轮无新增供应商网络请求或收费提交，仍8/10，账本记录零调用复核。没有Git提交推送、业务主规范同步或归档。后续需要供应商规则性证据、干净Windows及实际Host验收；国际样片链、常规模型差异和优化开启不能用当前局部证据代替。

## 2026-11-14 国际版样片/成片统一队列真实闭环

用户新增8次额度；原余量2次合并为新窗口10次，历史8次不抹除。验收执行器只允许global样片和成片两个模型、历史序号9/10，并在每次POST前写独占intent和账本；本次用2/10、余8，终身账本10/18。没有重复提交或额外收费探测。

复用既有方块提示词，global 2.5 t2v样片4秒480p、draft=true、音频/优化false；成功下载复制后，通过独立MCP submit_video显式提交global draft-to-video，引用此次已完成同区域样片，native1080p/mp4，不传prompt/素材/seconds/优化。两次收费POST、26次查询、0次上传、2份主视频下载复制成功。样片实扣2.877682/¥，成片15.933802/¥，合计18.811484/¥，历史合计42.572482/¥。

数据库只读核对2个任务/2次submit attempt、不同远端ID、同连接绑定、正确样片引用及最低参数；同key工具重放返回原任务。两份原产物与交付副本摘要相等，成片完成后样片摘要仍相同；源码摘要与执行快照一致。后端正常退出0。第一次样片get_task在list_artifacts前取得delivery=pending，最终数据库已partial；机器证据分别保留这个早期快照和最终状态，避免把跨调用瞬时快照当作一致终态。完整产物集合仍unverified，未做人工播放/画面质量验收。

交付：docs/global-queue-acceptance.md/.json、tests/fixtures/provider/global-queue-observed（6份完整脱敏响应、28个原始响应摘要）、13.4当前矩阵、tasks、剩余任务/契约/交付证据表和收费账本。原始记录及两个视频在受ACL保护、Git忽略的.cache/global-queue-20261114。没有改生产代码、Host配置或默认供应商派发；公开新增两个global响应回放用例。

实际检查：
- `uv run --frozen pytest tests/test_models.py tests/test_parameters.py tests/test_preflight.py tests/test_provider_response.py -q --tb=short`：退出0，151 passed in2.99s。
- 真实响应脱敏导出后，`uv run --frozen pytest tests/test_compatibility_adapter.py tests/test_provider_response.py -q --tb=short`：退出0，79 passed in3.36s，包含国内/国际样片、成片的实际费用/样片ID重开库持久化回放。网络隔离，不发生收费调用。
- Ruff check与format --check通过，143 files already formatted；版本入口0.1.0.dev0；uv build成功；change严格校验与git diff --check通过。
- 26个矩阵模型与注册表一致，6个模型有真实局部记录，10笔实扣及新窗口2/10已核对；公开文件密钥/真实ID/签名URL扫描通过。wheel40项、sdist73项排除tests/.cache/.env，dist/SHA256SUMS.txt刷新。

本轮未重跑全量测试；此前532通过属于历史记录。OpenSpec仍61/67、剩余6项：国际链补齐不等于所有常规模型差异、优化开启或13.4全矩阵完成；1.2/1.5/1.6的规则性缺口、干净Windows和实际Host验收保持。暂存区为空，无Git提交推送，未同步业务主规范或归档。

## 2026-11-14 Fast图生与Standard多模态真实队列验收

使用此前授权窗口剩余8次中的2次，历史收费序号11/12；窗口累计4/10、余6，历史累计12次/授权18次。限定两个模型、4秒480p、优化和音频false；POST前独占记录意图及账本，未知结果占预算、不重提。Fast为seedance-2.0-global-fast-i2v，复用既有JPEG及图生提示词；multi为seedance-2.0-standard-multi，复用同JPEG与既有4.041667秒MP4，canonical content按图片/视频顺序，不传2.5专用任务类型字段。

通过真实MCP SDK stdio submit_video/get_task/list_artifacts/copy_artifact，调用生产共享后端、上传服务、兼容适配器、网络策略和统一队列；只注入实际适配器用于隔离验收，没有直接HTTP提交替代队列。实际2次生成POST、3次上传、24次查询、2份主视频下载与复制。Fast实扣1.504578/¥，multi实扣2.14038/¥，本轮合计3.644958/¥、历史46.217440/¥。原始记录在.cache/fast-multi-queue-20261114，受ACL保护且Git忽略。

核验2个任务/2次submit attempt/不同远端ID/同连接绑定、同key重放不增加任务；3份托管副本摘要与已有原件一致，实际生成payload的媒体URL等于对应上传记录且顺序正确；4秒/480p及优化/音频false已持久化。两个服务原产物和工作区交付副本摘要一致，Fast视频906118字节、multi视频830770字节，均H264、640×640、4.041667秒。输入原件、本轮输入副本、托管副本保持不变；集合仍unverified/partial，不提前清理。客户端退出后后端返回0，生产源码与执行前摘要一致。未做人工播放或画面质量验收。

更新docs/fast-multi-queue-acceptance.md/.json、13.4矩阵、tasks、收费账本、契约/交付/剩余任务表。新增fast-multi-queue-observed的7份完整脱敏响应及29份原始响应摘要；multi实际NOT_START沿用既有解析，没有扩展未知状态。新增两个真实fixture持久化回放，检查费用、重开库保持、单次提交、关闭优化及多模态顺序；生产代码不变。

实际检查及结果：
- `uv run --frozen pytest tests/test_models.py tests/test_parameters.py tests/test_preflight.py tests/test_uploads.py tests/test_upload_service.py -q --tb=short`：退出0，147 passed in1.61s。
- `uv run --frozen pytest tests/test_compatibility_adapter.py tests/test_provider_response.py -q --tb=short`：退出0，81 passed in3.74s。两组隔离测试均无真实网络调用。
- `uv run --frozen ruff check .`、`uv run --frozen ruff format --check .`：通过，145 files already formatted；版本入口0.1.0.dev0；uv build成功；OpenSpec change严格校验通过；git diff --check通过，暂存区为空。
- 26模型矩阵与注册表集合一致，8个模型有局部真实证据；Decimal实扣和窗口4/10核对通过。公开文件密钥、真实任务ID、上传/产物URL与签名扫描通过。wheel40项、sdist75项，未包含tests/.cache/.env，dist/SHA256SUMS.txt刷新。

本轮未重跑全量测试，不把先前532通过记为本轮结果。13.4仍保留其他模式及优化开启等未验收范围，61/67、剩余6项；单配置成功不解除1.2/1.5/1.6规则性缺口，不替代实际Host与干净Windows。没有Git提交推送、业务主规范同步或归档。

## 2026-11-14 单次提示词优化真实闭环与13.4完成

用户明确单次允许优化、不修改“总是允许”，从原剩余6次中使用1次，历史序号13；当前授权窗口5/10、余5，终身累计13/18。使用seedance-2.0-mini-t2v，复用已有方块提示词，4秒480p/1:1、音频false；MCP submit_video allow_once=true，实际payload enhance_prompt=true。POST前独占保存意图并更新账本，没有重提或额外付费对照。

通过真实MCP SDK stdio和生产共享后端/兼容适配器/网络/队列完成生成、下载、copy_artifact交付。1次生成POST、9次查询、0上传；实扣0.8028/¥，历史总实扣47.020240/¥。视频H264、640×640、4.041667秒、734552字节，服务原产物与工作区副本SHA-256相等；后端正常退出0，1个任务/1次submit attempt，生产源码摘要未变。集合仍unverified/partial，未做画面质量或优化效果比较。

授权证据：接收快照enabled=true/source=single_allow；实际发送参数与持久化有效参数相等。同key重复调用返回原任务。验收使用独立LOCALAPPDATA/任务库，未修改用户现有Host配置或任务库；未调用set_prompt_optimization_policy。get_prompt_optimization_policy前后均false/version0，preferences表0行；完成后省略enhance_prompt和allow_once的只读预检返回default_false，未创建第二个任务。单次授权不扩散为持久允许。

公开交付docs/optimization-queue-acceptance.md/.json、optimization-queue-observed四份完整脱敏响应及10份原始响应摘要，更新矩阵/tasks/收费账本和相关状态文档。原始证据及视频在Git忽略且ACL保护的.cache/optimization-queue-20261114。增加一项真实响应回放，验证优化true、single_allow、偏好表不写入、费用及授权在重开库后保持；没有修改生产代码。

实际检查：
- `uv run --frozen pytest tests/test_admission.py tests/test_preflight.py tests/test_tools.py -q --tb=short`退出0：55 passed in16.86s。
- `uv run --frozen pytest tests/test_compatibility_adapter.py tests/test_provider_response.py -q --tb=short`退出0：82 passed in5.80s；隔离网络，无收费请求。
- Ruff check通过；首次format --check发现新增测试一处await断言排版，执行ruff format后复验通过：147 files already formatted。版本入口0.1.0.dev0，uv build成功，OpenSpec change严格校验与git diff --check通过，暂存区为空。
- 26行模型集合与注册表一致，8个局部真实、18个仅契约/隔离；13笔Decimal实扣、窗口5/10及余量5核对通过。新增公开材料密钥/真实任务ID/上传或产物URL扫描通过；wheel40项、sdist77项排除tests/.cache/.env，dist/SHA256SUMS.txt刷新。

13.4按原完成判断逐项核对后勾选：两个api_id、Mini/Fast/Standard代表差异、两区域样片/成片、独立超分、上传/单次优化/实际费用、授权与逐模型契约覆盖均有可追溯证据。矩阵新增完成判断索引，不要求为关闭最小矩阵对全部26模型收费实测，不把其他模式、音频、边界参数或人工质量记为通过。CLI复核62/67、剩余1.2/1.5/1.6/13.1/13.3五项。未重跑全量测试，历史532通过不记为本轮结果；无Git提交推送、业务主规范同步或归档。

## 2026-11-14 剩余五项契约复核与样片事实接线

从62/67开始，原剩余1.2、1.5、1.6、13.1、13.3。本轮未调用供应商、未新增收费提交。新增contract-review-closure.md的操作/错误/证据/未知回退映射，以及model-contract-audit.json的26模型差异台账；2.0时长继续provisional，seed与媒体边界等未知保持，不用现有成功配置证明全范围。核对26模型注册集合、18个暂定时长、6个确认时长、24个seed范围/默认未知、8个canonical multi以及各模型真实收费序号通过。

1.6发现缺陷：DraftFact仅在参数函数内校验，正式预检/接收没有提供本地源事实。按既有已知不符拒绝要求重新打开6.3，先补design与spec，再增加draft_evidence本地只读解析；同binding唯一remote_id匹配用于区域、已固定draft和完成状态，不把binding当账号证明、不猜有效期。预检读事实，接收事务重新读取，真实适配器准备阶段复查；外部/跨binding/多条匹配保留DRAFT_SOURCE_UNVERIFIED，账号和7天起算继续未知。重复key返回原任务，派发前不符转待处理，无自动样片链或额外上游请求。

新增9个隔离场景覆盖已知区域/类型/未完成拒绝、未知来源、预检后变化、接收失败清理预留、重放及派发前拒绝、真实stdio入口。首次定向146 passed/1 failed，失败是测试错误期待MCP is_error=true；现有工具按structured_content.ok=false/error返回业务错误。修正断言后相同定向命令通过147 passed in5.30s：`uv run --frozen pytest tests/test_draft_evidence.py tests/test_parameters.py tests/test_admission.py tests/test_compatibility_adapter.py tests/test_preflight.py -q --tb=short`。Ruff最初报告新增行过长/导入顺序及fixture导入遮蔽，格式化并显式从测试模块绑定fixture后check/format复验通过，150 files already formatted；OpenSpec严格校验通过。

因修改生产接线，已启动完整`uv run --frozen pytest`，日志.cache/five-full-tests.txt；运行中不记为通过。收费窗口仍5/10、余5，历史13次/47.020240/¥。无Git提交推送、业务主规范同步或归档。

本轮最终全量结果：`uv run --frozen pytest`退出0，546 passed in 530.61s (0:08:50)，日志保存在私有.cache/five-full-tests.txt。初次定向测试146通过/1失败为工具错误响应包装断言不符；修正断言后147通过。按CLI sourcePath/line核对四个复选框后关闭1.2、1.5、1.6、6.3，再运行apply确认65/67，未完成13.1、13.3。未修改原完成判断；供应商未明分支仍保留，外部实际Host及干净Windows证据仍缺。

最终检查：`uv run --frozen ruff check .`、`uv run --frozen ruff format --check .`均退出0（150 files already formatted）；版本入口退出0、0.1.0.dev0；`uv build`成功；`openspec validate add-local-video-generation-service --type change --strict`通过；`git diff --check`通过，`git diff --cached --exit-code`确认暂存区为空。构建包进行成员检查及SHA-256更新；未将私有运行证据、配置或测试目录加入包。

## 2026-11-14 干净Windows与实际Host验收准备

本轮只读检查Win32_OperatingSystem/ComputerSystem、服务/进程、Appx与安装注册表、指定配置文件存在性及去敏解析。结果与限制见windows-host-preparation.md。Get-WindowsOptionalFeature -Online被Windows要求提升，Get-VM权限不足；CIM仅见宿主项，不推断无VM。首轮命令有权限/缺失可选命令而退出1，未视为完整盘点成功；修正为逐项结果记录。探测不存在paths.py产生rg退出2，改读实际config.py确认LOCALAPPDATA与固定用户数据根。未访问凭据内容、未启动Host会话/VM、未改注册表/Host配置。

`uv run --frozen pytest tests/test_installation.py tests/test_windows_integration.py -q --tb=short`退出0，9 passed in74.10s；覆盖当前机器隔离安装、切换回切、备份屏障及多客户端，非干净OS/实际Host证据。日志.cache/environment-preparation-tests.txt。只修改文档，没有业务代码改动，本轮不重复全量546项，上一轮全量结果保留。13.1/13.3仍未完成，65/67。收费账本未新增事件，0供应商请求、0收费，余5次不变。无Git提交推送、业务主规范同步或归档。

文档收尾检查：Ruff check通过、format --check通过（151 files already formatted）；版本入口0.1.0.dev0；OpenSpec strict校验、git diff --check与暂存区为空检查均退出0。随后构建交付包并核验私有配置/测试/缓存未入包；包与SHA256SUMS位于本地dist，未发布。

## 2026-11-14 默认发行入口与意外派发保护（14.1）

先更新design、runtime-configuration delta spec并新增14.1任务，再实现EXECUTION_MODE严格枚举/配置优先级/冲突，默认local网络阻断，provider组合真实适配器、上传服务与调度。accepted事件同事务保存执行授权，旧/local任务启动前隔离及网络副作用前授权检查；无schema迁移。更新proposal、两份.env示例、成员/配置/工具/Host准备手册，说明仅新授权任务可执行。实际安装.env、Host配置均未修改。

隔离证据见production-entry-validation.md。初次定向3失败/48通过：同pytest PID重开被所有权检查拒绝，夹具在后端关闭后删除专用发现记录；随后1失败/4通过因合成响应遗漏model/object，补齐完整身份后5通过。未放宽生产解析或所有权检查。编辑脚本初次因Windows默认编码读取失败导致部分写入，复核去重并统一UTF-8；初始Ruff问题均修正。

最终定向`uv run --frozen pytest tests/test_production_entry.py tests/test_config.py tests/test_configuration_docs.py tests/test_compatibility_adapter.py -q --tb=short`退出0，92 passed in4.54s。全量回归运行中，结果随后补记；未提前关闭14.1。0供应商调用、0新增收费，剩余5次不变；无Git提交推送，未同步业务主规范或归档。

代码复核发现local网络包装重复，移除冗余后复跑默认构造、独立后端和配置示例：`uv run --frozen pytest tests/test_production_entry.py tests/test_runtime.py tests/test_configuration_docs.py -q --tb=short`退出0，13 passed in27.73s。原有独立后端进程、两个客户端、退出与接续测试通过；新生产组合重开用同进程夹具，不将其描述为实际Host。Ruff check/format退出0（154 files already formatted），构建成功。全量日志独立保存，完成后另记。

14.1全量回归：`uv run --frozen pytest`退出0，551 passed in540.30s (0:09:00)，日志.cache/entry-full-tests.txt。运行期间仅移除等价重复local包装，并已以13项默认入口/独立后端定向测试复验最终代码；无其他生产代码变动。92项入口/配置/兼容解析定向亦通过。按CLI sourcePath/line核对14.1复选框后关闭；重新核对进度66/68，剩余13.1、13.3。

14.1收尾检查：Ruff check/format均退出0（154 files already formatted），版本入口0.1.0.dev0；OpenSpec strict通过，git diff --check通过、暂存区为空。最终源码包/wheel构建及成员白名单检查、SHA-256更新随本轮交付执行；仅本地dist，无发布。

## 2026-11-14 13.3 local实际Host验收准备与确认门

只读Appx/进程/文件版本、指定Codex TOML与Cursor JSON结构检查；目标服务不存在，既有9/2条目。当前源码包解到专用.cache目录，uv sync --frozen --no-dev --offline退出0；包SHA及具体路径见host-local-review.md和私有manifest。安装版本检查退出0（0.1.0.dev0）；独立Python读取配置退出0（3.12.14，local来自dotenv，根与输出均专用路径）。候选片段在内存中解析合并，原服务语义不变；Host真实文件未写入。观察器仅compile语法检查，未启动、无租约。git check-ignore确认准备目录被忽略。

本轮无代码变更，不重复全量551项；未将准备或SDK结果算作实际Host。需要确认的对象/改动/重启顺序已形成具体清单，13.3保持未完成。无供应商请求，余5次收费不变；无Git提交推送、业务主规范同步或归档。

收尾：Ruff check/format退出0（155 files already formatted）；OpenSpec strict、git diff --check通过，暂存区为空。重新核对两个真实Host配置SHA均与准备前一致，专用状态目录无后端发现记录。最终构建文档包不替换已经冻结的验收安装副本，其原包SHA仍按验收清单记录。

## 2026-11-14 工程规范及实际 Host 范围调整（0.1.0.dev0，13.3）

工程主规范、Git协作规范/指南/PR指南和AGENTS同步测试清理及feature→dev→main政策；无强制其他人审批，日常按改动检查、发布完整验收、合并按差异复验、内容及相关输入一致才复用、实际发布才执行CD。新增docs/test-resource-register.json持久交接清单。

配置验证：Codex TOML与Claude JSON剔除新增服务后与备份语义一致；DSH YAML移除新增insert后与备份语义一致；Cursor配置与原备份逐字节一致。三款目标为Codex Desktop/Claude Desktop/DeepSeek Harness Desktop，沿用同一local隔离安装。当前Codex工具集未发现seedance；DSH窗口截图/文字不一致，停止UI操作，实际Host发现和生命周期均不冒充通过。待用户完整重启三款Host后继续，Agent没有关闭当前Codex。

实际检查均退出0：OpenSpec change严格校验；engineering-practices和git-collaboration主规范严格校验；ruff check全部通过；ruff format --check为155 files already formatted；git diff --check通过。本轮只改规范、记录及Host配置，没有新增业务代码，不重复运行pytest/build；既有551项全量结果不当作本轮重跑。

清理：Cursor临时配置已撤销；复扫当前专用目录仍有安装/依赖、受保护备份和local状态，验收未结束故保留；观察器未启动。49个历史缓存目录已登记待分类，不宣称全清理；下次测试前按清单先复用/核定清理，不能盲删付费原件。配置恢复须保留期间并发修改。13.1/13.3保持待完成、66/68；无供应商请求、无收费变化、无Git提交推送。工程主规范已修改，业务主规范未同步、change未归档。

## 2026-11-14 13.3实际Codex重启后local验证

版本0.1.0.dev0、冻结包身份沿用host-local-review.md。Codex发现23个MCP工具；实际健康工具返回local、PID19900、3租约、派发关闭；无参能力工具返回26+1模型。首次只给model_id的能力查询返回API_ID_REQUIRED，改无参后成功。唯一local任务接收及按请求标识找回一致，任务version1、未提交、优化关闭。只读专用库计数tasks=1，attempts/uploads/remote_observations/artifacts/charge_observations全0；没有供应商请求。证据见host-local-codex-evidence.json。

多租约不能代替每款Host验证。DSH自动化无法可靠聚焦编辑输入，未发送请求；已请用户在Claude及DSH各执行三项只读调用。启动无RPC租约只读观察器，最长15分钟，清单登记PID/时点。退出恢复尚未完成，仍需用户手动退出承载聊天的Codex；保留当前使用的安装及配置待验收后逐字段恢复与清理。本轮无生产代码变更，不重跑pytest/build。OpenSpec严格校验与git diff --check退出0。13.1/13.3未关闭，66/68；无Git提交推送、业务主规范同步或归档。

2026-11-14：依据用户回传，Codex 与 DSH 的 local 共享查询通过；Claude 未发现服务。Claude 打包配置包含服务条目但加载原因尚待定位；无新增供应商请求。详见 host-local-review.md；13.3 未完成。

2026-11-14：Claude 未发现服务的配置路径差异由用户指出。已向 Claude-3p 配置合并验收条目，误修改的打包配置原样恢复；待重启验证，未调用供应商。

2026-11-14：用户回传Claude成功查询与Codex/DSH相同后端和任务；三Host发现及共享查询通过，退出恢复尚未完成。local任务不自动获得provider执行授权。

2026-11-14：DSH 正常退出后租约5→4，后端PID/实例不变且原任务可查询；最终退出与重启接续待验证。详见host-local-review.md。

2026-11-14 13.3：最后Host退出后旧后端已确认退出；重启后工具执行失败且发现两个新实例，任务恢复未通过。只读库保留原任务且无供应商尝试；不将文件存在等同恢复通过。见host-local-review.md。

13.3 排查：独立stdio客户端local读取原任务成功，Codex自身工具调用仍失败；分别记录初次路径/timeout探针错误，不能将SDK客户端成功替代实际Host验收。隔离资源继续保留用于修复。

13.3 后续排查：相同安装与状态的SDK stdio空闲15秒两次状态查询成功，PID不变；Codex工具连接失败根因仍未核实，未作推测性代码修复。验收未完成，现有资源保留供排查。

前端断连恢复补强：并发重连与禁止在途调用重放2项测试通过；runtime 6项通过；Ruff和OpenSpec严格校验通过。实际Codex验证未完成，14.2不勾选，暂留隔离安装和备份。

实际Codex修复版重启后查询原任务成功，随后取消测试任务；该结果不证明在途断连重连已实际触发。已移除三Host测试配置，运行中的Codex仍持有安装，等待手动重启后清理。

2026-11-14：Codex重启后确认专用后端退出、三Host测试配置已移除，清理并复扫本次独立安装、状态及备份；历史缓存按清单待分类。13.3/14.2 完整验收仍未完成。

14.2 通过：定向并发重连/在途不重放2项测试、运行时6项测试及实际DSH同会话隔离后端中断重接；用户返回从PID20476到39572、local、未派发。Codex先前错误根因未确认。临时配置已移除，等待DSH退出完成清理。

14.2验收后：DSH退出，测试后端39572确认退出，配置及专用安装/状态/备份已清理复扫；其他历史缓存仍待分类。67/69，13.1/13.3尚未完成；无供应商调用、Git提交推送、业务主规范同步或归档。

2026-11-14 13.1/13.3现有环境复验：uv run --frozen pytest tests/test_installation.py tests/test_runtime.py tests/test_frontend_reconnect.py -q 退出0，10 passed in 65.35s；为隔离客户端及本机安装测试，不能代替干净Windows或实际Host业务交付。用户表示已有干净Windows环境，访问方式/版本/快照/Host状态待补充。

清理异常：本轮测试目录 af30659bec2c4dbd8e767e23381fe19e 的重解析点扫描失败，但后续 PowerShell 清理未因前一进程失败而停止，仍执行 Remove-Item。目录已不存在；未能在删除前记录链接目标，不能证明链接目标未受影响。后续清理必须在同一控制流检查扫描退出码后再删除，并记录重解析点。
Sandbox：用户确认刚启动且未操作，实际窗口显示Windows桌面；Get-VM权限拒绝，未验证来宾命令或安装。已构建专用sdist SHA256 f9ec4432775f152d65055ebc8b969143953ae5d4243ba19c3e2ac5dfb27e3c7d，供用户复制至Sandbox；不含凭据。

Sandbox安装：用户实际报告Python 3.12.14可用、uv 0.12.9，在线uv sync因PyPI超时失败，独立Invoke-WebRequest也超时。宿主按锁文件筛选uv缓存，首次使用相对缓存路径测试失败，改绝对路径离线sync --frozen --no-dev --reinstall退出0；缓存zip完整性检查通过，SHA256 e47d590fc0714fc70d99eb39b76d82ca8174f682d55ea2ab5d238879df213ad1，49.2 MiB。Sandbox离线安装尚待实际执行。

13.1完成：Sandbox冻结离线安装及SDK stdio 23工具发现通过；安装目录删除后外部输出标记/数据库摘要一致，独立Python只读integrity ok、tasks0；schema拒绝/一致备份/备份窗口三项隔离测试3 passed in 1.12s。非真实视频与实际Agent Host交付，跨版本回滚未验证。清理待执行。

13.1宿主清理：本轮专用sandbox-acceptance-20261114目录内三处pytest符号链接目标均核验位于其maintenance-tests目录内，逐个解除后复扫并删除专用目录，路径不存在。Windows Sandbox仍待用户关闭以清除其余来宾资源。先前另一目录重解析点目标未记录的清理异常仍未被此结果证明或消除。

13.1清理：用户确认关闭Sandbox，宿主复扫未发现Sandbox会话进程或本轮专用验收目录；资源清单更新。此前另一测试目录重解析点误清理事件仍未能确认目标影响。13.3原判断尚需实际Host Job Object与跨Host正式生成交付证据，禁止真实供应商调用期间保留未完成。

13.3实际DSH Job检查：DSH、前端、后端IsProcessInJob(None)=True，无法判定同一Job；DSH正常退出后SDK客户端仍能访问同一后端（租约2→1），最后断开后后端退出。见windows-host-acceptance.md；不等同强制Host退出或业务交付。

Job local验收后，DSH测试配置撤销，相关进程退出，专用安装/状态/备份目录经过重解析点扫描后删除并复扫；13.3仍未完成。

13.3 DSH强制退出：隔离SDK持有另一连接，用户强制结束DSH后原后端仍服务且租约2→1；SDK退出后后端确认退出。IsProcessInJob(None)三个进程均为True，但没有同一Job句柄证明；一次Job枚举探针TypeError失败。无供应商调用，详见windows-host-acceptance.md。

强制退出验收资源已收尾：DSH测试配置撤销，Host、SDK及后端退出，专用目录重解析点扫描通过并删除。Job同一对象归属仍未确认；13.3保持未完成。

13.3 Job具体句柄探针：自测已知成员真/无关进程假；DSH主进程持有并属于的具体Job不含前端解释器及后端，启动器持有另一具体Job含前端但不含后端；不能排除不可访问共同外层Job。详见windows-host-acceptance.md；无供应商请求。

Job句柄归属验收后，DSH配置撤销、Host和后端退出，独立目录经重解析点扫描后删除并复扫；13.3仍未完成。

13.3准备：新增实际Host跨Host业务交付方案及验收/不确定提交/按量实扣/清理条件；未新建测试环境、未新增供应商请求。既有local Host和SDK真实视频证据仍不能合并宣称实际Host交付通过；13.3待验。

13.3实际Host业务交付及重启接续通过：Codex提交/DSH复制主视频、实扣0.8028¥、账本第14次、重启后相同任务远端ID与状态；Job实际有限证据、partial/unverified集合及多个新实例原因未核实均如实保留。最终清理待用户退出Codex，原件副本保留。

13.3清理核验：Codex再次重启后测试后端/观察器退出、Host测试配置不存在；SQLite integrity ok/提交1次、两份视频摘要一致。保留任务状态、原件和交付副本，专用安装及私有备份清理中。

13.3最终清理完成：专用安装、私有配置及备份、观察器已移除；按用户要求保留原件、复制视频及任务状态，清理范围与资源清单已更新。
