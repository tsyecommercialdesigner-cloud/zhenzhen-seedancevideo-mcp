# 提交信息指南

规范性要求见 [spec.md](spec.md)。仅在获得提交授权后应用；规范本身不授予 Git 写权限。

使用 Conventional Commits 结构 `type(scope): subject`，scope 可省略；body 解释原因与影响，footer 关联真实任务或破坏性变更。

| type | 用途 |
|---|---|
| feat | 新功能 |
| fix | 缺陷修复 |
| docs | 文档 |
| style | 不改变行为的格式调整 |
| refactor | 保持行为的重构 |
| test | 测试或评测 |
| chore | 工具、依赖、CI 等维护 |
| perf | 性能改进 |
| revert | 回滚提交 |

scope 来自实际模块，例如工具适配、技能资源或文档分类，不固定业务模块或数据库产品。subject 默认不超过 50 个字符，以动作表述、不加句号，中英文由团队统一。破坏性变更使用适用的 `!` 或 `BREAKING CHANGE:` 并说明迁移影响。

示例（按实际改动替换）：

```text
docs(manual-writing): 更新安装说明

说明新旧安装步骤的差异及验证范围。
```

基于实际暂存差异生成信息，检查遗漏和无关文件，不能只凭任务标题声称已实现。可使用任意适用助手辅助起草，但提交前核对事实；不要求调用某一 Agent CLI。
