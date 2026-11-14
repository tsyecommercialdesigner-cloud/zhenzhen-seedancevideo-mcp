# Fast图生与Standard多模态统一队列真实验收

2026-11-14，13.4中的Fast图生与Standard多模态代表案例完成。沿用生产run_backend、CompatibilityAdapter、UploadService和NetworkPolicy，通过真实MCP SDK stdio工具调用完成本地接收、素材托管、上传、统一队列提交、查询、下载与复制；不以直接HTTP提交替代队列。

## 最低参数与素材

Fast：seedance-2.0-global-fast-i2v，已有JPEG作为单张首帧，4秒、480p、adaptive，generate_audio=false、enhance_prompt=false；复用此前图生提示词。Standard：seedance-2.0-standard-multi，canonical metadata.content依次为image_url、video_url，复用同一JPEG及已有MP4，4秒、480p、1:1，音频与优化均false。不传仅适用于2.5的omni_reference_task_type，不引入音频素材或加工素材。

原始素材分别来自.cache/artifact-probe-20261114/last_frame.bin与video.bin，JPEG 112496字节、MP4 823227字节/4.041667秒。输入SHA-256分别为01857416757fda8169dde7e47f9b1c32ca6cb82b0f6fc646f8adfe6e6c8a50fa及674d710c8443a67d2e8d7f9ea82c7e920ab6e85106357ce02cb40a81b847aed9。两个任务各自托管：共3份副本，摘要与原素材一致；不跨任务共用删除归属。

## 结果与收费

| 案例 | 模型 | 实际媒体 | 实扣 |
| --- | --- | --- | --- |
| Fast图生 | `seedance-2.0-global-fast-i2v` | h264，640×640，4.041667秒，906118字节 | 1.504578 / ¥ |
| Standard多模态 | `seedance-2.0-standard-multi` | h264，640×640，4.041667秒，830770字节 | 2.14038 / ¥ |

本轮2次收费生成POST、3次素材上传、24次查询，完成2份主视频下载和复制。本轮实扣3.644958 / ¥，历史总实扣46.217440 / ¥，只记录外层data.usage返回值。当前授权窗口累计4/10、余6，其中此前国际链2次、本轮2次；历史共12次，终身授权上限18。窗口不重置，结果不明的提交也占预算。

## 实际核验

- 隐藏后端与MCP查询PID匹配；重复submit_video使用同key返回原任务。数据库中2个任务、2次submit attempt、2个不同远端ID，共用连接绑定。
- 3个上传记录分别关联其托管素材；实际供应商生成payload的图片/视频URL逐项等于已持久化上传URL，且顺序正确。有效参数的4秒/480p/关闭优化及音频已核对。
- 两份视频分别落到任务目录，通过copy_artifact以显式工作区相对路径复制为fast-delivered.mp4、multi-delivered.mp4，默认不覆盖；交付副本与服务原产物摘要一致。
- 完成后再次核对输入原件、本轮输入副本、3份托管副本摘要，全部保持；完整产物集合未知，任务delivery=partial，未因主视频ready提前清理素材。
- 客户端断开后后端正常退出0；生产源码与执行前快照摘要一致，没有修改默认CLI供应商派发或用户Host配置。

机器证据见[JSON记录](fast-multi-queue-acceptance.json)。公开响应在tests/fixtures/provider/fast-multi-queue-observed；完整原始记录、工具结果、数据库和视频位于Git忽略且ACL保护的.cache/fast-multi-queue-20261114。公开材料隐藏真实ID、签名URL和密钥，保留结构、类型和实际费用。

本次只证明这两个模型、这些素材与最低参数下的真实成功链路；不证明全部Fast/Standard模型、2.5多模态edit/extend、音频输入、边界时长/大小、默认值或优化开启。没有实际品牌Host、干净OS或人工播放/画面质量验收；完整产物集合仍未知。13.4继续保留未完成，当前61/67、剩余6项。无Git提交推送、业务主规范同步或归档。检查命令和结果见implementation-progress.md。
