# 主视频协议与重启验证


## 主视频 MCP 端到端与跨进程恢复（2026-11-13）

新增 tests/test_main_video_protocol.py 与仅测试使用的 main_video_backend.py。两个独立 stdio 前端通过 MCP SDK v2 客户端、真实 RPC／隐藏后端／SQLite／文件服务，调用 CompatibilityAdapter；API 与下载均由 MockTransport 回应，绝无外部 HTTP 请求。API JSON 来自用户已提供样例，下载 URL 替换和文件内容明确为合成数据。测试子进程隔离 LOCALAPPDATA、安装 .env 和用户环境配置，不读取生产凭据；测试驱动不会进入发行包。

| 场景 | 可执行验证 |
| --- | --- |
| A提交、B接续 | 同request_key返回同task_id；A退出B在线时继续主视频下载，get_task/wait_task/list_artifacts/verify_artifact/copy_artifact经真实协议调用 |
| 复制交付 | 工作区相对路径与绝对路径均验证文件SHA-256；默认目标冲突不破坏已有文件，显式覆盖成功，原产物保留，工具摘要不含签名URL或视频Base64 |
| 最后客户端退出与重启 | 等待原后端退出码0；新后端/新客户端按request_key找回生成中任务并继续查询下载；已就绪主视频复制不再查询或下载 |
| 发布前后崩溃 | 测试后端在指定点退出91；发布前按预算重新下载，发布后凭intent与摘要补登记，无重复生成POST；新客户端可交付 |
| 下载403待处理 | 跨后端重启保留needs_attention，不自动复活；显式retry_task_download后恢复，同URL可用性变化仅为合成测试，不宣称支持上游链接刷新 |

所有场景保留artifact_set_status=unverified和delivery=partial，费用not_returned，不以已知主视频ready冒充全部产物就绪。每个任务的合成生成POST恰好一次；发布前崩溃／显式下载重试允许第二次下载，发布后核对不重复下载。进程由测试保留的句柄等待退出，不通过扫描或强杀无关进程。

首次端到端测试发现 Lifecycle 将active成功任务的ARTIFACT_SET_UNVERIFIED误升级为needs_attention，阻断发布前恢复；修复仅豁免这一非阻断集合说明。原needs_attention／abandoned、其他错误和身份不兼容仍阻断，tests/test_lifecycle.py补充参数化回归。9.6重新打开后按复验结果关闭；不放宽原恢复授权。

该证据属于当前Windows的多进程协议隔离验证，不能替代实际Agent Host（13.3）或真实供应商验收。尾帧、完整集合、SUCCESS、完整费用响应继续待核实，8.4未完成。实际命令和结果见 implementation-progress.md。


本地素材完整协议复验：已通过独立stdio客户端串联托管、multipart上传、生成、主视频下载和复制，并覆盖上传未落账／引用已保存／生成处理中三种重启接续。参见[素材完整流程验证](material-protocol-validation.md)；合成证据不替代真实Host或供应商验收。
