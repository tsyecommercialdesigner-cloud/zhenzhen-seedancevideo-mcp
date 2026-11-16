# 验证与资源记录

- 资源清单：`.cache/clarify-artifact-apply-20261116` 用于本变更未发布工作区的隔离测试及构建，归本任务、由 Agent 使用；测试完成后检查 296 个 discovery 文件，未发现仍存活的匹配后端身份（其中 3 个为 RPC 测试故意写入的非 JSON 文件）；核对并逐个移除 1333 个指向目录内部的 pytest 链接，删除专属目录并复扫确认不存在。旧测试目录和付费产物不属于本任务，保留；持久清单见 `docs/test-resource-register.json`。
- 根目录 `dist` 中本轮 `uv build --offline` 生成了同名 `0.1.0.dev2` 源码包和 wheel；这些是未发布工作区构建，不等同已发布资产。因无法确认同路径之前的本地文件归属，暂保留并记录，后续由用户或 Agent 在确认来源后清理；发布时不可把它们当作既有 Release 资产。
- 组合测试 `tests4` 的源码安装夹具遗漏显式 local，默认 provider 导致一个合成任务产生 `submit` 的 `intent`、`effect_started=1`；本地记录远端为 unknown，无法证明请求是否到达真实端点。仅使用合成占位密钥，未重试；发现后进程已退出，修复夹具显式 local。此次可能的真实端点访问违反本轮不调用供应商的要求，不能记录为供应商验收。
- 未修改 Host 配置；实际 Host 对新 Schema 的展示、供应商完整产物集合仍待核实。

## 本次隔离验证

- Windows，Python 3.12.14、MCP SDK 2.3.0；所有合成适配器测试使用任务专属隔离状态与本地模拟服务。测试默认显式 local，子进程阻断外部地址；provider 仅用于合成适配器测试。
- 第一轮全量 `uv run --frozen pytest -q --basetemp .cache/clarify-artifact-apply-20261116/full`：620 passed、2 failed。失败分别为任务找回的旧等值断言及最后租约退出与自动轮询竞争；前者改为校验原字段与新增状态，后者仅将 `NETWORK_WORK_PAUSED` 视为预期暂停，其他错误不吞掉。修复后关联的素材恢复及调度测试、实际 stdio 恢复专项通过。一次修订断言缩进错误造成测试收集失败，已修正并重测，不计为通过。
- 第二轮全量 `--basetemp .cache/clarify-artifact-apply-20261116/full-final`：623 passed、1 failed；失败为 `test_probe_isolates_provider_mode` 返回 `PROBE_FAILED: ExceptionGroup`，隔离后端随后已退出，未取得异常组内部原因。此用例之后单独复测一次及连续 8 次通过，不能据此认定原因已修复；本条偶发失败保留作为限制。
- 第三轮全量 `uv run --frozen pytest -q --basetemp .cache/clarify-artifact-apply-20261116/full-confirm`：625 passed，退出码 0，耗时 566.44 秒；子进程网络隔离测试在收集后新增，另行执行通过。
- 工具、安装与协议检查专项：18 passed；跨客户端托管素材、已发现产物就绪、找回和复制专项：1 passed；异常分类、空集合和多产物专项：2 passed；业务诊断及旧记录回退专项：7 passed；退出竞争修复与 stdio 重启专项：2 passed。素材分阶段恢复及退出竞争专项：4 passed（同次运行另有旧断言失败，随后修正通过）。
- 后续补充的子进程隔离测试分别验证供应商域名解析和外部直连 IP 均在发出网络请求前被阻断：1 passed。新增测试在第三轮全量开始后加入，已单独执行。
- `uv run --frozen ruff check .`、`uv run --frozen ruff format --check .` 和 `openspec validate clarify-artifact-status-and-diagnostics --type change --strict` 通过；`uv build --offline --out-dir .cache/clarify-artifact-apply-20261116/dist-current` 通过。最终资源清理记录在构建后更新，发行时须重新构建并验证当前内容。
- 对上述本地源码包和 wheel 各自创建隔离虚拟环境，用 `UV_OFFLINE=1` 执行 `scripts.release_control.verify_install`：二者安装和版本检查成功，协议检查均输出 `protocol=2025-11-25 tools=23 resources=0 templates=0 prompts=0 local=ok`。这不代表真实 Host 或供应商通过。
- Codex、Claude、DSH 示例经 TOML、JSON、YAML 解析检查；无实际 Host 配置改动。旧版本验收不能推广到此次更名和新字段。

