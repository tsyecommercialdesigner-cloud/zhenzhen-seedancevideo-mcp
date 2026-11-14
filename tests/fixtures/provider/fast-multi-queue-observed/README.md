# Fast图生与Standard多模态真实队列响应

2026-11-14用户明确授权在当前剩余8次内验收Fast图生和Standard多模态。本轮2次收费提交（历史序号11、12），当前授权窗口累计4/10、余6；未重置历史计数。两模型分别为seedance-2.0-global-fast-i2v、seedance-2.0-standard-multi，均4秒480p、音频/提示词优化false，复用此前JPEG和MP4，无素材加工或新素材生成。

使用生产统一队列与真实MCP SDK stdio工具，先托管/上传再生成，3次上传、2次生成POST、24次查询；两任务均完成主视频下载和copy_artifact交付。同key重复工具请求返回原任务，没有第二次收费提交。多模态canonical content依次image_url、video_url，不传2.5专用omni_reference_task_type。数据库中的3份托管副本摘要、上传URL与最终payload引用逐项匹配。

兼容POST返回顶层queued/id；GET包含IN_PROGRESS/SUCCESS，多模态还实际观察NOT_START。外层data.usage实扣为1.504578/¥和2.14038/¥。选取每个模型/状态的首份完整响应供隔离回放；完整原始29份响应的SHA-256见provenance.json（含上传），不把重复查询当成额外收费。

JSON保留键/层级/类型；ID为稳定别名、URL为example.invalid、私有字符串为[REDACTED]、非实扣数值为同类型0。这些0不是实际时间、尺寸或Token值。原始响应、任务库、素材和视频位于Git忽略且ACL保护的.cache/fast-multi-queue-20261114；费用、媒体与复制摘要见docs/fast-multi-queue-acceptance.json。

此证据不证明其他Fast/Standard模型、音频素材、2.5 edit/extend、完整产物集合、退款或边界限制。完整集合仍unverified/partial，输入副本保留。未验证真实品牌Host或人工画面质量，未开启提示词优化。
