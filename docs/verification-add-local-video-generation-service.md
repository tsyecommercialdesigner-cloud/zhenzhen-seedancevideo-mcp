# OpenSpec 验证：add-local-video-generation-service

## 本地协议检查与 DSH 配置核对（2026-11-14）

新增发行包模块 `zhenzhen_seedance_video.protocol_probe`：独立临时状态根，仅允许 local，调用 SDK stdio 初始化、发现、状态与能力查询，不提交任务、不调用供应商；失败保留隔离目录并提示，不打印密钥或原始异常。当前已发布 v0.1.0.dev0 不含模块，待后续发行后才能按手册命令使用。

本机 DSH 文档镜像 `dsh-plugin-guide` 0.3.39 的 MCP 指南和配置目录给出 `insert`、插件名、`serverName`、`transport`、`command`、`args`；手册 YAML 用本机 yaml 模块解析并核对字段。Desktop 此前有实际 Host 发现证据，新 uv 配置片段未直接接入；web 和 multica 的配置机制可见，具体接入尚未实测。没有修改 Host 配置。

首次探针测试由于 SDK v2 字段使用旧驼峰名失败，修正为 `protocol_version` 后重跑；provider 拒绝测试始终通过。最终 `tests/test_protocol_probe.py` 2 passed；Ruff check/format 通过；离线 sdist、wheel 构建成功且包含模块；JSON/TOML/YAML 解析和本地链接检查通过。未做真实供应商或实际 Host 新接入，未做全量测试或发布。测试及构建临时资源清理见资源清单。

## 成员手册修订检查（2026-11-14）

对照手册主规范、编写指南、当前实现与实际验收记录，修订 MANUAL：增加固定标签/完整 SHA clone、安装目录凭据规则、Codex TOML 与 Claude Desktop JSON、只读 Host 检查、升级回滚及排障；修正干净 Windows 和实际 Host 证据状态。保留产物集合未知、Job 调查关闭但限制未修复、跨版本升级未验证。

本轮解析3个 PowerShell 代码块、1个 JSON 和1个 TOML 块，核对本地文档链接；git diff --check 及11项主规范严格校验通过。未执行 clone、安装、Host 配置修改或供应商调用。发行包没有独立成员协议检查脚本，当前手册提供 Host 只读步骤但无法给出统一退出码或自动超时；DSH Desktop 完整 YAML 补丁及 web/Multica、其他 CLI／Shell 组合的具体适配未能从现有脱敏证据核实，手册明确未验证，不虚构示例。本次未证明指南全部要求已满足。

## 主规范同步与归档（2026-11-14）

用户明确授权后，八项业务主规范共83条需求同步至openspec/specs；逐份核对Purpose及需求正文与delta一致，主规范无delta操作标题。11项主规范严格校验通过，归档前change严格校验通过，71/71任务完成。归档位置： [2026-11-14-add-local-video-generation-service](../openspec/changes/archive/2026-11-14-add-local-video-generation-service/archive-record.md)。

产物集合仍待核实；Job调查关闭但兼容性限制未修复，不重开排查。归档不消除既有WARNING，也不等于正式发布。下方“未同步/未归档”均为历史执行记录。本次无测试临时资源新增，无供应商调用或Git提交推送。

## 全量隔离与构建交付复验（2026-11-14）

本轮使用当前工作区，未修改实现、依赖或测试代码。`uv run --frozen pytest -q --basetemp .cache/delivery-recheck-20261114/tests`：**558 passed in 550.09s，退出0**。包括既有Job隔离对照用例，不涉及实际Host重启或重开已关闭调查。

`uv run --frozen ruff check .`、`uv run --frozen ruff format --check .`（160 files）、`openspec validate add-local-video-generation-service --type change --strict`均通过。`uv build --offline --out-dir .cache/delivery-recheck-20261114/build`成功生成sdist和wheel；`uv run --frozen zhenzhen-seedance-video --version`返回0.1.0.dev0。包内容扫描未包含.env、.cache、.venv、deliveries或__pycache__目录。首次扫描误把辅助文件当tar导致失败，限定wheel/tar.gz后复查通过，不影响构建结果。

输入摘要：按路径排序的src/tests下Python文件及uv.lock、pyproject.toml、.python-version，共90个文件，逐项以UTF-8相对路径、NUL、文件原始字节、NUL拼接，SHA256为`6349b4ee439e25c5ea214093edce1df8ea2c22cb45f2fafefbb7ca8fe5378a4c`。wheel SHA256：`6de025149e29a81d0dd1124ee6abb07415a207641fc0ff06e54ebab6e12b2336`；sdist SHA256：`43c59b3b58ff2c1411928db5bfad07f3f1709f8bb646dc56367f565060e6966e`。这是本轮构建快照；后续验证记录更新会改变包含docs的sdist输入，不能仅凭版本号复用包摘要。

结论：当前工作区通过全量隔离、代码检查与本地构建门槛，可作为带已知限制的开发交付候选，不是正式发布/远端CI或全部供应商能力认证。tasks保持71/71；完整产物集合仍待核实，Job生命周期调查保持关闭且兼容性限制未修复。未新增供应商调用、主规范同步、归档或Git提交推送。

本轮测试和构建临时资源在证据记录后按资源清单清理，保留现有视频原件、副本及任务状态；最终清理状态见docs/test-resource-register.json。

## 文档同步后的重点复验（2026-11-14）

使用 openspec-verify-change 复验 add-local-video-generation-service（repo-local、spec-driven）。本轮核查最新AGENTS、status/instructions、proposal及design当前状态、tasks完成记录、README/MANUAL、交付汇总和历史任务页，并定向对照产物及共享运行规范与实现。未重开Job排查。