## 2026-11-16 OpenSpec 验证

- 对照 proposal、三份 delta specs、design 和 22 项 tasks 检查代码与场景；`openspec validate clarify-artifact-status-and-diagnostics --type change --strict`、`uv run --frozen ruff check .` 和 `uv run --frozen ruff format --check .` 均通过。
- 在独立 `.cache/verify-clarify-20261116` 使用合成适配器执行产物、跨客户端与重启、工具诊断、默认模式、协议探针、网络隔离和停机竞争专项，共 47 passed，退出码 0；未复跑全量。历史全量 625 passed 不覆盖此轮新增的只读诊断复现。
- 本次验证资源：Windows 当前工作区、未发布工作区版本、Agent 使用，测试结束后检查 18 个 discovery 文件未发现仍存活的对应后端；核对并移除 41 个指向测试目录内部的链接，删除专属目录并复扫确认不存在。未触碰既有付费产物和先前保留的 dist 文件。
- **当时发现：未知异常可能泄露外层错误文本（后续已修复）。** 原 `_handler` 只根据大写下划线格式接受异常文本作为外层 error；合成 `RuntimeError('SYNTHETIC_SECRET_TOKEN')` 可得到外层原文、内层 `INTERNAL_ERROR`。当时重新打开 3.4；修复与验证见下节。
- 当时探针测试尚未直接建立现存后端及任务库哨兵，故重新打开 4.3；补充测试见下节。历史偶发 `ExceptionGroup` 仍未定位，不因本次通过而关闭。
- 实际 Host 对新名称和字段的展示、供应商完整产物集合及本变更真实供应商调用仍未验证；本轮未调用供应商、未修改 Host 配置。此前可能接触供应商端点的事故仍按上文保留，不作为验收证据。

## 未知异常与探针隔离修复

- 对外错误码使用静态集合和已有诊断目录；未知大写异常文本或伪造 code 不再直接输出。已声明的业务和参数错误码继续返回原标识。新增固定错误码必须更新静态集合。
- 协议探针哨兵测试建立独立真实 RPC 监听器、已有任务和事件、模拟 provider 安装配置；检查探针未连接监听器，发现记录、任务、事件和安装配置未变，且探针报告 local 模式。
- 隔离测试：工具、诊断、协议探针和网络隔离 24 passed；接收、产物、生产入口与交付 67 passed；最终诊断和哨兵专项 10 passed。首次运行因新集合的容器语法错误在收集阶段失败，已修正后重测。上述测试使用合成数据，未调用真实供应商或修改 Host 配置。
- 本轮四个 `.cache/clarify-fix-20261116-{b,c,d,e}` 专属目录已核对进程和重解析点，移除 113 个指向各自目录内部的测试链接后删除并复扫；资源清单已记录。未运行全量测试或构建；此前全量测试结果仅适用于此前工作区版本。
- 上述历史偶发 `ExceptionGroup` 根因仍未知，未因本轮通过而关闭；实际 Host 新名称／字段展示、供应商完整产物集合仍待核实。

## 可信错误码边界再次验证

