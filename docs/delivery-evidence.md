# 交付证据汇总

归档更新（2026-11-14）：八项业务主规范已同步，change已[归档](../openspec/changes/archive/2026-11-14-add-local-video-generation-service/archive-record.md)，71/71完成。产物集合待核实及已关闭但未修复的Job生命周期限制保留；下文未同步/未归档表述为历史状态。

当前汇总（2026-11-14，文档同步）：tasks为71/71完成；13.1 干净 Windows 安装和 13.3 实际 Host 跨 Host 主视频交付已有验收记录。26 个视频模型中 8 个有局部真实证据，其余 18 个仅契约与隔离验证；独立超分另有真实闭环。局部样例不证明所有参数、模型或完整产物集合；产物集合仍待核实，重启终止机制已完成最后一轮有界排查：本机复现启动器自身 Job 关闭可终止后端，历史 Codex 对启动器的最初终止方式未直接取证；按用户要求关闭调查，保留生命周期兼容性限制，不宣称已修复。收费账本累计 14 次、已观察实扣 47.823040 元、现有最大剩余 4 次；本轮无供应商请求。具体范围见 [实际 Host 验收](host-delivery-acceptance-plan.md)、[收费账本](paid-test-ledger.json) 和 [验证记录](verification-add-local-video-generation-service.md)。下方阶段记录均为历史快照，数字不代表当前状态。

历史续记（2026-11-14）：新增14.1默认发行入口接线与防意外派发保护已完成，66/68，剩余13.1干净Windows和13.3实际Host。默认local，provider显式启用仅新授权任务；551项全量通过。见[入口验证](production-entry-validation.md)。本轮0供应商/收费调用、Host配置未修改，收费余5次不变。以下为历史阶段记录。

2026-11-14本轮契约复核完成：按原完成判断交付1.2错误/证据映射与未知回退、1.5逐模型26行差异和来源台账、1.6已知不符拒绝/未知提示规则；修复实际MCP预检、接收事务与派发前未接入本地样片事实的问题，重新关闭6.3。全量546项隔离测试通过，当前65/67，剩余13.1干净Windows与13.3实际Agent Host验收。调查完成不等于供应商未知规则获证；详见docs/contract-review-closure.md及docs/model-contract-audit.json。本轮0次供应商请求、0次收费；历史13次，当前窗口5/10、余5，实扣47.020240/¥未变。未提交或推送Git，业务主规范未同步、change未归档。

以下续记保留各阶段状态；当前状态以文首汇总为准。

历史状态（2026-11-14）：[单次提示词优化](optimization-queue-acceptance.md)已通过真实统一队列下载复制，single_allow不修改持久偏好，后续预检默认关闭。13.4按最小矩阵原完成判断关闭，62/67、剩余5项；26模型仍为8个局部真实、18个仅契约/隔离。当前窗口5/10、余5，历史13次实扣47.020240/¥。实际Host、干净Windows及剩余规则性调查未完成。

最新追加（2026-11-14）：[Fast图生/Standard多模态](fast-multi-queue-acceptance.md)已完成真实统一队列的托管、上传、生成、下载、复制；输入及交付摘要核验通过。8个模型有局部真实证据、18个仅契约/隔离，超分单列；当前授权窗口4/10、余6，历史12次实扣46.217440/¥。仍61/67，不把局部证据当作完整矩阵、实际Host或干净OS验收。

当前更新（2026-11-14）：国内与国际样片/成片均已有统一队列真实闭环，国际证据见[专项记录](global-queue-acceptance.md)。当前61/67、剩余6项；26模型中6个局部真实覆盖、20个仅契约/隔离，超分单列。新收费窗口2/10、余8，历史共10次实扣42.572482/¥。下方数字为历史阶段，不替代当前账本；实际Host、干净OS和完整矩阵仍未验收完成。

> 2026-11-14专项推进：1.8完成，当前59/67；1.2/1.6获得部分新证据但未关闭。累计4/10收费提交，余量最多6；直接接口取证与真实统一队列/Host验收严格区分。

> 2026-11-14更新：1.7主视频下载核心证据已取得，尾帧真实路径及JPEG接线完成，当前58/67、剩余9项。本轮仅1次收费提交，¥0.8028；完整集合、其他模型及长期恢复仍待核实。旧进度条目保留为历史。

