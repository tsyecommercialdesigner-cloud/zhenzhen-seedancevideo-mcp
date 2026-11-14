# 配置与诊断

配置模块已落实安装目录优先规则；隔离测试不代表完整视频闭环或真实 Host／供应商验收。

配置文件为实际安装目录 `.env`，不搜索 Host cwd、Agent 工作区、HOME 或用户数据根。安装根依据包文件位置识别：源码／editable 使用 `src/zhenzhen_seedance_video` 所属且项目名匹配的 `pyproject.toml` 目录；wheel 在项目 `.venv/Lib/site-packages` 内时使用 `.venv` 父目录；独立虚拟环境安装使用虚拟环境根。后两者必须存在 `pyvenv.cfg`。无法识别的全局安装或自定义布局明确拒绝，不猜测目录。升级保留私有 `.env` 及权限，服务不自动移动或覆盖配置。

逐字段优先级：**安装目录 `.env` > 进程环境 > Windows 当前用户环境 > 默认值**。仅未定义时回退；空值、非法值、重复字段或文件读取／解析失败报错，不以旧密钥兜底。低优先级同名字段不会覆盖已选值。字段名不区分大小写；未知服务前缀字段拒绝。文件使用 UTF-8（兼容 BOM），不展开 `${变量}`；用户环境也不展开 `%变量%`，路径填写完整绝对路径。

Windows 用户环境只读 `HKEY_CURRENT_USER\Environment`。Host 若仍携带旧进程值，其优先级高于用户环境；要采用新用户值，应移除 Host 中该字段或重启 Host 更新进程环境。用户环境读取失败明确拒绝。

状态根仍为 `%LOCALAPPDATA%\ZhenzhenSeedanceVideo`，状态库、运行锁、托管素材和默认输出在此，与安装目录分离。

运行配置在后端启动时固定。新客户端未指定的值沿用后端；显式不同的值返回冲突项名，不回显敏感值、不覆盖现有后端。修改配置后需正常退出所有 Host、等待后端结束，再启动。不要强杀后端或删除状态库。新输出目录只用于新任务，旧任务仍应使用接收时固定的目录。

仓库 `docs/configuration.env.example` 仅含空密钥；复制到安装目录 `.env` 后必须填写。空值会报错，即使环境有密钥也不会回退；要使用环境密钥，请删除或注释文件中的密钥字段。唯一密钥名为 `ZHENZHEN_SEEDANCE_API_KEY`，不读取通用 `API_KEY`。输出目录须为本地绝对路径；拒绝 UNC、驱动器相对路径和备用数据流。状态和托管素材位置不随输出目录迁移。

可选字符串项（以下均加前缀 `ZHENZHEN_SEEDANCE_`）：

| 项 | 默认 | 规则 |
| --- | --- | --- |
| API_KEY | 无，必填 | 不含空白，不进入任务、日志、命令行 |
| EXECUTION_MODE | local | local/provider；重启生效，显式provider启用新任务的供应商执行 |
| OUTPUT_DIR | 用户数据根下 outputs | 本地绝对路径 |
| PROXY_URL | 未配置，直连 | 显式 http/https 代理；不读系统代理、PAC 或 HTTP_PROXY |
| PROXY_BYPASS | 无 | 逗号分隔域名、域后缀、IP 或 CIDR；不支持通配符 |
| CA_FILE | 系统信任 | 本地已有 CA 文件；网络初始化还须验证证书内容，禁止忽略坏 CA 或关闭验证 |

代理及 CA 策略统一用于网络执行器及每次重定向；替身测试不代表真实供应商网络验收。代理 URL 可含认证信息，任何报错只输出配置名。

数值配置同样使用上述前缀。除跟踪期限可为 0（关闭跟踪期限）外，已配置整数须大于 0，最大为有符号 64 位整数。下载字节上限不配置表示不额外限制；不是无限磁盘或无限请求期限。重试数是首次失败之后的重试预算，不用于自动重试结果不明的生成提交。