- OpenSpec 状态与现有实现对照发现两个问题，以独立 Python 进程和合成异常只读复现，未调用供应商：`RuntimeError('TASK_NOT_FOUND')` 返回外层和诊断均为 `TASK_NOT_FOUND`，把未知异常误判为可信业务错误；`ValueError('INVALID_CURSOR')` 返回外层 `INVALID_CURSOR`、诊断 `INTERNAL_ERROR`，不满足已知业务错误码一致性。
- 当时静态集合只校验码值而不核实异常来源，部分码未被 `CATALOG` 映射；重新打开 3.4 并增加 3.5。后续修复及验证见下节。
- 协议探针哨兵测试创建隔离 RPC 监听器及任务库，核对未接入、任务与事件、发现记录和安装配置未变化；这是隔离环境证据，不扩大至实际 Host 或真实供应商。此前偶发 `ExceptionGroup` 仍未定位。
- 本轮 `uv run --frozen pytest -q tests/test_protocol_probe.py tests/test_diagnostics.py tests/test_tools.py::test_business_diagnostics_are_safe_and_actionable tests/test_tools.py::test_local_queries_provider_gate_and_sanitized_errors tests/test_test_isolation.py --basetemp .cache/verify-errors-20261116`：14 passed，退出码 0；`ruff check` 和 OpenSpec 严格校验通过。未复跑全量测试或构建。
- 本轮专属测试目录 `.cache/verify-errors-20261116` 已检查后端身份，未发现存活测试后端；核对并移除 14 个目录内测试链接，删除专属目录并复扫确认不存在。未调用供应商或修改 Host 配置；原有待核实项和先前可能触及供应商端点的记录保持不变。

## 异常来源与诊断一致性修复

- 使用内部异常的确切类型和静态码共同确定可信性；内置异常的业务拒绝使用专用子类，未知异常和伪造子类均安全回退。对已知公开码使用固定通用诊断，反查保持相同码；仅可信状态异常可附带任务快照。
- 首轮相关隔离测试 88 passed；扩展运行 31 passed；最终代码上诊断、伪造异常和版本冲突专项 11 passed。`ruff check`、格式检查和 OpenSpec 严格校验通过。本轮未复跑全量测试或构建；此前全量记录不能代表本轮代码。
- 资源清理：`.cache/clarify-trusted-20261116`、`-b`、`-c` 为本轮专属目录；检查没有存活的对应后端，核对并移除 117 个目录内链接后删除，复扫确认不存在。资源清单已更新。
- 测试使用本地隔离状态及合成数据，未调用供应商、未修改 Host 配置。此前协议探针偶发 `ExceptionGroup` 尚未定位；实际 Host 新字段和供应商完整产物集合仍待核实。

## 异常来源修复再次验证

- 类型与静态码联合检查、伪造子类和状态快照保护、公开码通用诊断及反查均有实现和专项测试。`uv run --frozen pytest -q tests/test_diagnostics.py tests/test_tools.py::test_business_diagnostics_are_safe_and_actionable tests/test_tools.py::test_local_queries_provider_gate_and_sanitized_errors tests/test_tools.py::test_duplicate_resume_and_conflict_over_protocol tests/test_protocol_probe.py --basetemp .cache/verify-trusted-20261116`：15 passed。`ruff check`、`ruff format --check` 和 OpenSpec 严格校验通过；未复跑全量测试或构建。
- 当时合成异常复现未知异常的 `__str__` 抛错时逃逸处理器：`getattr(error, 'code', str(error))` 的默认参数被提前求值。重新打开 3.5，后续修复见下节。
- 当时 `retry_material_cleanup` 的 `MATERIAL_CLEANUP_NOT_AUTHORIZED` 诊断错误地返回 `stage=query`，新增 3.6；后续修复见下节。
- 本轮没有调用真实供应商或修改 Host 配置。协议探针偶发 `ExceptionGroup` 仍未定位；实际 Host 新字段和供应商完整产物集合仍待核实。先前可能接触供应商端点的记录继续保留。
- 本轮专属目录 `.cache/verify-trusted-20261116` 已核对测试后端身份，未发现存活实例；核对并移除 15 个目录内测试链接，删除目录并复扫确认不存在。

## 异常提取与阶段修复

- 先判断确切异常类型，未知异常不读取其 code 或调用其 `__str__`；可信异常的码或字段访问出错时安全兜底。静态工具阶段映射区分接收、提交、查询、下载、清理，参数校验与存储故障优先映射。
- 隔离相关测试 96 passed；新增实际 MCP 清理拒绝、诊断反查和异常属性专项 13 passed；最终代码诊断、属性抛错和版本冲突专项 15 passed。首次两组测试在最后一轮细化前运行；本轮未重跑全量测试或构建。Ruff、格式检查和 OpenSpec 严格校验通过。
- 未调用供应商或修改 Host 配置；此前探针偶发 `ExceptionGroup` 仍未定位，实际 Host 新字段及供应商完整产物集合仍待核实。先前可能接触供应商端点的记录继续保留。
- 本轮专属 `.cache/clarify-stage-20261116`、`-b`、`-c` 已检查对应后端进程，核对并移除 107 个目录内链接，删除并复扫确认不存在；资源清单已更新。

