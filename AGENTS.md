# Project Working Agreement

## Project Context

- 项目目标：实现一个用于为 Agent 提供视频生成能力的 MCP Server。
- 实际技术栈以仓库依赖、代码和已有设计为准。
- Python 依赖使用 uv 管理；命令按 Windows PowerShell 表示。
- 规划说明使用简体中文，保留 OpenSpec 需要的英文标题和关键字。

## OpenSpec Workflow

- 本项目使用 OpenSpec 2.0 Skills。
- 先定位当前 change；目标不明确时先澄清。
- 使用 openspec status 和 openspec instructions 获取当前状态、指引与真实输出路径。
- 读取 openspec/config.yaml，以及当前阶段已存在且适用的 proposal、specs、design、tasks。
- 对尚未创建或明确跳过的产物，按 status 和 instructions 处理，不把不存在的文档当作已读。
- 按需读取相关主规范；不要假设所有项目都只有根目录三份 Markdown。
- 学习阶段逐份生成、逐份审阅；实施由明确的 apply 请求开始。
- 需求或设计发生变化时，先修订受影响文档并检查一致性，再实施。

## Engineering Practices

- 修改应符合当前规范与设计边界。
- 对新增的架构选择，说明备选方案、理由与影响。
- 一项任务对应明确交付物和可执行的完成判断。
- 测试和必要文档随所属任务交付。

## Verification

- 使用当前任务中真实存在的验证命令。
- 报告实际执行内容、退出结果、关键输出及未验证事项。
- 测试未运行或失败时，不记录为通过。
- 后续发现缺陷时，重新打开对应任务或补充修复任务。
- 业务需要人工验收时，记录具体产物和验收结论。

## Commands

- 项目测试：`uv run --frozen pytest`
- 代码检查：`uv run --frozen ruff check .` 和 `uv run --frozen ruff format --check .`
- 构建：`uv build`；入口检查：`uv run --frozen zhenzhen-seedance-video --version`（服务尚在实施，版本检查不代表可运行）
- OpenSpec 校验：openspec validate "<change-name>" --type change --strict

## Completion Report

- 完成了哪些任务和文档修订。
- 哪些验证实际执行并通过。
- 还有哪些阻塞、风险或未验证项。
- 主规范同步与归档的实际状态。

## Test Resource Cleanup

- 新测试前扫描本任务缓存、worktree、独立安装、运行时、依赖环境、下载包和配置遗留；先复用或清理，确需并存记录原因。
- 维护持久资源清单：路径、用途、版本、任务归属、使用者、状态、释放条件和清理方法；跨Agent/模型交接以清单为准。
- 结论按任务、版本和测试类别文档化后，只保留最小必要脱敏证据，主动清理本任务临时资源和共享目录子目录，恢复临时配置字段且保留并发修改。
- 成功、失败或中断均收尾并复扫，核对磁盘与清单；未清理项记录原因、接管人和处理时点，不默认永久保留。

## Git Operations Order

- feature/* 从 dev 分出，经 PR 合入 dev；dev 可积累多个功能，再通过发布 PR 合入 main；feature 不直接进 main。
- 用户本人、Agent 与 CI 协作评审，不强制其他人批准，不伪造审批或绕过实际保护。
- feature → dev 按改动做格式、类型、相关测试及安全检查；纯文档用文档检查。合入 dev 不重复同套 push CI、不发布。
- dev → main 对累计变更完整发布验收并生成候选产物；合入 main 按合并差异复验，一致时仅必要快速检查。
- 只有源码、依赖、构建配置等相关输入一致时才复用验证及产物；缓存命中不等于通过。CD 仅正式发布时由单一受控入口发布已验证产物，再回填 README/MANUAL。