| 维度 | 结果 |
| --- | --- |
| 完整性 | instructions返回71/71、remaining=0，与tasks勾选一致；未重新完成全部需求/场景的逐条覆盖审计。 |
| 正确性 | 本轮重点实现与文档一致：compatibility_adapter.py:127返回complete=False，artifacts.py:73及queries保留集合未知；runtime按execution_mode选择供应商适配器。其余业务场景未逐项重新验证。 |
| 一致性 | 先前过时验收进度警告已修正：proposal、README、MANUAL、design文首、delivery-evidence与remaining-work均区分现行验收与历史快照，13.1/13.3/13.4完成范围与tasks一致。Job规范差距继续明确披露，不能据此给出无条件全符合结论。 |

**已解决：过时验收进度。** 旧的66/68等数字位于明确标注的历史阶段；proposal不再把干净Windows及实际Host一概写成未完成，README/MANUAL也不再把发行入口说成仅有隔离验证。历史测试失败与阶段记录保留，不用新结果覆盖原始事实。

**保留1项WARNING：Job生命周期兼容性限制。** runtime.py仍通过虚拟环境解释器隐藏启动并尝试breakaway；已有对照证据表明启动器自身Job可连带终止后端。shared-local-runtime的跨Host保活要求并未因此降低。tasks最终说明、design文首与交付文档均表明调查关闭但未修复；本轮不重新开启任务、进程实验或Host重启。不把已关闭调查写成全面兼容通过。

**产物集合继续待核实。** 主视频及Mini尾帧局部证据已存在；必需集合、跨模型适用性、链接期限/刷新/续传仍未知。代码的partial/unverified分支与文档一致，任务完成不等于供应商全集已获证。

本轮实际执行：OpenSpec strict validate通过，Ruff check通过，Ruff format --check通过（160 files）。文档变更后执行git diff --check。未重跑业务测试、构建或实际Host/供应商验收；既往21项测试仅作历史证据。无临时安装、状态目录、观察器或Host配置新增，资源清单无需新增条目。

最终评估：重点范围未发现新增CRITICAL，过时进度警告关闭；保留上述1项已知WARNING，0项SUGGESTION。完整Spec Coverage、逐条Requirement Implementation Mapping、全量Scenario Coverage及全部Design Adherence未重新验证；本轮不能替代全量符合性审计或宣称归档就绪。业务主规范未同步、change未归档，未调用真实供应商、提交或推送Git。

## 验收进度文档同步（2026-11-14）

按用户授权修订proposal、design、README、MANUAL、delivery-evidence及remaining-work中的当前验收状态：tasks维持71/71；13.1干净Windows安装、13.3实际Host主视频交付及13.4代表性最小矩阵按完成判断已有证据。早期实施说明和旧任务表明确标为历史快照，收费计数引用账本，不沿用旧8/10或剩余任务数作为当前值。

上轮WARNING 2（过时验收进度）经本次文档同步处理；WARNING 1仍作为已关闭调查的已知Job生命周期兼容性限制保留，不重开、不宣称修复、不降低原规范。完整产物集合及跨模型适用性继续待核实，局部尾帧证据不扩张为全集保证。未改变spec需求、任务勾选或实现代码。

本轮为纯文档检查：OpenSpec严格校验、git diff --check、修改文档新增本地链接存在性和71/71任务计数核对。未运行业务测试或构建，不复用旧测试作为本轮通过；无新测试安装/缓存/Host配置或观察器，资源清单原已清理状态保持，无新增清理对象。业务主规范未同步、change未归档，无供应商调用、提交或推送。

## 再次 OpenSpec 验证（2026-11-14，诊断关闭后）

使用 openspec-verify-change，复核当前 repo-local/spec-driven change。status 与 instructions apply 返回71/71完成、0未完成；这只是任务登记结果，不代表全部规范无条件满足。本轮只做静态复核及检查，不重开 Job 排查，不运行 Host 重启或供应商调用。

| 维度 | 本轮结论 |
| --- | --- |
| 完整性 | 71项任务均勾选；八项能力有实现及测试证据。规划文件已读取，但一次批量输出发生截断，未完成所有需求/场景逐条无遗漏审计，Spec Coverage 为部分验证。 |
| 正确性 | 重点核对产物集合保守分支、原状态/统一状态与已关闭Job限制；其他需求逐条实现映射、所有场景覆盖未重新验证。本轮不重跑业务测试，不将上一轮21项测试写成本轮通过。 |
| 一致性 | 最新tasks收尾、交付汇总与最终诊断结论一致；设计的跨Host保活要求仍存在已知兼容性差距。规划和历史记录存在过时验收表述，不能宣布所有文档完全一致。 |

### WARNING（2项）

1. **已关闭的Job生命周期限制仍是规范/设计差距。** shared-local-runtime的“强制结束Host”“跨Host接续”和design隐藏启动要求不能由71/71或关闭调查证明完全满足。上一轮启动器自身Job对照已复现后端可随启动器终止；历史Codex的最初终止调用者未取证。用户已明确关闭调查，本轮不重开、不新增调查任务、不触发重启；交付时必须继续携带这一限制，不宣称已修复或任意Host兼容。
2. **部分规划正文的验收进度过时。** proposal“现有能力与技术约束”“MCP SDK组合”仍写干净Windows及实际Host待验收，末段仍写实际Host未完成，与tasks的13.1/13.3完成及最新delivery-evidence冲突。后续文档修订应将这些段落明确标为历史快照或引用当前汇总，同时保留Job限制；本次验证仅登记，不擅自修改已批准范围。

### 产物集合：继续待核实，不是新增缺陷

compatibility_adapter保持complete=False；artifacts/queries保留ARTIFACT_SET_UNVERIFIED，主视频已下载或复制不等于整个必需集合ready。Mini尾帧已有局部真实证据，但必需性、全模型适用性、完整集合、链接期限/刷新/续传继续未知。tests/test_main_video_delivery.py已有partial与重启分支。本轮检查代码与记录一致，未请求新的上游样例、未新增真实验证；不得把尾帧一概写成从未实测，也不得把局部证据扩张为全集保证。

### 检查与最终评估

