# 常规生成、样片与成片统一队列真实验收

2026-11-14，13.5真实闭环通过。用户进一步明确选择“另生成一条最低参数样片，再显式生成成片”，因此没有导入此前直接接口生成的旧样片，也没有新增远端任务导入后门。旧样片保留，本轮复用此前原创视频的JPEG尾帧作为普通图生输入，并复用已使用的简单样片提示词。

## 参数、次数与结果

| 案例 | 模型与参数 | 实际视频 | 实扣 amount / currency |
| --- | --- | --- | --- |
| regular | seedance-2.0-mini-i2v；4秒、480p、adaptive；一张既有JPEG；音频及优化false | H264 MP4，640×640，4.041667秒，1013504字节 | 0.8028 / ¥ |
| draft | seedance-2.5-standard-t2v；4秒、480p、draft=true、1:1；音频及优化false | H264 MP4，640×640，4.041667秒，1151381字节 | 2.688892 / ¥ |
| final | seedance-2.5-standard-draft-to-video；引用本轮draft_task_id；native1080p、output_format=mp4、return_last_frame=false | HEVC MP4，1440×1440，4.041667秒，2756092字节 | 14.224814 / ¥ |

480p为常规/样片最低档，native1080p为成片唯一允许档。成片不提交prompt、素材、seconds或enhance_prompt，沿用4秒样片。参数档位和实际像素分别记录，不假定方形视频恰好480/1080像素高。成片编码为HEVC，不能由.mp4推断H264；本次未做人工播放/画面质量验收。

本轮仅3次收费生成POST、1次图片上传、13次同任务查询和3次完成的主视频下载。累计收费8/10，最多剩余2次；本轮实扣17.716506/¥，累计23.760998/¥，只取data.usage实际值，不推导按量费用或换算币种。详见[收费账本](paid-test-ledger.json)。

## 生产组件与MCP交付

通过MCP SDK stdio客户端调用submit_video、find_task_by_request_key、get_task、list_artifacts和copy_artifact；内部run_backend注入实际CompatibilityAdapter、UploadService及NetworkPolicy，沿用生产接收、统一队列、SQLite、下载、复制及退出协调。没有用直接提交脚本替代队列，没有修改用户Host配置，也没有默认启用普通CLI的真实派发。

隔离安装配置和LOCALAPPDATA，沿用配置凭据及网络策略；隐藏启动后核验发现记录与服务PID一致。每个案例独立request_key，重复调用返回原任务。数据库核验：3个任务、3次提交intent、3个不同远端ID，连接绑定相同；成片有效参数中的draft_task_id严格等于本轮样片远端ID。样片先成功下载与复制，才由客户端发起独立成片调用，服务自身没有自动成片链。

三份主视频分别保存在各自任务目录，并通过copy_artifact复制到显式工作区下的regular/draft/final-delivered.mp4，默认不覆盖。交付副本与对应原产物SHA-256逐项相同；素材原件和托管副本摘要一致。原样片不被成片覆盖。全部文件摘要、请求计数、源码与验收脚本摘要见[机器可读证据](generation-queue-acceptance.json)。

## NOT_START发现与原任务恢复

首次Mini图生POST已返回queued和ID，但首次GET为code=success/data.status=NOT_START、progress=0%。旧解析器拒绝未核实状态，使任务needs_attention并保留已知ID、占位和素材；后端正常退出，没有再次POST。

按缺陷规则重新打开8.4，先补design和spec，再依据完整实测响应增加NOT_START→queued，保留原状态；它不代表未接单或允许重提。[供应商通用文档](https://api.seedance.nz/docs/index.html)的排队语义仅作辅助，实际字段来自兼容端点取证。未实测的SUBMITTED保持拒绝，未扩展其他状态。隔离测试证明重复排队响应不增加POST、不改变跟踪轮次、保留占位及原状态。

同一隔离任务库重启后，按request_key找回原任务并显式refresh_task，一次查询得到SUCCESS，原任务继续下载和复制。未重新生成、未人工改写数据库。后续成片也实际返回NOT_START并经新解析器正常接续IN_PROGRESS/SUCCESS。最终客户端退出后后端返回0。

## 证据边界与验证

完整原始响应、任务库、媒体和工具结果位于Git忽略且ACL保护的.cache/generation-queue-20261114；私有验收脚本.cache/generation_queue_acceptance.py在每次收费POST前持久化独占intent及公共账本，限制ordinal 6–8及固定模型/最低档参数。公开fixtures位于tests/fixtures/provider/generation-queue-observed，脱敏保留完整JSON层级、键和类型；不公开真实任务ID、签名URL、API密钥或私有素材路径。

所有任务生成成功且已交付主视频；完整产物集合仍未知，artifact_set_status=unverified、delivery=partial，未提前清理托管素材。本次不关闭1.2/1.5/1.6等完整调查，不证明样片7天起算、跨账号核验、成片默认格式、国际版或全部26模型、实际Agent Host与干净OS验收。

实际执行的隔离测试、Ruff、构建、入口及OpenSpec校验见[验证记录](implementation-progress.md)。主规范业务同步和归档未执行，无Git提交或推送。
