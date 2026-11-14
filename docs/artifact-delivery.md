# 视频产物下载与交付

本说明对应 `ArtifactService`、Windows 文件发布模块以及合成 Scheduler 的下载组合，已由隔离测试验证。MCP 产物工具已接线，调用示例见 agent-tools.md；本说明中的 Python 调用仍是内部服务示例。生产适配器与跨阶段恢复闭环尚未全部完成。已有一次Mini主视频和尾帧真实下载证据；实际Host、完整供应商矩阵和链接刷新能力仍未验收。

## 下载和持久化

内部适配器在确认任务生成成功后提供产物引用集合，至少一个必需视频；Agent 不能通过此接口要求下载任意 URL。样片、成片和超分任务各有独立产物，按任务接收时固定的输出目录保存，后续配置变化不迁移旧文件。默认长期保留，不自动删除生成视频。

下载走统一 NetworkPolicy，不携带 API Bearer；使用独立下载并发、总请求期限和配置字节上限。下载不调用生成接口，也不要求费用已返回或原输入仍存在。临时文件位于目标目录，流式写入并刷新，再检查长度、SHA-256 和基本 ISO BMFF 结构。检查只证明基本结构与完整性，不证明视频可播放或内容质量。mp4 与 MOV 按实际 ftyp 品牌验证，格式不一致报错，不改后缀充当转码。

发布前持久化文件摘要、大小及设备／文件身份；原子发布后登记 ready。发布后登记失败保留文件与 intent，重启核对身份和摘要后补记，不认领同名甚至同内容的其他文件。只有全部必需产物 ready 才触发正常输入清理待办；清理执行已由 CleanupService 接入本地后端，边界见 material-cleanup.md。部分成功保留并可复制，失败部分独立恢复，不重新生成。

暂时网络失败有限重试，预算和退避写入 attempts；重启不重置。磁盘、无效容器、空间或链接错误转产物待处理；401/403/404/410 标记 `ARTIFACT_LINK_REFRESH_UNVERIFIED`，不盲目加密钥或伪造新 URL。已发布 intent 的异常须先恢复核对，不能直接当作一次可重试传输。停止／放弃任务后旧下载不能重新授权发布；已发布事实仍可保留，但不能重新开启自动执行。

## 查询和显式恢复

`list(task_id, after="", limit=20)` 返回有界清单（最多 100 条）和下一游标；不返回签名 URL、视频字节或 Base64。查询检查存在性和大小，`verify(artifact_id)` 进一步核对摘要。外部删改标记 missing／changed 并更新任务版本，不自动重新下载，也不持续扫描目录。

内部调用示例（`service` 为已初始化服务；ID 和版本来自实际查询）：

```python
page = await service.list(task_id, limit=20)
artifact = await service.verify(artifact_id)
await service.retry(task_id, expected_version=task_version)
await service.due()  # 正式组合由调度器调用；不发送生成 POST。
```

恢复使用新预算并保留历史；已 ready 的产物保留。异常目标仍存在时默认拒绝，只有 `overwrite=True` 才允许新视频完整后原子替换；恢复授权时不会先删除旧文件。已无可靠产物引用时明确提示链接刷新待核实，不能承诺永久恢复。SUCCESS 与完整费用封装继续待核实，不以合成测试填补契约。

## 复制交付

```python
result = await service.copy(artifact_id, "videos/result.mp4", workspace_root=r"D:\AgentWorkspace")
# 写到工作区外须使用明确的本地绝对文件路径：
result = await service.copy(artifact_id, r"E:\Exports\result.mp4", overwrite=False)
```

相对路径必须有显式绝对工作区基准，规范化后不得越界；拒绝 UNC、驱动器相对路径、备用数据流、保留文件名和重解析路径。目标必须是文件路径。复制不改变格式；请沿用源文件扩展名。目录逐级持有禁止删除共享的 Windows 句柄，源文件禁止写入／删除共享，防止复制中路径替换。

复制先写同目录临时文件，核对源和副本摘要后发布。默认不覆盖已有目标（内容相同也拒绝），显式 overwrite 才替换；不能覆盖另一服务产物。源目标指向同一文件时明确无操作。取消发生在发布前则保留旧目标并清理临时副本；发布后响应丢失不回删目标，重试仍遵守默认不覆盖。交付副本由用户管理，修改副本不会改变服务原产物。

对应验证见 `tests/test_artifacts.py`：本地 HTTP 字节、合成断流、磁盘故障、预算、并发、发布窗口、数据库重开、部分成功、删改恢复、路径竞争、取消与响应丢失。容器 fixture 为人工构造的结构样本，不是实际供应商视频。


## 2026-11-13 主视频引用与部分交付

已确认的 metadata.url 可通过内部 CompatibilityAdapter（注入任务库）接通主视频下载、持久化与复制。任务查询新增 artifact_set_status；完整集合未知时为 unverified，已就绪主视频可单独交付，任务保持 partial，保留 ARTIFACT_SET_UNVERIFIED 和输入托管副本。显式放弃仍按既有规则清理素材。测试 tests/test_main_video_delivery.py 使用合成传输覆盖下载、复制、403恢复、数据库重开、重复查询、格式和引用关联以及清理协调。四份样例仍是契约来源；尾帧／完整集合、SUCCESS、费用完整响应待核实，无真实调用证据。


主视频协议复验：独立stdio客户端的提交、等待、主视频下载／复制，以及最后客户端退出、发布前后崩溃和下载待处理恢复，见[端到端验证说明](main-video-protocol-validation.md)。此为合成供应商、多进程协议证据；实际Host和供应商仍未验收。


## 已观察JPEG尾帧（2026-11-14）

兼容SUCCESS封装中的data.data.content.last_frame_url可独立登记、下载、校验并经原产物tools复制到指定路径。实测URL后缀及outputType是png，实际字节是JPEG；按JPEG结构保存.jpg，不执行转码。校验SOI、段长度、尺寸段、扫描段及EOI，不宣称完全解码或质量验收；实际PNG或其他未核实编码被拒绝并进入待处理。JPEG使用与视频相同的独立预算、发布及文件恢复规则。

已返回尾帧登记为需下载引用，缺尾帧不伪造；complete=false持续保留，因为必需集合与跨模型适用仍待核实。即使视频与尾帧均ready，任务仍partial、素材不自动清理。原先仅主视频的任务行为不变。单次真实下载不证明链接永久有效或支持刷新／断点续传。
