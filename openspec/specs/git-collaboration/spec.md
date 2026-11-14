# git-collaboration Specification

## Purpose

为集成项目提供与语言和 Agent Harness 无关的提交及 PR 协作基准，以真实差异、检查和评审证据组织交付，同时明确当前授权、合入门禁与发布之间的边界。

详细说明见 [guide.md](guide.md)。

## Requirements

### Requirement: 提交信息
项目 SHALL 按实际暂存差异使用 Conventional Commits，scope 来自实际模块，subject 简明描述动作并遵循团队约定。

#### Scenario: 提交信息验收
- **WHEN** 生成提交信息
- **THEN** 核对改动与验证事实，标记破坏性变更；未获授权不得提交。

### Requirement: PR 范围与证据
项目 SHALL 保持 PR 目标聚焦，按模板说明问题、行为变化、需求及实际验证，执行受影响的真实检查。

#### Scenario: PR 范围与证据验收
- **WHEN** 检查未配置、未运行或失败
- **THEN** 明确记录，不填虚假通过，不强制使用某一语言或助手的命令。

### Requirement: 评审责任
项目 SHALL 核对需求、接口、边界、权限、安全及适用性能问题；命名、类型和格式依据实际检查结果判断。

#### Scenario: 评审责任验收
- **WHEN** 使用 AI 或 Harness 规则辅助评审
- **THEN** 人工核验结论并补齐未覆盖内容，不把规则文件当作质量保证。

### Requirement: 合入门禁
项目 SHALL 由用户本人、Agent和CI协作评审，不强制其他人批准；必需检查通过且阻塞问题解决后按授权合入，合并后按差异复验，不强制全量重跑。

#### Scenario: 合入门禁验收
- **WHEN** 存在权限或单人维护限制
- **THEN** 记录替代策略和实际状态，不伪造审批或绕过门禁；发布仍需对应授权。

### Requirement: 分支与发布顺序
项目 SHALL 采用feature/* → dev → main，feature从dev分出且不直接进main；dev可积累多个功能再发布。

#### Scenario: 日常集成与正式发布
- **WHEN** feature通过PR合入dev
- **THEN** 按改动检查，不重复同套push CI、不发布；dev到main发布PR才对累计变更完整验收，CD仅在实际发布时执行。

### Requirement: 验证复用依据
项目 SHALL 将结果和候选产物关联实际内容及源码、依赖、构建配置等相关输入；只有一致才复用，缓存命中不作为通过依据。

#### Scenario: 合并后内容变化
- **WHEN** 合并结果与已验收候选存在差异
- **THEN** 重跑受影响检查；一致时仅必要快速检查，不机械复制完整验收。
