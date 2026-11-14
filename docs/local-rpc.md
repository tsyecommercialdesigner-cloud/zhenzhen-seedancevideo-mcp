# 本地所有权与 RPC 基础

当前已交付所有权、传输、隐藏后端拉起、Job Object 受限处理、Host 租约与 SDK v2 stdio 状态转发。工具门面及统一恢复／停机协调已接入，生产供应商适配器尚未完成，不应把本地协议测试视为实际 Agent Host 或供应商验收。

startup.lock 和 owner.lock 是固定文件。StableLock 使用 Win32 独占句柄，关闭句柄释放锁，不删除再建文件；启动锁用于串行化发现／拉起，所有权锁须由后端持有至退出。acquire_ownership 在得到锁后核对旧 PID 和进程创建时间；旧进程仍活着或权限不足时拒绝，PID 复用时不终止新进程。数据库只能在完成这些步骤后打开。锁文件存在不等于锁被占用。

四个真实 Windows 子进程的测试证明只有一个进程取得所有权；存活进程、拒绝访问、PID 复用和原进程退出后接管都有对应测试。测试没有终止用户进程，也不删除锁文件或任务库。

RPCServer 仅绑定 127.0.0.1 随机端口；每帧为 4 字节网络字节序长度，加 UTF-8 JSON 对象。拒绝空帧、超限、重复 JSON 字段、非有限数值和非对象。协议版本当前为 1。首帧须在鉴权期限内提供 256 位随机令牌和协议版本；鉴权前不分派业务、不计入 authenticated 集合。之后请求携带 id、method 和对象 params，method 仅来自注册处理器表。

默认帧上限 8 MiB、连接上限 32、每连接在途上限 8、鉴权时限 5 秒。达到限制或重复在途请求 ID 时明确返回错误；不同请求响应通过单连接写锁保持帧完整。协议不兼容、显式配置冲突只拒绝新客户端，不另起后台。配置错误只返回项名，不返回密钥。受信任后台调用方须将有效配置上限传入传输模块。

发现文件含 PID、创建时间、实例随机标识、端口和协议版本；令牌放在独立 rpc-token 文件，不进入发现 JSON。两者在 SID ACL 保护的 runtime 目录中原子发布。它们只用于定位和鉴权，不替代所有权锁，不承诺隔离同一用户的恶意进程。

普通客户端断连不撤销已开始的处理器；服务器关闭会回收连接与传输处理器。后续任务接收器须把已接收事务的生命周期与 RPC 等待分离。LeaseManager 使用单调时钟，最后 Host 离线立即关闭新派发门；宽限期可重连，draining 不可逆，既有处理器最多收尾至期限。启动会将未决 intent 的 active 任务保守转为待处理，保留占位、预算和历史；正常轮询／下载的完整阶段恢复仍属任务 9.6。

验证命令：`uv run --frozen pytest tests/test_ownership.py tests/test_rpc.py`。RPC 使用本地回环字节测试和临时配置，覆盖鉴权、协议、配置冲突、异常帧、限额、响应及关闭；没有连接供应商或修改实际 Host 配置。

## 启动与正常退出

Host 配置使用 stdio 入口 `uv run --frozen zhenzhen-seedance-video stdio`，默认不带 mode 也为 stdio。命令须在安装目录运行，或为 uv 增加 `--directory` 指向该目录。唯一密钥名和固定 .env 位置见 configuration.md。当前仅注册 get_service_status；状态会明确 generation_execution=not_implemented，不应据本地进程就绪尝试生成。

```json
{
  "mcpServers": {
    "zhenzhen-seedance-video": {
      "command": "uv",
      "args": ["--directory", "E:\\mcp-server-workspace\\zhenzhen-seedancevideo-mcp", "run", "--frozen", "zhenzhen-seedance-video", "stdio"]
    }
  }
}
```

这是通用配置结构示例，具体 Host 字段须依据对应 Host 版本调整；本项目未修改或验收任何实际 Host 配置。stdout 仅用于 MCP 帧，启动失败仅输出有界静态诊断到 stderr。

前端持有短期启动锁，连接已发现后端或用固定当前虚拟环境解释器和绝对 cwd 启动隐藏进程。没有 shell 拼接、继承连接句柄或密钥命令行。启动器先挂起，写 starting.json 的 PID／创建时间及随机启动标识，再恢复执行。Windows 虚拟环境启动器可能再创建实际解释器进程，因此 discovery.json 记录实际后端身份并携带同一启动标识；不能直接把启动器 PID 当实际后端 PID。

正常退出全部 Host 后，EOF 会解除租约；半开连接到租约期限后回收。默认心跳 5 秒、租约 20 秒、宽限 10 秒、收尾上限 15 秒。宽限期内其他 Host 接入复用原实例；draining 期间新连接被拒，前端确认旧进程退出后才重启。后台无未完成处理器时可提前结束收尾。服务不删除锁或任务库，不自动强杀旧后端。

## 故障处理

| 错误 | 含义与处理 |
| --- | --- |
| OLD_PROCESS_STILL_ALIVE | 旧进程还活着但连接不可用；正常退出关联 Host 后重试，不能通过删除锁或空库旁路 |
| OLD_PROCESS_EXIT_UNCONFIRMED | 进程身份／退出无法确认；核对 Windows 用户和权限，保持现有状态，不提权强杀 |
| BACKEND_LAUNCH_OR_JOB_INCOMPATIBLE | 启动失败或 Host Job Object 不允许合法脱离；使用允许独立子进程的 Host／启动环境，不关闭系统保护或伪称保活成功 |
| PROTOCOL_INCOMPATIBLE | 新旧版本协议不同；正常退出所有 Host 后统一安装版本，不覆盖运行中后端 |
| CONFIGURATION_CONFLICT | 新连接显式配置不同；统一固定 .env／Host 环境，再正常重启，旧连接不受影响 |
| STARTUP_TIMEOUT | 启动未在期限内完成；检查本地配置、状态库和进程身份，不重复强制启动 |
| DATABASE_MISSING_WITH_HISTORY | 有历史但主库缺失；使用已核实的一致备份维护流程，不删除初始化标记重建 |

如果现有 backend 已可连接，受限 Host 可连接该实例；若需从受限 Job 首次拉起且不能脱离，必须拒绝。测试创建了两种真实 Windows Job Object：允许脱离的 Host 作业被关闭后，后台仍供 B 使用；禁止脱离的 Job 返回明确错误。后台可能属于 Python 启动器自己的 Job，这不等同仍属于原 Host 的 Job，测试按具体 Host Job 核对归属并验证退出后的存活。

隔离演练命令：`uv run --frozen pytest tests/test_runtime.py tests/test_runtime_recovery.py tests/test_leases.py tests/test_cli.py`。覆盖两个客户端、SDK v2 stdio 初始化与工具发现、EOF、宽限重连、无心跳失效、真实 Job 退出、重启保留未知占位，以及 draining 拒绝重连和有限收尾。最后两项含可控本地处理器测试；没有真实生成中的供应商网络操作，不等同任务 13.3 实际 Host 验收。
