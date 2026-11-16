# Git 协作指南

要求见 [主规范](spec.md)。

- 编写提交信息时读 [提交指南](commit-guide.md)。
- 创建或评审 PR 时读 [PR 与评审指南](pr-review-guide.md)。
- CI/CD 与发布细则见 [工程指南](../engineering-practices/guide.md)。

本仓库由用户本人、Agent与CI协作评审，不强制其他人批准。分支顺序feature/* → dev → main，dev可积累功能。日常按差异检查，发布PR完成完整验收，合并后按差异复验；相关输入一致且证据可信有效并覆盖目标范围时才复用结果及产物，CD仅正式发布时执行。发布事实回填的用途判断、轻量检查及必需状态报告按工程指南执行。规则变更不自动修改远端ruleset或授权Git操作。
