# 本地素材完整 MCP 流程隔离验证

2026-11-13，对应7.1–7.3、8.3、9.6、第10／12组与13.2。测试入口：`tests/test_material_protocol.py`，复用仅测试使用的`tests/main_video_backend.py`。

## 实际链路

两个独立stdio前端通过真实MCP SDK客户端、RPC、Tools、AdmissionService、UploadService、CompatibilityAdapter、Scheduler和ArtifactService执行：提交本地图片 → 完整托管与请求去重 → multipart上传 → 固定兼容端点生成／查询 → metadata.url主视频下载／摘要核验 → 工作区相对路径复制交付。上传没有新增公开tool，仍属于正式提交授权后的内部准备。

API及下载全部使用MockTransport，不访问真实供应商。上传JSON基于documented/upload-success.json替换合成URL和大小；生成响应基于用户样例显式替换模型为mini-i2v及结果URL。原fixtures不修改，这些替换不是新的上游证据。图片和视频字节都是测试内容，不证明媒体内容质量或真实供应商接受性。

## 接续场景与断言

| 断点 | 恢复预期及验证 |
| --- | --- |
| 上传请求已发送、响应未落账 | 测试后端退出91；保留已消耗预算，旧intent标reconciled；新后端从同托管副本再次上传，合计2次上传、1次生成、1次下载 |
| 上传引用已保存、生成尚未提交 | prepare阶段退出91；新后端复用未到期URL，合计1次上传、1次生成、1次下载 |
| 生成处理中，全部客户端退出 | 原后端有限退出码0；新客户端按request_key找回并接续查询交付，合计1次上传、1次生成、1次下载 |

每次入队都由第二客户端重放同request_key核对同task_id；托管完成后修改用户原文件，上传传输断言仍包含原始托管字节且不含修改后内容，内部上传文件名为material.png。生成payload的images只有临时URL，没有local_path或material_id。后端退出后只读检查隔离数据库：只有一份任务／素材／上传记录，material_id、有效参数快照不变，重启不重置上传预算，历史尝试保留。

新客户端调用find_task_by_request_key、get_task、wait_task、list_artifacts、verify_artifact、copy_artifact；逐文件SHA-256核对，保留服务原视频和用户修改后的原图片。任务仍为partial、artifact_set_status=unverified、费用not_returned，托管副本继续存在、没有正常完成清理任务；不冒充完整集合就绪。测试拥有的后端进程通过保留句柄等待退出；临时状态根、安装.env和用户环境全部隔离。

## 验证边界

本轮是当前Windows上的多进程MCP协议隔离测试，不等同实际Agent Host或供应商验收。尾帧及完整集合、SUCCESS、完整费用响应继续待核实；上传精确有效期、模型约束适用性及上游读取时机亦未因本轮测试得到确认。生产CLI不启用完整供应商适配器。命令、退出结果和收尾见[实施验证记录](implementation-progress.md)。