本轮实际执行Ruff check、Ruff format --check及OpenSpec strict validate；结果见本轮工具输出。第一次组合搜索用了PowerShell不支持的花括号路径，解析失败、后续命令未执行，改为目录搜索后重新执行。没有新增测试安装、状态目录、观察器或Host配置，沿用上轮资源清单的已清理状态；无清理新增对象。

重点检查未发现新增CRITICAL；2项WARNING，0项SUGGESTION。完整需求覆盖、逐条实现映射、全部场景覆盖及完整设计遵循仍为部分验证/未验证，不能给出“全部一致”或“已具备归档条件”的结论。任务勾选维持71/71，Job调查保持关闭；业务主规范未同步，未归档、提交或推送Git。

## 最后一轮终止机制核查与关闭决定（2026-11-14）

**状态：按用户要求结束这条诊断，不再安排实际 Host 反复重启。已复现后端启动器自身 Job 的终止机制；历史 Codex 退出时最初由谁、用什么方式结束启动器仍未直接取证。本结论是诊断关闭，不是生命周期兼容性修复或全场景验收通过。** 下方各轮“等待重启／待进一步诊断”均为历史过程，不再作为待执行操作。

### 本轮控制实验

新增 `tests/test_runtime_launcher_diagnostic.py`，使用现有 local 配置隔离夹具、占位密钥、独立状态目录和当前发行启动函数 `launch_hidden`；无 Host 配置改动，无供应商调用。用 starting/discovery 的启动标识、PID 和创建时间核对专用启动器与真实后端，逐句柄核验启动器持有的 Job，绝不按被隐藏的内核对象地址分组。只强制结束本测试创建并持有进程句柄的启动器，其他 Host 不受影响。

三组均发现启动器持有且包含后端的具体 Job，flags=0x3000（KILL_ON_JOB_CLOSE、SILENT_BREAKAWAY_OK），启动器自身不属于该具体 Job。首次成功运行与格式调整后的回归运行结果一致；以下为回归中的实际记录，时间为 UTC：

| 条件 | 启动器 → 后端 PID | 实际结果 |
| --- | --- | --- |
| 无额外 Job 句柄，保留有效 RPC 客户端，结束启动器 | 16328 → 34008 | 后端退出，退出码 0，退出时间 07:29:27.258，所有权锁可重新取得。 |
| 保持额外 Job 句柄，结束启动器 | 32512 → 26940 | 后端仍存活，原客户端成功查询同 PID、1 个租约；释放额外句柄后后端退出，退出码 0，时间 07:29:28.452，所有权锁释放。 |
| 保持额外 Job 句柄，结束启动器，再主动断开最后客户端 | 31348 → 36200 | 后端先仍可查询，随后按配置的无租约宽限期退出；退出码 0，时间 07:29:31.125，此时额外句柄仍有效，所有权锁释放。 |

这证明本机虚拟环境启动器消失可以通过自己的 Job 终止真实后端，而且 **退出码 0 不能证明后端执行了正常收尾**。它与上一轮“共同外层 Job 的额外句柄仍持有，后端仍退出”的结果相容。结合实际 Codex 中已确认的共同外层 Job 和启动器内层 Job，最有依据的解释是启动器被结束后内层 Job 句柄关闭，连带结束后端；历史启动器的精确退出/句柄关闭与调用者缺失，故保留为强证据支持的解释，不声称已经捕获历史完整因果链。

Windows 对带 KILL_ON_JOB_CLOSE 标志的 Job 最后句柄关闭行为，以及嵌套 Job 的影响，参考 [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)。本机结论主要依据上述对照实验，不把文档机制当成历史调用证据。

### 其他退出机制代码复核

- `runtime.py:launch_hidden` 唯一显式 TerminateProcess 路径是发布 starting.json 失败后结束尚未恢复执行的新启动器；它不能解释已发布 RPC、已接收租约的后端退出。
- `frontend.py` 关闭路径只关闭 RPC 客户端；`rpc.py` 的 finally 释放对应租约。`leases.py` 与 `serve_until_idle` 在最后租约消失后按宽限期/有限收尾退出，仍有有效租约时不会因此退出。上述第三组与既有生命周期测试覆盖正常退出路径。
- `run_backend` 等待服务循环或后台生命周期先结束，未处理异常会进入 finally 清理；`Lifecycle.run` 在存储故障保护下停止新操作，非预期异常仍可上传。`cli.py` 捕获普通运行异常返回 2，正常返回 0。异常退出路径存在，但没有历史错误证据能把此前退出归因于它；不能用退出码单独判别 Job 终止。
- `ownership.py` 只核验旧进程退出与独占锁，不会强杀旧实例。源码检索未发现后台自杀计时器、os._exit 或其他 TerminateProcess/TerminateJobObject 调用。
- 操作系统、Host 显式结束进程/Job、未访问的其他 Job、控制台或系统关机等外部机制没有逐项实际触发。本轮不安装系统级追踪、不关闭当前 Host，也不把未取证的外部原因全部排除。

### 影响与结束边界

本机被 Host 约束的启动器可能使后端未经过宽限期即退出，甚至在其他客户端仍持有租约时中断连接。这是共享后端生命周期兼容性限制，不将其改写成规范允许的正常退出；后续接入仍依赖旧实例退出确认、唯一所有权锁及持久化恢复，结果不明提交不应自动重放。现有恢复证据不等于不存在中断风险。

本轮不修改生产启动策略，不以长时间持有 Job 句柄作为修复，不减少既有规范要求。按用户授权关闭历史 PID／退出原因调查；未来只有新的业务故障或明确的兼容性修复请求才重新开启。完整产物集合仍独立待核实，业务主规范未同步、change 未归档。

### 实际检查与清理