> 2026-11-13 8.4 更新：双封装解析与实扣事务持久化已完成，当前 57/67，剩余 10 项。旧表／历史记录中的 8.4 未完成状态已被本条及 tasks.md 替代。本轮只回放既有真实脱敏 fixture，不新增真实调用；其他供应商证据和实际 Host 验收仍待完成。

> 2026-11-13更新：第1项专项授权真实提交1次、查询4次，已取得Mini的SUCCESS／最终费用完整响应；1.1完成，56/67。以下历史“真实调用0／SUCCESS全未知”状态已由本次证据部分更新，不代表生产适配或完整供应商交付验收通过。详见[真实响应证据](provider-contract-evidence.md)。

截至 2026-11-13，本地实现及隔离验证已推进，**尚未达到完整供应商接入／正式发布验收**。本页对应任务 13.7，汇总不等于关闭其他未完成任务。具体命令、结果和失败修复过程保留在 [实施验证记录](implementation-progress.md)；未来变更后须重新验证，不能复用旧结果冒充当前通过。

## 历史八项能力映射（2026-11-13）

表内代码路径相对 `src/zhenzhen_seedance_video/`，测试路径相对 `tests/`。代码和测试存在不自动代表所有规范分支已实现；最后一列列出关键缺口。

| Change capability | 实现入口 | 隔离验证文件 | 使用／验证说明 | 未验证或条件能力 |
| --- | --- | --- | --- | --- |
| shared-local-runtime | `runtime.py`, `frontend.py`, `ownership.py`, `leases.py`, `lifecycle.py`, `windows_security.py` | `test_runtime.py`, `test_runtime_recovery.py`, `test_windows_integration.py`, `test_installation.py`, `test_windows_security.py` | [RPC](local-rpc.md)、[测试分层](testing.md)、[安装手册](../MANUAL.md) | 当前 Windows 独立进程已验证；干净 OS/VM 13.1、实际 Host/Job Object 13.3 未验收 |
| provider-api-contracts | `models.py`, `parameters.py`, `preflight.py`, `provider_response.py`, `compatibility_adapter.py`, `provider.py` | `test_models.py`, `test_parameters.py`, `test_preflight.py`, `test_provider_response.py`, `test_compatibility_adapter.py` | [模型预检](model-preflight.md)、[契约证据](provider-contract-evidence.md)、[真实验收矩阵](provider-acceptance-matrix.md) | 四份用户样例不是真实调用；SUCCESS/完整费用、HTTP 错误等 1.x 待核实；生产适配器 8.4 未完成 |
| task-admission | `admission.py`, `admission_rpc.py`, `materials.py`, `storage.py` | `test_admission.py`, `test_tools.py`, `test_windows_integration.py` | [任务接收](task-admission.md) | 本地接收／去重／授权与共享后端已隔离验证，不代表供应商幂等；远端未创建核验仍是条件能力 |
| task-scheduling-recovery | `scheduler.py`, `task_state.py`, `lifecycle.py`, `storage.py` | `test_scheduler.py`, `test_task_state.py`, `test_lifecycle.py`, `test_runtime_recovery.py`, `test_storage_fault.py`, `test_windows_integration.py` | [调度恢复](scheduling-recovery.md)、[存储恢复](storage-recovery.md) | 合成 submit/query 及分阶段崩溃；上游取消、历史核对、身份校验等不宣称支持 |
| input-material-lifecycle | `materials.py`, `upload_service.py`, `uploads.py`, `material_readers.py`, `cleanup.py`, `cleanup_rules.py` | `test_admission.py`, `test_upload_service.py`, `test_uploads.py`, `test_cleanup.py`, `test_runtime_recovery.py` | [素材清理](material-cleanup.md)、[接收](task-admission.md) | 托管／摘要／有限清理重试已验证；1.4 文档证据调查完成；8.3 内部持久化准备已有隔离验证；真实供应商上传未验收 |
| video-artifact-delivery | `artifacts.py`, `artifact_files.py`, `network.py` | `test_artifacts.py`, `test_network.py`, `test_windows_integration.py` | [产物交付](artifact-delivery.md)、[网络策略](network-policy.md) | 本地 HTTP／合成产物；供应商签名 URL 生命周期、尾帧集合、链接刷新／续传仍待核实 |
| agent-task-observability | `tools.py`, `queries.py`, `diagnostics.py`, `charges.py` | `test_tools.py`, `test_diagnostics.py`, `test_charges.py`, `test_windows_integration.py` | [Agent 工具](agent-tools.md) | SDK stdio 客户端不等同实际 Host；费用仅合成内部 Decimal 持久化，尚无完整真实费用解析／结算验收 |
| runtime-configuration | `config.py`, `network.py`, `admission.py`, `storage.py` | `test_config.py`, `test_configuration_docs.py`, `test_network.py`, `test_admission.py`, `test_installation.py` | [配置](configuration.md)、[手册](../MANUAL.md) | 安装目录 .env 优先及逐字段回退已验证；真实账号换钥／连接身份与实际供应商代理链未验收 |

