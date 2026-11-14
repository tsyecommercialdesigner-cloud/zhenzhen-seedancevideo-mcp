# 国际版样片/成片真实队列响应

2026-11-14用户授权新增8次，合并旧余量2次形成新窗口10次。本次仅2次收费提交（历史序号9、10），复用既有方块提示词；global 2.5 t2v样片4秒480p、draft=true、音频和优化false。样片完成后显式创建同区域draft-to-video，native1080p/mp4、return_last_frame=false，不传提示词/素材/seconds/优化。两任务经真实生产统一队列和MCP工具完成查询、主视频下载、复制，未绕过队列直接提交。

兼容端点POST返回顶层queued/id；GET观察到IN_PROGRESS和SUCCESS。外层data.usage金额分别2.877682、15.933802，币种¥。样片data.data.content.draft_task_id与该任务ID一致。26次查询，0次上传，2个收费提交；同key重复工具调用未增加提交。没有人为制造错误或追加收费探测。

JSON保留键、层级和类型；任务ID替换稳定别名，URL替换example.invalid，非公开字符串替换[REDACTED]、非实扣数值同类型0。0不是实际时间/尺寸/Token值。完整原始响应、媒体和任务库保存在Git忽略且ACL保护的.cache/global-queue-20261114；原始响应摘要见provenance.json，主视频摘要与参数/交付核验见docs/global-queue-acceptance.json。

只证明这两个global模型在此次最低配置下的成功链路。未验证7天起算、外部账号核验、默认格式、mov、完整产物集合或实际品牌Host；主视频可复制，集合仍unverified/partial。未开启优化。