- 首次新探针3项均因 pywin32 不接受 CreateJobObject 的 None 名称失败，尚未进入强制退出比较；finally 已关闭客户端并等待专用进程退出。改为唯一命名自测 Job 后，3 passed in 5.09s。首次 Ruff 发现两行过长及格式问题，格式修正后重跑。
- `uv run --frozen pytest -q -s tests/test_runtime_launcher_diagnostic.py tests/test_runtime_lifecycle_diagnostic.py tests/test_runtime.py tests/test_leases.py tests/test_ownership.py tests/test_frontend_reconnect.py tests/test_runtime_recovery.py --basetemp .cache/final-job-diagnosis-20261114/regression`：**21 passed in 38.98s，退出0**。未运行全量套件，也未构建新的发行包；生产源码未修改。
- `uv run --frozen ruff check .`、`uv run --frozen ruff format --check .`（160 files）、OpenSpec strict validate 及 `git diff --check` 均通过。
- 内容证据 SHA256：`.venv/Scripts/python.exe` = `3b5cc4150dc98800ee46b09034187bb2d8ba3c8ea3368d3a46e9bb42876b58db`；`runtime.py` = `194a7338666f50802febdcdcbf68af6c0a1c92bceb102d5f9b97f9602c1044da`；新增诊断测试 = `85af6512770c91d8169027720464f61f845413ccf3653437ef10d43171022cfb`。测试通过不能仅按 Git HEAD 复用，工作区仍有其他未提交内容。
- 清理前核对30条 starting/discovery 进程身份均已退出，旧四项 Codex 诊断配置均不存在；未发现命令行指向本轮及旧诊断目录的 Python 进程。本轮没有创建 Host 配置备份或常驻观察器。
- 付费主视频原件与副本摘要均仍为 `28ca7bc7bb0c5f25eb011836280d2600f506bf14716c7d4df13c50134abb64c1`，原任务状态保留。本轮仅删除专用测试目录，最终复扫状态见资源清单。

## 后端 Job 持有者逐句柄复核准备（2026-11-14）

在本机创建两个不同的命名 Job 后检查系统扩展句柄表，发现两者内核对象标识均不可用；此前按该字段分组会错误合并对象，原 Codex 句柄持有者结论已撤回。新探针逐句柄复制、核验目标进程是否属于该具体 Job，并立即关闭复制句柄，不记录内核地址或无关句柄数据。首次自测因旧分组方式未找到已知持有者而失败；修正后用命名 Job 和专用子进程自测通过，206 个 Job 句柄中 115 个不可访问，无法据此排除未知持有者或 Job。独立 local 服务 `seedance-job-owner`、受保护配置备份与只读进程观察器已准备，等待 Host 重启。此时尚未观察实际后端的最后 Job 句柄关闭，不能断言根因。

实际 Codex 运行中逐句柄检查两次一致：后端 PID 5020、前端 PID 42748，local、2 个租约。扫描 212 个 Job 句柄，其中 115 个无法访问；可访问结果中，codex PID 27988 持有一个 flags=0x2000（KILL_ON_JOB_CLOSE）的 Job 句柄，后端 5020、其启动器 5720、前端 42748、前端启动器 22044 均为该具体 Job 成员；codex 27988 自身不是该 Job 成员。另发现后端启动器 5720 持有一个 flags=0x3000 的 Job 句柄，后端为其成员而上述前端及启动器不是。逐句柄结果证明本次前后端存在共同 Job，但无法排除其他不可访问句柄或证明最后句柄关闭。

为区分共同 Job 最后句柄关闭与其他终止机制，在用户授权的隔离实验中短暂复制 PID 27988 所持、经核验同时包含前端和后端的 0x2000 Job 句柄；独立持有器最长保留 120 秒并自动释放，记录持有期间后端是否退出及释放后状态。该复制会有意延长该 Job 句柄寿命，只针对隔离测试进程；观察器仍仅持有进程句柄。等待用户退出 Host，后续记录实际结果并清理。

持有实验结果（2026-11-14 UTC）：持有器自 07:22:37.630 起保留共同 Job 的额外句柄；用户退出 Codex 后，后端 5020 于 07:23:28.247 退出、退出码 0，此时句柄仍在持有。持有器于约 07:24:37.709 自动释放，释放前后后端均已退出。独立观察器按 PID 和创建时间确认相同退出。因额外句柄在后端退出时仍有效，本次退出不能由该共同 Job 的最后句柄关闭直接触发；不排除其他 Job（包括启动器持有的后端 Job）、显式终止或其他原因。探针未记录前端精确退出时间，也无法判断不可访问句柄的关闭情况。

## Codex Job 句柄持有者排查准备（2026-11-14）

**勘误（后续自测）：** 下方“一个可查询 Job”及其完整持有者列表不能成立。原探针按系统句柄表的内核对象字段分组；本机对两个已知不同 Job 的自测显示该字段均被隐藏，多个 Job 可能被错误合并。下文持有者集合及其与查询结果的对应关系均撤回；前端/后端进程链、退出时间以及独立的 `QueryInformationJobObject(NULL, ...)` 观察不受此勘误影响。后续使用逐句柄查询，并保留访问不足的限制。

新增隔离 local 服务 `seedance-job-handles`，独立源码和状态目录，Codex 配置备份受保护。只读探针通过系统句柄表筛选指定测试进程及祖先的 Job 句柄，临时复制可访问句柄，查询关联进程与限制后立即关闭；不记录内核对象地址、不遍历其他进程的句柄内容。自测创建命名 Job 并将专用子进程加入，成功识别持有者及成员；不可访问句柄和未选进程不能据此排除。独立观察器只持有进程句柄，记录后端生灭，最多运行一小时。等待 Codex 重启并连接后检查；实验结束撤销临时服务并清理。

