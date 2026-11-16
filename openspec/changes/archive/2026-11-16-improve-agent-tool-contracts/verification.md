# 验证记录

## 2026-11-16 dev2 发布候选验证资源

- 工作区 `.cache/release-agent-dev2-20261116`：本任务 Windows 全量隔离测试及本地构建的专用目录，版本 0.1.0.dev2，使用者为当前 Agent；测试进程退出并归档摘要后，核验并解除目录内 pytest current 符号链接，清理目录并复扫确认不存在。现有历史测试资源和付费产物不属于本次，不删除。
- `uv run --frozen pytest -q --basetemp .cache/release-agent-dev2-20261116/final-tests`：退出 0，616 passed，540.65 秒；此前针对旧入口版本的测试运行已中断，不计为通过。
- `uv run --frozen ruff check .`、`uv run --frozen ruff format --check .`、`openspec validate --specs` 均退出 0；`uv run --frozen zhenzhen-seedance-video --version` 输出 `0.1.0.dev2`。入口原硬编码 dev1 已改为读取包元数据，安装测试从项目元数据读取预期版本。
- `uv build --offline --out-dir .cache/release-agent-dev2-20261116/final-dist`：退出 0，源码包 SHA-256 `d5743096982663f47c67c0fe990fa5c2c181ff8e80ae9fa44baf00ea6ce69692`、wheel SHA-256 `8fc70efc448971cbb6cb1dc2c58fca7f6bda3892b346b839fdf516418a0b1d29`；本地构建摘要不是正式 Release 资产摘要。检查包包含手册、锁文件及协议脚本，并排除测试、缓存和 `.env`。
- 实际 Host 对新 Schema 的展示及供应商完整产物集合仍未核实。本轮未调用供应商或修改 Host 配置。

## 2026-11-16 主规范同步与归档

- 两项 delta 已同步至 `provider-api-contracts` 与 `agent-task-observability` 主规范；逐项对照确认四项新增需求及全部场景完整一致，已有规范内容与 Purpose 保留。
- `openspec validate --specs`：退出 0，11 项主规范通过；归档前 `openspec validate improve-agent-tool-contracts --type change --strict`：退出 0；`git diff --check`：退出 0，仅有换行提示。
- 此次为文档同步与归档检查，未重新运行代码测试、调用供应商或修改 Host 配置；上次 111 项隔离测试见下方记录，不算作本轮新运行。
- 新 Schema 的实际 Host 展示和提前校验行为仍未验证；供应商完整产物集合及跨模型适用性继续待核实。未改变既有已关闭的 Job 生命周期调查状态。
- 本轮不产生测试临时资源；按用户授权将完整变更归档，不提交或推送 Git。

## 2026-11-16 OpenSpec 复核

- 完整性：变更任务 4/4，四项新增需求和对应场景可映射到实现及隔离测试。
- 修复复核中发现的联合 Schema 默认值可能覆盖共享优化授权或向成片、超分注入不适用音频字段的问题，改为说明文本；素材条目要求对应类型的 URL。模型、提示词和时长的类型错误与不支持值分开，诊断继续只允许静态字段和期望类型；纠正 local 与 provider 的执行授权说明。
- `uv run --frozen pytest tests/test_parameters.py tests/test_preflight.py tests/test_tools.py tests/test_diagnostics.py tests/test_admission.py --basetemp .cache/test-runs/verify-agent-contract-final-20261116 -q`：退出 0，111 passed；包括标准 JSON Schema 校验、合成 MCP 协议调用、共享授权、参数诊断和脱敏。新 Schema 在各实际 Host 的呈现和 Host 提前校验行为未实测。
- 最终 `uv run --frozen ruff check .`、`uv run --frozen ruff format --check .`、`openspec validate improve-agent-tool-contracts --type change --strict` 和 `git diff --check` 均退出 0；Git 提示部分文件将按配置转换换行。
- 本轮使用 `.cache/test-runs/verify-agent-contract-20261116` 和 `.cache/test-runs/verify-agent-contract-final-20261116`，仅供本次隔离测试；测试结束后核验并解除指向各自目录的 pytest current 链接，清理目录并复扫确认均不存在；其他历史资源保留。
- 复核当时未调用真实供应商；完整产物集合等既有供应商限制仍待核实。当时主规范尚未同步、变更未归档，当前状态见上方归档记录。

日期：2026-11-16。范围为 Windows 本地隔离测试，未调用真实供应商或修改 Host 配置。

- `uv run --frozen pytest tests/test_parameters.py tests/test_preflight.py tests/test_tools.py tests/test_diagnostics.py tests/test_admission.py --basetemp .cache/test-runs/agent-contract-final-20261116 -q`：退出 0，111 passed。覆盖工具 Schema、常规／成片／超分预检、默认值、优化授权语义、错误分类及脱敏、原有任务接收。
- `uv run --frozen ruff check .` 与 `uv run --frozen ruff format --check .`：通过；最终修改后重新核验。
- `openspec validate improve-agent-tool-contracts --type change --strict`：通过；最终修改后重新核验。
- 额外启动的全量隔离测试在完成前主动中断，不计为通过；本次以针对受影响功能的隔离测试为准。
- MCP 协议使用本机隔离客户端及合成适配器；实际 Host 的新 Schema 展示与真实供应商行为本次未验证。未核实的供应商限制、完整产物集合继续保留原状态。

## 临时资源清单

本次 pytest 使用工作区 `.cache/test-runs/` 下的独立目录 `8efeb28865b34e359bc0b390da2401d1`、`91b991eca7354fc4b8445ec45ed69f95`、`agent-contracts-20261116`、`agent-contract-focus-20261116`、`agent-contract-final-20261116`；用途为隔离数据库、协议进程和临时文件，无跨任务使用者。测试进程退出后，核验并解除指向各自测试目录的 pytest current 符号链接，清理上述目录并复扫确认均不存在。其他历史目录不属于本次测试，保留。