## 异常阶段修复再次验证

- 专项隔离测试 `uv run --frozen pytest -q tests/test_diagnostics.py tests/test_tools.py::test_business_diagnostics_are_safe_and_actionable tests/test_tools.py::test_duplicate_resume_and_conflict_over_protocol tests/test_tools.py::test_local_queries_provider_gate_and_sanitized_errors --basetemp .cache/verify-stage-20261116`：15 passed。`ruff check`、`ruff format --check` 与 OpenSpec 严格校验通过；未复跑全量测试或构建。
- 未知异常的 code 属性和字符串转换抛错、可信异常 code 属性抛错均有安全兜底测试；清理错误经 MCP 和诊断反查返回 cleanup 阶段，版本冲突等既有测试通过。
- 当时发现 `PUBLIC_ERROR_CODES` 遗漏由常量或运行时转换产生的已知码，`STORAGE_CONSTRAINT` 和 `PROVIDER_EXECUTION_NOT_AUTHORIZED` 被处理器转为 `INTERNAL_ERROR`，故重新打开 3.5；修复和路径边界见下节。
- 本轮未调用供应商或修改 Host 配置；此前探针偶发 `ExceptionGroup` 仍未定位，实际 Host 新字段及供应商完整产物集合仍待核实。先前可能接触供应商端点的记录继续保留。
- 本轮 `.cache/verify-stage-20261116` 专属目录已检查后端身份，无存活实例；核对并移除 15 个目录内测试链接，删除目录并复扫确认不存在。

## 动态构造的可信错误码修复

- 检查可信异常构造中模块常量、条件表达式、异常转换、默认参数和返回值：补入供应商执行授权、SQLite 约束、数据库打开、锁、查询响应／超时及 HTTP 分类等固定码。参数错误到供应商错误的转换仍受原静态参数码约束；不将任意上游错误码加入白名单。新增的约束错误使用 storage 阶段，授权错误提供查询任务的安全动作。
- `tests/test_diagnostics.py`、`tests/test_tools.py`、`tests/test_storage.py`、`tests/test_production_entry.py`、`tests/test_scheduler.py`、`tests/test_provider_response.py` 隔离运行：112 passed；最终诊断与两项 MCP 专项 16 passed。SQLite 唯一约束经真实任务库和 MCP 工具处理器返回 `STORAGE_CONSTRAINT`，诊断及反查一致；供应商执行授权通过实际授权检查函数注入 MCP 处理器验证，未请求供应商。生产调度查询会自行捕获 ProviderFailure，此项不宣称原始码必然作为该调度工具的外层错误返回。
- 未知的合成供应商错误码仍回退为 `INTERNAL_ERROR`；已确认固定码的处理器和安全诊断一致。Ruff、格式检查和 OpenSpec 严格校验通过。本轮未重跑全量测试或构建；旧全量结果不代表本轮代码。
- 本轮未调用供应商或修改 Host 配置。此前协议探针偶发 `ExceptionGroup` 尚未定位，实际 Host 新字段和供应商完整产物集合仍待核实；历史可能接触供应商端点的记录继续保留。
- `.cache/clarify-codes-20261116`、`-b`、`-c` 专属测试目录已核对后端身份，无存活实例；核对并移除 120 个目录内测试链接，删除目录并复扫确认不存在，资源清单已更新。

## 动态可信错误码再次验证