实际 Host 连接时：服务 local、后端 PID 7000、1 租约；进程链为后端 7000 ← 启动器 17152 ← 前端 42988 ← 启动器 30976 ← codex 34008 ← ChatGPT 43856。对上述进程及同服务的 12660/28456、父级 9764 执行一次短时句柄探测，识别到一个可查询 Job，flags 0x3c00；在所选进程中持有该 Job 句柄的是 12660、17152、30976、34008、43856，其中成员为 34008 与 43856，所选前端 42988、后端 7000 及其余所选进程均不是该具体 Job 的成员。探针不持续持有复制的句柄；结果不覆盖不可访问或未选进程持有的句柄，也不能排除其他共同外层 Job，尚不能证明后端终止原因。观察器记录此前后端 40068、34224 分别退出后才观察到后续实例；当前后端存活。等待退出观察及清理。

临时配置撤销后，观察器记录后端 7000 于 07:16:44.334 UTC 退出，退出码 0；复扫测试前端和后端均不存在。观察器未持有前端句柄，不能据此比较前后端精确退出时间；未监测 Job 最后句柄关闭，因此关闭行为、未访问的 Job 持有者及历史共同外层 Job 仍未核实。

## 实际 Host Job 归属排查准备（2026-11-14）

针对 Codex 增加临时 `seedance-job-diagnosis`，使用独立源码副本、local 模式、占位密钥和独立状态目录；保存受保护配置备份。测试副本内的探针按进程记录自身 Job 的限制标志及可查询成员 PID，独立观察器记录进程创建/退出与退出码，不加入租约，一小时后停止。自测 PID 19900 可查询自身 Job flags 0x3000 和成员列表，观察器捕获正常退出；该自测不代表 Codex 实际 Job 归属。等待用户重启 Host 后取得实际前端和后端记录；实验结束撤销测试条目并清理资源。

实际 Codex 重启后：前端 PID 39488 与后端 PID 44452 同时存活，调用临时服务得到后端 44452、local、2 个租约。两进程各自通过 `QueryInformationJobObject(NULL, ...)` 读取其当前关联 Job：成员列表分别仅含 39488 和 44452，flags 均为 0x3000，即 `SILENT_BREAKAWAY_OK` 与 `KILL_ON_JOB_CLOSE`。这说明各自查询到的当前 Job 成员集合不同，不排除共同外层 Job，也不能由该结果确定各 Job 最后句柄的持有者或证明它在退出时关闭。早期前端 23736 和后端 14324 分别于 07:10:00.566 / 07:10:00.533 UTC 以退出码 1 结束，后端 44452 于 07:10:02.995 创建，两代后端无进程寿命重叠。观察器继续运行，等待实际 Host 退出与清理。

临时配置撤销后，观察器记录前端 39488 与后端 44452 均于 07:10:37.384 UTC 退出，退出码均为 0；重启后这两个测试进程及测试配置不存在。两者同时退出与各自 Job 的 `KILL_ON_JOB_CLOSE` 标志相容，但未观察 Job 句柄关闭，不能据此断定因果；同一外层 Job 的归属也仍未验证。

## 后端生命周期隔离排查（2026-11-14）

实际 Host 后续排查已准备：独立源码副本与状态根、local 模式和占位密钥，Codex Desktop 增加临时 `seedance-lifecycle-observe` 配置，保存受保护配置备份；测试探针记录锁及租约变化，独立观察器保存进程创建、退出时间与退出码，不连接 RPC、不占租约，最多运行一小时。SDK 准备探针可获取 local 状态（PID 28028）；探针退出时该后端也随即退出，未观察到 owner.lock 正常释放，退出原因尚未确认，不能推断是 Host 重启原因。等待实际 Codex 启动连接后的阶段观察。完成后逐项撤销测试配置并按资源清单清理；不访问供应商。

实际 Codex 重启后的记录（UTC）：后端 2964 于 07:01:42.246 创建、07:01:46.335 退出码 1；后端 21260 于 07:01:48.874 创建、07:01:54.518 退出码 1；后端 26248 于 07:01:57.563 创建、07:02:01.102 退出码 1，三者进程寿命不重叠。每代均取得 owner.lock、接收租约；退出前未记录 lease_drop、draining 或 owner.lock 正常释放，排除将所记录退出直接归因于已观察的宽限期正常收尾。对应创建前端 27208、30768、42176 与各代后端退出时间分别相差 16ms、0ms、0ms，均退出码 1，提示关联但不证明操作系统终止原因。第一次工具查询在 26248 尚运行时返回 local、两个租约；其后发现该 PID 已退出。随后同一前端 15512 重连并启动后端 33436，查询成功且 1 租约；其进程链为 15512 → Python 虚拟环境启动器 41316 → 真实后端 33436，三者均处于某个 Job，但 `IsProcessInJob(..., None)` 不能证明它们处于同一个 Job，也不能证明 Job 导致退出。观察器继续运行，等待最后 Host 退出实验；以上均为 local 隔离副本，不等同历史 PID 具体根因。

用户完整退出 Codex 后，前端 15512 和后端 33436 均于 07:02:49.944 UTC 退出、退出码 0；之前仅见 1 个租约加入，未见 lease_drop、draining 或 owner.lock 正常释放，因而无法认定按宽限期正常收尾。随后用户重启：后端 41748 创建 07:04:54.215、退出 07:05:00.809，创建前端 11144 同时退出，二者退出码 1；后端 33624 创建 07:05:03.539，晚于前代退出，运行时取得 owner.lock。多个前端竞争 startup.lock，锁忙后重试，先后建立三条租约、其中两条退出后降至一条。此轮观察到的后端进程寿命不重叠；前端与后端同时退出仍只能说明关联，不足以确定 Job 或其他外部终止机制。

移除临时服务配置并再次完整退出 Codex 后，观察器记录前端 11212 与后端 33624 均于 07:05:49.236 UTC 退出，退出码 0；后端此前租约由 3 降至 1，最后一条未记录回收，也未记录 draining 或 owner.lock 正常释放。重新打开后测试服务配置不存在，测试前端和后端进程未再出现。此观察不证明退出的操作系统机制或历史实例变化原因；关联和未观察到正常收尾的事实保留待进一步诊断。

