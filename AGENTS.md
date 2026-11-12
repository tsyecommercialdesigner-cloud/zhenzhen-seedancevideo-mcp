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

- 项目测试：<实际测试命令待定>
- 代码检查：<实际检查命令待定>
- 构建或启动：<实际命令待定>
- OpenSpec 校验：openspec validate "<change-name>" --type change --strict

## Completion Report

- 完成了哪些任务和文档修订。
- 哪些验证实际执行并通过。
- 还有哪些阻塞、风险或未验证项。
- 主规范同步与归档的实际状态。