# 单次优化开启真实队列响应

2026-11-14用户明确只允许本次开启优化，不修改“总是允许”。使用seedance-2.0-mini-t2v，复用既有方块提示词，4秒480p、generate_audio=false，提交工具allow_once=true、请求enhance_prompt=true。1次收费POST（历史序号13）、9次查询、0次上传，经生产统一队列完成下载和copy_artifact交付；同key重放没有额外提交。

兼容POST返回顶层queued/id；GET观察NOT_START、IN_PROGRESS和SUCCESS。实扣外层data.usage为0.8028/¥。选取各状态首份完整响应供隔离回放；原始10份响应摘要见provenance.json。授权记录single_allow，前后持久偏好均false/version0，preferences表无新增行；之后省略优化和单次许可的预检仍为default_false，未创建后续任务。

JSON保留键/层级/类型，ID为稳定别名，URL为example.invalid，非公开字符串[REDACTED]，非实扣数值同类型0；占位0不是实际时间/尺寸/Token量。原始记录、任务库和媒体在受ACL保护、Git忽略的.cache/optimization-queue-20261114。已授权true被接受并完成交付，不证明上游具体改写或质量提升；未额外付费对照。完整集合仍unverified/partial。详情见docs/optimization-queue-acceptance.md/.json。