本机 Windows、local 模式、假密钥及独立状态目录；心跳 1 秒、租约 3 秒、宽限 1 秒、收尾 1 秒，不调用供应商。`tests/test_runtime_lifecycle_diagnostic.py` 保持 Windows 进程句柄，记录创建/退出时间并检查所有权锁；双客户端连接由 2 个租约降为 1 个，最后连接关闭后在宽限期内重连保持同一实例，最后退出后所有权锁释放。

第二轮实际轨迹（UTC）：PID 40972 创建 06:58:40.726、退出 06:58:42.855；PID 40436 创建 06:58:45.175、退出 06:58:47.391；PID 38784 创建 06:58:49.438、退出 06:58:51.321。每次下一进程创建时间均晚于上个进程的 Windows 退出时间；三个运行期所有权锁均被占用，进程结束后可独占取得。人为持有启动锁时两个并发连接均等待，释放后连接到同一实例。测试首次和扩展后的重跑各 1 passed（11.77s / 11.28s）。所有六个测试 PID 均已退出。

结论仅覆盖上述隔离场景：短连接在无人持有租约的宽限期后触发退出，后续连接会启动新 PID，这是已复现的合理机制；该现象可以解释类似 PID 变化，但不能证明历史真实 Host 的 PID 13936、40144、31928 是否按此退出，也不能凭本轮轨迹判断那次实例是否重叠。历史原始记录缺少退出时间和 Host 连接日志，根因仍未确定；没有执行实际 Host 重启或全量测试。

清理复核：专用目录内两个符号链接在清理前已确认目标位于该目录内；清理命令被中断，未取得完成输出。恢复后复扫确认专用目录不存在，六个测试 PID 均不存在；清理记录见 test-resource-register.json。付费任务库及原视频、交付副本未纳入清理范围。

## 修复复验（2026-11-14）

15.1 已修复：保留既有数据库归一化字段用于内部逻辑，MCP 快照按归一化状态校验原始值白名单并返回 `raw_status`，另以 `normalized_status` 返回规范化值；旧记录缺失或不匹配时原始值为 null，不猜测或输出任意内容。脱敏真实 SUCCESS fixture 和用户提供的 completed fixture 经 MCP 查询验证，另覆盖旧记录及敏感文本过滤。

15.2 已修复：能力查询按 8 个已局部实测视频模型及独立超分标注 `partial` 和 `observed_partial`；未实测模型及跨模型响应契约仍为 `unverified`。交付汇总改以实际 Host、干净 Windows 和账本最新证据为准。真实样本不代表全部参数、状态或产物；重启实例变化仍待定位。

本轮执行 `uv run --frozen pytest -q tests/test_preflight.py tests/test_tools.py tests/test_provider_response.py tests/test_compatibility_adapter.py --basetemp .cache/fix-status-151-152/tests`：120 passed in 20.12s。此前同组首次运行 120 passed in 27.76s；随后补充 completed 的 MCP 验证后重新运行。`uv run --frozen ruff check .` 与 `uv run --frozen ruff format --check .` 通过。未调用供应商，未执行完整套件；下述原验证问题及旧进度为发现当时的历史记录。

日期：2026-11-14。只验证，不归档、不提交或推送；没有新增供应商调用。依据现有proposal、八个delta spec、design、tasks和实现/测试及真实验收记录。OpenSpec schema为spec-driven；验证发现缺陷前69/69，登记15.1和15.2后69/71。

## 结论与范围

| 维度 | 结果 |
| --- | --- |
| 完整性 | 69/71任务完成；新增15.1、15.2未完成。八份spec共83条需求、190个场景；按能力及重点链路检查，未完成逐条需求/场景与测试一一映射。 |
| 正确性 | 发现原始状态查询不符合规范；能力查询与当前证据不一致。未知产物集合的保守分支及已记录真实任务状态核对一致。所有190个场景逐一覆盖未验证。 |
| 一致性 | 核查共享后端锁、重连、配置/网络及产物分层的重点设计；历史真实Host重启实例变化未定位，无法证明当次实例寿命无重叠或根因。未逐项核实全部design细化决策。 |

## 问题

1. **必须修复：原始状态丢失于查询。** spec agent-task-observability/spec.md:110-112要求区分原始SUCCESS/completed。task_state.py:246以归一化状态写raw_status，原始provider_status另存facts:254；queries.py:81直接输出前者而不输出facts.provider_status。真实验收任务持久化最后一条为raw_status=completed、provider_status=SUCCESS，实际查询只显示completed。15.1要求修复并增加真实响应MCP回放覆盖。
2. **应修复：能力与汇总证据过时。** preflight.py:15-16、45将SUCCESS/实扣响应标记unverified并对任何模型返回real_provider_validation=not_performed，而provider-api-contracts/spec.md及contract-review-closure.md已有对应局部真实证据。不能将局部样例推广到所有模型，但也不应否认已发生的真实验证。delivery-evidence.md:3仍称13.1/13.3未完成、账本余5，与最新任务和账本不一致。15.2要求按范围表达并更新汇总。
3. **待核实：重启实例变化。** host-delivery-acceptance-plan.md:43记录旧后端退出后PID13936、40144、31928先后出现，前两次原因未知。runtime.py:228-265和ownership.py的启动/所有权锁及退出身份核验存在，隔离测试覆盖并发与恢复；但该次记录没有足够生命周期证据确定前三实例无重叠或根因。建议在专用非付费环境增加脱敏生命周期诊断并复现，不自动强杀。

## 重点证据

- 产物：compatibility_adapter.py返回complete=False；artifacts.py:73-78和queries.py:50保留ARTIFACT_SET_UNVERIFIED，tests/test_main_video_delivery.py及test_main_video_protocol.py覆盖partial、重启与素材保留。保留的真实任务库只读查询为succeeded/partial/version9、attention含ARTIFACT_SET_UNVERIFIED，提交意图1次；原视频与DSH副本各1641276字节、SHA256 28ca7bc7bb0c5f25eb011836280d2600f506bf14716c7d4df13c50134abb64c1。集合完整性仍待供应商证据，不视为已完成。
- 实际Host：Codex提交、DSH找回并复制主视频；实扣0.8028¥，用户再次重启后旧后端退出和任务恢复已记录。Job具体句柄及强制退出证据分别记录，不能证明所有共同外层Job或同一次关闭Job句柄行为。