| 配置后缀 | 默认值 | 单位／意义 |
| --- | ---: | --- |
| GENERATION_CONCURRENCY | 3 | 未结束生成占位 |
| QUERY_CONCURRENCY | 4 | 查询并发 |
| DOWNLOAD_CONCURRENCY | 2 | 下载并发 |
| UPLOAD_CONCURRENCY | 2 | 上传并发 |
| ADMISSION_CONCURRENCY | 2 | 接收并发 |
| CLEANUP_CONCURRENCY | 1 | 清理并发 |
| QUEUE_LIMIT | 100 | 等待任务 |
| INPUT_BYTES_LIMIT | 536870912 | 输入字节 |
| DOWNLOAD_BYTES_LIMIT | 未配置 | 下载字节 |
| CONNECT_TIMEOUT_SECONDS | 10 | 秒 |
| REQUEST_TIMEOUT_SECONDS | 60 | 秒 |
| UPLOAD_TIMEOUT_SECONDS | 300 | 秒 |
| DOWNLOAD_TIMEOUT_SECONDS | 1800 | 秒 |
| TRACKING_TIMEOUT_SECONDS | 21600 | 秒；0 关闭期限 |
| POLL_INTERVAL_SECONDS | 5 | 秒 |
| QUERY_RETRIES | 5 | 次 |
| UPLOAD_RETRIES | 3 | 次 |
| DOWNLOAD_RETRIES | 3 | 次 |
| CLEANUP_RETRIES | 3 | 次 |
| SHUTDOWN_GRACE_SECONDS | 10 | 秒 |
| SHUTDOWN_DRAIN_SECONDS | 15 | 秒 |
| STARTUP_TIMEOUT_SECONDS | 30 | 秒 |
| HEARTBEAT_SECONDS | 5 | 秒 |
| LEASE_TIMEOUT_SECONDS | 20 | 秒 |
| WAIT_DEFAULT_SECONDS | 20 | 秒 |
| WAIT_MAX_SECONDS | 30 | 秒 |
| PAGE_DEFAULT_SIZE | 20 | 条 |
| PAGE_MAX_SIZE | 100 | 条 |
| TOOL_RESPONSE_BYTES_LIMIT | 32768 | 字节 |
| ERROR_SUMMARY_CHARS_LIMIT | 512 | 字符 |
| DIAGNOSTIC_BYTES_LIMIT | 8192 | 字节 |
| HTTP_RESPONSE_BYTES_LIMIT | 2097152 | 字节 |
| RPC_FRAME_BYTES_LIMIT | 8388608 | 字节 |
| LOG_BYTES_LIMIT | 10485760 | 单日志字节 |
| LOG_BACKUP_COUNT | 5 | 轮转备份数量，另有当前文件 |
| STREAM_IDLE_TIMEOUT_SECONDS | 60 | 秒 |

连接时限不得超过请求时限；默认等待和默认页大小不得超过各自上限；心跳间隔必须小于租约时限。诊断大小还须容纳必要字段，过小会明确拒绝写入，而不会截断任务 ID 或动作。

凭据绑定文件使用当前用户 DPAPI 加密，内部 HMAC 秘密不对 Agent 暴露。服务私有目录 ACL 仅授予当前 SID 与 SYSTEM。任务只存随机连接绑定 ID；同凭据与端点可识别为原绑定，换钥或换端点不会证明账号兼容，旧任务须等待核验。恢复旧配置也不意味着自动恢复已停止的跟踪。

诊断使用稳定错误目录、阶段、可重试性、待处理标记、允许动作和随机诊断 ID。仅允许有限计数、HTTP 状态及已知远端状态进入详情；任意供应商文本、嵌套凭据、签名 URL、HTML 和堆栈不保存为消息。先白名单过滤和凭据过滤，再限制摘要长度。诊断写入独立轮转 JSONL，不写 stdout；按诊断 ID 返回重新过滤后的有界记录，轮转淘汰后返回不存在，不提供原始日志下载。日志保留不影响任务或视频保留。

对应验证：`uv run --frozen pytest tests/test_config.py tests/test_windows_security.py tests/test_diagnostics.py tests/test_configuration_docs.py`。RPC 冲突和隐藏后端接续见 tests/test_rpc.py、tests/test_runtime.py；真实 Host 和供应商网络仍未验收。

## 发行入口执行保护

默认local：不安装供应商调度，request/stream均阻断，但本地任务查询及已下载产物复制可用。即使环境中有真实密钥也不自动启用。启用时在安装目录.env显式设置`ZHENZHEN_SEEDANCE_EXECUTION_MODE=provider`，正常退出全部Host，确认旧后端退出后重启；不同显式模式的Host被配置冲突拒绝，不改变运行中后端。健康响应execution_mode显示实际模式，adapter_installed不代表供应商已探测可用。

provider模式正式接收新任务时，在同一事务写入供应商执行授权；这是提交授权的记录，不是额外确认。旧任务、local任务和缺授权记录均不补授权，启动时转待处理并保留事实/预算/占位，返回PROVIDER_EXECUTION_NOT_AUTHORIZED。重复request_key返回原任务，不能借重放开启执行。不要为旧的远端结果未知任务换key重提。需核对后另行制定迁移方案，本轮没有批量授权或迁移工具。上传、生成、查询和引用提取还会逐次核对持久授权。

模式与提示词优化偏好独立，provider不等于允许enhance_prompt；已授权任务在provider重启时按既有恢复/租约规则接续，local重启停止网络执行。内部合成注入仅供测试构造，发行配置不能指定任意适配器。