- 对照 change 的 proposal、三份 specs、design 和 tasks；OpenSpec 跟踪为 24/24。对可信异常构造的字面量静态扫描未发现码表遗漏，并检查模块常量、条件表达式、错误转换和默认参数的既有覆盖；不能将静态扫描视为未来新增动态码自动通过的保证。
- `uv run --frozen pytest -q tests/test_diagnostics.py tests/test_tools.py::test_storage_constraint_through_mcp_and_diagnostic tests/test_tools.py::test_unapproved_provider_guard_through_mcp_handler tests/test_tools.py::test_business_diagnostics_are_safe_and_actionable tests/test_tools.py::test_duplicate_resume_and_conflict_over_protocol tests/test_storage.py tests/test_production_entry.py --basetemp .cache/verify-codes-20261116`：33 passed；`ruff check`、`ruff format --check` 和 OpenSpec 严格校验通过。本轮未运行全量测试或构建，既有全量证据不覆盖当前代码，发布候选须按实际内容验证。
- SQLite 约束经隔离任务库与 MCP 工具处理器、诊断反查覆盖；供应商授权检查经注入 MCP 处理器覆盖，不等于实际生产调度直接透传该错误码。未知供应商错误码安全回退；与既有业务码一致的诊断覆盖以测试范围为限。
- 测试目录 `.cache/verify-codes-20261116` 已核查后端身份、无存活实例；核对并移除 31 个目录内链接，删除并复扫确认不存在。未调用供应商、未修改 Host 配置；历史探针偶发 `ExceptionGroup` 仍未定位，实际 Host 新字段及完整产物集合仍待核实，先前可能接触供应商端点的记录继续保留。

## 2026-11-16 主规范同步与归档

- OpenSpec 状态确认 `spec-driven` 四项规划产物完成，CLI 统计 24/24 任务完成。逐项同步 `agent-task-observability`、`runtime-configuration` 和 `video-artifact-delivery` 三份主规范；比对确认各 delta 要求与场景完整、主规范标题及 Purpose 保留，未涉及的要求不变。
- 归档前 change 和三份主规范均经 `openspec validate ... --strict` 校验通过；归档至 `openspec/changes/archive/2026-11-16-clarify-artifact-status-and-diagnostics`，归档后 `openspec list --json` 未显示活动 change。`git diff --check` 通过。本轮仅核对文档与既有验证记录，未重新运行全量测试或构建。
- 历史协议探针偶发 `ExceptionGroup` 仍未定位；供应商完整产物集合及实际 Host 新字段／名称展示仍待核实。历史可能接触供应商端点的记录继续保留。本轮未调用供应商、修改 Host 配置或执行 Git 提交推送。

## 2026-11-16 dev3 发布候选本地复验

- 候选版本 `0.1.0.dev3`，Windows、Python 3.12.14、uv 0.12.9；`uv run --frozen pytest -q --tb=short --basetemp .cache/dev3-delivery-20261116/tests` 退出 0，637 passed，581.82 秒。首次尝试因 `--basetemp` 的父目录不存在而在夹具初始化阶段连续报错并中止；`-x` 复现 `FileNotFoundError`，创建专用父目录后完整重跑，结果如上。
- `uv run --frozen ruff check .`、`uv run --frozen ruff format --check .`（199 files）、`uv run --frozen zhenzhen-seedance-video --version`（0.1.0.dev3）通过；三项受影响主规范严格校验通过。`uv build --offline --out-dir .cache/dev3-delivery-20261116/dist` 构建源码包与 wheel 成功；检查源码包包含 dev3 安装及升级命令、排除私有配置与测试缓存，wheel 包含协议探针。该本地构建早于最终证据和资源清单收尾，不能当作最终发行资产。
- 隔离测试未调用真实供应商或修改 Host 配置，实际 Host 新字段／名称、供应商完整产物集合仍待核实；此前协议探针偶发 `ExceptionGroup` 的根因依然未定位。本地完整测试通过不代替远端 PR 门禁或发布候选验收。
- 本轮专用目录检查无匹配测试进程；核对并解除 387 个目标位于该目录内的测试链接后删除，复扫确认目录不存在。资源清单已更新。
- 测试收尾后再次离线构建 dev3 sdist 和 wheel，检查目标版本的两条手册命令、协议探针和私有文件排除通过；随后清理专用构建目录。发布候选 CI 仍须按最终提交构建并核验资产，不复用这次本地临时包。