## 实际执行的检查

- 首次 `uv run --frozen pytest -q --basetemp .cache/verify-change-20261114/tests`：父目录缺失，553项夹具初始化错误，未进入业务断言；退出1。创建专用父目录后重跑同一命令：553 passed in 532.01s，退出0。
- `uv run --frozen ruff check .`：通过；`uv run --frozen ruff format --check .`：157 files already formatted。
- `uv build --offline --out-dir .cache/verify-change-20261114/build`：sdist及wheel构建成功；`uv run --frozen zhenzhen-seedance-video --version`：0.1.0.dev0。
- `openspec validate add-local-video-generation-service --type change --strict`：通过；`git diff --check`：通过。
- 本轮未重新实测真实供应商/收费操作、全部模型、全部Job对象、人工视频质量；亦未对83条需求与190个场景逐项完成测试映射。未对业务主规范执行同步或归档。

验证环境为本机Windows及隔离测试，资源清理状态见test-resource-register.json。

清理：全量测试结束且专用进程退出后，核验321处pytest符号链接及其目标均在本轮验证目录内，逐一解除后复扫无重解析点，删除专用测试与构建目录；保留付费任务库及两份视频。先前af30659目录清理异常仍独立保留为未能确认目标影响。
## 2026-11-14 手册全面核对及本地协议检查

- 对照 `openspec/specs/manual-writing/spec.md` 和 `guide.md` 核对 MANUAL 十节、固定版本、安装与不覆盖配置、工具清单、DSH 三 profile 适用范围、升级回滚及验证边界；更新工具手册中过时的实际 Host 和 SUCCESS／费用响应表述。23 项工具名称与 `frontend.py` 一致，完整产物集合仍待核实，已关闭的 Job 生命周期调查不重开。
- 本机静态检查：5 个 MANUAL PowerShell 代码块通过 PowerShell 语法解析；Claude JSON 和 Codex TOML 均可解析且命令参数相同；使用本机 DSH desktop 的 yaml 解析库检查 YAML 和字段、参数，核对插件文档的 stdio 格式；本地文档链接路径存在。语法检查不等于目标 Host 连接通过，DSH web／multica 仍未实测。
- `uv run --frozen pytest -q tests/test_protocol_probe.py --basetemp .cache/manual-audit-20261114/tests`：2 passed；添加资源模板发现后首次复测为 1 failed、1 passed，原因是 SDK Python 字段使用 `resource_templates`，已修正；最终同一测试使用 `tests-final` 目录复跑 2 passed，退出码 0。`ruff check` 和 `ruff format --check` 对两个检查脚本文件通过。
- `uv build --offline --out-dir .cache/manual-audit-20261114/build` 退出码 0，静态检查 sdist 与 wheel 均包含 `protocol_probe.py`。该模块处于当前未发布工作区，发布标签 `v0.1.0.dev0` 不含此模块；本次没有对新构建包执行干净环境安装或实际 Host 联调。
- 本次仅 local 模式和合成配置，不调用供应商、不修改 Host 配置；未重新运行全量测试，不将历史验证扩展到不同构建输入。临时资源及清理状态见 `test-resource-register.json`。

## 2026-11-14 DSH 代理旁路示例修订

- `MANUAL.md` 的 DSH stdio 示例补充 `NO_PROXY` 和 `no_proxy`，说明合并既有旁路项及其他环境变量，并区分 MCP 供应商网络策略和 Host 子进程兼容设置。
- 使用本机 DSH desktop 自带的 `yaml` 包解析手册中的 YAML 块，检查插件名、服务名、stdio、命令、参数数量及两个旁路值，退出码 0；`git diff --check` 通过。检查在内存中完成，未产生专用测试资源。
- 此次未修改 Host 配置、启动实际 Host 或调用供应商；新增旁路值在 Windows 上的实际传递和修复效果未验证。既有 Desktop 验收不覆盖本次示例变更，web／multica 仍未实测。

## 2026-11-14 DSH MCP 插件 local 环境旁路验证

- 使用本机 DSH 0.2.1-rc.5 的 `@deepseek-ai/dsh-mcp-client` 实际插件及其 stdio 启动链，隔离插件宿主用内存工具注册表，配置取自 MANUAL 的 YAML，仅替换隔离安装路径并设置测试宿主参数。隔离源码副本的入口只记录旁路变量，使用占位密钥、独立 `LOCALAPPDATA` 和 local 模式；未更改正式安装或任何 Host 配置。
- 人为给父进程设置含 `[::1]` 的旁路值：空 `env` 对照组中子进程仍读到该项；手册覆盖组读取到 `localhost,127.0.0.1,::1`；自定义旁路组在两个值中附加 `internal.example.invalid` 后，子进程也读到该项。Windows 子进程实际枚举出一个 `NO_PROXY` 条目，但 Python 的大小写两种查找均得到相同预期值。三组均注册 23 个工具并成功调用 `get_service_status`，结果为 `execution_mode=local`、`dispatch_allowed=false`、`storage_fault=false`。
- 该检查覆盖插件实际启动与工具注册，不是完整 DSH Desktop 图形宿主联调；对照组在本项目中也能启动，未复现 HTTP 客户端报错，不能据此断言此变通修复所有版本。未调用供应商；完整产物集合仍待核实，已关闭的 Job 调查未重开。隔离目录与进程清理状态见资源清单。

## 2026-11-14 实际 DSH Desktop 旁路验收