## 证据层级与本次核查

- 用户契约：`tests/fixtures/provider/user-supplied/` 中四份 JSON，只有明确提供的字段／层级证据，没有本项目实际 HTTP 请求证据。
- 单元与本地 HTTP 隔离：默认 pytest 拒绝真实网络，覆盖授权、状态、故障、文件和网络策略。合成费用、SUCCESS 拒绝分支不能核实上游协议。
- 当前 Windows 独立进程：13.2 两个前端／共享隐藏后端、去重、复制、冲突、退出、崩溃与存储恢复。13.1 新解包目录和独立虚拟环境安装已验证，但并非干净 OS/VM。
- 实际 Host：13.3 尚未执行，不记录 Host 名称／版本或 Job Object 兼容结论。
- 供应商：13.4 仅完成离线候选矩阵；13.5／13.6 未执行。9 次候选提交不是授权，当前真实调用为 0。

本轮检查命令与最终输出见 [验证记录的 13.4／13.7 小节](implementation-progress.md#验收矩阵与交付证据134137)。构建产物只属于本地开发构建，`dist/SHA256SUMS.txt` 用于本地校验，未发布正式版本或获得远端 CI 结果。包含未提交工作区内容，不能只用当前 Git HEAD 标识构建。

## 规划一致性复核

- 保持 26 视频模型与独立超分、两个 api_id；不增加端点透传，不自动派发样片依赖，不因生成成功追加付费超分。
- 安装目录 .env 逐字段优先，进程／用户环境依次回退；密钥仍为 ZHENZHEN_SEEDANCE_API_KEY；空值不回退。优化共享授权是即时业务偏好，单次 false 优先，任务接收后固定。
- 四份兼容端点样例的字段证据已明确，proposal 的旧“全部结构未知”说明修正；SUCCESS 及 data.usage 完整响应保持待核实。
- proposal/design 中“尚无实现、尚无 tasks”的表述标为规划阶段历史；当前状态以 tasks 和本页验证记录为准，未改变已批准需求。
- 任务 13.7 可在证据映射和检查完成后关闭，不要求把未验收的 13.1/13.3–13.6 写成通过。任务 13.4 因真实素材、调用和费用尚未授权、核心契约未齐，保持未完成。

## 历史剩余交付门槛（非当前待办）

剩余12项的逐项已交付、阻塞证据与下一步见[剩余任务清单](remaining-work.md)；干净Windows和实际Host的待执行记录见[验收记录模板](windows-host-acceptance.md)。

任务 1.1/1.2/1.5–1.8 的剩余契约、8.4 生产适配器、13.1 干净 Windows、13.3 实际 Host、13.4 授权矩阵、13.5/13.6 真实验收仍按 tasks 跟踪。未知提交不得自动重提；条件能力调查不是功能支持证明。未返回费用不得记零，费用缺失不阻止已确认成功的主视频下载。

本轮不执行供应商请求，不提交／推送 Git，不创建发布、不同步八项业务主规范、不归档 change。此前导入的 manual-writing、git-collaboration、engineering-practices 主规范保持既有状态。

上传证据补充：1.3 条件能力调查与 1.4 上传文档证据整理已完成，仍无真实调用；uploads 单次组件与严格解析测试不代表 8.3 持久化调度接线完成。后续结果见实施记录。

8.3 续记：持久化准备／恢复／调度接线已交付，见 [上传准备](upload-preparation.md)。此前单次组件限制为历史状态，生产完整适配器与真实验收仍未完成。

8.4续记：四样例提交／查询接线及严格解析已完成隔离验证，见 [兼容适配器](compatibility-adapter.md)；SUCCESS和费用完整响应仍待核实，任务整体未完成，未启用生产真实调用。


## 2026-11-13 主视频引用与部分交付

已确认的 metadata.url 可通过内部 CompatibilityAdapter（注入任务库）接通主视频下载、持久化与复制。任务查询新增 artifact_set_status；完整集合未知时为 unverified，已就绪主视频可单独交付，任务保持 partial，保留 ARTIFACT_SET_UNVERIFIED 和输入托管副本。显式放弃仍按既有规则清理素材。测试 tests/test_main_video_delivery.py 使用合成传输覆盖下载、复制、403恢复、数据库重开、重复查询、格式和引用关联以及清理协调。四份样例仍是契约来源；尾帧／完整集合、SUCCESS、费用完整响应待核实，无真实调用证据。


主视频协议复验：独立stdio客户端的提交、等待、主视频下载／复制，以及最后客户端退出、发布前后崩溃和下载待处理恢复，见[端到端验证说明](main-video-protocol-validation.md)。此为合成供应商、多进程协议证据；实际Host和供应商仍未验收。


本地素材完整协议复验：已通过独立stdio客户端串联托管、multipart上传、生成、主视频下载和复制，并覆盖上传未落账／引用已保存／生成处理中三种重启接续。参见[素材完整流程验证](material-protocol-validation.md)；合成证据不替代真实Host或供应商验收。


上传异常协议证据：tests/test_upload_failure_protocol.py覆盖有限重试、耗尽后重启不复活、过期同副本重传与在途放弃清理，参见[上传准备](upload-preparation.md)。仅合成上游，多进程MCP协议测试不替代实际Host或真实供应商验收。


多素材协议续记：tests/test_multi_material_protocol.py覆盖三图部分上传成功、失败／耗尽跨后端恢复、重启前后双客户端并发去重及主视频复制。第一项成功引用保持复用，不将测试推广为混合音视频或真实供应商验收。见[上传准备](upload-preparation.md)和[验证记录](implementation-progress.md)。


混合素材协议续记：tests/test_multi_material_protocol.py现包含PNG／MP4／MP3两种顺序，覆盖视频或音频上传部分失败、有限预算耗尽、跨后端恢复及双客户端去重，成功路径完成主视频下载和MCP复制。传输类型／引用顺序有严格断言；输入为合成标记字节，不证明媒体有效性或真实供应商接受性。详见[上传准备](upload-preparation.md)及[验证记录](implementation-progress.md)。


混合素材生命周期续记：tests/test_mixed_lifecycle_protocol.py覆盖视频／音频引用过期后从原托管副本重传，以及部分成功时在途取消／放弃清理和跨后端重启不复活；对应8.3、9.6、11、12／13.2。详见docs/upload-preparation.md与docs/implementation-progress.md（docs内使用同目录文档）。55/67，8.4和实际Host13.3仍未完成，尾帧／完整集合、SUCCESS及完整费用待核实；仅合成验证，无真实调用或Git提交推送。


混合素材清理恢复续记：tests/test_mixed_cleanup_protocol.py覆盖取消／放弃后部分清理失败、有限预算跨后端恢复、耗尽后重启不重置及MCP显式恢复；旧版本拒绝、已完成项不重复删除、原件保留。对应11.1／11.2、9.6、12／13.2，详情见docs/implementation-progress.md及docs/upload-preparation.md。55/67保持；尾帧／完整集合、SUCCESS及完整费用待核实，无真实供应商调用、Git提交或推送。


清理崩溃窗口续记：tests/test_mixed_cleanup_crash_protocol.py覆盖混合素材删除前／删除后未落账、剩余预算1／0的跨后端恢复。已删除核对补记，未删除且无预算需MCP显式恢复；实际删除每项一次，原件保留，不复活生成。对应11.1／11.2、9.6、12／13.2，详见docs/implementation-progress.md与docs/upload-preparation.md。55/67保持，待核实接口和实际Host验收不变；无真实调用或Git提交推送。


并发清理恢复续记：tests/test_cleanup_concurrency_protocol.py覆盖取消／放弃后双独立stdio客户端旧版本冲突、当前版本并发恢复只授予一份预算，以及pending／done跨后端重启重放幂等。对应11.2、9.6、12.4／13.2，详见docs/implementation-progress.md和docs/upload-preparation.md。55/67保持；待核实接口、实际Host和真实供应商验收状态不变，无真实调用或Git提交推送。


清理存储故障续记：tests/test_cleanup_storage_protocol.py覆盖intent／complete真实事务回滚、storage_fault禁止新增副作用、两客户端只读观察及跨后端恢复。Lifecycle修复只在已确认存储保护时保留只读服务，9.6重新验证；对应4.3、9.6、11.1、12／13.2。详情见docs/implementation-progress.md和docs/upload-preparation.md，实际Host与待核实接口状态不变，无真实调用或Git提交推送。


存储故障并发续记：tests/test_cleanup_storage_protocol.py扩展双stdio客户端并发查询、七类管理操作统一STORAGE_FAULT拒绝，以及三代后端的清理预算／旧版本重复恢复幂等。Tools入口补充非只读故障门，修复能力错误掩盖存储阻断的问题。对应12.3、4.3、9.6、11.2、13.2；详情见[验证记录](implementation-progress.md)。真实Host与上游待核实边界不变，无真实供应商调用、Git提交或推送。


恢复再次故障续记：tests/test_cleanup_storage_protocol.py新增两项连续存储故障场景，跨四代后端验证启动后的清理恢复再次失败、双stdio客户端接入查询与管理拒绝、预算保持和重复恢复幂等。补齐find_task_by_request_key的stale字段，对应12.3、9.6、11.2和13.2。详见[验证记录](implementation-progress.md)。仅合成适配器，不代表RPC公布前恢复扫描故障或真实Host／供应商验收。


RPC前启动扫描续记：tests/test_cleanup_storage_protocol.py增加两种既存清理状态下的启动scan事务故障，验证RPC未启动、发现记录未更新、非零退出和后续正常启动／重复恢复。测试区分已提交的上传阶段恢复与失败清理事务回滚。对应9.6、11.1／11.2、13.2，详见[验证记录](implementation-progress.md)。仅合成验证，生产实现不变。


夹具修订后完整复验：全量隔离测试495 passed in462.20s，退出0；本轮无代码改动，上轮发现文件读取竞争与合成接入宽限期调整已获得完整回归证据。历史失败记录保留，详见[验证记录](implementation-progress.md)。55/67，真实供应商／实际Host及待核实接口边界不变。


剩余任务离线推进：新增同版本双安装目录切换／回切验证，定向2 passed、全量495 passed in479.12s；逐项剩余条件见[任务清单](remaining-work.md)，未来环境记录见[验收模板](windows-host-acceptance.md)。不以本机隔离演练关闭干净OS或实际Host任务，55/67保持。


2026-11-14更新：13.6独立超分统一队列真实闭环通过，新增1次720p收费提交，累计5/10。经MCP上传/查询/下载/复制，实际费用0.875/¥，累计6.044492/¥；输入保留，完整产物集合仍未核实。详见[专项验收](upscaler-queue-acceptance.md)。当前60/67、剩余7项；此前各日期及表格是历史快照，不代表本次未执行。


2026-11-14 13.5更新：真实Mini i2v、国内2.5样片及其成片经统一队列/MCP下载复制通过，累计8/10、23.760998/¥。新增已关联NOT_START→queued解析，保留原状态且不允许重提；未观察的SUBMITTED仍拒绝。原Mini任务解析待处理后通过同库重启及显式刷新恢复，未重复POST。三模型完整脱敏响应及持久化回放见generation-queue-observed，详见[专项验收](generation-queue-acceptance.md)。当前61/67、剩余6项，完整集合与其他未知项保持，业务主规范未同步，change未归档。
