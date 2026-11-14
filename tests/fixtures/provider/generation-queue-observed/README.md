# 13.5统一队列真实响应证据

2026-11-14用户授权累计10次以内、最低参数。常规Mini i2v复用此前生成的JPEG尾帧，4秒480p、音频/优化关闭。提交兼容端点返回queued；首次同ID/模型查询返回code=success/data.status=NOT_START、progress=0%，且未提供结果URL或费用。实际响应是兼容端点证据，公开文档的通用排队状态仅作辅助：https://api.seedance.nz/docs/index.html 。本次没有观察到SUBMITTED，仍不开放该状态。

原始响应保存在Git忽略且ACL保护的.cache/generation-queue-20261114。JSON保持键/层级/类型，ID统一化，URL替换example.invalid，私有字符串[REDACTED]、非实扣数值同类型0。这些0是脱敏占位，不是实际费用或时间。

随后同库重启显式刷新取得regular SUCCESS，未再提交。用户进一步授权新样片：国内2.5 t2v、4秒480p、draft=true；完成后显式提交国内draft-to-video，native1080p、mp4、return_last_frame=false，不传prompt/素材/seconds/优化。final首次查询也观察到NOT_START，随后IN_PROGRESS及SUCCESS。三任务均经实际统一队列下载复制成功，金额分别0.8028/2.688892/14.224814，币种¥；累计8/10次。参见docs/generation-queue-acceptance.md。