- 建立独立源码及依赖安装、local 模式占位密钥和隔离状态目录；SDK stdio 预检输出 `protocol=2025-11-25 tools=23 resources=0 templates=0 prompts=0 local=ok`，未调用供应商。隔离入口仅记录 NO_PROXY 变量及自身 PID，不记录其他环境变量。
- 经用户确认，在 Desktop 的 `cordis.patch.yml` 追加 `seedance-proxy-acceptance` 临时服务项；修改前已备份并保留原 ACL，修改后解析 YAML、确认仅一个测试服务且原始内容保留。
- 用户重启 Desktop 后实际调用状态和能力工具：后端 PID 32200、local、派发关闭、存储正常，发现 Seedance 26 个模型及独立超分。隔离入口 PID 41752 记录到一个 `NO_PROXY` 环境条目，大小写两种读取均为 `localhost,127.0.0.1,::1`。Desktop 重写配置换行为 LF，按唯一标记仅移除测试项并保留当前其余内容。用户正常退出后，两个记录的 PID、隔离路径相关进程均不存在，Desktop YAML 解析通过且临时项不存在。未调用供应商；最终资源清理状态见资源清单。

## 2026-11-14 手册及 DSH 验收一致性复核

- 对照手册主规范、指南与上述证据，说明实际 Desktop 检查采用临时服务名、隔离路径、额外环境变量及入口探针；自定义旁路仅在插件宿主验证，未复现 HTTP 错误。web／multica 仍未实测。
- 核对当前协议检查源码与手册输出、120 秒时限、local 限制一致；`git cat-file -e v0.1.0.dev0:src/zhenzhen_seedance_video/protocol_probe.py` 退出 128，确认该发布标签不包含脚本。当前脚本仍是未发布工作区内容，不能将后续离线构建等同于正式 Release。
- 5 个 PowerShell 代码块语法解析通过，JSON／TOML 命令参数一致，DSH YAML 及两个代理旁路值解析通过；十节标题和本地链接路径存在。仅静态文档检查，未重新运行实际 Host、脚本测试或供应商调用；未修改 Host 配置。CLI／Shell 组合及跨版本升级仍未验收，完整产物集合仍待核实，已关闭的 Job 生命周期调查未重开。

## 2026-11-14 协议检查脚本发行包安装验证

- `uv build --offline` 基于当前未提交工作区构建 sdist 与 wheel；检查两者均包含 `protocol_probe.py`，sdist 包含 MANUAL。源码包 SHA-256 `fdf06e78e596cbc6c943ef9bc18ac9e38336c79eedf446f29bfdf323b6a811d7`，wheel SHA-256 `58b30e9a0158b819c1703d8d91a235bec8eee7bf732e441e03812b3685afa319`。这些是本地构建证据，不是已发布资产，尽管版本号相同。
- 独立目录解压 sdist，使用 `uv sync --offline --frozen --no-dev` 安装，配置 local 及占位密钥，从无关工作目录以手册的 `uv --directory ... run --no-sync python -m zhenzhen_seedance_video.protocol_probe` 执行，退出码 0，输出 `protocol=2025-11-25 tools=23 resources=0 templates=0 prompts=0 local=ok`。使用现有 uv 缓存，未证明空缓存离线安装；wheel 未做独立安装运行验证，未使用真实供应商或 Host。
- 包内容检查首次将构建工具生成的 `.gitignore` 误当作归档而报错；改为仅匹配 `.whl` 和 `.tar.gz` 后复查通过。隔离测试资源的清理状态见资源清单。

## 2026-11-14 协议检查脚本交付审查

- 对照手册主规范与指南检查 local 限制、隔离状态、失败脱敏、清理与发行边界；修正子进程 stderr 透传及清理失败前提前输出成功的问题，并要求派发状态明确为 false。手册说明异步超时后的收尾可能延长实际耗时。
- `uv run --frozen pytest -q tests/test_protocol_probe.py --basetemp .cache/probe-review-20261114/tests`：3 passed，包含 local 成功、provider 拒绝和清理失败脱敏；全仓 Ruff check 与 format check 通过（170 个文件），`uv build --offline` 成功。将此次构建的 sdist 在独立目录用现有缓存离线冻结安装，从无关工作目录运行手册协议命令，退出 0，输出协议 2025-11-25、23 工具和 local=ok。
- 脚本及测试仍未跟踪，须纳入下一版本的提交及发行候选后才能交付；当前发布标签仍不包含该脚本。未重新运行全量测试、真实供应商或实际 Host；wheel 独立安装运行和空缓存离线安装仍未验证。清理状态见资源清单。

## 2026-11-14 wheel 安装与全量隔离复验

- 基于当前未发布工作区离线构建 sdist 与 wheel；用 sdist 和锁文件在隔离虚拟环境执行 `uv sync --offline --frozen --no-dev` 准备依赖，卸载源码安装后单独以 `uv pip install --offline --no-deps` 安装 wheel。从无关工作目录确认模块加载路径在该虚拟环境 `site-packages`，设置 local 和占位密钥后运行 `python -m zhenzhen_seedance_video.protocol_probe`，退出 0：协议 2025-11-25、23 工具、资源及提示词均为空、local=ok。wheel SHA-256 `27b61d030615419bfcc51671f960d3d490297be923b37229c067ef747089767a`；更新手册后再次构建，wheel 摘要一致。
- 首次尝试使用 `uv export --frozen` 的带哈希依赖文件在新环境直接离线安装失败：当前缓存没有该安装方式所需的 pydantic-core 和 rpds-py 归档；随后使用上述冻结同步成功。测试依赖现有缓存，不代表空缓存或仅凭 wheel 完成离线安装。
- `uv run --frozen pytest -q --basetemp .cache/wheel-full-20261114/tests`：561 passed，耗时 557.20 秒；`uv run --frozen ruff check .` 和 `uv run --frozen ruff format --check .` 通过（170 个文件）；`uv build --offline` 成功。未调用真实供应商，未测试实际 Host 或发布版本；脚本和测试仍待纳入版本控制及下一版本。完整产物集合待核实，Job 生命周期调查保持关闭。隔离资源清理状态见资源清单。
