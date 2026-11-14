# 国际版样片与成片统一队列真实验收

2026-11-14，13.4中的国际版样片/成片真实闭环完成。使用真实MCP SDK stdio客户端调用生产工具，隐藏后端注入CompatibilityAdapter与NetworkPolicy，沿用生产接收、全局队列、SQLite、轮询、下载和复制流程。未用直接供应商POST替代统一队列，未修改实际Host配置或普通CLI默认派发策略。

## 授权与最低参数

用户新增8次额度，与此前剩余2次合计本次可用10次。历史8次保留，账本终身上限18；本次只用2/10、剩余8，历史总提交10。提交意图在POST前独占持久化，未知结果仍占预算；执行器仅允许本轮序号9、10及两个指定global模型。没有自动重提或额外探测。

样片复用既有提示词 `A small red wooden cube slowly rotates on a plain white table. Static camera.`，4秒、480p、draft=true、1:1，enhance_prompt=false、generate_audio=false。样片成功且已下载复制后，由验收客户端显式创建独立成片任务；引用本次同区域已完成样片，native1080p为唯一允许档，显式mp4、return_last_frame=false，不传prompt、素材、seconds或enhance_prompt。没有自动样片链。

## 实际结果

| 案例 | 模型 | 实际媒体 | 实扣 |
| --- | --- | --- | --- |
| 样片 | `seedance-2.5-global-standard-t2v` | h264，640×640，4.041667秒，1063145字节 | 2.877682 / ¥ |
| 成片 | `seedance-2.5-global-standard-draft-to-video` | hevc，1440×1440，4.041667秒，1992890字节 | 15.933802 / ¥ |

请求档位与实际像素分开报告。此次2次收费POST、26次同任务查询、0次上传，2份主视频均下载并通过copy_artifact复制交付。本轮实扣18.811484 / ¥；历史总实扣42.572482 / ¥。仅记录外层data.usage实际金额，不换算币种、不推导Token费用。

## 核验与证据范围

重复submit_video使用同request_key返回原任务。数据库核对2个任务、2次submit attempt、2个不同远端ID、同一连接绑定；成片有效参数引用严格等于本轮样片远端ID。关闭优化的参数及复用提示词已与持久化快照核对。样片和成片分别落盘，copy_artifact使用显式工作区下相对路径、默认不覆盖；两个交付副本与原产物SHA-256均一致，成片完成后再次检查样片摘要不变。客户端断开后后端正常返回0。

主视频ready，完整产物集合仍unverified、delivery=partial，不冒充集合级完成。没有人工播放/画面质量验收；不证明七天起算、外部账号核验、默认格式或mov、其他模型，也不替代实际品牌Agent Host及干净Windows OS验收。13.4继续保留未完成，常规模型差异和优化开启等仍有缺口。

原始响应、数据库及媒体保存在Git忽略且ACL保护的`.cache/global-queue-20261114`。两份交付文件为该目录的`draft-delivered.mp4`和`final-delivered.mp4`。验收脚本`.cache/global_queue_acceptance.py`及生产源码摘要、文件摘要、媒体信息、账本窗口见[机器证据](global-queue-acceptance.json)。公开完整脱敏响应见`tests/fixtures/provider/global-queue-observed`，保留层级与类型，隐藏实际ID/URL/秘密。只复用了既有文案，本次无输入素材上传；脚本保留的既有JPEG副本未参与生成。

运行的隔离测试与检查见[验证记录](implementation-progress.md)。无Git提交推送、业务主规范同步或归档。
