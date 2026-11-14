# 独立超分统一队列真实验收

2026-11-14，任务13.6通过。用户明确授权复用已有测试视频，以最低分辨率完成上传、查询、下载与复制交付，累计收费提交不超过10次。本次新增1次，累计5/10；实扣0.875/¥，累计观测6.044492/¥。金额仅来自data.usage，不推导计费公式。

## 执行路径与证据

使用当前未提交工作区源码、Python3.12.14及锁定依赖。通过MCP SDK stdio客户端调用真实工具，不修改用户日常Host配置。隔离后端由run_backend组合CompatibilityAdapter、UploadService和统一NetworkPolicy，调度、持久化、下载及复制均使用生产实现。私有审计网络包装仅限制一次收费提交并保存响应，未伪造供应商结果；没有开启默认CLI的真实派发功能。

1. 将此前原创测试视频video.bin按原字节复制为input.mp4；823227字节、4.041667秒，SHA-256见[机器可读证据](upscaler-queue-acceptance.json)。原文件和本次输入均保留。
2. 独立安装目录及LOCALAPPDATA隔离配置、数据库、素材副本和输出；沿用已配置凭据和显式网络策略，敏感值不进入命令行或公开证据。后端隐藏启动，stdio客户端确认发现记录PID匹配。
3. 调用upscale_video，request_key固定，model=zhenzhen-upscaler，metadata.resolution=720p，metadata.content仅一个video_url，其url为local_path输入。不传prompt或seconds。
4. 再次用相同请求标识和内容调用，返回同一任务。统一队列从托管副本完成一次/v1/files/upload、一次/v1/video/generations提交和13次同任务GET查询。
5. get_task和list_artifacts持续读取本地进度；观察到SUCCESS后生产解析器持久化data.task_id、data.result_url及data.usage，主视频自动下载一次并发布。
6. copy_artifact以显式workspace_root及相对target_path=delivered.mp4复制，默认不覆盖。交付副本与保留的产物摘要相同；数据库仅1个任务、1次提交、1次完成的下载、1条实际费用观察。上传和文件发布均完成，素材托管副本保留且摘要匹配。
7. stdio客户端退出后后端正常收尾，退出码0。没有额外price-preview、取消、重新生成或其他模型调用。

实际产物为H264 MP4、960×960、4.041667秒、1043959字节。720p是请求档位，实际尺寸单独记录。输入为方形视频，不将档位名称解释成固定720像素高。输出SHA-256：115a392649349d8e25c38ee8c283f557783e20af2f0c74a1768919b07f082910。

## 范围与限制

主视频已就绪且复制成功；完整产物集合仍待核实，因此artifact_set_status=unverified、delivery=partial，未提前清理托管素材。这不影响13.6规定的主视频闭环完成判断，不扩展为完整产物集合、全模型、画面质量人工验收、跨Host重启或实际Agent Host验收。

原始响应、数据库、媒体及验收脚本保存在Git忽略且当前用户/SYSTEM ACL保护的.cache/upscale-queue-20261114-run2及.cache/upscale_queue_acceptance.py。公开JSON只含摘要、计数、费用和状态，不含远端任务ID、API密钥或签名URL；源码及脚本摘要用于定位本次未提交快照。禁止盲目重跑该收费脚本，独占intent使相同目录不能重复提交。

首次验收夹具启动误从uploads模块导入UploadService，在任何网络调用之前失败；修正为upload_service并使用新的隔离目录后成功。首次目录保留作诊断，不计为收费提交。生产代码未因本次验收修改。

检查命令和全量结果见[验证记录](implementation-progress.md)。业务主规范未同步，change未归档；无Git提交或推送。
